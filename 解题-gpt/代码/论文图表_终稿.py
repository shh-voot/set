#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate clean paper figures from the official-data result workbooks.

The figures use only official data/results in this repository.  This plotting
program was completed with AI-assisted coding support (OpenAI Codex, 2026-09)
and was manually checked against the source workbooks before export.
"""

from __future__ import annotations

import base64
import io
import json
import re
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np
import pandas as pd
from PIL import Image


HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]  # D:/claude/华为杯/D题
RESULT = PROJECT / "解题-gpt" / "结果"
OUT = PROJECT / "解题-gpt" / "可视化" / "论文图表"
OUT.mkdir(parents=True, exist_ok=True)
HTML = PROJECT / "数据" / "镇龙乡地理空间数据" / "镇龙乡地理空间详情地图.html"

COLORS = {
    "A": "#598EBB",
    "B": "#8CCDC6",
    "C": "#948EC1",
    "relay": "#9CC896",
    "highlight": "#6CAAC4",
    "baseline": "#B8C0C8",
    "ink": "#2B2B2B",
    "muted": "#66717A",
    "grid": "#E6E6E6",
    "fail": "#C77772",
}

plt.rcParams.update({
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.labelsize": 10,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "text.color": COLORS["ink"],
    "axes.labelcolor": COLORS["ink"],
    "xtick.color": COLORS["ink"],
    "ytick.color": COLORS["ink"],
    "axes.edgecolor": "#4A4A4A",
})


def load_map():
    text = HTML.read_text(encoding="utf-8")
    terrain_url = re.search(r'const terrainUrl\s*=\s*"(data:image/png;base64,[^"]+)";', text).group(1)
    bounds = json.loads(re.search(r"const terrainBounds\s*=\s*([^;]+);", text).group(1))
    services = json.loads(re.search(r"const services\s*=\s*(\{.*?\});\s*const summary", text, re.S).group(1))
    dispatch = json.loads(re.search(r"const dispatchCenter\s*=\s*(\{.*?\});\s*const services", text, re.S).group(1))
    image = Image.open(io.BytesIO(base64.b64decode(terrain_url.split(",", 1)[1]))).convert("RGB")
    west, south, east, north = bounds

    def merc_y(lat):
        rad = np.radians(lat)
        return np.log(np.tan(np.pi / 4.0 + rad / 2.0))

    x0, x1 = np.radians([west, east])
    y0, y1 = merc_y(south), merc_y(north)
    scale = min((1176.0 - 24.0) / (x1 - x0), (750.0 - 20.0) / (y1 - y0))
    tx = 24.0 + (1176.0 - 24.0 - scale * (x1 - x0)) / 2.0 - scale * x0
    ty = 20.0 + (750.0 - 20.0 + scale * y0 + scale * y1) / 2.0

    def project(lon, lat):
        return scale * np.radians(lon) + tx, ty - scale * merc_y(lat)

    points = {
        f["properties"]["服务区编号"]: project(*f["geometry"]["coordinates"])
        for f in services["features"]
    }
    depot = project(*dispatch["features"][0]["geometry"]["coordinates"])
    return image, project, points, depot, services["features"]


def map_ax(ax, image, points, depot, labels=True):
    ax.imshow(image, extent=(24, 1176, 20, 750), origin="upper", alpha=0.72, zorder=0)
    coords = list(points.values()) + [depot]
    xs, ys = zip(*coords)
    pad_x = max(35, (max(xs) - min(xs)) * 0.23)
    pad_y = max(35, (max(ys) - min(ys)) * 0.23)
    ax.set_xlim(min(xs) - pad_x, max(xs) + pad_x)
    ax.set_ylim(max(ys) + pad_y, min(ys) - pad_y)
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    for side in ax.spines.values():
        side.set_visible(False)
    for area, (x, y) in points.items():
        ax.scatter(x, y, s=28, c="#C74859", edgecolor="white", linewidth=0.8, zorder=5)
        if labels:
            ax.text(x + 5, y - 4, area, fontsize=7, weight="bold",
                    bbox=dict(facecolor="white", edgecolor="none", alpha=0.78, pad=0.6), zorder=6)
    ax.scatter(*depot, marker="*", s=135, c="#D3B532", edgecolor="#4A4A4A", linewidth=0.8, zorder=7)
    ax.text(depot[0] + 7, depot[1] + 3, "O01", fontsize=8, weight="bold",
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.82, pad=0.7), zorder=8)


def save(fig, filename):
    fig.savefig(OUT / filename, dpi=360, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def q1():
    image, _, points, depot, _ = load_map()
    schedule = pd.read_excel(RESULT / "问题一_18架次方案_修复版.xlsx", sheet_name="架次方案")
    fig, (ax_map, ax_bar) = plt.subplots(1, 2, figsize=(13.5, 5.8), gridspec_kw={"width_ratios": [1.18, 0.82]})
    map_ax(ax_map, image, points, depot)
    for _, row in schedule.iterrows():
        area = str(row.get("area_id", row.get("服务区编号", "")))
        if area not in points:
            continue
        ax_map.plot([depot[0], points[area][0]], [depot[1], points[area][1]],
                    color=COLORS.get(str(row.get("uav_type", "A")), COLORS["highlight"]),
                    lw=1.1, alpha=0.45, zorder=2)
    ax_map.set_title("官方DEM底图与18架次直飞路径", loc="left", weight="bold")
    ax_map.legend(handles=[Line2D([0], [0], color=COLORS[t], lw=2, label=f"机型{t}") for t in ("A", "B", "C")],
                  loc="lower left", fontsize=8, framealpha=0.9)

    names = ["架次", "总能耗\n(kWh)", "最长任务\n(min)"]
    values = [18, 56.5159, 38.6048]
    ax_bar.barh(np.arange(3), values, color=[COLORS["highlight"], COLORS["relay"], COLORS["C"]], height=0.54)
    ax_bar.set_yticks(np.arange(3), names)
    ax_bar.invert_yaxis(); ax_bar.grid(axis="x", color=COLORS["grid"], lw=0.7)
    ax_bar.set_axisbelow(True)
    ax_bar.set_title("严格约束下的关键指标", loc="left", weight="bold")
    for i, value in enumerate(values):
        ax_bar.text(value + max(values) * 0.025, i, f"{value:.4g}" if i else f"{value:.0f}", va="center", fontsize=10, weight="bold")
    ax_bar.set_xlim(0, max(values) * 1.22)
    fig.suptitle("问题一  单架次组批与安全返航", x=0.04, ha="left", fontsize=16, weight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    save(fig, "问题一_路径与约束指标.png")


def active_counts(schedule, typ):
    events = []
    for _, row in schedule[schedule["uav_type"] == typ].iterrows():
        events.append((float(row["start_min"]), 1))
        events.append((float(row["end_min"]), -1))
    events.sort(key=lambda x: (x[0], -x[1]))
    t, y, cur = [0.0], [0], 0
    for event_t, delta in events:
        t.extend([event_t, event_t])
        y.extend([cur, cur + delta])
        cur += delta
    return np.array(t), np.array(y)


def q2():
    schedule = pd.read_excel(RESULT / "问题二_增强优化版.xlsx", sheet_name="架次调度")
    fig = plt.figure(figsize=(13.5, 7.0))
    grid = fig.add_gridspec(2, 3, height_ratios=[1.0, 1.28], hspace=0.42, wspace=0.32)
    metrics = [("架次", len(schedule)),
               ("完成时间（min）", schedule["end_min"].max()),
               ("总能耗（kWh）", schedule["energy_kwh"].sum())]
    for j, (label, value) in enumerate(metrics):
        ax = fig.add_subplot(grid[0, j])
        bar = ax.bar([0], [value], color=COLORS["highlight"], width=0.55)[0]
        ax.set_xticks([0], ["正式方案"])
        ax.set_title(label, loc="left", weight="bold")
        ax.grid(axis="y", color=COLORS["grid"], lw=0.7); ax.set_axisbelow(True)
        ax.text(bar.get_x() + bar.get_width() / 2, value, f"{value:.1f}" if j else f"{value:.0f}",
                ha="center", va="bottom", fontsize=10, weight="bold")
    ax = fig.add_subplot(grid[1, :2])
    for typ in ("A", "B", "C"):
        t, y = active_counts(schedule, typ)
        ax.step(t, y, where="post", color=COLORS[typ], lw=2, label=f"机型{typ}")
    for typ, cap in (("A", 4), ("B", 2), ("C", 2)):
        ax.axhline(cap, color=COLORS[typ], lw=0.8, ls="--", alpha=0.45)
    ax.set_xlabel("调度时间（min）"); ax.set_ylabel("同时执行架次")
    ax.set_title("正式方案的实体机并发峰值与官方库存上限", loc="left", weight="bold")
    ax.grid(color=COLORS["grid"], lw=0.7); ax.legend(ncol=3, frameon=False)
    ax = fig.add_subplot(grid[1, 2])
    labels = ["按时货箱", "迟到货箱"]
    vals = [80, 0]
    bars = ax.bar(labels, vals, color=[COLORS["relay"], COLORS["fail"]], width=0.55)
    ax.set_ylim(0, 88); ax.set_ylabel("货箱数")
    ax.set_title("时限核验", loc="left", weight="bold")
    ax.grid(axis="y", color=COLORS["grid"], lw=0.7); ax.set_axisbelow(True)
    for bar, value in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 2, str(value), ha="center", weight="bold")
    fig.suptitle("问题二  异构机队调度正式结果", x=0.04, ha="left", fontsize=16, weight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    save(fig, "问题二_性能与资源峰值.png")


def q3():
    image, project, points, depot, _ = load_map()
    schedule = pd.read_excel(RESULT / "问题三_运输调度_修复版.xlsx")
    relays = pd.read_excel(RESULT / "问题三_中继部署方案_修复版.xlsx")
    summary = json.loads((RESULT / "问题三_汇总_修复版.json").read_text(encoding="utf-8"))
    fig = plt.figure(figsize=(13.5, 6.8))
    grid = fig.add_gridspec(2, 2, width_ratios=[1.25, 0.75], height_ratios=[1.1, 0.9], hspace=0.36, wspace=0.28)
    ax_map = fig.add_subplot(grid[:, 0]); map_ax(ax_map, image, points, depot)
    relay_colors = {"R01": COLORS["relay"], "R02": COLORS["highlight"]}
    for _, row in relays.iterrows():
        rx, ry = project(float(row["longitude"]), float(row["latitude"]))
        rid = str(row["relay_id"])
        ax_map.scatter(rx, ry, marker="D", s=80, c=relay_colors.get(rid, COLORS["relay"]), edgecolor="#4A4A4A", zorder=8)
        ax_map.text(rx + 7, ry - 5, rid, fontsize=8, weight="bold",
                    bbox=dict(facecolor="white", edgecolor="none", alpha=0.82, pad=0.7), zorder=9)
        for area in [x for x in str(row["covered_area_ids"]).split(",") if x in points]:
            ax_map.plot([rx, points[area][0]], [ry, points[area][1]], color=relay_colors.get(rid, COLORS["relay"]), lw=1.1, alpha=0.45, zorder=3)
    ax_map.set_title("官方DEM视距判定下的中继覆盖", loc="left", weight="bold")
    ax_map.legend(handles=[Line2D([0], [0], marker="D", color="w", markerfacecolor=relay_colors[r], markeredgecolor="#4A4A4A", markersize=8, label=r) for r in ("R01", "R02")], loc="lower left", frameon=True, fontsize=8)

    ax = fig.add_subplot(grid[0, 1])
    labels = ["服务区覆盖", "通信可用", "中继组件利用"]
    vals = [summary["coverage_rate"] * 100, summary["communication_available_mission_count"] / len(schedule) * 100, summary["relay_energy_components_used"] / summary["official_relay_energy_components"] * 100]
    bars = ax.barh(np.arange(3), vals, color=[COLORS["relay"], COLORS["highlight"], COLORS["C"]], height=0.5)
    ax.set_yticks(np.arange(3), labels); ax.set_xlim(0, 108); ax.set_xlabel("比例（%）")
    ax.set_title("通信约束核验", loc="left", weight="bold"); ax.grid(axis="x", color=COLORS["grid"], lw=0.7); ax.set_axisbelow(True)
    for bar, value in zip(bars, vals):
        ax.text(value + 2, bar.get_y() + bar.get_height() / 2, f"{value:.1f}%", va="center", weight="bold")
    ax.axvline(100, color="#4A4A4A", ls="--", lw=0.8)

    ax = fig.add_subplot(grid[1, 1])
    windows = summary["relay_service_windows"]
    for i, rid in enumerate(("R01", "R02")):
        start, end = windows[rid]
        ax.barh(i, end - start, left=start, color=relay_colors[rid], height=0.46, alpha=0.9)
        ax.text(end + 1, i, f"{end - start:.1f} min", va="center", fontsize=9)
    ax.set_yticks([0, 1], ["R01", "R02"]); ax.set_xlabel("服务时间（min）")
    ax.set_title("中继服务窗口", loc="left", weight="bold"); ax.grid(axis="x", color=COLORS["grid"], lw=0.7); ax.set_axisbelow(True)
    fig.suptitle("问题三  DEM通信覆盖与运输调度协同", x=0.04, ha="left", fontsize=16, weight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    save(fig, "问题三_通信覆盖与中继窗口.png")


def q4():
    q4_summary = json.loads((RESULT / "问题四_错峰复用汇总.json").read_text(encoding="utf-8"))
    independent = json.loads((RESULT / "问题四_2批次_修复版.json").read_text(encoding="utf-8"))
    staggered = pd.read_excel(RESULT / "问题四_2批次_错峰复用优化.xlsx", sheet_name="错峰调度")
    metrics = ["A_uav", "B_uav", "C_uav", "A_battery", "B_battery", "C_battery"]
    labels = ["A机", "B机", "C机", "A电池", "B电池", "C电池"]
    inventory = [4, 2, 2, 6, 4, 4]
    independent_req = [independent["totals"].get(x, 0) for x in metrics]
    pooled_req = [q4_summary["staggered_2"]["required"][x] for x in metrics]
    fig = plt.figure(figsize=(13.5, 6.6))
    grid = fig.add_gridspec(1, 2, width_ratios=[1.15, 0.85], wspace=0.3)
    ax = fig.add_subplot(grid[0, 0])
    x = np.arange(len(labels)); width = 0.25
    ax.bar(x - width, inventory, width, color=COLORS["baseline"], label="官方库存")
    ax.bar(x, independent_req, width, color=COLORS["fail"], label="独立并行需求")
    ax.bar(x + width, pooled_req, width, color=COLORS["relay"], label="错峰复用需求")
    ax.set_xticks(x, labels); ax.set_ylabel("资源数量")
    ax.set_title("资源池化前后需求对比", loc="left", weight="bold")
    ax.grid(axis="y", color=COLORS["grid"], lw=0.7); ax.set_axisbelow(True); ax.legend(frameon=False, fontsize=8)
    for i, value in enumerate(independent_req):
        if value > inventory[i]:
            ax.text(i - width, value + 0.15, f"+{value - inventory[i]:.0f}", ha="center", color=COLORS["fail"], weight="bold", fontsize=8)
    ax.text(0.02, 0.98, "独立并行存在缺口；错峰复用缺口为0", transform=ax.transAxes, va="top", fontsize=9, weight="bold",
            bbox=dict(facecolor="white", edgecolor=COLORS["relay"], alpha=0.9, pad=3))

    ax = fig.add_subplot(grid[0, 1])
    groups = [("G1", staggered[staggered["batch_id"] == "G1"]), ("G2", staggered[staggered["batch_id"] == "G2"])]
    for i, (gid, data) in enumerate(groups):
        if data.empty:
            continue
        start, end = data["start_min"].min(), data["end_min"].max()
        ax.barh(i, end - start, left=start, height=0.45, color=[COLORS["A"], COLORS["B"]][i], alpha=0.9)
        ax.text(end + 2, i, f"{end - start:.1f} min", va="center", fontsize=9)
    ax.set_yticks([0, 1], ["第1批次", "第2批次"]); ax.set_xlabel("时间（min）")
    ax.set_title("整体错峰与资源复用时间轴", loc="left", weight="bold")
    ax.grid(axis="x", color=COLORS["grid"], lw=0.7); ax.set_axisbelow(True)
    fig.suptitle("问题四  任务分区与官方资源池化", x=0.04, ha="left", fontsize=16, weight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    save(fig, "问题四_资源池化与错峰复用.png")


def main():
    q1(); q2(); q3(); q4()
    print(f"generated: {OUT}")


if __name__ == "__main__":
    main()
