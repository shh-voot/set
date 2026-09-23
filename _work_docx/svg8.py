import re
t = open(r"D:\claude\华为杯\D题\_work_docx\media\image2.svg", encoding="utf-8", errors="replace").read()
t2 = re.sub(r'xlink:href="data:image/png;base64,[A-Za-z0-9+/=]+"', 'xlink:href="[BASE64]"', t)
for m in re.finditer(r'<path[^>]*stroke="#d8dde2"[^>]*d="([^"]+)"', t2):
    d = m.group(1)
    print("d8dde2 path, len", len(d))
    print(d[:1500])
    print("...")
    print(d[-400:])
    print("="*100)
