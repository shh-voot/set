import pandas as pd, numpy as np
root = r"D:\claude\华为杯\D题\数据"
p = root + r"\无人机应急物资运输基础数据\物资需求与配送时限.xlsx"
d = pd.read_excel(p, sheet_name=None)
agg = d["数据"]; box = d["逐箱货箱清单"]
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 100)
print("=== 服务区 x 物资类型 明细 ===")
print(agg.to_string())
print()
print("=== 检查1: 首批必须箱数>0 但首批截止时间为空 ===")
m = agg[(agg["首批必须送达箱数"]>0) & (agg["首批截止时间（s）"].isna())]
print(m if len(m) else "none")
print()
print("=== 检查2: 首批必须箱数==0 但有首批截止时间 ===")
m = agg[(agg["首批必须送达箱数"]==0) & (agg["首批截止时间（s）"].notna())]
print(m if len(m) else "none")
print()
print("=== 检查3: 首批截止时间 vs 该行期望送达时间 ===")
m = agg[agg["首批截止时间（s）"].notna() & (agg["首批截止时间（s）"]!=agg["期望送达时间（s）"])]
print(m if len(m) else "none")
print()
print("=== 检查4: 顺序性 期望时间 医疗<=饮用水<=应急食品<=生活卫生 ===")
order = ["医疗物资","饮用水","应急食品","生活卫生用品"]
bad=[]
for s,g in agg.groupby("服务区编号"):
    vals = {t: (int(g[g["物资类型"]==t]["期望送达时间（s）"].iloc[0]) if (g["物资类型"]==t).any() else None) for t in order}
    prev=-1; 
    for t in order:
        if vals[t] is None: continue
        if vals[t] < prev: bad.append((s,t,prev,vals[t]))
        prev=vals[t]
print(bad if bad else "none")
print()
print("=== 检查5: 逐箱清单 首批标记 vs 汇总 ===")
g1 = box[box["是否首批保障"]=="是"].groupby(["服务区编号","物资类型"]).size()
g2 = agg.set_index(["服务区编号","物资类型"])["首批必须送达箱数"]
diff = (g1.reindex(g2.index).fillna(0).astype(int) - g2).abs()
print("不一致:", diff[diff>0].to_dict() if (diff>0).any() else "none")
print()
print("=== 检查6: 逐箱清单中 首批箱的 首批截止时间/期望时间 vs 汇总 ===")
fb = box[box["是否首批保障"]=="是"]
print(fb.groupby(["服务区编号","物资类型"]).agg(首批截止=("首批截止时间（s）","first"), 期望=("期望送达时间（s）","first")).to_string())
print()
print("=== 检查7: 非首批箱是否带首批截止时间 ===")
print("非首批中含首批截止时间的行数:", int(box[box["是否首批保障"]!="是"]["首批截止时间（s）"].notna().sum()))
print()
print("=== 检查8: 各服务区订单数/人口/优先系数 ===")
nodes = pd.read_excel(root + r"\无人机应急物资运输基础数据\调度中心与服务区.xlsx", header=None)
rows=[]
for _,r in nodes.iterrows():
    a=r[0]
    if isinstance(a,str) and (a=="O01" or (len(a)==4 and a[0]=="S" and a[1:].isdigit())):
        rows.append((a, r[5]))
pop = pd.DataFrame(rows[1:], columns=["sid","pop"])
cnt = box.groupby("服务区编号").size().rename("箱数").reset_index()
tot = box.groupby("服务区编号")["单箱质量（kg）"].sum().rename("总质量").reset_index()
vol = box.groupby("服务区编号")["单箱体积（m³）"].sum().rename("总体积").reset_index()
mm = pop.merge(cnt, left_on="sid", right_on="服务区编号").merge(tot, left_on="sid", right_on="服务区编号").merge(vol, left_on="sid", right_on="服务区编号")
print(mm[["sid","pop","箱数","总质量","总体积"]].to_string(index=False))
print("合计:", int(mm["pop"].sum()), int(mm["箱数"].sum()), float(mm["总质量"].sum()), round(float(mm["总体积"].sum()),3))
print()
print("=== 检查9: 单箱质量/体积 与 物资类型 是否一一对应 ===")
print(box.groupby("物资类型")[["单箱质量（kg）","单箱体积（m³）"]].agg(["nunique","unique"]).to_string())
print()
print("=== 检查10: 逐箱编号是否连续/是否有重复区号 ===")
print(box["货箱编号"].head(20).tolist())
print("编号前缀:", sorted(set(box["货箱编号"].str.split("-").str[0].str[:1])))
