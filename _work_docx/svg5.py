import re, math
t = open(r"D:\claude\华为杯\D题\_work_docx\media\image2.svg", encoding="utf-8", errors="replace").read()
# find the embedded image and its transform
m = re.search(r'<image id="([^"]+)"[^>]*transform="([^"]*)"[^>]*x="([-\d.]+)" y="([-\d.]+)" width="([\d.]+)" height="([\d.]+)"', t)
print("image:", m.group(1), "transform:", m.group(2), "x", m.group(3), "y", m.group(4), "w", m.group(5), "h", m.group(6))
# All elements in axes_1 before/after image
i = t.find('id="axes_1"')
seg = t[i:i+30000]
print("--- elements after image ---")
for mm in re.finditer(r'<(g|image|path|use)[^>]{0,220}', seg):
    s = mm.group(0)
    if "clip-path" in s and "image" not in s and "d=\"" not in s:
        continue
    print(s[:220].replace("\n"," "))
    print("   ...")
