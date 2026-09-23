import zipfile, re
from lxml import etree

p = r"D:\claude\华为杯\D题\_work_docx\problem.docx"
z = zipfile.ZipFile(p)
root = etree.fromstring(z.read("word/document.xml"))
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
def q(t, ns=M): return "{%s}%s" % (ns, t)

body = root.find(q("body", W))
i = 0
for pel in body.iter(q("p", W)):
    i += 1
    txt = "".join(t.text or "" for t in pel.iter(q("t", W)))
    oms = list(pel.iter(q("oMath")))
    if oms and not txt.strip():
        print("PARA %d (no plain text)" % i)
    elif oms:
        # print plain text with math markers
        s = []
        def walk(node):
            for c in node:
                ln = etree.QName(c).localname
                if ln == "oMath":
                    s.append("⟦MATH⟧")
                elif ln == "r":
                    for t in c.findall(q("t", W)):
                        s.append(t.text or "")
                else:
                    walk(c)
        walk(pel)
        print("PARA %d: %s" % (i, "".join(s).strip()))
print("total paras:", i)
