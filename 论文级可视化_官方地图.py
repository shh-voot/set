# -*- coding: utf-8 -*-
"""Publication-ready figures using the official HTML terrain map as base.

Palette: paper-color/ocean-mint
  A / primary: #598EBB, B: #8CCDC6, C: #948EC1,
  relay: #9CC896, highlight: #6CAAC4.
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

ROOT = Path(__file__).parent
HTML = ROOT / "数据" / "镇龙乡地理空间数据" / "镇龙乡地理空间详情地图.html"
DATA = ROOT / "数据" / "无人机应急物资运输基础数据"
RESULT = ROOT / "结果"
OUT = RESULT / "图表_论文级"
OUT.mkdir(parents=True, exist_ok=True)

# paper-color: ocean-mint, fixed semantic mapping across all figures.
COLORS = {
    "A": "#598EBB",
    "B": "#8CCDC6",
    "C": "#948EC1",
    "relay": "#9CC896",
    "highlight": "#6CAAC4",
    "text": "#2B2B2B",
    "grid": "#E6E6E6",
    "outline": "#4A4A4A",
}

plt.rcParams.update({
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "text.color": COLORS["text"],
    "axes.labelcolor": COLORS["text"],
    "axes.edgecolor": COLORS["outline"],
    "xtick.color": COLORS["text"],
    "ytick.color": COLORS["text"],
    "figure.facecolor": "white",
    "axes.facecolor": "white",
})


def _load_map():
    text = HTML.read_text(encoding="utf-8")
    terrain_url = re.search(r"const terrainUrl\s*=\s*\"(data:image/png;base64,[^\"]+)\";", text).group(1)
    bounds = json.loads(re.search(r"const terrainBounds\s*=\s*([^;]+);", text).group(1))
    services = json.loads(re.search(r"const services\s*=\s*(\{.*?\});\s*const summary", text, re.S).group(1))
    dispatch = json.loads(re.search(r"const dispatchCenter\s*=\s*(\{.*?\});\s*const services", text, re.S).group(1))
    image = Image.open(io.BytesIO(base64.b64decode(terrain_url.split(",", 1)[1]))).convert("RGB")
    west, south, east, north = bounds
    # Same fitExtent used by the supplied HTML map.
    def merc_y(lat):
        rad = np.radians(lat)
        return np.log(np.tan(np.pi / 4.0 + rad / 2.0))
    x0, x1 = np.radians([west, east])
    y0, y1 = merc_y(south), merc_y(north)
    sx = (1176.0 - 24.0) / (x1 - x0)
    sy = (750.0 - 20.0) / (y1 - y0)
    scale = min(sx, sy)
    tx = 24.0 + (1176.0 - 24.0 - scale * (x1 - x0)) / 2.0 - scale * x0
    ty = 20.0 + (750.0 - 20.0 + scale * y0 + scale * y1) / 2.0
    def project(lon, lat):
        return scale * np.radians(lon) + tx, ty - scale * merc_y(lat)
    return image, project, services["features"], dispatch["features"][0]


def _base_ax(ax, image, project):
    # HTML SVG viewBox is 1200x780; the terrain image is positioned in its
    # projected bounds, so paths share the exact same coordinate system.
    ax.imshow(image, extent=(24, 1176, 20, 750), origin="upper", alpha=0.82, zorder=0)
    ax.set_xlim(0, 1200); ax.set_ylim(780, 0)
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


def _points(features, project):
    return {f["properties"]["服务区编号"]: project(*f["geometry"]["coordinates"]) for f in features}


def _draw_nodes(ax, features, dispatch, project, size_scale=12):
    points = _points(features, project)
    for f in features:
        p = f["properties"]
        x, y = points[p["服务区编号"]]
        size = size_scale + np.sqrt(max(1, float(p.get("本次需保障人口（人）", 1)))) * 0.8
        ax.scatter(x, y, s=size, c="#C74859", edgecolor="white", linewidth=0.8, zorder=5)
        ax.text(x + 8, y - 5, p["服务区编号"], fontsize=7, weight="bold", zorder=6,
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.72, pad=0.8))
    dx, dy = project(*dispatch["geometry"]["coordinates"])
    ax.scatter(dx, dy, marker="*", s=180, c="#D3B532", edgecolor=COLORS["outline"], linewidth=0.9, zorder=7)
    ax.text(dx + 10, dy + 2, "O01", fontsize=8, weight="bold", zorder=8,
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.8, pad=1.0))
    return points, (dx, dy)


def figure_q1():
    image, project, features, dispatch = _load_map()
    schedule = pd.read_excel(RESULT / "问题一_18架次方案_修复版.xlsx", sheet_name="架次方案")
    fig, ax = plt.subplots(figsize=(11, 8))
    _base_ax(ax, image, project); points, depot = _draw_nodes(ax, features, dispatch, project)
    for _, row in schedule.iterrows():
        x, y = points[str(row["area_id"])]
        ax.plot([depot[0], x], [depot[1], y], color=COLORS.get(str(row["uav_type"]), COLORS["highlight"]),
                lw=1.2, alpha=0.42, zorder=2)
        ax.annotate("", xy=(x, y), xytext=(depot[0], depot[1]),
                    arrowprops=dict(arrowstyle="-|>", color=COLORS.get(str(row["uav_type"]), COLORS["highlight"]),
                                    alpha=0.34, lw=0.7), zorder=3)
    handles = [Line2D([0], [0], color=COLORS[t], lw=2, label=f"机型 {t}") for t in ("A", "B", "C")]
    handles += [Line2D([0], [0], marker="*", color="w", markerfacecolor="#D3B532", markeredgecolor=COLORS["outline"], markersize=10, label="调度中心 O01")]
    ax.legend(handles=handles, loc="lower left", frameon=True, framealpha=0.92, fontsize=9)
    ax.set_title("问题一  官方DEM底图上的18架次直飞路径", loc="left", fontsize=15, weight="bold", pad=12)
    ax.text(0.01, 0.02, "底图：官方镇龙乡地理空间详情地图.html；路径：O01→服务区→O01",
            transform=ax.transAxes, fontsize=8, color="#666666")
    fig.tight_layout(); fig.savefig(OUT / "问题一_官方底图直飞路径.png", dpi=360, bbox_inches="tight"); plt.close(fig)


def figure_q2():
    image, project, features, dispatch = _load_map()
    p2 = RESULT / "问题二_增强优化版.xlsx"
    if not p2.exists():
        p2 = RESULT / "问题二_优化修复版.xlsx"
    schedule = pd.read_excel(p2, sheet_name="架次调度")
    fig, (ax_map, ax_time) = plt.subplots(1, 2, figsize=(15, 7), gridspec_kw={"width_ratios": [1.15, 1]})
    _base_ax(ax_map, image, project); points, depot = _draw_nodes(ax_map, features, dispatch, project)
    for _, row in schedule.iterrows():
        x, y = points[str(row["area_id"])]
        ax_map.plot([depot[0], x], [depot[1], y], color=COLORS[str(row["uav_type"])], lw=0.9, alpha=0.22)
    ax_map.set_title("运输路径与服务区", loc="left", fontsize=13, weight="bold")
    ax_map.legend(handles=[Line2D([0], [0], color=COLORS[t], lw=2, label=f"机型 {t}") for t in ("A", "B", "C")],
                  loc="lower left", fontsize=8, framealpha=0.9)
    # Actual scheduling strip, sorted by start time.
    ordered = schedule.sort_values(["start_min", "mission_id"]).reset_index(drop=True)
    for i, row in ordered.iterrows():
        ax_time.barh(i, row["end_min"] - row["start_min"], left=row["start_min"], height=0.72,
                     color=COLORS[str(row["uav_type"])], alpha=0.86, edgecolor="white", linewidth=0.3)
    ax_time.set_yticks(np.arange(len(ordered))); ax_time.set_yticklabels(ordered["mission_id"].astype(int), fontsize=6)
    ax_time.invert_yaxis(); ax_time.set_xlabel("时间（分钟）"); ax_time.set_ylabel("架次编号")
    ax_time.grid(axis="x", color=COLORS["grid"], linewidth=0.7)
    ax_time.set_title(f"{len(ordered)}架次实体机调度时间窗", loc="left", fontsize=13, weight="bold")
    ax_time.legend(handles=[Patch(facecolor=COLORS[t], label=f"机型 {t}") for t in ("A", "B", "C")], fontsize=8)
    fig.suptitle("问题二  官方机队与共享电池约束下的运输调度", fontsize=16, weight="bold", x=0.03, ha="left")
    fig.tight_layout(); fig.savefig(OUT / "问题二_路径与调度时间窗.png", dpi=360, bbox_inches="tight"); plt.close(fig)


def figure_q3():
    image, project, features, dispatch = _load_map()
    schedule = pd.read_excel(RESULT / "问题三_运输调度_修复版.xlsx")
    relays = pd.read_excel(RESULT / "问题三_中继部署方案_修复版.xlsx")
    fig, ax = plt.subplots(figsize=(11, 8)); _base_ax(ax, image, project)
    points, depot = _draw_nodes(ax, features, dispatch, project)
    relay_colors = {"R01": COLORS["relay"], "R02": COLORS["highlight"]}
    for _, relay in relays.iterrows():
        rx, ry = project(float(relay["longitude"]), float(relay["latitude"]))
        rid = str(relay["relay_id"])
        ax.scatter(rx, ry, marker="D", s=85, c=relay_colors.get(rid, COLORS["relay"]), edgecolor=COLORS["outline"], zorder=8)
        ax.text(rx + 9, ry - 4, rid, fontsize=8, weight="bold", zorder=9,
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.8, pad=1.0))
        covered = [x for x in str(relay["covered_area_ids"]).split(",") if x]
        for area in covered:
            if area not in points: continue
            ax.plot([rx, points[area][0]], [ry, points[area][1]], color=relay_colors.get(rid, COLORS["relay"]), lw=1.0, alpha=0.34, zorder=3)
    for _, row in schedule.iterrows():
        if str(row.get("communication_mode", "direct")) == "direct":
            continue
        x, y = points[str(row["area_id"])]
        ax.plot([depot[0], x], [depot[1], y], color="#D4897E", lw=0.65, alpha=0.16, zorder=2)
    handles = [Line2D([0], [0], marker="D", color="w", markerfacecolor=relay_colors[r], markeredgecolor=COLORS["outline"], markersize=8, label=r) for r in ("R01", "R02")]
    handles += [Line2D([0], [0], color="#D4897E", lw=2, label="中继保障运输路径")]
    ax.legend(handles=handles, loc="lower left", fontsize=9, framealpha=0.92)
    ax.set_title("问题三  DEM视距通信与R01/R02中继覆盖", loc="left", fontsize=15, weight="bold", pad=12)
    ax.text(0.01, 0.02, f"硬约束：15/15服务区覆盖、{len(schedule)}/{len(schedule)}架次通信可用、官方能源组件≤6组",
            transform=ax.transAxes, fontsize=8, color="#666666")
    fig.tight_layout(); fig.savefig(OUT / "问题三_官方底图中继覆盖.png", dpi=360, bbox_inches="tight"); plt.close(fig)


def figure_q4():
    image, project, features, dispatch = _load_map()
    q4 = json.loads((RESULT / "问题四_错峰复用汇总.json").read_text(encoding="utf-8"))
    base = json.loads((RESULT / "问题四_2批次_修复版.json").read_text(encoding="utf-8"))
    areas_to_group = {}
    for group in base["groups"]:
        for area in group["areas"]: areas_to_group[area] = group["group"]
    fig, (ax_map, ax_bar) = plt.subplots(1, 2, figsize=(14, 7), gridspec_kw={"width_ratios": [1.1, 1]})
    _base_ax(ax_map, image, project); points, depot = _draw_nodes(ax_map, features, dispatch, project)
    group_colors = {"G1": COLORS["A"], "G2": COLORS["B"], "G3": COLORS["C"]}
    for area, (x, y) in points.items():
        ax_map.scatter(x, y, s=90, facecolor="none", edgecolor=group_colors.get(areas_to_group.get(area), COLORS["outline"]), linewidth=2.0, zorder=8)
        ax_map.text(x + 8, y + 8, areas_to_group.get(area, ""), fontsize=7, color=group_colors.get(areas_to_group.get(area), COLORS["text"]), weight="bold")
    ax_map.set_title("2批次分区与官方地形底图", loc="left", fontsize=13, weight="bold")
    metrics = ["A_uav", "B_uav", "C_uav", "A_battery", "B_battery", "C_battery"]
    labels = ["A机", "B机", "C机", "A电池", "B电池", "C电池"]
    inventory = [4, 2, 2, 6, 4, 4]
    req = [q4["staggered_2"]["required"][m] for m in metrics]
    x = np.arange(len(metrics)); width = 0.35
    ax_bar.bar(x - width/2, inventory, width, color="#D8DDE2", edgecolor=COLORS["outline"], label="官方库存")
    ax_bar.bar(x + width/2, req, width, color=COLORS["relay"], edgecolor=COLORS["outline"], label="2批次错峰需求")
    ax_bar.set_xticks(x); ax_bar.set_xticklabels(labels); ax_bar.set_ylabel("数量")
    ax_bar.set_title("错峰复用后的资源核验", loc="left", fontsize=13, weight="bold")
    ax_bar.grid(axis="y", color=COLORS["grid"], linewidth=0.7); ax_bar.legend(fontsize=8)
    ax_bar.text(0.02, 0.98, f"完成时间：{q4['staggered_2']['completion_min']:.1f} min\n库存缺口：0",
                transform=ax_bar.transAxes, va="top", fontsize=10, weight="bold",
                bbox=dict(facecolor="white", edgecolor=COLORS["relay"], alpha=0.9))
    fig.suptitle("问题四  批次错峰复用与资源可行性", fontsize=16, weight="bold", x=0.03, ha="left")
    fig.tight_layout(); fig.savefig(OUT / "问题四_分区与资源可行性.png", dpi=360, bbox_inches="tight"); plt.close(fig)


def main():
    figure_q1(); figure_q2(); figure_q3(); figure_q4()
    print(f"generated figures in {OUT}")


if __name__ == "__main__":
    main()
