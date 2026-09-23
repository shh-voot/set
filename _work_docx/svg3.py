import re
t = open(r"D:\claude\华为杯\D题\_work_docx\media\image2.svg", encoding="utf-8", errors="replace").read()
# find text_ definitions (matplotlib svg uses <defs><path id="..."/></defs> + <use xlink:href="#...">)
ids = re.findall(r'<path id="([^"]+)"', t)
print("defs path ids:", len(ids), ids[:10])
# gather <use> with href
uses = re.findall(r'<use[^>]*xlink:href="#([^"]+)"[^>]*>', t)
print("uses:", len(uses), uses[:20])
# check any gid prefixes
print("g ids:", re.findall(r'<g id="([^"]+)"', t)[:30])
# look for 'DejaVu' font hints
print("font hints:", set(re.findall(r'font-family="([^"]+)"', t)))
print("style blocks:", len(re.findall(r'<style', t)))
# Try to see if there is any transform like rotate for ylab
print("ylab-ish transform:", re.findall(r'transform="[^"]*rotate[^"]*"', t)[:5])
