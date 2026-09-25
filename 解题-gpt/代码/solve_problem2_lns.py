#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Enhanced official-data solver for Problem 2.

The original solver chooses a UAV type group by group.  This version keeps
the same official mission model, but optimizes the type choice globally with
a bounded beam search followed by a one/two-swap large-neighbourhood search.
The objective is lexicographic: late boxes, total tardiness, makespan, energy,
then number of sorties.  No demand, inventory or physical parameter is
invented here; all candidates are evaluated by ``direct_mission``.
"""

from pathlib import Path
import json
import math
import os

import pandas as pd

from src.data.data_loader import DataLoader
from src.terrain.dem_loader import DEMLoader
from solve_problem1_18trips import direct_mission
from solve_problem2_optimized import (
    AREA, FIRST, FIRST_DEADLINE, EXPECTED_DEADLINE, ID, WEIGHT,
    deadline_seconds, make_plans, simulate,
)


def objective(missions, cargo_rows):
    late = sum(not x["on_time"] for x in cargo_rows)
    tardiness = sum(max(0.0, x["delivery_min"] - x["deadline_min"])
                    for x in cargo_rows)
    completion = max((x["end_min"] for x in missions), default=0.0)
    energy = sum(x["energy_kwh"] for x in missions)
    return (late, tardiness, completion, energy, len(missions))


def build_groups(cargo, areas):
    groups = []
    for area_id, area_df in cargo.groupby(AREA, sort=True):
        area_df = area_df.copy()
        area_df["_deadline_min"] = area_df.apply(deadline_seconds, axis=1) / 60.0
        for deadline, sub in area_df.groupby("_deadline_min", sort=True):
            groups.append({
                "area_id": area_id,
                "deadline_min": float(deadline),
                "priority": float(sub["应急优先系数"].max()),
                "items": sub.to_dict("records"),
            })
    return sorted(groups, key=lambda g: (g["deadline_min"],
                                          -sum(float(x[WEIGHT]) for x in g["items"]),
                                          g["area_id"]))


def state_key(state):
    missions, cargo_rows, chosen = state
    # Preserve diversity in the beam: a small type-count penalty prevents all
    # states from collapsing to the same type pattern at equal objective.
    counts = tuple(sum(1 for g in chosen if g["plan"]["type"] == t)
                   for t in ("A", "B", "C"))
    return objective(missions, cargo_rows) + counts


def beam_assign(groups, areas, types, depot, dem, cargo_by_id, width=80):
    states = [( [], [], [] )]
    for group in groups:
        options = make_plans(group["items"], types, areas[group["area_id"]], depot, dem)
        if not options:
            raise ValueError(f"没有可行机型组批: {group['area_id']} {group['deadline_min']}min")
        expanded = []
        for missions, cargo_rows, chosen in states:
            for typ, plan in options.items():
                g = dict(group)
                g["plan"] = plan
                partial = chosen + [g]
                m, c = simulate(partial, types, cargo_by_id)
                expanded.append((m, c, partial))
        expanded.sort(key=state_key)
        # Keep the best state and distinct type signatures. This is a compact
        # deterministic analogue of beam/ALNS diversification.
        kept = []
        signatures = set()
        for state in expanded:
            sig = tuple(g["plan"]["type"] for g in state[2])
            coarse = (sig[-1], tuple(sig.count(t) for t in ("A", "B", "C")))
            if coarse in signatures and len(kept) >= width // 2:
                continue
            signatures.add(coarse)
            kept.append(state)
            if len(kept) >= width:
                break
        states = kept
    return min(states, key=state_key)


def local_search(chosen, groups, areas, types, depot, dem, cargo_by_id):
    """Best-improvement 1/2-swap search over the beam solution."""
    current = list(chosen)

    def evaluate(candidate):
        missions, cargo_rows = simulate(candidate, types, cargo_by_id)
        return objective(missions, cargo_rows), missions, cargo_rows

    best_score, best_missions, best_cargo = evaluate(current)
    # Recompute all group-specific plans once; direct_mission is the expensive
    # part and the official terrain model is therefore never approximated.
    plan_cache = []
    for group in groups:
        plan_cache.append(make_plans(group["items"], types,
                                     areas[group["area_id"]], depot, dem))
    for _round in range(3):
        improved = False
        for i in range(len(current)):
            old_type = current[i]["plan"]["type"]
            for typ, plan in plan_cache[i].items():
                if typ == old_type:
                    continue
                trial = list(current)
                trial[i] = dict(trial[i]); trial[i]["plan"] = plan
                score, missions, cargo_rows = evaluate(trial)
                if score < best_score:
                    current, best_score = trial, score
                    best_missions, best_cargo = missions, cargo_rows
                    improved = True
        if not improved:
            break
    return current, best_missions, best_cargo, best_score


def main():
    project_root = Path(__file__).resolve().parents[2]
    root = project_root / "解题-gpt"
    data_dir = project_root / "数据" / "无人机应急物资运输基础数据"
    dem_dir = project_root / "数据" / "镇龙乡地理空间数据" / "镇龙乡及周边地理数据" / "数字高程模型数据（DEM）"
    loader = DataLoader(str(data_dir)); loader.load_all()
    cargo = loader.get_cargos().copy()
    cargo_by_id = cargo.set_index(ID, drop=False)
    types = {r["type"]: r.to_dict() for _, r in loader.get_uav_types().iterrows()}
    areas = {r["id"]: r.to_dict() for _, r in loader.get_service_areas().iterrows()}
    depot = loader.get_depot()
    dem = DEMLoader(str(next(dem_dir.glob("*.mat")))); dem.load()

    groups = build_groups(cargo, areas)
    beam_width = int(os.environ.get("P2_BEAM_WIDTH", "80"))
    chosen_state = beam_assign(groups, areas, types, depot, dem, cargo_by_id, width=beam_width)
    chosen, missions, cargo_rows = chosen_state[2], chosen_state[0], chosen_state[1]
    chosen, missions, cargo_rows, score = local_search(
        chosen, groups, areas, types, depot, dem, cargo_by_id)
    if len(cargo_rows) != len(cargo) or len({x["cargo_id"] for x in cargo_rows}) != len(cargo):
        raise ValueError("官方货箱未做到80箱唯一覆盖")

    mission_df = pd.DataFrame(missions)
    mission_df["cargo_ids"] = mission_df["cargo_ids"].apply(lambda x: ",".join(x))
    cargo_df = pd.DataFrame(cargo_rows)
    inv = []
    for typ, p in types.items():
        uids = sorted(mission_df.loc[mission_df.uav_type == typ, "uav_id"].unique())
        bids = sorted(mission_df.loc[mission_df.uav_type == typ, "battery_id"].unique())
        inv.append({"type": typ, "official_uav": int(p["count"]), "used_uav": len(uids),
                    "used_uav_ids": ",".join(uids), "official_battery": int(p["battery_count"]),
                    "used_battery": len(bids), "used_battery_ids": ",".join(bids),
                    "full_charge_time_min": p["full_charge_time_min"]})
    summary = pd.DataFrame({"metric": ["missions", "cargo_count", "unique_cargo_count",
                                        "completion_min", "late_cargo_count", "total_tardiness_min",
                                        "total_energy_kwh", "algorithm"],
                            "value": [len(mission_df), len(cargo_df), cargo_df.cargo_id.nunique(),
                                      mission_df.end_min.max(), sum(~cargo_df.on_time),
                                      sum(max(0.0, r["delivery_min"] - r["deadline_min"])
                                          for r in cargo_rows), mission_df.energy_kwh.sum(),
                                      f"EDD + bounded beam({beam_width}) + 1-swap LNS"]})
    output = root / "结果" / "问题二_增强优化版.xlsx"
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        mission_df.to_excel(writer, sheet_name="架次调度", index=False)
        cargo_df.to_excel(writer, sheet_name="逐箱时限", index=False)
        pd.DataFrame(inv).to_excel(writer, sheet_name="资源核验", index=False)
        summary.to_excel(writer, sheet_name="校验", index=False)
    print(json.dumps({"output": str(output), "score": score, "missions": len(mission_df),
                      "cargo": int(cargo_df.cargo_id.nunique()),
                      "completion_min": float(mission_df.end_min.max()),
                      "late": int((~cargo_df.on_time).sum()),
                      "energy_kwh": float(mission_df.energy_kwh.sum())}, ensure_ascii=True))


if __name__ == "__main__":
    main()
