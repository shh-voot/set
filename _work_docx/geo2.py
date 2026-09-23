import os, glob
base = r"D:\claude\华为杯\D题\数据\镇龙乡地理空间数据\镇龙乡及周边地理数据"
out = []
for name in ["村镇点位","水体（面）","水系（线）","道路"]:
    for p in sorted(glob.glob(os.path.join(base, name, "*.csv"))):
        out.append("="*90)
        out.append("CSV: " + os.path.basename(p))
        out.append("="*90)
        with open(p, "r", encoding="utf-8-sig", errors="replace") as f:
            lines = f.read().splitlines()
        out.append(f"total lines: {len(lines)}")
        for ln in lines[:10]:
            out.append("  " + ln[:250])
        out.append("  ...")
        for ln in lines[-2:]:
            out.append("  " + ln[:250])
with open(r"D:\claude\华为杯\D题\_work_docx\geo_csv_dump.txt","w",encoding="utf-8") as f:
    f.write("\n".join(out))
print("ok")
