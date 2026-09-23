import re
t = open(r"D:\claude\华为杯\D题\_work_docx\problem_full.txt", encoding="utf-8").read()
for kw in ["优先系数","需保障人口","人口","架次","充电","周转","SOC","首批","期望送达","架次周转","准备时间","装载时间","交接时间","下降能耗","爬升能耗","净空","悬停","中继","体积","载质量","返航"]:
    print(f"{kw:8s} count={t.count(kw)}")
print()
print("--- 含'优先'的句子 ---")
for s in re.split(r"[。；\n]", t):
    if "优先" in s: print("  *", s.strip())
print("--- 含'人口'的句子 ---")
for s in re.split(r"[。；\n]", t):
    if "人口" in s: print("  *", s.strip())
print("--- 含'周转'的句子 ---")
for s in re.split(r"[。；\n]", t):
    if "周转" in s: print("  *", s.strip())
print("--- 含'准备时间'的句子 ---")
for s in re.split(r"[。；\n]", t):
    if "准备时间" in s: print("  *", s.strip())
print("--- 含'装载'的句子 ---")
for s in re.split(r"[。；\n]", t):
    if "装载" in s: print("  *", s.strip())
print("--- 含'交接'的句子 ---")
for s in re.split(r"[。；\n]", t):
    if "交接" in s: print("  *", s.strip())
