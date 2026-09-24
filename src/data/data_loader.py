#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Canonical loader for the competition workbooks.

The source sheets contain several sections in one worksheet. This module
keeps the raw semantics explicit so downstream solvers do not depend on
accidental column interpretations.
"""

from pathlib import Path
from typing import Dict

import pandas as pd


TRANSPORT_FILE = "\u8fd0\u8f93\u65e0\u4eba\u673a\u6570\u636e.xlsx"
RELAY_FILE = "\u4e2d\u7ee7\u65e0\u4eba\u673a\u6570\u636e.xlsx"
DEPOT_FILE = "\u8c03\u5ea6\u4e2d\u5fc3\u4e0e\u670d\u52a1\u533a.xlsx"
CARGO_FILE = "\u7269\u8d44\u9700\u6c42\u4e0e\u914d\u9001\u65f6\u9650.xlsx"
COMM_FILE = "\u901a\u4fe1\u94fe\u8def\u53c2\u6570.xlsx"


class DataLoader:
    def __init__(self, data_dir: str = "\u6570\u636e/\u65e0\u4eba\u673a\u5e94\u6025\u7269\u8d44\u8fd0\u8f93\u57fa\u7840\u6570\u636e"):
        self.data_dir = Path(data_dir)
        self.depots = None
        self.service_areas = None
        self.uav_transport = None
        self.transport_inventory: Dict[str, int] = {}
        self.battery_inventory: Dict[str, int] = {}
        self.uav_relay = None
        self.relay_inventory = []
        self.relay_energy_inventory: Dict[str, float] = {}
        self.cargos = None
        self.comm_params: Dict[str, float] = {}

    def load_all(self):
        self.load_depots_and_service_areas()
        self.load_uav_transport()
        self.load_uav_relay()
        self.load_cargo_demands()
        self.load_comm_params()

    def load_depots_and_service_areas(self):
        df = pd.read_excel(self.data_dir / DEPOT_FILE, header=None)
        depot = df[df.iloc[:, 0].astype(str).str.startswith("O", na=False)]
        if depot.empty:
            raise ValueError("No depot row found")
        row = depot.iloc[0]
        self.depots = {
            "id": str(row.iloc[0]), "name": row.iloc[1],
            "longitude": float(row.iloc[2]), "latitude": float(row.iloc[3]),
            "altitude": float(row.iloc[4]),
        }
        rows = []
        for _, row in df.iterrows():
            if not str(row.iloc[0]).startswith("S"):
                continue
            try:
                rows.append({
                    "id": str(row.iloc[0]), "name": row.iloc[1],
                    "longitude": float(row.iloc[2]), "latitude": float(row.iloc[3]),
                    "altitude": float(row.iloc[4]),
                    "population": int(row.iloc[5]) if pd.notna(row.iloc[5]) else 0,
                })
            except (TypeError, ValueError):
                continue
        self.service_areas = pd.DataFrame(rows)

    def load_uav_transport(self):
        df = pd.read_excel(self.data_dir / TRANSPORT_FILE, header=None)
        type_rows = {}
        for _, row in df.iterrows():
            typ = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ""
            if typ in {"A", "B", "C"} and pd.notna(row.iloc[5]):
                type_rows[typ] = row

        self.transport_inventory = {"A": 0, "B": 0, "C": 0}
        for _, row in df.iterrows():
            ident = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ""
            typ = str(row.iloc[1]) if pd.notna(row.iloc[1]) else ""
            if ident.startswith("U") and typ in self.transport_inventory:
                self.transport_inventory[typ] += 1

        self.battery_inventory = {"A": 0, "B": 0, "C": 0}
        charge_min = {"A": 0.0, "B": 0.0, "C": 0.0}
        for _, row in df.iterrows():
            typ = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ""
            if typ in charge_min and pd.notna(row.iloc[1]) and pd.notna(row.iloc[2]):
                try:
                    self.battery_inventory[typ] = int(row.iloc[1])
                    charge_min[typ] = float(row.iloc[2]) / 60.0
                except (TypeError, ValueError):
                    pass

        records = []
        for typ in ["A", "B", "C"]:
            row = type_rows[typ]
            empty_range_m = float(row.iloc[6])
            full_range_m = float(row.iloc[7])
            speed = float(row.iloc[5])
            capacity = float(row.iloc[8])
            reserve = float(row.iloc[9]) / 100.0
            usable = capacity * (1.0 - reserve)
            cruise_hours = empty_range_m / speed / 3600.0
            records.append({
                "type": typ, "name": str(row.iloc[1]),
                "empty_mass_kg": float(row.iloc[2]),
                "max_load_kg": float(row.iloc[3]),
                "max_volume_m3": float(row.iloc[4]),
                "empty_range_km": empty_range_m / 1000.0,
                "full_range_km": full_range_m / 1000.0,
                "max_range_km": empty_range_m / 1000.0,
                "cruise_speed_ms": speed,
                "cruise_power_kw": usable / cruise_hours,
                "battery_capacity_kwh": capacity,
                "battery_reserve_pct": reserve,
                "full_charge_time_min": charge_min[typ],
                "prep_time_s": float(row.iloc[10]),
                "takeoff_time_s": float(row.iloc[10]),
                "landing_time_s": 0.0,
                "load_time_per_box_s": float(row.iloc[11]),
                "handoff_base_s": float(row.iloc[12]),
                "handoff_per_box_s": float(row.iloc[13]),
                "load_unload_time_s": float(row.iloc[11]),
                "ascent_speed_ms": float(row.iloc[14]),
                "descent_speed_ms": float(row.iloc[15]),
                "ascent_efficiency": float(row.iloc[16]),
                "descent_efficiency": float(row.iloc[17]),
                "count": self.transport_inventory[typ],
                "battery_count": self.battery_inventory[typ],
            })
        self.uav_transport = pd.DataFrame(records)

    def load_uav_relay(self):
        df = pd.read_excel(self.data_dir / RELAY_FILE, header=None)
        spec = df[df.iloc[:, 0].astype(str).eq("R")]
        if spec.empty:
            raise ValueError("No relay UAV specification found")
        row = spec.iloc[0]
        self.uav_relay = {
            "type": "R", "name": str(row.iloc[1]),
            "max_load_kg": float(row.iloc[2]), "relay_module_kg": float(row.iloc[3]),
            "cruise_speed_ms": float(row.iloc[5]), "cruise_power_kw": float(row.iloc[6]),
            "battery_capacity_kwh": float(row.iloc[7]), "reserve_pct": float(row.iloc[8]) / 100.0,
            "prep_time_s": float(row.iloc[9]), "setup_time_s": float(row.iloc[10]),
            "turnaround_time_s": float(row.iloc[11]), "ascent_speed_ms": float(row.iloc[12]),
            "descent_speed_ms": float(row.iloc[13]), "ascent_efficiency": float(row.iloc[14]),
            "descent_efficiency": float(row.iloc[15]), "hover_power_kw": float(row.iloc[16]),
            "comm_power_kw": float(row.iloc[17]), "hover_altitude_m": float(row.iloc[18]),
        }
        self.relay_inventory = []
        for _, item in df.iterrows():
            ident = str(item.iloc[0]) if pd.notna(item.iloc[0]) else ""
            if ident.startswith("R") and ident[1:].isdigit():
                self.relay_inventory.append(ident)
        self.relay_energy_inventory = {"count": 0, "full_charge_time_min": 0.0}
        for _, item in df.iterrows():
            if (str(item.iloc[0]) == "R" and pd.notna(item.iloc[1]) and
                    pd.notna(item.iloc[2]) and isinstance(item.iloc[1], (int, float))):
                self.relay_energy_inventory = {
                    "count": int(item.iloc[1]),
                    "full_charge_time_min": float(item.iloc[2]) / 60.0,
                }

    def load_cargo_demands(self):
        self.cargos = pd.read_excel(self.data_dir / CARGO_FILE, sheet_name=1)

    def load_comm_params(self):
        df = pd.read_excel(self.data_dir / COMM_FILE, header=None)
        params = {}
        for _, row in df.iterrows():
            if len(row) < 5 or pd.isna(row.iloc[3]) or pd.isna(row.iloc[4]):
                continue
            category = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ""
            symbol = str(row.iloc[3])
            try:
                value = float(row.iloc[4])
            except (TypeError, ValueError):
                value = row.iloc[4]
            params[symbol] = value
            if category:
                params[f"{category}:{symbol}"] = value
        self.comm_params = params

    def get_depot(self):
        return self.depots

    def get_service_areas(self):
        return self.service_areas

    def get_service_area(self, area_id: str):
        rows = self.service_areas[self.service_areas["id"] == area_id]
        return rows.iloc[0].to_dict() if not rows.empty else None

    def get_uav_types(self):
        return self.uav_transport

    def get_uav_type(self, uav_type: str):
        rows = self.uav_transport[self.uav_transport["type"] == uav_type]
        return rows.iloc[0].to_dict() if not rows.empty else None

    def get_relay_uav(self):
        return self.uav_relay

    def get_cargos(self):
        return self.cargos

    def get_comm_params(self):
        return self.comm_params


if __name__ == "__main__":
    loader = DataLoader()
    loader.load_all()
    print(loader.uav_transport[["type", "max_load_kg", "full_charge_time_min", "count", "battery_count"]])
    print(loader.transport_inventory, loader.battery_inventory)
    print(loader.relay_inventory, loader.relay_energy_inventory)
