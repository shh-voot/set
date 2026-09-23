import zipfile
from lxml import etree

p = r"D:\claude\华为杯\D题\_work_docx\problem.docx"
z = zipfile.ZipFile(p)
root = etree.fromstring(z.read("word/document.xml"))

M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
def q(t, ns=M): return "{%s}%s" % (ns, t)

def serialize(el, indent=0):
    tag = etree.QName(el).localname
    attrs = {etree.QName(k).localname: v for k, v in el.attrib.items()}
    line = "  " * indent + f"<{tag}" + (f" {attrs}" if attrs else "") + ">"
    txt = (el.text or "").strip()
    if txt:
        line += f" TEXT={txt!r}"
    out = [line]
    for c in el:
        out.extend(serialize(c, indent + 1))
    return out

lines = []
body = root.find(q("body", W))
idx = 0
prev_para = ""
for pel in body.iter(q("p", W)):
    # get plain text of paragraph
    txt = "".join(t.text or "" for t in pel.iter(q("t", W)))
    for om in pel.iter(q("oMath")):
        idx += 1
        lines.append("=" * 80)
        lines.append(f"EQ#{idx}  in paragraph: {txt.strip()[:60]!r}")
        lines.append("-" * 80)
        lines.extend(serialize(om))
        lines.append("")

with open(r"D:\claude\华为杯\D题\_work_docx\equations_tree.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("equations:", idx)
