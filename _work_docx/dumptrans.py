import pandas as pd
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 60); pd.set_option("display.max_rows", 100)
p = r"D:\claude\华为杯\D题\数据\无人机应急物资运输基础数据\运输无人机数据.xlsx"
d = pd.read_excel(p, sheet_name=None, header=None)
for k, df in d.items():
    print("="*110)
    print("SHEET:", k, df.shape)
    print(df.to_string(max_rows=60))
