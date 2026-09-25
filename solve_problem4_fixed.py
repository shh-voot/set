#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Problem 4: independent resource requirements for 2/3 task groups."""

from pathlib import Path
import json
import heapq

import pandas as pd

from src.data.data_loader import DataLoader
from src.battery.charging_model_correct import calculate_charging_time


def _components(area_ids, relay_rows):
    """Build inseparable area components induced by relay coverage."""
    parent = {x: x for x in area_ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for row in relay_rows:
        ids = [x for x in str(row.get("covered_area_ids", "")).split(",") if x]
        for x in ids[1:]:
            if x in parent:
                union(ids[0], x)
    groups = {}
    for x in area_ids:
        groups.setdefault(find(x), []).append(x)
    return list(groups.values())


def _partition(area_info, relay_rows, n_groups):
    components = _components(list(area_info), relay_rows)
    # Greedy load balancing on inseparable components.
    components.sort(key=lambda c: sum(area_info[x]["population"] for x in c), reverse=True)
    groups = [[] for _ in range(n_groups)]
    loads = [0] * n_groups
    for component in components:
        idx = min(range(n_groups), key=lambda i: (loads[i], i))
        groups[idx].extend(component)
        loads[idx] += sum(area_info[x]["population"] for x in component)
    return groups, loads


def _resource_counts(tasks, params):
    """Count peak UAVs, batteries and chargers for fixed task times.

    Mission start/end times are inherited from Problem 2. A shared battery is
    reusable only after its full official recharge interval has elapsed.
    """
    out = {"uav_count": 0, "battery_count": 0, "charger_count": 0}
    if not tasks:
        return out
    charge_intervals = []
    starts = sorted((float(t["start_min"]), float(t["end_min"])) for t in tasks)
    active = []
    for start, end in starts:
        while active and active[0] <= start + 1e-9:
            heapq.heappop(active)
        heapq.heappush(active, end)
        out["uav_count"] = max(out["uav_count"], len(active))

    full_charge = float(params["full_charge_time_min"])
    capacity = float(params["battery_capacity_kwh"])
    battery_ready = []
    for t in sorted(tasks, key=lambda x: (float(x["start_min"]), int(x.get("source_trip_id", x.get("mission_id", 0))))):
        start, end = float(t["start_min"]), float(t["end_min"])
        energy = float(t["energy_kwh"])
        soc_after = 1.0 - energy / capacity
        charge = calculate_charging_time(soc_after, 1.0, full_charge)
        ready_idx = next((i for i, ready in enumerate(battery_ready) if ready <= start + 1e-9), None)
        if ready_idx is None:
            battery_ready.append(end + charge)
        else:
            battery_ready[ready_idx] = end + charge
        charge_intervals.append((end, end + charge))
    out["battery_count"] = len(battery_ready)

    events = sorted([(a, 1) for a, _ in charge_intervals] + [(b, -1) for _, b in charge_intervals])
    charging = 0
    for _, delta in events:
        charging += delta
        out["charger_count"] = max(out["charger_count"], charging)
    return out


def solve_problem4(num_groups):
    root = Path(__file__).parent
    data_dir = root / "数据" / "无人机应急物资运输基础数据"
    loader = DataLoader(str(data_dir))
    loader.load_all()
    types = {row["type"]: row.to_dict() for _, row in loader.get_uav_types().iterrows()}

    schedule = pd.read_excel(root / "结果" / "问题二_优化修复版.xlsx", sheet_name="架次调度")
    cargo = loader.get_cargos().copy()
    area_df = loader.get_service_areas()
    area_info = {row["id"]: row.to_dict() for _, row in area_df.iterrows()}
    relay_df = pd.read_excel(root / "结果" / "问题三_中继部署方案_修复版.xlsx")
    relay_rows = relay_df.to_dict("records")

    groups, population_loads = _partition(area_info, relay_rows, num_groups)
    rows = []
    group_json = []
    for idx, area_ids in enumerate(groups, 1):
        missions = schedule[schedule["area_id"].isin(area_ids)].copy()
        resources = {"A": {"uav_count": 0, "battery_count": 0, "charger_count": 0},
                     "B": {"uav_count": 0, "battery_count": 0, "charger_count": 0},
                     "C": {"uav_count": 0, "battery_count": 0, "charger_count": 0}}
        for typ in resources:
            tasks = missions[missions["uav_type"] == typ].to_dict("records")
            resources[typ] = _resource_counts(tasks, types[typ])

        # Relay resources are assigned by covered service areas. The partition
        # keeps each relay's covered set in one group, so no relay is shared.
        relay_for_group = []
        for relay in relay_rows:
            covered = {x for x in str(relay.get("covered_area_ids", "")).split(",") if x}
            if covered & set(area_ids):
                relay_for_group.append(relay)
        relay_count = len(relay_for_group)
        relay_components = sum(int(r.get("energy_components_required", 0)) for r in relay_for_group)
        relay_ids = ",".join(str(r.get("relay_id", "")) for r in relay_for_group)
        cargo_count = int(cargo[cargo["服务区编号"].isin(area_ids)]["货箱编号"].nunique())
        rows.append({
            "group": f"G{idx}",
            "service_area_ids": ",".join(sorted(area_ids)),
            "population": population_loads[idx - 1],
            "mission_count": len(missions),
            "cargo_count": cargo_count,
            "completion_min": float(missions["end_min"].max()) if len(missions) else 0.0,
            "transport_energy_kwh": float(missions["energy_kwh"].sum()),
            "A_uav": resources["A"]["uav_count"],
            "A_battery": resources["A"]["battery_count"],
            "A_charger": resources["A"]["charger_count"],
            "B_uav": resources["B"]["uav_count"],
            "B_battery": resources["B"]["battery_count"],
            "B_charger": resources["B"]["charger_count"],
            "C_uav": resources["C"]["uav_count"],
            "C_battery": resources["C"]["battery_count"],
            "C_charger": resources["C"]["charger_count"],
            "relay_uav": relay_count,
            "relay_ids": relay_ids,
            "relay_energy_components": relay_components,
        })
        group_json.append({"group": f"G{idx}", "areas": area_ids, "resources": resources,
                           "relay_ids": relay_ids, "relay_count": relay_count,
                           "relay_energy_components": relay_components})

    totals = {key: sum(float(row[key]) for row in rows) for key in rows[0] if key.endswith(("_uav", "_battery", "_charger", "relay_energy_components"))}
    inventory = {
        "A_uav": int(loader.transport_inventory["A"]), "B_uav": int(loader.transport_inventory["B"]),
        "C_uav": int(loader.transport_inventory["C"]), "A_battery": int(loader.battery_inventory["A"]),
        "B_battery": int(loader.battery_inventory["B"]), "C_battery": int(loader.battery_inventory["C"]),
        "relay_uav": len(loader.relay_inventory),
        "relay_energy_components": int(loader.relay_energy_inventory["count"]),
    }
    gap = {key: max(0, totals.get(key, 0) - inventory.get(key, 0)) for key in inventory}
    output = root / "结果" / f"问题四_{num_groups}批次_修复版.xlsx"
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(rows).to_excel(writer, sheet_name="分组资源", index=False)
        pd.DataFrame([inventory]).to_excel(writer, sheet_name="官方库存", index=False)
        pd.DataFrame([gap]).to_excel(writer, sheet_name="资源缺口", index=False)
    (root / "结果" / f"问题四_{num_groups}批次_修复版.json").write_text(
        json.dumps({"groups": group_json, "totals": totals, "inventory": inventory, "gap": gap}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    return rows, totals, inventory, gap


def solve_staggered_inventory(num_groups):
    """Re-evaluate resources when groups execute sequentially with reuse.

    Unlike the independent-group upper bound above, this model assigns each
    group's missions to a non-overlapping time window. It keeps official UAV
    and battery types and shifts a group only as a whole, so the result is a
    conservative, auditable feasibility check rather than a fabricated fleet.
    """
    root = Path(__file__).parent
    data_dir = root / "数据" / "无人机应急物资运输基础数据"
    loader = DataLoader(str(data_dir)); loader.load_all()
    types = {row["type"]: row.to_dict() for _, row in loader.get_uav_types().iterrows()}
    schedule = pd.read_excel(root / "结果" / "问题二_优化修复版.xlsx", sheet_name="架次调度")
    area_df = loader.get_service_areas()
    area_info = {row["id"]: row.to_dict() for _, row in area_df.iterrows()}
    relay_rows = pd.read_excel(root / "结果" / "问题三_中继部署方案_修复版.xlsx").to_dict("records")
    groups, _ = _partition(area_info, relay_rows, num_groups)
    cursor = 0.0
    shifted = []
    for idx, area_ids in enumerate(groups, 1):
        missions = schedule[schedule["area_id"].isin(area_ids)].copy()
        if missions.empty:
            continue
        start = float(missions["start_min"].min())
        end = float(missions["end_min"].max())
        offset = cursor - start
        block = missions.copy()
        block["batch_id"] = f"G{idx}"
        block["batch_offset_min"] = offset
        block["start_min"] += offset
        block["delivery_min"] += offset
        block["end_min"] += offset
        shifted.append(block)
        cursor = float(block["end_min"].max())
    combined = pd.concat(shifted, ignore_index=True) if shifted else schedule.iloc[0:0].copy()
    resources = {}
    for typ, params in types.items():
        tasks = combined[combined["uav_type"] == typ].to_dict("records")
        resources[typ] = _resource_counts(tasks, params)
    inventory = {"A_uav": int(loader.transport_inventory["A"]), "B_uav": int(loader.transport_inventory["B"]),
                 "C_uav": int(loader.transport_inventory["C"]), "A_battery": int(loader.battery_inventory["A"]),
                 "B_battery": int(loader.battery_inventory["B"]), "C_battery": int(loader.battery_inventory["C"])}
    required = {f"{t}_uav": resources[t]["uav_count"] for t in types}
    required.update({f"{t}_battery": resources[t]["battery_count"] for t in types})
    gap = {k: max(0, required[k] - inventory[k]) for k in required}
    out = root / "结果" / f"问题四_{num_groups}批次_错峰复用优化.xlsx"
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        combined.to_excel(writer, sheet_name="错峰调度", index=False)
        pd.DataFrame([required]).to_excel(writer, sheet_name="需求", index=False)
        pd.DataFrame([inventory]).to_excel(writer, sheet_name="官方库存", index=False)
        pd.DataFrame([gap]).to_excel(writer, sheet_name="缺口", index=False)
    return {"groups": num_groups, "completion_min": float(combined["end_min"].max()) if len(combined) else 0.0,
            "required": required, "inventory": inventory, "gap": gap, "feasible_official_inventory": not any(gap.values())}


if __name__ == "__main__":
    root = Path(__file__).parent
    result2 = solve_problem4(2)
    result3 = solve_problem4(3)
    staggered2 = solve_staggered_inventory(2)
    staggered3 = solve_staggered_inventory(3)
    (root / "结果" / "问题四_错峰复用汇总.json").write_text(
        json.dumps({"staggered_2": staggered2, "staggered_3": staggered3}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(json.dumps({"groups_2": result2[1], "gap_2": result2[3],
                      "groups_3": result3[1], "gap_3": result3[3],
                      "staggered_2": staggered2, "staggered_3": staggered3}, ensure_ascii=True))
