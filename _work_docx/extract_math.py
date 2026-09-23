import zipfile, re
from lxml import etree

p = r"D:\claude\华为杯\D题\_work_docx\problem.docx"
z = zipfile.ZipFile(p)
xml = z.read("word/document.xml")
root = etree.fromstring(xml)

M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

def q(tag, ns=M):
    return "{%s}%s" % (ns, tag)

def omml_to_text(el):
    """Best-effort linearization of OMML."""
    tag = etree.QName(el).localname
    if tag == "t":
        return el.text or ""
    if tag == "r":
        return "".join(omml_to_text(c) for c in el)
    if tag == "sSub":
        base = "".join(omml_to_text(c) for c in el.findall(q("e")))
        sub = "".join(omml_to_text(c) for c in el.findall(q("sub")))
        return f"{base}_{{{sub}}}"
    if tag == "sSup":
        base = "".join(omml_to_text(c) for c in el.findall(q("e")))
        sup = "".join(omml_to_text(c) for c in el.findall(q("sup")))
        return f"{base}^{{{sup}}}"
    if tag == "sSubSup":
        base = "".join(omml_to_text(c) for c in el.findall(q("e")))
        sub = "".join(omml_to_text(c) for c in el.findall(q("sub")))
        sup = "".join(omml_to_text(c) for c in el.findall(q("sup")))
        return f"{base}_{{{sub}}}^{{{sup}}}"
    if tag == "f":
        num = "".join(omml_to_text(c) for c in el.findall(q("num")))
        den = "".join(omml_to_text(c) for c in el.findall(q("den")))
        return f"({num})/({den})"
    if tag == "rad":
        deg = "".join(omml_to_text(c) for c in el.findall(q("deg")))
        e = "".join(omml_to_text(c) for c in el.findall(q("e")))
        return f"sqrt[{deg}]({e})"
    if tag == "d":
        e = "".join(omml_to_text(c) for c in el.findall(q("e")))
        return f"({e})"
    if tag == "nary":
        chr_ = el.find(q("naryPr") + "/" + q("chr"))
        op = chr_.get(q("val")) if chr_ is not None else "∑"
        sub = "".join(omml_to_text(c) for c in el.findall(q("sub")))
        sup = "".join(omml_to_text(c) for c in el.findall(q("sup")))
        e = "".join(omml_to_text(c) for c in el.findall(q("e")))
        return f"{op}_{{{sub}}}^{{{sup}}} [{e}]"
    if tag == "func":
        fname = "".join(omml_to_text(c) for c in el.findall(q("fName")))
        e = "".join(omml_to_text(c) for c in el.findall(q("e")))
        return f"{fname}({e})"
    if tag == "m":
        rows = []
        for mr in el.findall(q("mr")):
            rows.append(" , ".join("".join(omml_to_text(c) for c in mc) for mc in mr.findall(q("e"))))
        return "matrix{" + " ; ".join(rows) + "}"
    if tag == "eqArr":
        rows = ["".join(omml_to_text(c) for c in e) for e in el.findall(q("e"))]
        return " \\\\ ".join(rows)
    if tag == "acc":
        e = "".join(omml_to_text(c) for c in el.findall(q("e")))
        return f"accent({e})"
    if tag == "bar":
        e = "".join(omml_to_text(c) for c in el.findall(q("e")))
        return f"bar({e})"
    if tag == "limLow":
        e = "".join(omml_to_text(c) for c in el.findall(q("e")))
        lim = "".join(omml_to_text(c) for c in el.findall(q("lim")))
        return f"{e}_{{{lim}}}"
    if tag == "limUpp":
        e = "".join(omml_to_text(c) for c in el.findall(q("e")))
        lim = "".join(omml_to_text(c) for c in el.findall(q("lim")))
        return f"{e}^{{{lim}}}"
    if tag == "groupChr":
        e = "".join(omml_to_text(c) for c in el.findall(q("e")))
        return e
    if tag in ("oMath", "oMathPara", "e", "num", "den", "sub", "sup", "lim", "fName", "deg"):
        return "".join(omml_to_text(c) for c in el)
    if tag in ("rPr", "ctrlPr", "sSubPr", "sSupPr", "fPr", "radPr", "naryPr", "dPr",
               "funcPr", "mPr", "eqArrPr", "accPr", "barPr", "limLowPr", "limUppPr",
               "groupChrPr", "oMathParaPr", "mPr", "argPr", "boxPr"):
        return ""
    # default: recurse
    return "".join(omml_to_text(c) for c in el)

def para_text(pel):
    parts = []
    for child in pel.iter():
        pass
    # Walk direct-ish children in document order, handling runs and math
    out = []
    def walk(node):
        for c in node:
            ln = etree.QName(c).localname
            if ln == "oMath":
                out.append(" $" + omml_to_text(c).strip() + "$ ")
            elif ln == "r":
                for t in c.findall(q("t", W)):
                    out.append(t.text or "")
            elif ln in ("hyperlink", "smartTag", "ins", "sdt", "sdtContent", "bookmarkStart", "bookmarkEnd"):
                walk(c)
            elif ln == "drawing":
                out.append("[[IMAGE]]")
            else:
                pass
    walk(pel)
    return "".join(out).strip()

lines = []
body = root.find(q("body", W))
for pel in body.iter(q("p", W)):
    t = para_text(pel)
    if t:
        lines.append(t)

with open(r"D:\claude\华为杯\D题\_work_docx\problem_full.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("lines:", len(lines))
