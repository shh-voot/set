#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Problem 2: schedule the repaired 18-mission Problem 1 plan.

The mission grouping is kept unchanged from Problem 1. This module adds the
physical UAV, shared-battery and charging constraints from the official
workbook, then reports box-level deadline performance.
"""

from pathlib import Path
import json

import pandas as pd

from src.data.data_loader import DataLoader
from src.battery.charging_model_correct import calculate_charging_time


ID = "货箱编号"
AREA = "服务区编号"
FIRST = "是否首批保障"
FIRST_DEADLINE = "首批截止时间（s）"
EXPECTED_DEADLINE = "期望送达时间（s）"


def deadline_seconds(row):
    if str(row[FIRST]).strip() == "是" and pd.notna(row[FIRST_DEADLINE]):
        return float(row[FIRST_DEADLINE])
    return float(row[EXPECTED_DEADLINE])


def main():
    root = Path(__file__).parent
    data_dir = root / "数据" / "无人机应急物资运输基础数据"
    p1 = root / "结果" / "问题一_18架次方案_修复版.xlsx"

    loader = DataLoader(str(data_dir))
    loader.load_all()
    cargo = loader.get_cargos().copy()
    types = {row["type"]: row.to_dict() for _, row in loader.get_uav_types().iterrows()}
    missions = pd.read_excel(p1, sheet_name="架次方案")
    if len(missions) != 18:
        raise ValueError(f"问题二必须继承问题一的18架次方案，当前为{len(missions)}架次")

    cargo_by_id = cargo.set_index(ID, drop=False)
    mission_records = []
    for _, mission in missions.iterrows():
        ids = [x.strip() for x in str(mission["cargo_ids"]).split(",") if x.strip()]
        missing = [x for x in ids if x not in cargo_by_id.index]
        if missing:
            raise ValueError(f"架次{mission['trip_id']}包含官方清单之外的货箱: {missing}")
        boxes = cargo_by_id.loc[ids]
        box_deadlines = boxes.apply(deadline_seconds, axis=1)
        mission_records.append({
            "trip_id": int(mission["trip_id"]),
            "area_id": mission["area_id"],
            "uav_type": str(mission["uav_type"]),
            "cargo_ids": ids,
            "deadline_min": float(box_deadlines.min() / 60.0),
            "priority": float(boxes["应急优先系数"].max()),
            "duration_min": float(mission["total_time_min"]),
            "delivery_offset_min": float(mission["delivery_time_min"]),
            "energy_kwh": float(mission["energy_kwh"]),
        })

    mission_records.sort(key=lambda x: (x["deadline_min"], -len(x["cargo_ids"]),
                                        -x["priority"], x["trip_id"]))

    uavs = {
        typ: [{"id": f"U{typ}{i + 1:02d}", "available": 0.0}
              for i in range(int(params["count"]))]
        for typ, params in types.items()
    }
    batteries = {
        typ: [{"id": f"{typ}-BAT-{i + 1:02d}", "available": 0.0}
              for i in range(int(params["battery_count"]))]
        for typ, params in types.items()
    }

    schedule_rows = []
    cargo_rows = []
    for schedule_id, mission in enumerate(mission_records, 1):
        typ = mission["uav_type"]
        if typ not in types:
            raise ValueError(f"官方机型表中不存在机型{typ}")
        params = types[typ]
        uav = min(uavs[typ], key=lambda item: (item["available"], item["id"]))
        battery = min(batteries[typ], key=lambda item: (item["available"], item["id"]))

        start = max(float(uav["available"]), float(battery["available"]))
        delivery = start + mission["delivery_offset_min"]
        end = start + mission["duration_min"]
        capacity = float(params["battery_capacity_kwh"])
        reserve = float(params["battery_reserve_pct"])
        usable = capacity * (1.0 - reserve)
        if mission["energy_kwh"] > usable + 1e-9:
            raise ValueError(
                f"架次{mission['trip_id']}能耗{mission['energy_kwh']:.6f} kWh"
                f"超过{typ}型可用电量{usable:.6f} kWh"
            )
        soc_after = 1.0 - mission["energy_kwh"] / capacity
        charge_min = float(calculate_charging_time(
            soc_after, 1.0, float(params["full_charge_time_min"])))

        uav["available"] = end
        battery["available"] = end + charge_min
        schedule_rows.append({
            "mission_id": schedule_id,
            "source_trip_id": mission["trip_id"],
            "uav_id": uav["id"],
            "uav_type": typ,
            "battery_id": battery["id"],
            "area_id": mission["area_id"],
            "cargo_count": len(mission["cargo_ids"]),
            "cargo_ids": ",".join(mission["cargo_ids"]),
            "start_min": start,
            "delivery_min": delivery,
            "end_min": end,
            "deadline_min": mission["deadline_min"],
            "on_time": delivery <= mission["deadline_min"] + 1e-9,
            "energy_kwh": mission["energy_kwh"],
            "soc_after": soc_after,
            "charge_min": charge_min,
        })

        for box_id in mission["cargo_ids"]:
            box = cargo_by_id.loc[box_id]
            box_deadline = deadline_seconds(box) / 60.0
            cargo_rows.append({
                "cargo_id": box_id,
                "mission_id": schedule_id,
                "source_trip_id": mission["trip_id"],
                "area_id": box[AREA],
                "uav_id": uav["id"],
                "delivery_min": delivery,
                "deadline_min": box_deadline,
                "on_time": delivery <= box_deadline + 1e-9,
            })

    result = pd.DataFrame(schedule_rows)
    cargo_result = pd.DataFrame(cargo_rows)
    if len(cargo_result) != len(cargo) or cargo_result["cargo_id"].nunique() != len(cargo):
        raise ValueError("问题二货箱覆盖校验失败：未做到80箱唯一覆盖")

    inventory = []
    for typ, params in types.items():
        used_uavs = sorted(result.loc[result["uav_type"] == typ, "uav_id"].unique())
        used_batteries = sorted(result.loc[result["uav_type"] == typ, "battery_id"].unique())
        inventory.append({
            "type": typ,
            "official_uav_inventory": int(params["count"]),
            "used_uav_count": len(used_uavs),
            "used_uav_ids": ",".join(used_uavs),
            "official_battery_inventory": int(params["battery_count"]),
            "used_battery_count": len(used_batteries),
            "used_battery_ids": ",".join(used_batteries),
        })

    summary = pd.DataFrame({
        "metric": ["missions", "cargo_count", "unique_cargo_count", "completion_min",
                   "late_cargo_count", "total_energy_kwh"],
        "value": [len(result), len(cargo_result), cargo_result["cargo_id"].nunique(),
                  result["end_min"].max(), int((~cargo_result["on_time"]).sum()),
                  result["energy_kwh"].sum()],
    })
    output = root / "结果" / "问题二_修复版.xlsx"
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        result.to_excel(writer, sheet_name="架次调度", index=False)
        cargo_result.to_excel(writer, sheet_name="逐箱时限", index=False)
        pd.DataFrame(inventory).to_excel(writer, sheet_name="资源核验", index=False)
        summary.to_excel(writer, sheet_name="校验", index=False)

    print(json.dumps({
        "output": str(output),
        "missions": len(result),
        "cargo": int(cargo_result["cargo_id"].nunique()),
        "completion_min": float(result["end_min"].max()),
        "late": int((~cargo_result["on_time"]).sum()),
        "energy_kwh": float(result["energy_kwh"].sum()),
    }, ensure_ascii=True))


if __name__ == "__main__":
    main()
