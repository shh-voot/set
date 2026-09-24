#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Problem 3: DEM-aware bidirectional relay coverage.

Only the official R01/R02 relay UAVs and six relay energy components are
available. A deployment is reported as infeasible when those resources cannot
cover every service area; extra relays are never invented.
"""

from pathlib import Path
import json
import math

import numpy as np
import pandas as pd

from src.communication.los_model import CommParams, LOSCommunicationModel, Position
from src.data.data_loader import DataLoader
from src.terrain.dem_loader import DEMLoader


def _param(comm, suffix, contains=()):
    for key, value in comm.items():
        if key.endswith(":" + suffix) and all(x in key for x in contains):
            return float(value)
    raise KeyError(f"missing communication parameter {contains}:{suffix}")


def _haversine(a, b):
    r = 6371000.0
    dlat = np.radians(b[1] - a[1])
    dlon = np.radians(b[0] - a[0])
    q = np.sin(dlat / 2) ** 2 + np.cos(np.radians(a[1])) * np.cos(np.radians(b[1])) * np.sin(dlon / 2) ** 2
    return float(2 * r * np.arctan2(np.sqrt(q), np.sqrt(1 - q)))


def _path_points(depot, area, dem, count=9):
    a = (depot["longitude"], depot["latitude"])
    b = (area["longitude"], area["latitude"])
    horizontal = _haversine(a, b)
    samples = max(2, int(math.ceil(horizontal / 1000.0)) + 1)
    ground = []
    for t in np.linspace(0.0, 1.0, max(count, samples)):
        x, y = a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])
        h = dem.get_height(x, y)
        ground.append(float(h) if h is not None else float(depot["altitude"]))
    cruise = max(ground) + 50.0
    points = []
    for i, t in enumerate(np.linspace(0.0, 1.0, count)):
        x, y = a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])
        if i == 0:
            z = float(depot["altitude"] + 20.0)
        elif i == count - 1:
            z = float(area["altitude"] + 50.0)
        else:
            z = cruise
        points.append(Position(float(x), float(y), z))
    return points


def _link_budget(p1, p2, pt, gt, gr, params):
    d = max(1.0, _haversine((p1.x, p1.y), (p2.x, p2.y)))
    d = math.sqrt(d * d + (p2.z - p1.z) ** 2)
    fspl = 20.0 * math.log10(d / 1000.0) + 20.0 * math.log10(params["frequency_mhz"]) + 32.45
    rx = pt + gt + gr - fspl - params["system_loss_db"] - params["obstacle_loss_db"]
    return rx, rx - params["sensitivity_dbm"]


def _bidirectional(p1, p2, tx1, gain1, rx_gain1, tx2, gain2, rx_gain2, params, los):
    ok_los_12, reason12 = los.check_los(p1, p2)
    ok_los_21, reason21 = los.check_los(p2, p1)
    r12, m12 = _link_budget(p1, p2, tx1, gain1, rx_gain2, params)
    r21, m21 = _link_budget(p2, p1, tx2, gain2, rx_gain1, params)
    threshold = params["margin_db"]
    ok = ok_los_12 and ok_los_21 and m12 >= threshold and m21 >= threshold
    return ok, {
        "rx_12_dbm": r12, "margin_12_db": m12, "rx_21_dbm": r21,
        "margin_21_db": m21, "los_12": ok_los_12, "los_21": ok_los_21,
        "reason_12": reason12 or "", "reason_21": reason21 or "",
    }


def _relay_energy(relay_pos, depot_pos, duration_min, specs):
    d = math.sqrt(_haversine((relay_pos.x, relay_pos.y), (depot_pos.x, depot_pos.y)) ** 2 +
                  (relay_pos.z - depot_pos.z) ** 2)
    flight = specs["cruise_power_kw"] * (2.0 * d / specs["cruise_speed_ms"]) / 3600.0
    hover = (specs["hover_power_kw"] + specs["comm_power_kw"]) * duration_min / 60.0
    return flight + hover, flight, hover


def _component_schedule(flight_energy, hover_energy, flight_one_way_min,
                        service_start, service_end, return_end, specs):
    """Split relay energy over official usable component capacity."""
    usable = specs["battery_capacity_kwh"] * (1.0 - specs["reserve_pct"])
    charge_min = float(specs.get("energy_component_charge_time_min", 30.0))
    phases = [
        ("outbound", 0.0, flight_one_way_min, flight_energy / 2.0),
        ("hover", service_start, service_end, hover_energy),
        ("return", service_end, return_end, flight_energy / 2.0),
    ]
    remaining_capacity = usable
    component_no = 1
    segments = []
    last_end = {}
    for phase, phase_start, phase_end, phase_energy in phases:
        left = float(phase_energy)
        t = float(phase_start)
        phase_duration = max(0.0, float(phase_end - phase_start))
        while left > 1e-9:
            take = min(left, remaining_capacity)
            frac = take / phase_energy if phase_energy > 1e-12 else 1.0
            dt = phase_duration * frac
            comp_id = f"RE-{component_no:02d}"
            segments.append({"component_id": comp_id, "phase": phase,
                             "start_min": t, "end_min": t + dt,
                             "energy_kwh": take})
            last_end[comp_id] = t + dt
            t += dt
            left -= take
            remaining_capacity -= take
            if remaining_capacity <= 1e-9 and left > 1e-9:
                component_no += 1
                remaining_capacity = usable
    charge_windows = {comp: (end, end + charge_min) for comp, end in last_end.items()}
    return segments, charge_windows, component_no


def main():
    root = Path(__file__).parent
    data_dir = root / "数据" / "无人机应急物资运输基础数据"
    dem_dir = root / "数据" / "镇龙乡地理空间数据" / "镇龙乡及周边地理数据" / "数字高程模型数据（DEM）"
    loader = DataLoader(str(data_dir))
    loader.load_all()
    dem = DEMLoader(str(next(dem_dir.glob("*.mat"))))
    dem.load()

    comm = loader.get_comm_params()
    params = {
        "frequency_mhz": float(comm["f"]),
        "system_loss_db": float(comm["Lsys"]),
        "obstacle_loss_db": float(comm["Lobs"]),
        "sensitivity_dbm": float(comm["Psens"]),
        "margin_db": float(comm["M"]),
        "ground_pt": _param(comm, "Pt", ("G01",)),
        "ground_gain": _param(comm, "G", ("G01",)),
        "transport_pt": _param(comm, "Pt", ("运输",)),
        "transport_gain": _param(comm, "G", ("运输",)),
        "relay_pt": _param(comm, "Pt", ("中继接入端",)),
        "relay_gain": _param(comm, "G", ("中继接入端",)),
        "relay_rx_gain": _param(comm, "G", ("中继回传端",)),
    }
    relay_specs = loader.get_relay_uav()
    relay_specs["energy_component_charge_time_min"] = loader.relay_energy_inventory["full_charge_time_min"]
    depot = loader.get_depot()
    areas = {row["id"]: row.to_dict() for _, row in loader.get_service_areas().iterrows()}
    gateway = Position(depot["longitude"], depot["latitude"], depot["altitude"] + 20.0)

    # The official link budget is the range constraint.  No extra terrain
    # clearance or arbitrary range limit is introduced here.
    los = LOSCommunicationModel(dem.dem_data, dem.dem_bounds,
                                CommParams(max_range_m=float("inf"), safety_margin_m=0.0))
    p2_file = root / "结果" / "问题二_优化修复版.xlsx"
    schedule = pd.read_excel(p2_file, sheet_name="架次调度")
    duration_min = float(schedule["end_min"].max())

    paths = {area_id: _path_points(depot, area, dem) for area_id, area in areas.items()}
    transport_positions = {area_id: path[-1] for area_id, path in paths.items()}

    # Direct gateway coverage and candidate relay coverage are both evaluated
    # over the complete depot-to-service path, not just the endpoint.
    direct = {}
    for area_id, path in paths.items():
        details = []
        for point in path:
            ok, detail = _bidirectional(
                gateway, point, params["ground_pt"], params["ground_gain"], params["ground_gain"],
                params["transport_pt"], params["transport_gain"], params["transport_gain"], params, los)
            details.append(detail)
        direct[area_id] = all(
            d["los_12"] and d["los_21"] and
            d["margin_12_db"] >= params["margin_db"] and
            d["margin_21_db"] >= params["margin_db"]
            for d in details
        )

    lons = [depot["longitude"]] + [a["longitude"] for a in areas.values()]
    lats = [depot["latitude"]] + [a["latitude"] for a in areas.values()]
    lon_pad = (max(lons) - min(lons)) * 0.05
    lat_pad = (max(lats) - min(lats)) * 0.05
    candidates = []
    for lon in np.linspace(min(lons) - lon_pad, max(lons) + lon_pad, 11):
        for lat in np.linspace(min(lats) - lat_pad, max(lats) + lat_pad, 11):
            terrain = dem.get_height(float(lon), float(lat))
            if terrain is None:
                continue
            relay = Position(float(lon), float(lat), float(terrain + relay_specs["hover_altitude_m"]))
            relay_ground, ground_detail = _bidirectional(
                gateway, relay, params["ground_pt"], params["ground_gain"], params["ground_gain"],
                params["relay_pt"], params["relay_gain"], params["relay_rx_gain"], params, los)
            if not relay_ground:
                continue
            covered = set()
            for area_id, path in paths.items():
                if direct[area_id]:
                    continue
                if all(_bidirectional(
                    point, relay, params["transport_pt"], params["transport_gain"], params["transport_gain"],
                    params["relay_pt"], params["relay_gain"], params["relay_rx_gain"], params, los)[0]
                       for point in path):
                    covered.add(area_id)
            energy, flight, hover = _relay_energy(relay, gateway, duration_min, relay_specs)
            components = int(math.ceil(energy / (relay_specs["battery_capacity_kwh"] * (1.0 - relay_specs["reserve_pct"]))))
            if components <= 0 or components > loader.relay_energy_inventory["count"]:
                continue
            candidates.append({"position": relay, "covered": covered, "energy": energy,
                               "flight_energy": flight, "hover_energy": hover,
                               "components": components, "ground_detail": ground_detail})

    required = {a for a, ok in direct.items() if not ok}
    selected = []
    covered = set()
    for _ in range(min(len(loader.relay_inventory), 2)):
        options = [c for c in candidates if c not in selected]
        if not options:
            break
        best = max(options, key=lambda c: (len((c["covered"] - covered) & required), -c["energy"]))
        gain = len((best["covered"] - covered) & required)
        if gain == 0:
            break
        selected.append(best)
        covered.update(best["covered"])
        if covered >= required:
            break

    relay_components = sum(c["components"] for c in selected)
    all_covered = set(a for a, ok in direct.items() if ok) | covered
    coverage = len(all_covered) / len(areas)
    transport_energy = float(schedule["energy_kwh"].sum())
    relay_energy = float(sum(c["energy"] for c in selected))

    relay_by_area = {}
    relay_service_windows = {}
    relay_rows = []
    for i, c in enumerate(selected):
        relay_id = loader.relay_inventory[i]
        for area_id in c["covered"]:
            relay_by_area[area_id] = relay_id
        relay = c["position"]
        distance_m = math.sqrt(_haversine((relay.x, relay.y),
                                          (gateway.x, gateway.y)) ** 2 +
                               (relay.z - gateway.z) ** 2)
        flight_one_way_min = distance_m / relay_specs["cruise_speed_ms"] / 60.0
        service_start = (float(relay_specs["prep_time_s"]) / 60.0 +
                         flight_one_way_min + float(relay_specs["setup_time_s"]) / 60.0)
        service_end = service_start + duration_min
        return_end = service_end + flight_one_way_min + float(relay_specs["turnaround_time_s"]) / 60.0
        segments, charge_windows, component_no = _component_schedule(
            c["flight_energy"], c["hover_energy"], flight_one_way_min,
            service_start, service_end, return_end, relay_specs)
        relay_service_windows[relay_id] = (service_start, service_end)
        relay_rows.append({
            "relay_id": relay_id,
            "longitude": relay.x,
            "latitude": relay.y,
            "altitude_m": relay.z,
            "deployment_start_min": 0.0,
            "service_start_min": service_start,
            "service_end_min": service_end,
            "return_end_min": return_end,
            "hover_duration_min": duration_min,
            "covered_area_ids": ",".join(sorted(c["covered"])),
            "energy_kwh": c["energy"],
            "flight_energy_kwh": c["flight_energy"],
            "hover_energy_kwh": c["hover_energy"],
            "energy_components_required": c["components"],
            "energy_component_ids": ",".join(sorted(charge_windows)),
            "component_use_segments": json.dumps(segments, ensure_ascii=False),
            "component_charge_windows": json.dumps(charge_windows, ensure_ascii=False),
        })

    schedule = schedule.copy()
    def mission_comm(row):
        area_id = row["area_id"]
        if direct.get(area_id, False):
            return "direct", True
        relay_id = relay_by_area.get(area_id)
        if relay_id is None:
            return "interrupted", False
        service_start, service_end = relay_service_windows[relay_id]
        ok = (float(row["start_min"]) >= service_start - 1e-9 and
              float(row["end_min"]) <= service_end + 1e-9)
        return (relay_id if ok else "relay_outside_service_window"), ok

    comm_values = schedule.apply(mission_comm, axis=1, result_type="expand")
    schedule["communication_mode"] = comm_values[0]
    schedule["communication_available"] = comm_values[1]
    coverage_rows = [{"area_id": area_id, "direct_gateway": bool(direct[area_id]),
                      "covered": area_id in all_covered, "relay_required": not direct[area_id]}
                     for area_id in sorted(areas)]
    interrupted_missions = schedule.loc[~schedule["communication_available"], "mission_id"].astype(int).tolist()

    output_dir = root / "结果"
    pd.DataFrame(relay_rows).to_excel(output_dir / "问题三_中继部署方案_修复版.xlsx", index=False)
    pd.DataFrame(coverage_rows).to_excel(output_dir / "问题三_覆盖核验_修复版.xlsx", index=False)
    schedule.to_excel(output_dir / "问题三_运输调度_修复版.xlsx", index=False)
    summary = {
        "coverage_rate": coverage,
        "covered_area_count": len(all_covered),
        "area_count": len(areas),
        "relay_count": len(selected),
        "official_relay_inventory": len(loader.relay_inventory),
        "relay_energy_components_used": relay_components,
        "official_relay_energy_components": loader.relay_energy_inventory["count"],
        "transport_energy_kwh": transport_energy,
        "relay_energy_kwh": relay_energy,
        "total_energy_kwh": transport_energy + relay_energy,
        "uncovered_area_ids": sorted(set(areas) - all_covered),
        "communication_available_mission_count": int(schedule["communication_available"].sum()),
        "communication_interrupted_mission_ids": interrupted_missions,
        "relay_service_windows": relay_service_windows,
        "feasible_100_percent": coverage >= 1.0 and relay_components <= loader.relay_energy_inventory["count"],
    }
    (output_dir / "问题三_汇总_修复版.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"coverage": coverage, "relays": len(selected), "components": relay_components,
                      "uncovered": summary["uncovered_area_ids"], "total_energy_kwh": summary["total_energy_kwh"]}, ensure_ascii=True))


if __name__ == "__main__":
    main()
