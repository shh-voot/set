import zipfile
from lxml import etree

p = r"D:\claude\华为杯\D题\_work_docx\problem.docx"
z = zipfile.ZipFile(p)
root = etree.fromstring(z.read("word/document.xml"))
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
def q(t, ns=M): return "{%s}%s" % (ns, t)

body = root.find(q("body", W))
out = []
n = 0
for pel in body.iter(q("p", W)):
    # collect direct-ish m:t in document order for this paragraph
    ts = [t.text or "" for t in pel.iter(q("t", M))]
    if ts:
        n += 1
        out.append("[%03d] %s" % (n, "".join(ts)))
print("\n".join(out))

print("\n=== search for numeric constants ===")
allm = "".join(t.text or "" for t in root.iter(q("t", M)))
for kw in ["3.6", "3600", "1000", "9.8", "0.72", "1.15", "1.05", "0.05", "50", "30", "20", "η", "ρ", "θ"]:
    print(kw, "->", allm.count(kw))
