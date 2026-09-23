import re
t = open(r"D:\claude\华为杯\D题\_work_docx\media\image2.svg", encoding="utf-8", errors="replace").read()
t2 = re.sub(r'xlink:href="data:image/png;base64,[A-Za-z0-9+/=]+"', 'xlink:href="[BASE64]"', t)
# find path elements with low stroke-opacity outside tick lines, with long d and stroke white
for m in re.finditer(r'<path[^>]*stroke="#[0-9a-fA-F]{6}"[^>]*stroke-opacity="([\d.]+)"[^>]*d="([^"]{200,})"', t2):
    print("opacity", m.group(1), "d-start:", m.group(2)[:120])
    print()
print("=== all fill-opacity/stroke-opacity values ===")
print(sorted(set(re.findall(r'stroke-opacity="([\d.]+)"', t2))))
print(sorted(set(re.findall(r'fill-opacity="([\d.]+)"', t2))))
print()
print("=== distinct stroke colors ===")
print(sorted(set(re.findall(r'stroke="(#[0-9a-fA-F]{3,6})"', t2))))
