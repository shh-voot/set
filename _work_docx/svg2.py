import re
p = r"D:\claude\华为杯\D题\_work_docx\media\image2.svg"
t = open(p, encoding="utf-8", errors="replace").read()
# find clip path definitions and transforms
for pat in [r'<clipPath[^>]*>.{0,300}', r'<g id="axes_1"[^>]*>', r'clip-path="[^"]*"']:
    for m in list(re.finditer(pat, t, re.S))[:6]:
        print(m.group(0)[:300].replace("\n"," "))
        print("--")
# Look for the top-left coordinates of axes
for m in list(re.finditer(r'id="text_\d+"[^>]*>', t))[:5]:
    print("TEXTPATH:", m.group(0)[:200])
# Does the SVG have any text drawn as path? count path elements
print("path count:", t.count("<path"))
print("use count:", t.count("<use"))
print("g id=\"axes_1\" block length:", )
i = t.find('id="axes_1"')
print(t[i:i+2000].replace("\n"," ")[:2000])
