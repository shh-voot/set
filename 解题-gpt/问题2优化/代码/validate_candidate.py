#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Independent audit of the ALNS candidate against official inputs."""
from pathlib import Path
import json, sys
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd
HERE=Path(__file__).resolve(); PROJECT=HERE.parents[3]; WORK=PROJECT/'解题-gpt'
sys.path.insert(0,str(PROJECT)); sys.path.insert(0,str(WORK/'问题2优化'/'代码'))
from optimize_alns import load_official, workbook_tasks, simulate_sequence, score
from solve_problem1_18trips import direct_mission
cargo,cargo_by_id,types,areas,depot,dem=load_official()
path=WORK/'问题2优化'/'结果'/'问题二_ALNS候选方案.xlsx'
df=pd.read_excel(path,sheet_name='架次调度')
tasks=workbook_tasks(path)
physical=[]
for r,t in zip(df.to_dict('records'),tasks):
    items=[cargo_by_id.loc[c].to_dict() for c in t['cargo_ids']]
    m=direct_mission(areas[t['area_id']],depot,types[t['uav_type']],items,dem)
    physical.append({'mission_id':int(r['mission_id']),
                     'energy_abs_err':abs(float(r['energy_kwh'])-m['energy_kwh']),
                     'duration_abs_err':abs(float(r['duration_min'])-m['total_time_min']),
                     'delivery_offset_abs_err':abs(float(r['delivery_offset_min'])-m['delivery_time_min']),
                     'official_feasible':bool(m['feasible']),
                     'reserve_margin_kwh':float(m['energy_margin_kwh']),
                     'range_margin_km':float(m['range_margin_km'])})
m,c=simulate_sequence(tasks,types,cargo_by_id); s=score(m,c)
ids=[x for t in tasks for x in t['cargo_ids']]
resource=[]
for typ,p in types.items():
    resource.append({'type':typ,'official_uav':int(p['count']),
                     'used_uav':len({r['uav_id'] for r in m if r['uav_type']==typ}),
                     'official_battery':int(p['battery_count']),
                     'used_battery':len({r['battery_id'] for r in m if r['uav_type']==typ})})
report={'official_input_dir':str(PROJECT/'数据'/'无人机应急物资运输基础数据'),
        'candidate_file':str(path),'cargo_count':len(ids),'unique_cargo_count':len(set(ids)),
        'duplicate_cargo_count':len(ids)-len(set(ids)),'score':s,
        'all_cargo_on_time':all(x['on_time'] for x in c),
        'physical_all_feasible':all(x['official_feasible'] for x in physical),
        'max_physical_energy_abs_err':max(x['energy_abs_err'] for x in physical),
        'max_physical_duration_abs_err':max(x['duration_abs_err'] for x in physical),
        'max_physical_delivery_offset_abs_err':max(x['delivery_offset_abs_err'] for x in physical),
        'resource':resource,'physical_checks':physical}
out=WORK/'问题2优化'/'结果'/'候选方案官方约束核验.json'
out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
