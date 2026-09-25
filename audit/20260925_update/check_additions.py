"""Targeted checks of newly submitted experiments; no original output writes."""
from pathlib import Path
import sys,json,math,importlib.util,hashlib,subprocess
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent;E=HERE/'evidence'
sys.path.insert(0,str(ROOT))
from src.data.data_loader import DataLoader
from src.terrain.dem_loader import DEMLoader
from solve_problem1_18trips import direct_mission
loader=DataLoader(str(ROOT/'数据/无人机应急物资运输基础数据'));loader.load_all()
dem=DEMLoader(str(next((ROOT/'数据').rglob('*DEM.mat'))));dem.load()
types={r['type']:r.to_dict() for _,r in loader.get_uav_types().iterrows()}
areas={r['id']:r.to_dict() for _,r in loader.get_service_areas().iterrows()}
depot=loader.get_depot();cargo=loader.get_cargos().set_index('货箱编号',drop=False)
rows=[]; case_info={}
files={
 'ALNS交付':ROOT/'解题-gpt/问题2优化/结果/问题二_ALNS候选方案.xlsx',
 'Q3复现':HERE/'reproduction/解题-gpt/结果/问题三_运输调度_修复版.xlsx',
}
for case,path in files.items():
    frame=pd.read_excel(path,sheet_name=0)
    ids=[]; late=[]
    for _,r in frame.iterrows():
        boxids=str(r.cargo_ids).split(',');ids+=boxids
        weight=float(cargo.loc[boxids,'单箱质量（kg）'].sum());volume=float(cargo.loc[boxids,'单箱体积（m³）'].sum())
        p=types[r.uav_type]
        m=direct_mission(areas[r.area_id],depot,p,cargo.loc[boxids].to_dict('records'),dem)
        for ident in boxids:
            b=cargo.loc[ident];limits=[]
            if b['是否首批保障']=='是':limits.append(float(b['首批截止时间（s）'])/60)
            if b['物资类型']=='医疗物资':limits.append(float(b['期望送达时间（s）'])/60)
            if limits and r.delivery_min>min(limits)+1e-7:late.append(ident)
        rows.append(dict(case=case,mission_id=int(r.mission_id),area_id=r.area_id,uav_type=r.uav_type,
                         weight_kg=weight,max_weight_kg=p['max_load_kg'],volume_m3=volume,max_volume_m3=p['max_volume_m3'],
                         load_ok=weight<=p['max_load_kg']+1e-9,volume_ok=volume<=p['max_volume_m3']+1e-9,
                         same_code_energy_error=abs(m['energy_kwh']-r.energy_kwh)))
    conflicts={}
    for key in ('uav_id','battery_id'):
        out=[]
        for ident,g in frame.groupby(key):
            g=g.sort_values('start_min');ready=-1
            for _,r in g.iterrows():
                if r.start_min<ready-1e-7:out.append(dict(resource=ident,mission=int(r.mission_id),overlap_min=ready-r.start_min))
                ready=max(ready,r.end_min+(r.charge_min if key=='battery_id' else 0))
        conflicts[key]=out
    case_info[case]=dict(missions=len(frame),cargo_count=len(ids),unique_count=len(set(ids)),
                         missing=sorted(set(cargo.index)-set(ids)),hard_late=late,
                         energy_kwh=float(frame.energy_kwh.sum()),completion_min=float(frame.end_min.max()),conflicts=conflicts)
pd.DataFrame(rows).to_csv(E/'new_candidate_checks.csv',index=False,encoding='utf-8-sig')
# Exercise new functions directly, with original official loader values.
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m
code=ROOT/'解题-gpt/问题2优化claude/代码'
eu=module('audit_new_energy',code/'energy_utils.py')
cp=module('audit_new_cp',code/'cpsat_scheduler.py')
ns=module('audit_new_ns',code/'nsga2_optimizer.py')
broken_energy=[]
for typ,p in types.items():
    a=areas['S003'];boxes=cargo.loc[['S003-MED-01']].to_dict('records')
    bad=eu.direct_mission(a,depot,p,boxes,dem);good=direct_mission(a,depot,p,boxes,dem)
    broken_energy.append(dict(type=typ,official_full_range_m=p['full_range_km']*1000,
                             helper_full_range_m=eu.EnergyModel(p).equivalent_range_m(p['max_load_kg']),
                             helper_dem_max_m=bad['dem_max_ground_m'],existing_dem_max_m=good['dem_max_ground_m'],
                             helper_cruise_alt_m=bad['cruise_altitude_m'],
                             required_service_alt_m=a['altitude']+30,official_cruise_speed=p['cruise_speed_ms']))
# Small synthetic cases isolate truncation, rather than claim a real task result.
testtypes={'A':dict(types['A'],count=1,battery_count=2)}
scheduler=cp.CPSATScheduler(testtypes,cargo,time_limit_sec=5)
single=cp.Mission(1,'synthetic','A',['synthetic'],.01,1.09,1.09,1.0)
r=scheduler.schedule([single])
case_late=dict(synthetic=True,success=r.success,makespan_min=r.makespan_min,missions=r.missions)
pair=[cp.Mission(i,'synthetic','A',[str(i)],.01,1.09,.2,10.0) for i in (1,2)]
r=scheduler.schedule(pair);ordered=sorted(r.missions,key=lambda x:x['start_min'])
case_overlap=dict(synthetic=True,success=r.success,missions=r.missions,
                  actual_uav_overlap_min=ordered[0]['start_min']+1.09-ordered[1]['start_min'])
# Route evaluator expects a leg but calls the complete return-trip function.
obj=object.__new__(ns.NSGAIIOptimizer);obj.types=types;obj.cargo_by_id=cargo
obj.depot=depot;obj.areas=areas;obj.dem=dem;obj.direct_mission_func=direct_mission
ident='S001-MED-01';one=direct_mission(areas['S001'],depot,types['C'],[cargo.loc[ident].to_dict()],dem)
aggregated=obj._calculate_mission_metrics([ident],['S001'],'C')
route_case=dict(cargo_id=ident,type='C',single_return_mission=one,nsga_single_area_route=aggregated)
lb=[]
for a,g in cargo.groupby('服务区编号'):
    lb.append(dict(area=a,weight=float(g['单箱质量（kg）'].sum()),volume=float(g['单箱体积（m³）'].sum()),
                   lower_bound=max(math.ceil(g['单箱质量（kg）'].sum()/80),math.ceil(g['单箱体积（m³）'].sum()/.25))))
pd.DataFrame(lb).to_csv(E/'q1_capacity_lower_bound.csv',index=False,encoding='utf-8-sig')
info=dict(candidates=case_info,claude_energy=broken_energy,cp_truncation_lateness=case_late,
          cp_truncation_overlap=case_overlap,nsga_roundtrip_duplication=route_case,q1_capacity_lower_bound=sum(r['lower_bound'] for r in lb))
# Cell content comparisons, including numeric error magnitude and stale Q3/Q4 chains.
comparisons=[]
for left,right in [
 (HERE/'reproduction/解题-gpt/问题2优化/结果/问题二_ALNS候选方案.xlsx',files['ALNS交付']),
 (HERE/'reproduction/结果/问题二_增强优化版.xlsx',ROOT/'解题-gpt/结果/问题二_增强优化版.xlsx')]:
    a=pd.read_excel(left,sheet_name=None);b=pd.read_excel(right,sheet_name=None)
    tolerance_diffs=[]
    for k,v in a.items():
        try:pd.testing.assert_frame_equal(v,b[k],check_exact=False,rtol=1e-10,atol=1e-8)
        except (AssertionError,KeyError):tolerance_diffs.append(k)
    comparisons.append(dict(reproduced=str(left.relative_to(HERE)),delivered=str(right.relative_to(ROOT)),
                            all_sheets_equal=all(k in b and v.equals(b[k]) for k,v in a.items()),
                            different_sheets=[k for k,v in a.items() if k not in b or not v.equals(b[k])],
                            tolerance_different_sheets=tolerance_diffs))
info['additional_reproduction_comparisons']=comparisons
(E/'additions_summary.json').write_text(json.dumps(info,ensure_ascii=False,indent=2,default=lambda x:x.item()),encoding='utf8')
print(json.dumps({'candidates':case_info,'claude_energy':broken_energy,'cp_late':case_late,
                  'cp_overlap_min':case_overlap['actual_uav_overlap_min'],
                  'single_roundtrip_duration':one['total_time_min'],'nsga_duration':aggregated['duration_min'] if aggregated else None,
                  'capacity_lower_bound':info['q1_capacity_lower_bound'],'comparisons':comparisons},ensure_ascii=False,indent=2))
