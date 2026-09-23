import os, glob
out = []
root0 = "D:\\claude\\华为杯\\D题\\数据"
for root, dirs, files in os.walk(root0):
    for fn in sorted(files):
        p = os.path.join(root, fn)
        out.append(os.path.relpath(p, root0) + f"  ({os.path.getsize(p)})")
with open(r"D:\claude\华为杯\D题\_work_docx\filelist.txt","w",encoding="utf-8") as f:
    f.write("\n".join(out))
print("ok", len(out))
