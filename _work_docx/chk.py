import zipfile
from lxml import etree
p = r"D:\claude\华为杯\D题\_work_docx\problem.docx"
z = zipfile.ZipFile(p)
root = etree.fromstring(z.read("word/document.xml"))
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
mt = "{%s}t" % M
cnt = 0
sample = []
for el in root.iter(mt):
    cnt += 1
    if len(sample) < 30:
        sample.append(repr(el.text))
print("m:t count:", cnt)
print(sample)
