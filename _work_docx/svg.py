import re
p = r"D:\claude\华为杯\D题\_work_docx\media\image2.svg"
t = open(p, encoding="utf-8", errors="replace").read()
print("svg length:", len(t))
print("has <text>:", t.count("<text"))
print("has <image:", t.count("<image"))
print("first 600:", t[:600].replace("\n"," "))
found = re.findall(r"<text[^>]*>(.*?)</text>", t, re.S)
print("text nodes:", len(found))
for s in found[:60]:
    s2 = re.sub(r"<[^>]+>", "", s).strip()
    if s2: print("   ", s2)
print("...")
import collections
# also look for embedded base64 images
print("base64 blocks:", t.count("base64,"))
for m in re.finditer(r'data:image/(\w+);base64,', t):
    print("  img:", m.group(1))
    break
