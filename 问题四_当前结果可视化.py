#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Official-data visualization for Problem 4 independent and staggered plans."""
from pathlib import Path
import json
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).parent
OUT = ROOT / "结果" / "图表"
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

def main():
    rows = []
    for n in (2, 3):
        base = json.loads((ROOT / "结果" / f"问题四_{n}批次_修复版.json").read_text(encoding="utf-8"))
        opt = json.loads((ROOT / "结果" / "问题四_错峰复用汇总.json").read_text(encoding="utf-8"))[f"staggered_{n}"]
        rows.append({"方案": f"{n}批次独立", **{k: base["totals"].get(k, 0) for k in ("A_uav", "B_uav", "C_uav", "A_battery", "B_battery", "C_battery")}, "完成时间": None, "库存可行": False})
        rows.append({"方案": f"{n}批次错峰复用", **{k: opt["required"].get(k, 0) for k in ("A_uav", "B_uav", "C_uav", "A_battery", "B_battery", "C_battery")}, "完成时间": opt["completion_min"], "库存可行": opt["feasible_official_inventory"]})
    df = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(12, 6))
    metrics = ["A_uav", "B_uav", "C_uav", "A_battery", "B_battery", "C_battery"]
    x = np.arange(len(metrics)); width = 0.2
    for i, (_, row) in enumerate(df.iterrows()):
        ax.bar(x + (i - 1.5) * width, [row[m] for m in metrics], width, label=row["方案"])
    inventory = [4, 2, 2, 6, 4, 4]
    ax.plot(x, inventory, "k--", marker="o", label="官方库存")
    ax.set_xticks(x); ax.set_xticklabels(metrics)
    ax.set_ylabel("数量"); ax.set_title("问题四：独立需求与错峰复用需求对比")
    ax.legend(fontsize=9); ax.grid(axis="y", alpha=0.3)
    fig.tight_layout(); fig.savefig(OUT / "问题四_资源需求与官方库存对比.png", dpi=300); plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 5))
    for n, color in ((2, "#3b82f6"), (3, "#ef4444")):
        opt = json.loads((ROOT / "结果" / "问题四_错峰复用汇总.json").read_text(encoding="utf-8"))[f"staggered_{n}"]
        sched = pd.read_excel(ROOT / "结果" / f"问题四_{n}批次_错峰复用优化.xlsx", sheet_name="错峰调度")
        for _, r in sched.iterrows():
            ax.barh(f"{n}批次", r["end_min"] - r["start_min"], left=r["start_min"], color=color, alpha=0.35)
        ax.text(opt["completion_min"], f"{n}批次", f"  {opt['completion_min']:.1f} min", va="center")
    ax.set_xlabel("时间（分钟）"); ax.set_title("问题四：批次错峰复用调度时间轴")
    ax.grid(axis="x", alpha=0.3); fig.tight_layout(); fig.savefig(OUT / "问题四_错峰复用时间轴.png", dpi=300); plt.close(fig)
    print("generated", OUT / "问题四_资源需求与官方库存对比.png", OUT / "问题四_错峰复用时间轴.png")

if __name__ == "__main__":
    main()
