#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Repeat the official-data sequence search for an auditable seed check."""
from pathlib import Path
import json, sys
sys.stdout.reconfigure(encoding='utf-8')
HERE=Path(__file__).resolve(); PROJECT=HERE.parents[3]; WORK=PROJECT/'解题-gpt'
sys.path.insert(0,str(PROJECT)); sys.path.insert(0,str(WORK/'问题2优化'/'代码'))
from optimize_alns import load_official, workbook_tasks, simulate_sequence, score, alns_sequence
cargo, cargo_by_id, types, areas, depot, dem = load_official()
initial=workbook_tasks(WORK/'结果'/'问题二_增强优化版.xlsx')
bm,bc=simulate_sequence(initial,types,cargo_by_id)
rows=[{'seed':'baseline','iterations':0,'late':score(bm,bc)[0],'tardiness_min':score(bm,bc)[1],
       'completion_min':score(bm,bc)[2],'energy_kwh':score(bm,bc)[3],'missions':score(bm,bc)[4]}]
for seed in (20260925,20260926,20260927):
    best,bm2,bc2,s=alns_sequence(initial,types,cargo_by_id,iterations=40,seed=seed)
    rows.append({'seed':seed,'iterations':40,'late':s[0],'tardiness_min':s[1],
                 'completion_min':s[2],'energy_kwh':s[3],'missions':s[4]})
print(json.dumps(rows,ensure_ascii=False,default=float))
out=WORK/'问题2优化'/'结果'/'多随机种子对照.csv'
import pandas as pd
pd.DataFrame(rows).to_csv(out,index=False,encoding='utf-8-sig')
