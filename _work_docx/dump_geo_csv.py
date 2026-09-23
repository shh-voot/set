import os, glob, csv, io

base = r"D:\claude\华为杯\D题\数据\镇龙乡地理空间数据\镇龙乡及周边地理数据"
out = []
out.append("### directory listing ###")
for root, dirs, files in os.walk(r"D:\claude\华为杯\D题\数据"):
    for fn in files:
        p = os.path.join(root, fn)
        out.append(f"{os.path.relpath(p, r'D:\claude\华为杯\D题\数据')}  ({os.path.getsize(p)} bytes)")

for name in ["村镇点位", "水体（面）", "水系（线）", "道路"]:
    d = os.path.join(base, name)
    for p in glob.glob(os.path.join(d, "*.csv")):
        out.append("")
        out.append("=" * 90)
        out.append("CSV: " + os.path.basename(p))
        out.append("=" * 90)
        with open(p, "r", encoding="utf-8-sig", errors="replace") as f:
            lines = f.read().splitlines()
        out.append(f"total lines: {len(lines)}")
        for ln in lines[:12]:
            out.append("  " + ln[:300])
        if len(lines) > 12:
            out.append("  ...")
            for ln in lines[-3:]:
                out.append("  " + ln[:300])

with open(r"D:\claude\华为杯\D题\_work_docx\geo_csv_dump.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("\n".join(out[:40]))
