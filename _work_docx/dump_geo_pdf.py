import sys
pdf = r"D:\claude\华为杯\D题\数据\镇龙乡地理空间数据\镇龙乡地理空间数据说明.pdf"
txt = None
for mod in ("pypdf", "PyPDF2", "pdfplumber", "fitz"):
    try:
        if mod == "fitz":
            import fitz
            d = fitz.open(pdf)
            txt = "\n".join(f"--- page {i+1} ---\n" + p.get_text() for i, p in enumerate(d))
        elif mod == "pdfplumber":
            import pdfplumber
            with pdfplumber.open(pdf) as d:
                txt = "\n".join(f"--- page {i+1} ---\n" + (p.extract_text() or "") for i, p in enumerate(d.pages))
        else:
            m = __import__(mod)
            r = m.PdfReader(pdf)
            txt = "\n".join(f"--- page {i+1} ---\n" + (pg.extract_text() or "") for i, pg in enumerate(r.pages))
        print("used:", mod)
        break
    except Exception as e:
        print(mod, "failed:", e)
if txt:
    with open(r"D:\claude\华为杯\D题\_work_docx\geo_pdf_text.txt", "w", encoding="utf-8") as f:
        f.write(txt)
    print(txt[:3000])
