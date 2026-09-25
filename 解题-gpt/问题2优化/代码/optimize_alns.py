#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Problem 2 official-data optimisation experiment.

The baseline builder is kept intact and every candidate mission is still
validated by the official DEM/energy model.  The added ALNS layer searches
the dispatch order of already feasible sorties inside equal-deadline strata.
It also evaluates every candidate with the same finite UAV/shared-battery
discrete-event simulation used by the formal solution.
"""
from __future__ import annotations

import json
import os
import random
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve()
PROJECT = HERE.parents[3]  # D:\\claude\\华为杯\\D题
WORK = PROJECT / "解题-gpt"
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(WORK / "代码"))

from src.battery.charging_model_correct import calculate_charging_time
from src.data.data_loader import DataLoader
from src.terrain.dem_loader import DEMLoader
from solve_problem1_18trips import direct_mission
from solve_problem2_lns import build_groups, beam_assign, local_search
from solve_problem2_optimized import deadline_seconds


def load_official():
    data_dir = PROJECT / "数据" / "无人机应急物资运输基础数据"
    dem_dir = PROJECT / "数据" / "镇龙乡地理空间数据" / "镇龙乡及周边地理数据" / "数字高程模型数据（DEM）"
    loader = DataLoader(str(data_dir)); loader.load_all()
    cargo = loader.get_cargos().copy()
    cargo_by_id = cargo.set_index("货箱编号", drop=False)
    types = {r["type"]: r.to_dict() for _, r in loader.get_uav_types().iterrows()}
    areas = {r["id"]: r.to_dict() for _, r in loader.get_service_areas().iterrows()}
    depot = loader.get_depot()
    dem = DEMLoader(str(next(dem_dir.glob("*.mat")))); dem.load()
    return cargo, cargo_by_id, types, areas, depot, dem


def task_list(chosen):
    tasks = []
    k = 0
    for group in chosen:
        for j, mission in enumerate(group["plan"]["missions"]):
            row = dict(mission)
            row["deadline_min"] = float(group["deadline_min"])
            row["_order"] = (float(group["deadline_min"]), k, j)
            tasks.append(row); k += 1
    return sorted(tasks, key=lambda x: x["_order"])


def workbook_tasks(path):
    """Read the current formal workbook as a reproducible baseline.

    The workbook was generated from the official DEM model; reading it avoids
    rebuilding the expensive beam search for each optimisation experiment.
    The optimiser still re-simulates every candidate with the official
    finite-pool charging model below.
    """
    df = pd.read_excel(path, sheet_name="架次调度")
    tasks = []
    for i, r in df.sort_values("mission_id").iterrows():
        ids = [x for x in str(r["cargo_ids"]).split(",") if x]
        tasks.append({"area_id": r["area_id"], "uav_type": r["uav_type"], "cargo_ids": ids,
                      "cargo_count": int(r["cargo_count"]), "energy_kwh": float(r["energy_kwh"]),
                      "duration_min": float(r["duration_min"]),
                      "delivery_offset_min": float(r["delivery_offset_min"]),
                      "deadline_min": float(r["deadline_min"]), "_order": int(r["mission_id"])})
    return tasks


def simulate_sequence(tasks, types, cargo_by_id):
    """Official finite-pool simulation for an explicit mission sequence."""
    uavs = {typ: [{"id": f"U{typ}{i + 1:02d}", "available": 0.0}
                  for i in range(int(p["count"]))] for typ, p in types.items()}
    batteries = {typ: [{"id": f"{typ}-BAT-{i + 1:02d}", "available": 0.0}
                       for i in range(int(p["battery_count"]))] for typ, p in types.items()}
    missions, cargo_rows = [], []
    for mid, mission in enumerate(tasks, 1):
        typ = mission["uav_type"]; p = types[typ]
        uav = min(uavs[typ], key=lambda x: (x["available"], x["id"]))
        bat = min(batteries[typ], key=lambda x: (x["available"], x["id"]))
        start = max(uav["available"], bat["available"])
        end = start + float(mission["duration_min"])
        delivery = start + float(mission["delivery_offset_min"])
        energy = float(mission["energy_kwh"])
        capacity = float(p["battery_capacity_kwh"])
        usable = capacity * (1.0 - float(p["battery_reserve_pct"]))
        if energy > usable + 1e-9:
            raise ValueError(f"energy reserve violation: {typ} {energy}")
        soc_after = 1.0 - energy / capacity
        charge = float(calculate_charging_time(soc_after, 1.0, float(p["full_charge_time_min"])))
        uav["available"] = end
        bat["available"] = end + charge
        rec = {**mission, "mission_id": mid, "uav_id": uav["id"], "battery_id": bat["id"],
               "start_min": start, "delivery_min": delivery, "end_min": end,
               "on_time": delivery <= float(mission["deadline_min"]) + 1e-9,
               "soc_after": soc_after, "charge_min": charge}
        missions.append(rec)
        for cid in mission["cargo_ids"]:
            box = cargo_by_id.loc[cid]
            d = deadline_seconds(box) / 60.0
            cargo_rows.append({"cargo_id": cid, "mission_id": mid, "area_id": box["服务区编号"],
                               "delivery_min": delivery, "deadline_min": d,
                               "on_time": delivery <= d + 1e-9})
    return missions, cargo_rows


def score(missions, cargo_rows):
    late = sum(not r["on_time"] for r in cargo_rows)
    tardy = sum(max(0.0, r["delivery_min"] - r["deadline_min"]) for r in cargo_rows)
    makespan = max((r["end_min"] for r in missions), default=0.0)
    energy = sum(r["energy_kwh"] for r in missions)
    return (late, tardy, makespan, energy, len(missions))


def alns_sequence(initial, types, cargo_by_id, iterations=40, seed=20260925):
    """Adaptive large-neighborhood search on equal-deadline strata.

    Four destroy operators and three repair operators compete. Their weights
    are updated from accepted/improving moves, while every candidate is still
    evaluated by the official finite-pool simulation.
    """
    rng = random.Random(seed)
    current = list(initial)
    current_m, current_c = simulate_sequence(current, types, cargo_by_id)
    current_score = score(current_m, current_c)
    best_score = current_score; best = list(current); best_m, best_c = current_m, current_c
    deadlines = sorted({float(t["deadline_min"]) for t in current})
    destroy_names = ["random", "longest", "energy", "charge"]
    repair_names = ["offset", "duration", "energy"]
    destroy_w = {name: 1.0 for name in destroy_names}
    repair_w = {name: 1.0 for name in repair_names}
    rho = 0.20

    def pick(weights):
        names = list(weights)
        total = sum(weights[x] for x in names)
        z = rng.random() * total
        for name in names:
            z -= weights[name]
            if z <= 0:
                return name
        return names[-1]

    def charge_burden(task):
        p = types[task["uav_type"]]
        soc = 1.0 - float(task["energy_kwh"]) / float(p["battery_capacity_kwh"])
        return float(calculate_charging_time(soc, 1.0, float(p["full_charge_time_min"])))

    for _ in range(iterations):
        trial = list(current)
        d = rng.choice(deadlines)
        positions = [i for i, t in enumerate(trial) if float(t["deadline_min"]) == d]
        if len(positions) < 2:
            continue
        destroy = pick(destroy_w); repair = pick(repair_w)
        q = min(len(positions) - 1, rng.randint(2, 5))
        if destroy == "random":
            removed_pos = rng.sample(positions, q)
        else:
            key = {"longest": lambda i: float(trial[i]["duration_min"]),
                   "energy": lambda i: float(trial[i]["energy_kwh"]),
                   "charge": lambda i: charge_burden(trial[i])}[destroy]
            ordered = sorted(positions, key=key, reverse=True)
            # retain a small stochastic component among the top candidates
            removed_pos = ordered[:q] if rng.random() < 0.75 else rng.sample(positions, q)
        removed = [trial[i] for i in sorted(removed_pos, reverse=True)]
        for i in sorted(removed_pos, reverse=True):
            trial.pop(i)
        if repair == "offset":
            removed.sort(key=lambda x: (float(x["delivery_offset_min"]), -float(x["energy_kwh"])))
        elif repair == "duration":
            removed.sort(key=lambda x: (-float(x["duration_min"]), -float(x["energy_kwh"])))
        else:
            removed.sort(key=lambda x: (-float(x["energy_kwh"]), str(x["area_id"])))
        for task in removed:
            valid = [i for i, x in enumerate(trial) if float(x["deadline_min"]) == d]
            lo = min(valid) if valid else len(trial); hi = max(valid) + 1 if valid else len(trial)
            candidates = []
            for ins in range(lo, hi + 1):
                cand = list(trial); cand.insert(ins, task)
                mm, cc = simulate_sequence(cand, types, cargo_by_id)
                candidates.append((score(mm, cc), cand, mm, cc))
            candidates.sort(key=lambda x: x[0]); _, trial, _, _ = candidates[0]
        trial_m, trial_c = simulate_sequence(trial, types, cargo_by_id)
        trial_score = score(trial_m, trial_c)
        reward = 0.0
        if trial_score < best_score:
            best_score, best, best_m, best_c = trial_score, list(trial), trial_m, trial_c
            reward = 5.0
        previous_score = current_score
        if trial_score <= previous_score:
            current, current_m, current_c, current_score = trial, trial_m, trial_c, trial_score
            reward = max(reward, 2.0 if trial_score < previous_score else 1.0)
        destroy_w[destroy] = (1-rho)*destroy_w[destroy] + rho*max(reward, 0.1)
        repair_w[repair] = (1-rho)*repair_w[repair] + rho*max(reward, 0.1)
    return best, best_m, best_c, best_score


def write_result(missions, cargo_rows, types, output):
    mission_df = pd.DataFrame(missions).copy()
    mission_df["cargo_ids"] = mission_df["cargo_ids"].apply(lambda x: ",".join(x) if isinstance(x, list) else x)
    cargo_df = pd.DataFrame(cargo_rows)
    inv = []
    for typ, p in types.items():
        uids = sorted(mission_df.loc[mission_df.uav_type == typ, "uav_id"].unique())
        bids = sorted(mission_df.loc[mission_df.uav_type == typ, "battery_id"].unique())
        inv.append({"type": typ, "official_uav": int(p["count"]), "used_uav": len(uids),
                    "used_uav_ids": ",".join(uids), "official_battery": int(p["battery_count"]),
                    "used_battery": len(bids), "used_battery_ids": ",".join(bids),
                    "full_charge_time_min": p["full_charge_time_min"]})
    summary = pd.DataFrame({"metric": ["missions", "cargo_count", "unique_cargo_count", "completion_min",
                                         "late_cargo_count", "total_tardiness_min", "total_energy_kwh", "algorithm"],
                            "value": [len(mission_df), len(cargo_df), cargo_df.cargo_id.nunique(),
                                      mission_df.end_min.max(), int((~cargo_df.on_time).sum()),
                                      sum(max(0.0, r["delivery_min"] - r["deadline_min"]) for r in cargo_rows),
                                      mission_df.energy_kwh.sum(), "official DEM + ALNS sequence destroy/repair"]})
    output.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        mission_df.to_excel(writer, sheet_name="架次调度", index=False)
        cargo_df.to_excel(writer, sheet_name="逐箱时限", index=False)
        pd.DataFrame(inv).to_excel(writer, sheet_name="资源核验", index=False)
        summary.to_excel(writer, sheet_name="校验", index=False)


def main():
    cargo, cargo_by_id, types, areas, depot, dem = load_official()
    baseline_path = WORK / "结果" / "问题二_增强优化版.xlsx"
    initial = workbook_tasks(baseline_path)
    base_m, base_c = simulate_sequence(initial, types, cargo_by_id)
    iterations = int(os.environ.get("P2_ALNS_ITER", "40"))
    seed = int(os.environ.get("P2_ALNS_SEED", "20260925"))
    best, best_m, best_c, best_s = alns_sequence(initial, types, cargo_by_id, iterations=iterations, seed=seed)
    out = WORK / "问题2优化" / "结果" / "问题二_ALNS候选方案.xlsx"
    write_result(best_m, best_c, types, out)
    payload = {"baseline": {"score": score(base_m, base_c), "missions": len(base_m)},
               "candidate": {"score": best_s, "missions": len(best_m), "cargo": len(best_c), "output": str(out)}}
    print(json.dumps(payload, ensure_ascii=False, default=float))


if __name__ == "__main__":
    main()
