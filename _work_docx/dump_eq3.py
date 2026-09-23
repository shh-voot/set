import zipfile
from lxml import etree

p = r"D:\claude\华为杯\D题\_work_docx\problem.docx"
z = zipfile.ZipFile(p)
root = etree.fromstring(z.read("word/document.xml"))

M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
def q(t, ns=M): return "{%s}%s" % (ns, t)

SKIP = {"rPr", "ctrlPr", "sSubPr", "sSupPr", "sSubSupPr", "fPr", "radPr", "naryPr",
        "dPr", "funcPr", "mPr", "eqArrPr", "accPr", "barPr", "limLowPr", "limUppPr",
        "groupChrPr", "oMathParaPr", "argPr", "boxPr"}

def clean(el):
    tag = etree.QName(el).localname
    if tag in SKIP:
        return None
    new = etree.Element(el.tag)
    for k, v in el.attrib.items():
        new.set(k, v)
    if el.text:
        new.text = el.text
    for c in el:
        r = clean(c)
        if r is not None:
            new.append(r)
    return new

def show(el, indent=0, out=None):
    tag = etree.QName(el).localname
    attrs = {etree.QName(k).localname: v for k, v in el.attrib.items()}
    line = "  " * indent + tag + (f" {attrs}" if attrs else "")
    txt = el.text
    if tag == "t" and txt:
        line += f"  >>> {txt!r}"
    out.append(line)
    for c in el:
        show(c, indent + 1, out)

lines = []
body = root.find(q("body", W))
pi = 0
for pel in body.iter(q("p", W)):
    pi += 1
    txt = "".join(t.text or "" for t in pel.iter(q("t", W)))
    oms = list(pel.iter(q("oMath")))
    if not oms:
        continue
    lines.append("#" * 78)
    lines.append(f"PARA {pi} :: {txt.strip()[:90]!r}")
    for k, om in enumerate(oms, 1):
        cl = clean(om)
        s = []
        show(cl, 0, s)
        lines.append(f"--- math {k}/{len(oms)} ---")
        lines.extend(s)

with open(r"D:\claude\华为杯\D题\_work_docx\eq_with_text.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("paras with math:", pi)
