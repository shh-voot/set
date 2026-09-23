import re
t = open(r"D:\claude\华为杯\D题\_work_docx\media\image2.svg", encoding="utf-8", errors="replace").read()
t2 = re.sub(r'xlink:href="data:image/png;base64,[A-Za-z0-9+/=]+"', 'xlink:href="[BASE64]"', t)
for gid in ["patch_3","patch_4","patch_5","patch_6","LineCollection_1","LineCollection_2","patch_7","PathCollection_1","PathCollection_2"]:
    i = t2.find('id="%s"' % gid)
    if i < 0: continue
    seg = t2[i-20:i+900]
    print("###", gid)
    print(seg[:900].replace("\n"," "))
    print()
