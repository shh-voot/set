import zipfile, os
z = zipfile.ZipFile(r"D:\claude\华为杯\D题\_work_docx\problem.docx")
print(z.read("word/_rels/document.xml.rels").decode("utf-8"))
os.makedirs(r"D:\claude\华为杯\D题\_work_docx\media", exist_ok=True)
for n in ["word/media/image1.png","word/media/image2.svg"]:
    open(os.path.join(r"D:\claude\华为杯\D题\_work_docx\media", os.path.basename(n)),"wb").write(z.read(n))
    print("extracted", n)
xml = z.read("word/document.xml").decode("utf-8")
import re
for m in re.finditer(r"<w:drawing>.{0,400}", xml, re.S):
    print("DRAWING:", m.group(0)[:400].replace("\n"," "))
    print("---")
print("rel ids referenced:", set(re.findall(r'r:(?:embed|link)="([^"]+)"', xml)))
