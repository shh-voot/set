import pandas as pd, numpy as np
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 50)

base = r"D:\claude\华为杯\D题\数据\无人机应急物资运输基础数据"
d = pd.read_excel(base + r"\物资需求与配送时限.xlsx", sheet_name=None)
agg = d["数据"]; box = d["逐箱货箱清单"]

# --- cross-check the two sheets box by box ---
print("### 1. 两表一致性 ###")
rows = []
for (s, t), g in agg.groupby(["服务区编号","物资类型"]):
    n_agg = int(g["总需求箱数"].iloc[0]); nb = int(g["首批必须送达箱数"].iloc[0])
    sub = box[(box["服务区编号"]==s) & (box["物资类型"]==t)]
    rows.append((s, t, n_agg, len(sub), nb, int((sub["是否首批保障"]=="是").sum()),
                 g["单箱质量（kg）"].iloc[0], sub["单箱质量（kg）"].iloc[0] if len(sub) else None,
                 g["单箱体积（m³）"].iloc[0], sub["单箱体积（m³）"].iloc[0] if len(sub) else None,
                 g["应急优先系数"].iloc[0], sub["应急优先系数"].iloc[0] if len(sub) else None))
chk = pd.DataFrame(rows, columns=["服务区","物资","汇总箱数","逐箱条数","汇总首批","逐箱首批","汇总单重","逐箱单重","汇总单积","逐箱单积","汇总优先","逐箱优先"])
bad = chk[(chk["汇总箱数"]!=chk["逐箱条数"]) | (chk["汇总首批"]!=chk["逐箱首批"]) |
          (chk["汇总单重"]!=chk["逐箱单重"]) | (chk["汇总单积"]!=chk["逐箱单积"]) | (chk["汇总优先"]!=chk["逐箱优先"])]
print("不一致行数:", len(bad)); print(bad)

print("\n### 2. 首批截止 / 期望时间 唯一性 ###")
for t, g in agg.groupby("物资类型"):
    print(t, "首批截止值:", sorted(set(g["首批截止时间（s）"].dropna().astype(int))), "期望值:", sorted(set(g["期望送达时间（s）"].dropna().astype(int))))

print("\n### 3. 优先系数 vs 期望时间 映射 ###")
m = agg.groupby(["物资类型","应急优先系数"])["期望送达时间（s）"].agg(["unique","count"])
print(m)
print("\n### 4. 每个服务区首批截止是否等于该区最早的期望时间 ###")
base_t = agg.dropna(subset=["首批截止时间（s）"])
for s, g in base_t.groupby("服务区编号"):
    e = int(g["首批截止时间（s）"].iloc[0])
    exp = agg[agg["服务区编号"]==s]["期望送达时间（s）"].astype(int).min()
    if e != exp: print(" 差异:", s, "首批截止=", e, " 该区最早期望=", exp)

print("\n### 5. 货箱清单排序/编号检查 ###")
print("编号唯一:", box["货箱编号"].is_unique, " 条数:", len(box))
import collections
pref = box["货箱编号"].str.split("-").str[1]
print(pref.value_counts().to_dict())
print("每区货箱数:"); print(box.groupby("服务区编号").size().to_string())
