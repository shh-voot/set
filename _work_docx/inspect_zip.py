import zipfile, re, os
p = r"D:\claude\华为杯\D题\_work_docx\problem.docx"
z = zipfile.ZipFile(p)
print("--- entries ---")
for n in z.namelist():
    print(n, z.getinfo(n).file_size)
print("--- document.xml math check ---")
xml = z.read("word/document.xml").decode("utf-8", "ignore")
print("len:", len(xml))
print("oMath count:", xml.count("<m:oMath"))
print("oMathPara count:", xml.count("<m:oMathPara"))
print("drawing count:", xml.count("<w:drawing"))
print("object count:", xml.count("<w:object"))
print("pict count:", xml.count("<w:pict"))
