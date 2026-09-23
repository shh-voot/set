import pandas as pd
base = r"D:\claude\华为杯\D题\数据\无人机应急物资运输基础数据\物资需求与配送时限.xlsx"
d = pd.read_excel(base, sheet_name=None)
for k, df in d.items():
    print("SHEET:", k, df.shape)
    print("cols:", df.columns.tolist())
df1 = d["数据"]
agg = df1.groupby("物资类型").agg(
    boxes=("总需求箱数","sum"),
    firstbatch=("首批必须送达箱数","sum"),
    w=("单箱质量（kg）","first"),
    v=("单箱体积（m³）","first"),
    n_serv=("服务区编号","nunique"),
)
agg["tot_w"] = agg["boxes"]*agg["w"]
agg["tot_v"] = agg["boxes"]*agg["v"]
print(agg)
print("TOTAL boxes:", df1["总需求箱数"].sum(), "first:", df1["首批必须送达箱数"].sum())
print("TOTAL weight:", (df1["总需求箱数"]*df1["单箱质量（kg）"]).sum())
print("TOTAL vol:", (df1["总需求箱数"]*df1["单箱体积（m³）"]).sum())
df2 = d["逐箱货箱清单"]
print("per-box rows:", df2.shape, "firstbatch:", (df2["是否首批保障"]=="是").sum())
