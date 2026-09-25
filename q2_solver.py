#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Official-data Problem 2 solver.

The heuristic follows the literature notes in the repository: earliest
deadline first for heterogeneous VRPTW, adaptive type choice for a scarce
fleet, and a no-stockout shared-battery event simulation.  Every candidate
mission is evaluated by the official DEM-based mission model from Problem 1.
"""

from pathlib import Path
import json
import math

import pandas as pd

from src.battery.charging_model_correct import calculate_charging_time
from src.data.data_loader import DataLoader
from src.terrain.dem_loader import DEMLoader
from solve_problem1_18trips import direct_mission


ID = "货箱编号"
AREA = "服务区编号"
FIRST = "是否首批保障"
FIRST_DEADLINE = "首批截止时间（s）"
EXPECTED_DEADLINE = "期望送达时间（s）"
WEIGHT = "单箱质量（kg）"
VOLUME = "单箱体积（m³）"


def deadline_seconds(row):
    if str(row[FIRST]).strip() == "是" and pd.notna(row[FIRST_DEADLINE]):
        return float(row[FIRST_DEADLINE])
    return float(row[EXPECTED_DEADLINE])


def pack_group(items, typ, params, area, depot, dem):
    """Best-fit decreasing packing for one service-area/deadline group."""
    ordered = sorted(items, key=lambda x: (float(x[WEIGHT]), float(x[VOLUME])), reverse=True)
    bins = []
    for item in ordered:
        best_idx = None
        best_slack = None
        for i, bucket in enumerate(bins):
            trial = bucket + [item]
            if sum(float(x[WEIGHT]) for x in trial) > float(params["max_load_kg"]) + 1e-9:
                continue
            if sum(float(x[VOLUME]) for x in trial) > float(params["max_volume_m3"]) + 1e-9:
                continue
            if not direct_mission(area, depot, params, trial, dem)["feasible"]:
                continue
            slack = float(params["max_load_kg"]) - sum(float(x[WEIGHT]) for x in trial)
            if best_slack is None or slack < best_slack:
                best_idx, best_slack = i, slack
        if best_idx is None:
            if not direct_mission(area, depot, params, [item], dem)["feasible"]:
                return None
            bins.append([item])
        else:
            bins[best_idx].append(item)
    return bins


def make_plans(group, types, area, depot, dem):
    plans = {}
    for typ, params in types.items():
        bins = pack_group(group, typ, params, area, depot, dem)
        if bins is None:
            continue
        metrics = [direct_mission(area, depot, params, b, dem) for b in bins]
        plans[typ] = {
            "type": typ,
            "bins": bins,
            "metrics": metrics,
            "missions": len(bins),
            "energy": sum(x["energy_kwh"] for x in metrics),
            "duration": max(x["total_time_min"] for x in metrics),
        }
    return plans


def choose_plans(cargo, areas, depot, types, dem, bias):
    """Choose a type plan for every deadline group with fleet scarcity feedback."""
    groups = []
    for area_id, area_df in cargo.groupby(AREA, sort=True):
        area = areas[area_id]
        area_df = area_df.copy()
        area_df["_deadline_min"] = area_df.apply(deadline_seconds, axis=1) / 60.0
        for deadline, sub in area_df.groupby("_deadline_min", sort=True):
            groups.append({
                "area_id": area_id,
                "deadline_min": float(deadline),
                "priority": float(sub["应急优先系数"].max()),
                "items": sub.to_dict("records"),
            })
    groups.sort(key=lambda g: (g["deadline_min"], -sum(float(x[WEIGHT]) for x in g["items"]),
                               g["area_id"]))

    assigned = {typ: 0 for typ in types}
    chosen = []
    for group in groups:
        plans = make_plans(group["items"], types, areas[group["area_id"]], depot, dem)
        if not plans:
            raise ValueError(f"没有可行机型组批: {group['area_id']} {group['deadline_min']}min")
        scored = []
        for typ, plan in plans.items():
            fleet = max(1, int(types[typ]["count"]))
            projected_wave = math.ceil((assigned[typ] + plan["missions"]) / fleet)
            # Completion-wave proxy plus energy and a tunable scarcity bias.
            score = (projected_wave * plan["duration"] +
                     0.15 * plan["energy"] + float(bias.get(typ, 0.0)))
            scored.append((score, typ, plan))
        _, typ, plan = min(scored, key=lambda x: (x[0], x[2]["missions"], x[1]))
        assigned[typ] += plan["missions"]
        group["plan"] = plan
        chosen.append(group)
    return chosen


def simulate(chosen, types, cargo_by_id):
    uavs = {typ: [{"id": f"U{typ}{i + 1:02d}", "available": 0.0}
                  for i in range(int(p["count"]))] for typ, p in types.items()}
    batteries = {typ: [{"id": f"{typ}-BAT-{i + 1:02d}", "available": 0.0}
                       for i in range(int(p["battery_count"]))] for typ, p in types.items()}
    missions = []
    # Expand groups into missions and use the literature's EDD rule. Larger
    # urgent loads are placed first at equal deadlines.
    expanded = []
    for group in chosen:
        plan = group["plan"]
        for bucket, metrics in zip(plan["bins"], plan["metrics"]):
            expanded.append({"area_id": group["area_id"], "deadline_min": group["deadline_min"],
                             "priority": group["priority"], "ids": [x[ID] for x in bucket],
                             "metrics": metrics, "uav_type": plan["type"]})
    expanded.sort(key=lambda x: (x["deadline_min"], -len(x["ids"]), -x["priority"], x["area_id"]))

    for mission_id, m in enumerate(expanded, 1):
        typ = m["uav_type"]
        params = types[typ]
        uav = min(uavs[typ], key=lambda x: (x["available"], x["id"]))
        battery = min(batteries[typ], key=lambda x: (x["available"], x["id"]))
        metrics = m["metrics"]
        start = max(float(uav["available"]), float(battery["available"]))
        end = start + float(metrics["total_time_min"])
        delivery = start + float(metrics["delivery_time_min"])
        capacity = float(params["battery_capacity_kwh"])
        reserve = float(params["battery_reserve_pct"])
        usable = capacity * (1.0 - reserve)
        energy = float(metrics["energy_kwh"])
        if energy > usable + 1e-9:
            raise ValueError(f"{typ}任务能量超过返航安全余量")
        soc_after = 1.0 - energy / capacity
        charge = float(calculate_charging_time(soc_after, 1.0, float(params["full_charge_time_min"])))
        uav["available"] = end
        battery["available"] = end + charge
        missions.append({"mission_id": mission_id, "uav_id": uav["id"], "uav_type": typ,
                         "battery_id": battery["id"], "area_id": m["area_id"],
                         "cargo_ids": m["ids"], "start_min": start, "delivery_min": delivery,
                         "end_min": end, "deadline_min": m["deadline_min"],
                         "on_time": delivery <= m["deadline_min"] + 1e-9,
                         "energy_kwh": energy, "soc_after": soc_after, "charge_min": charge})

    cargo_rows = []
    for m in missions:
        for box_id in m["cargo_ids"]:
            box = cargo_by_id.loc[box_id]
            deadline = deadline_seconds(box) / 60.0
            cargo_rows.append({"cargo_id": box_id, "mission_id": m["mission_id"],
                               "area_id": box[AREA], "uav_id": m["uav_id"],
                               "uav_type": m["uav_type"], "delivery_min": m["delivery_min"],
                               "deadline_min": deadline,
                               "on_time": m["delivery_min"] <= deadline + 1e-9})
    return missions, cargo_rows


def score(missions, cargo_rows):
    late = sum(not x["on_time"] for x in cargo_rows)
    tardiness = sum(max(0.0, x["delivery_min"] - x["deadline_min"]) for x in cargo_rows)
    completion = max(x["end_min"] for x in missions)
    energy = sum(x["energy_kwh"] for x in missions)
    # Deadline performance dominates; then makespan and energy.
    return late, tardiness, completion, energy, len(missions)


def main():
    root = Path(__file__).parent
    data_dir = root / "数据" / "无人机应急物资运输基础数据"
    dem_dir = root / "数据" / "镇龙乡地理空间数据" / "镇龙乡及周边地理数据" / "数字高程模型数据（DEM）"
    loader = DataLoader(str(data_dir)); loader.load_all()
    cargo = loader.get_cargos().copy(); cargo_by_id = cargo.set_index(ID, drop=False)
    types = {r["type"]: r.to_dict() for _, r in loader.get_uav_types().iterrows()}
    areas = {r["id"]: r.to_dict() for _, r in loader.get_service_areas().iterrows()}
    dem = DEMLoader(str(next(dem_dir.glob("*.mat")))); dem.load()
    depot = loader.get_depot()

    candidates = []
    biases = []
    for a in (0.0, 1.0, 3.0, 6.0):
        for b in (0.0, 1.0, 3.0, 6.0):
            for c in (0.0, 1.0, 3.0, 6.0, 10.0):
                biases.append({"A": a, "B": b, "C": c})
    for bias in biases:
        chosen = choose_plans(cargo, areas, depot, types, dem, bias)
        missions, cargo_rows = simulate(chosen, types, cargo_by_id)
        candidates.append((score(missions, cargo_rows), bias, missions, cargo_rows))
    best_score, best_bias, missions, cargo_rows = min(candidates, key=lambda x: x[0])
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
    summary = pd.DataFrame({"metric": ["missions", "cargo_count", "unique_cargo_count", "completion_min",
                                        "late_cargo_count", "total_tardiness_min", "total_energy_kwh", "best_bias"],
                            "value": [len(mission_df), len(cargo_df), cargo_df.cargo_id.nunique(),
                                      mission_df.end_min.max(), sum(~cargo_df.on_time),
                                      sum(max(0.0, r["delivery_min"] - r["deadline_min"]) for r in cargo_rows),
                                      mission_df.energy_kwh.sum(), json.dumps(best_bias, ensure_ascii=False)]})
    output = root / "结果" / "问题二_优化修复版.xlsx"
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        mission_df.to_excel(writer, sheet_name="架次调度", index=False)
        cargo_df.to_excel(writer, sheet_name="逐箱时限", index=False)
        pd.DataFrame(inv).to_excel(writer, sheet_name="资源核验", index=False)
        summary.to_excel(writer, sheet_name="校验", index=False)
    print(json.dumps({"output": str(output), "score": best_score, "bias": best_bias,
                      "missions": len(mission_df), "cargo": int(cargo_df.cargo_id.nunique()),
                      "completion_min": float(mission_df.end_min.max()),
                      "late": int((~cargo_df.on_time).sum()),
                      "energy_kwh": float(mission_df.energy_kwh.sum())}, ensure_ascii=True))


if __name__ == "__main__":
    main()
