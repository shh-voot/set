"""Additional targeted checks for observed risks, not new optimizations."""
from pathlib import Path
import json,math,sys
import numpy as np
import pandas as pd
from scipy.io import loadmat

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent/'evidence'
sys.path.insert(0,str(ROOT))
from src.data.data_loader import DataLoader
from src.terrain.dem_loader import DEMLoader
from src.communication.los_model import Position,LOSCommunicationModel,CommParams
from solve_problem3_relay import _bidirectional,_param
from solve_problem1_18trips import direct_mission

loader=DataLoader(str(ROOT/'数据/无人机应急物资运输基础数据'));loader.load_all()
path=next((ROOT/'数据').rglob('*DEM.mat')); dem=DEMLoader(str(path));dem.load()
mat=loadmat(path); data=mat['dem']; tr=mat['transform'].ravel()
depot=loader.get_depot(); areas={r['id']:r.to_dict() for _,r in loader.get_service_areas().iterrows()}
relays=pd.read_excel(ROOT/'解题-gpt/结果/问题三_中继部署方案_修复版.xlsx')
comm=loader.get_comm_params()
params={'frequency_mhz':float(comm['f']),'system_loss_db':float(comm['Lsys']),
    'obstacle_loss_db':float(comm['Lobs']),'sensitivity_dbm':float(comm['Psens']),'margin_db':float(comm['M'])}
los=LOSCommunicationModel(dem.dem_data,dem.dem_bounds,CommParams(max_range_m=float('inf'),safety_margin_m=0))
gateway=Position(depot['longitude'],depot['latitude'],depot['altitude']+20)

def hav(p1,p2):
    la1,la2=np.radians([p1.y,p2.y]);dl=np.radians(p2.x-p1.x);dt=la2-la1
    return float(6371000*2*np.arcsin(np.sqrt(np.sin(dt/2)**2+np.cos(la1)*np.cos(la2)*np.sin(dl/2)**2)))

def centered_bilinear(p1,p2):
    n=max(2,math.ceil(hav(p1,p2)/1)+1)
    tt=np.linspace(0,1,n)
    xx=p1.x+(p2.x-p1.x)*tt;yy=p1.y+(p2.y-p1.y)*tt
    cc=(xx-tr[2])/tr[0]-.5;rr=(yy-tr[5])/tr[4]-.5
    ci=np.floor(cc).astype(int);ri=np.floor(rr).astype(int)
    cf=cc-ci;rf=rr-ri
    h=(data[ri,ci]*(1-cf)+data[ri,ci+1]*cf)*(1-rf)+(data[ri+1,ci]*(1-cf)+data[ri+1,ci+1]*cf)*rf
    z=p1.z+(p2.z-p1.z)*tt
    return bool((h>z+1e-8).any()),float((h-z).max())

def own_link(p1,p2,pt1,g1,pt2,g2):
    blocked,penetration=centered_bilinear(p1,p2)
    dist=math.hypot(hav(p1,p2),p1.z-p2.z)
    fspl=32.45+20*math.log10(2400)+20*math.log10(max(1,dist)/1000)
    margin=min(pt1,pt2)+g1+g2-3-fspl-10*blocked+90
    return margin,penetration

rows=[]
for area,a in areas.items():
    p=Position(a['longitude'],a['latitude'],a['altitude']+30)
    mg,penetration=own_link(p,gateway,20,3,27,12)
    row={'area_id':area,'required_altitude_m':p.z,'bilinear_direct_margin_db':mg,
         'direct_terrain_penetration_m':penetration}
    old=_bidirectional(gateway,p,27,12,12,20,3,3,params,los)
    row['old_dem_direct_ok_at_30m']=old[0]
    for _,r in relays.iterrows():
        rp=Position(r.longitude,r.latitude,r.altitude_m)
        ma,pen=own_link(p,rp,20,3,20,6);mb,_=own_link(rp,gateway,19,8,27,12)
        row[r.relay_id+'_bilinear_margin_db']=min(ma,mb)
        row[r.relay_id+'_access_terrain_penetration_m']=pen
        old=_bidirectional(p,rp,20,3,3,20,6,8,params,los)
        row[r.relay_id+'_old_dem_ok_at_30m']=old[0]
    row['bilinear_any_link_ok']=max(mg,row['R01_bilinear_margin_db'],row['R02_bilinear_margin_db'])>=0
    rows.append(row)
pd.DataFrame(rows).to_csv(OUT/'q3_endpoint_robustness.csv',index=False,encoding='utf-8-sig')

# Changing reserve must not change the energy of an identical physical flight.
boxes=loader.get_cargos();boxes=boxes[boxes['服务区编号']=='S004'].to_dict('records')
p=loader.get_uav_type('C')
sensitivity=[]
for rho in (.1,.2,.3,.4):
    q=dict(p);q['battery_reserve_pct']=rho
    q['cruise_power_kw']=q['battery_capacity_kwh']*(1-rho)/(q['empty_range_km']*1000/q['cruise_speed_ms']/3600)
    m=direct_mission(areas['S004'],depot,q,boxes,dem)
    sensitivity.append(dict(rho=rho,energy_kwh=m['energy_kwh'],limit_kwh=m['usable_energy_kwh'],
        energy_limit_ratio=m['energy_kwh']/m['usable_energy_kwh'],feasible=m['feasible']))

# Preserve Q3 times while recomputing per-group resource requirements.
def peak(intervals):
    # Excel round-trips can differ by ~1e-14 at a shared boundary. Half-open
    # intervals release before reallocation, with nanominute rounding.
    events=sorted([(round(float(s),9),1) for s,e in intervals]+[(round(float(e),9),-1) for s,e in intervals])
    active=mx=0
    for _,delta in events:active+=delta;mx=max(mx,active)
    return mx
q3=pd.read_excel(ROOT/'解题-gpt/结果/问题三_运输调度_修复版.xlsx')
resource_rows=[]
for k in (2,3):
    old=pd.read_excel(ROOT/f'解题-gpt/结果/问题四_{k}批次_修复版.xlsx',sheet_name='分组资源')
    for _,group in old.iterrows():
        mission=q3[q3.area_id.isin(group.service_area_ids.split(','))]
        rec=dict(k=k,group=group['group'],areas=group.service_area_ids,missions=len(mission),
            completion_min=float(mission.end_min.max()))
        for typ in ('A','B','C'):
            part=mission[mission.uav_type==typ]
            rec[typ+'_uav']=peak(list(zip(part.start_min,part.end_min)))
            rec[typ+'_battery']=peak(list(zip(part.start_min,part.end_min+part.charge_min)))
        resource_rows.append(rec)
pd.DataFrame(resource_rows).to_csv(OUT/'q4_from_actual_q3_times.csv',index=False,encoding='utf-8-sig')

# Semantic reproduction comparison (avoid ZIP metadata/timestamp differences).
diffs=[]
run=Path(__file__).resolve().parent/'reproduction/解题-gpt/结果'
for file in sorted(run.glob('*.xlsx')):
    left=pd.read_excel(file,sheet_name=None)
    right=pd.read_excel(ROOT/'解题-gpt/结果'/file.name,sheet_name=None)
    for sheet,a in left.items():
        b=right.get(sheet)
        if b is None or not a.equals(b):
            diffs.append(dict(file=file.name,sheet=sheet,
                reproduced_rows=len(a),delivered_rows=None if b is None else len(b),
                reproduced=a.to_dict('records'),delivered=None if b is None else b.to_dict('records')))
info={'endpoint_fail_areas':[r['area_id'] for r in rows if not r['bilinear_any_link_ok']],
    'reserve_sensitivity':sensitivity,'reproduction_differences':diffs,
    'q4_resource_totals_inheriting_q3':{str(k):pd.DataFrame([r for r in resource_rows if r['k']==k])[
        [t+s for t in ('A','B','C') for s in ('_uav','_battery')]].sum().to_dict() for k in (2,3)}}
(OUT/'targeted_checks.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in info.items() if k!='reproduction_differences'},ensure_ascii=False,indent=2))
print('Reproduction differing sheets:',len(diffs))
