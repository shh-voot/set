import re
t = open(r"D:\claude\华为杯\D题\_work_docx\media\image2.svg", encoding="utf-8", errors="replace").read()
i = t.find('id="axes_1"')
j = t.find('</g>', t.find('<image'))
# Walk sequential top-level elements with regex, but skip base64 payload
out=[]
k=i
pat = re.compile(r'<(/?)(g|image|path|use|rect)\b')
# strip base64
t2 = re.sub(r'xlink:href="data:image/png;base64,[A-Za-z0-9+/=]+"', 'xlink:href="[BASE64]"', t)
seg = t2[i:]
# print structure up to 4000 chars after
print(seg[:6000])
