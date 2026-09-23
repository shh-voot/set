import re, base64, os
p = r"D:\claude\华为杯\D题\_work_docx\media\image2.svg"
t = open(p, encoding="utf-8", errors="replace").read()
m = re.search(r'data:image/(\w+);base64,([A-Za-z0-9+/=]+)', t)
print("format:", m.group(1), "b64 len:", len(m.group(2)))
data = base64.b64decode(m.group(2))
out = r"D:\claude\华为杯\D题\_work_docx\media\fig2_embedded.png"
open(out, "wb").write(data)
print("wrote", out, len(data), "bytes")
from PIL import Image
im = Image.open(out)
print("size:", im.size, im.mode)
