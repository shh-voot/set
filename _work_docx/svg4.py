import re, math
t = open(r"D:\claude\华为杯\D题\_work_docx\media\image2.svg", encoding="utf-8", errors="replace").read()
# find the polygon-like path (long d=)  and identify boundary path
paths = re.findall(r'<path[^>]*d="([^"]+)"[^>]*/?>', t)
print("num paths:", len(paths))
for i, d in enumerate(paths):
    if len(d) > 500:
        print("path", i, "len", len(d), "start:", d[:200])
        print()
# count coordinate pairs in the longest path
best = max(paths, key=len)
print("LONGEST path len:", len(best))
coords = re.findall(r'([-\d.]+)[ ,]([-\d.]+)', best)
print("num coord pairs:", len(coords))
print("first 10:", coords[:10])
print("last 5:", coords[-5:])
xs = [float(a) for a,b in coords]; ys=[float(b) for a,b in coords]
print("x range", min(xs), max(xs), " y range", min(ys), max(ys))
