"""Independent audit of the delivered tables against the supplied raw data.

Energy 'reference' results use explicitly stated engineering assumptions where
the supplied DOCX omits the individual horizontal/ascent energy expressions.
They are sensitivity calculations, not a claim of an additional official rule.
"""
from pathlib import Path
from collections import Counter
from functools import lru_cache
import json
import math
import sys

import numpy as np
import pandas as pd
from scipy.io import loadmat

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / 'evidence'
RESULTS = ROOT/'解题-gpt/结果'
DATA = ROOT/'数据/无人机应急物资运输基础数据'
sys.path.insert(0, str(ROOT))
from src.data.data_loader import DataLoader
from src.terrain.dem_loader import DEMLoader
from solve_problem1_18trips import direct_mission
from solve_problem3_relay import _path_points
from src.battery.charging_model_correct import calculate_charging_time

def write_json(name, value):
    (OUT/name).write_text(json.dumps(value, ensure_ascii=False, indent=2,
        default=lambda x: x.item() if isinstance(x, np.generic) else str(x)), encoding='utf-8')

def raw(file):
    return pd.read_excel(DATA/file, header=None)

t = raw('运输无人机数据.xlsx')
types = {}
for i in (2,3,4):
    r = t.iloc[i]
    typ = r[0]
    charge = t.loc[(t[0] == typ) & (t.index > 15)].iloc[0,2]/60
    types[typ] = dict(empty_mass=r[2], payload=r[3], volume=r[4], speed=r[5],
        L0=r[6], LF=r[7], C=r[8], rho=r[9]/100, prep=r[10], load=r[11],
        handoff=r[12], per_box=r[13], up=r[14], down=r[15], eta=r[16], charge=charge)
official_ids = {r[0]:r[1] for _,r in t.iterrows() if str(r[0]).startswith('U')}
nodes = raw('调度中心与服务区.xlsx')
nodes = {r[0]:dict(longitude=r[2],latitude=r[3],altitude=r[4]) for _,r in nodes.iterrows()
         if str(r[0]).startswith(('O0','S0'))}
depot = nodes['O01']
cargo = pd.read_excel(DATA/'物资需求与配送时限.xlsx', sheet_name='逐箱货箱清单').set_index('货箱编号',drop=False)
dem_path = next((ROOT/'数据').rglob('*DEM.mat'))
mat = loadmat(dem_path)
dem = mat['dem']
tr = mat['transform'].ravel()
loader = DataLoader(str(DATA)); loader.load_all()
old_dem = DEMLoader(str(dem_path)); old_dem.load()
old_types = {r['type']:r.to_dict() for _,r in loader.get_uav_types().iterrows()}

def hav(a,b):
    x1,y1,x2,y2 = map(math.radians,[a[0],a[1],b[0],b[1]])
    h = math.sin((y2-y1)/2)**2 + math.cos(y1)*math.cos(y2)*math.sin((x2-x1)/2)**2
    return 6371000*2*math.asin(math.sqrt(min(1,h)))

def xy(node):
    return node['longitude'],node['latitude']

def grid_intervals(a,b):
    """All raster cells intersected by the open pieces of a straight segment.

    The supplied affine transform locates pixel edges, so cell membership
    uses floor; sampling the midpoint between grid crossings misses no cell.
    For exact corner crossings zero-length touch-only cells are not included.
    """
    c0,r0=(a[0]-tr[2])/tr[0],(a[1]-tr[5])/tr[4]
    c1,r1=(b[0]-tr[2])/tr[0],(b[1]-tr[5])/tr[4]
    cuts=[0.,1.]
    for u,v in ((c0,c1),(r0,r1)):
        if abs(v-u)>1e-12:
            cuts.extend((k-u)/(v-u) for k in range(math.floor(min(u,v))+1,math.ceil(max(u,v)))
                        if 0<(k-u)/(v-u)<1)
    cuts=np.unique(cuts)
    lo,hi=cuts[:-1],cuts[1:]
    mid=(lo+hi)/2
    rr=np.floor(r0+mid*(r1-r0)).astype(int)
    cc=np.floor(c0+mid*(c1-c0)).astype(int)
    if not ((rr>=0)&(rr<dem.shape[0])&(cc>=0)&(cc<dem.shape[1])).all():
        raise ValueError('Outside DEM')
    heights=dem[rr,cc].astype(float)
    if (heights==float(mat['nodata'][0,0])).any():
        raise ValueError('NoData on segment')
    return lo,hi,heights

@lru_cache(None)
def geometry(area):
    a,b=xy(depot),xy(nodes[area])
    d=hav(a,b)
    _,_,heights=grid_intervals(a,b)
    z=float(max(heights))+50
    return d,z

def reference(area,typ,weight,count):
    """Explicit reconstruction: Ehor=C*d/L(q), Eup=m*g*h/(eta*3.6e6).

    Formula for L(q), flight time and reserve bound is explicit in DOCX.
    Ehor and Eup are derived assumptions pending clarification of DOCX.
    """
    p=types[typ]; d,z=geometry(area)
    h0=max(z-depot['altitude'],0)
    h1=max(z-(nodes[area]['altitude']+30),0)
    L=p['L0']-(p['L0']-p['LF'])*(weight/p['payload'])**1.5
    eh=p['C']*d*(1/L+1/p['L0'])
    eu=((p['empty_mass']+weight)*h0+p['empty_mass']*h1)*9.81/(p['eta']*3.6e6)
    out=(h0/p['up']+d/p['speed']+h1/p['down'])/60
    back=(h1/p['up']+d/p['speed']+h0/p['down'])/60
    op=(p['prep']+p['load']*count+p['handoff']+p['per_box']*count)/60
    return dict(reference_energy_kwh=eh+eu,reference_hor_kwh=eh,reference_up_kwh=eu,
        exact_cruise_altitude_m=z,reference_duration_min=out+back+op,
        reference_delivery_offset_min=out+op,reference_soc=1-(eh+eu)/p['C'],
        reference_energy_feasible=eh+eu<=p['C']*(1-p['rho'])+1e-9,
        official_range_m=L)

def charge(s,T):
    return T*(.65*(.9-s)/.9+.35) if s<.9 else T*.35*(1-s)/.1

def conflicts(df,resource,corrected=False):
    errors=[]
    for ident,g in df.groupby(resource):
        prev=None; ready=-math.inf
        for _,r in g.sort_values('start_min').iterrows():
            if float(r.start_min)<ready-1e-7:
                errors.append(dict(resource=ident,previous=prev,current=int(r.mission_id),
                    start=float(r.start_min),ready=float(ready),overlap_min=float(ready-r.start_min)))
            if corrected:
                end=float(r.start_min+r.reference_duration_min)
                extra=charge(r.reference_soc,types[r.uav_type]['charge']) if resource=='battery_id' else 0
            else:
                end=float(r.end_min)
                extra=float(r.charge_min) if resource=='battery_id' else 0
            ready=max(ready,end+extra); prev=int(r.mission_id)
    return errors

audits={}
all_rows={}
files={'q1':('问题一_18架次方案_修复版.xlsx','架次方案'),
       'q2':('问题二_增强优化版.xlsx','架次调度'),
       'q3':('问题三_运输调度_修复版.xlsx',0)}
for q,(file,sheet) in files.items():
    df=pd.read_excel(RESULTS/file,sheet_name=sheet)
    records=[]; ids=[]
    for _,r in df.iterrows():
        box_ids=str(r.cargo_ids).split(','); ids.extend(box_ids)
        b=cargo.loc[box_ids]
        typ=r.uav_type; p=types[typ]
        weight=float(b['单箱质量（kg）'].sum()); volume=float(b['单箱体积（m³）'].sum())
        own=direct_mission(nodes[r.area_id],depot,old_types[typ],b.to_dict('records'),old_dem)
        ref=reference(r.area_id,typ,weight,len(box_ids))
        d,z=geometry(r.area_id)
        # Isolated correction only to the explicitly given 3/2 exponent.
        old_range=own['equivalent_range_km']*1000
        delta=old_types[typ]['battery_capacity_kwh']*(1-old_types[typ]['battery_reserve_pct'])*d*(1/ref['official_range_m']-1/old_range)
        rec=r.to_dict()
        rec.update(ref, audited_weight_kg=weight,audited_volume_m3=volume,
            load_ok=weight<=p['payload']+1e-9,volume_ok=volume<=p['volume']+1e-9,
            area_ok=bool((b['服务区编号']==r.area_id).all()),
            code_energy_kwh=own['energy_kwh'], code_duration_min=own['total_time_min'],
            code_delivery_offset_min=own['delivery_time_min'],
            code_matches_energy=abs(own['energy_kwh']-r.energy_kwh)<1e-7,
            exponent_only_energy_kwh=own['energy_kwh']+delta,
            code_dem_max=own['dem_max_ground_m'], exact_dem_max=z-50,
            dem_underestimate_m=z-50-own['dem_max_ground_m'])
        records.append(rec)
    checked=pd.DataFrame(records); all_rows[q]=checked
    counts=Counter(ids)
    summary=dict(missions=len(df),box_assignments=len(ids),unique_boxes=len(counts),
        missing_boxes=sorted(set(cargo.index)-set(ids)),extra_boxes=sorted(set(ids)-set(cargo.index)),
        duplicate_boxes=[k for k,n in counts.items() if n>1],
        load_violations=int((~checked.load_ok).sum()),volume_violations=int((~checked.volume_ok).sum()),
        area_violations=int((~checked.area_ok).sum()),
        published_energy_kwh=float(df.energy_kwh.sum()),
        code_recomputed_energy_kwh=float(checked.code_energy_kwh.sum()),
        code_energy_mismatch_count=int((~checked.code_matches_energy).sum()),
        exponent_only_energy_kwh=float(checked.exponent_only_energy_kwh.sum()),
        reference_energy_kwh=float(checked.reference_energy_kwh.sum()),
        reference_energy_failures=int((~checked.reference_energy_feasible).sum()),
        max_dem_underestimate_m=float(checked.dem_underestimate_m.max()))
    if q=='q1':
        summary.update(published_duration_sum_min=float(df.total_time_min.sum()),
            published_duration_max_min=float(df.total_time_min.max()),
            code_duration_sum_min=float(checked.code_duration_min.sum()),
            reference_duration_sum_min=float(checked.reference_duration_min.sum()),
            reference_duration_max_min=float(checked.reference_duration_min.max()))
    else:
        checked['reference_delivery_min']=checked.start_min+checked.reference_delivery_offset_min
        checked['reference_end_min']=checked.start_min+checked.reference_duration_min
        boxchecks=[]
        for _,r in checked.iterrows():
            for ident in str(r.cargo_ids).split(','):
                b=cargo.loc[ident]
                hard=[]
                if b['是否首批保障']=='是': hard.append(float(b['首批截止时间（s）'])/60)
                if b['物资类型']=='医疗物资': hard.append(float(b['期望送达时间（s）'])/60)
                deadline=float(min(hard)) if hard else None
                boxchecks.append(dict(cargo_id=ident,mission_id=r.mission_id,
                    published_delivery=r.delivery_min,reference_delivery=r.reference_delivery_min,
                    hard_deadline=deadline,expected_deadline=float(b['期望送达时间（s）'])/60,
                    hard_late=bool(deadline is not None and r.delivery_min>deadline+1e-7),
                    reference_hard_late=bool(deadline is not None and r.reference_delivery_min>deadline+1e-7),
                    expected_late=bool(r.delivery_min>float(b['期望送达时间（s）'])/60+1e-7)))
        pd.DataFrame(boxchecks).to_csv(OUT/f'{q}_cargo_check.csv',index=False,encoding='utf-8-sig')
        summary.update(completion_min=float(df.end_min.max()),
            unsupported_uav_ids=sorted(set(df.uav_id)-set(official_ids)),
            hard_late_boxes=[b['cargo_id'] for b in boxchecks if b['hard_late']],
            expected_late_boxes=[b['cargo_id'] for b in boxchecks if b['expected_late']],
            reference_hard_late_boxes=[b['cargo_id'] for b in boxchecks if b['reference_hard_late']],
            published_uav_conflicts=conflicts(checked,'uav_id'),
            published_battery_conflicts=conflicts(checked,'battery_id'),
            reference_uav_conflicts=conflicts(checked,'uav_id',True),
            reference_battery_conflicts=conflicts(checked,'battery_id',True))
    checked.to_csv(OUT/f'{q}_mission_check.csv',index=False,encoding='utf-8-sig')
    audits[q]=summary

# DEM pixel-center regression against the explicit MAT longitude/latitude.
r,c=650,740
audits['dem_pixel_center']={'row':r,'col':c,'cell_value':float(dem[r,c]),
    'code_get_height':old_dem.get_height(float(mat['longitude'][0,c]),float(mat['latitude'][r,0]))}
audits['charging']={'full_charge_min':{k:p['charge'] for k,p in types.items()},
    'maximum_error':max(abs(charge(s,p['charge'])-calculate_charging_time(s,1,p['charge']))
                        for p in types.values() for s in np.linspace(0,1,101))}

# Relay endurance evidence does not depend on any unspecified ascent formula.
relays=pd.read_excel(RESULTS/'问题三_中继部署方案_修复版.xlsx')
rr=raw('中继无人机数据.xlsx').iloc[2]
relay_checks=[]
for _,r in relays.iterrows():
    duration=float(r.service_end_min-r.service_start_min)
    hover=(rr[16]+rr[17])*duration/60
    usable=rr[7]*(1-rr[8]/100)
    relay_checks.append({'relay_id':r.relay_id,'service_duration_min':duration,
        'hover_energy_lower_bound_kwh':float(hover),'single_component_limit_kwh':float(usable),
        'hover_only_max_minutes':float(usable/(rr[16]+rr[17])*60),
        'hover_alone_exceeds_component':bool(hover>usable),
        'component_ids':r.energy_component_ids,'published_energy_kwh':r.energy_kwh})
audits['relay_endurance']=relay_checks

# Correct endpoint/interface link budgets, with exact traversed DEM cells.
comm=raw('通信链路参数.xlsx')
cp={(str(r[0]),str(r[3])):r[4] for _,r in comm.iterrows() if pd.notna(r[3])}
freq=float(cp['传播参数','f']); loss=float(cp['传播参数','Lsys'])
obs=float(cp['传播参数','Lobs']); threshold=float(cp['接收参数','Psens']+cp['接收参数','M'])
params={'T':(20.,3.),'G':(27.,12.),'RA':(20.,6.),'RB':(19.,8.)}
gateway=(*xy(depot),depot['altitude']+float(cp['固定网关 G01','hG']))
relay_positions={r.relay_id:(r.longitude,r.latitude,r.altitude_m) for _,r in relays.iterrows()}

def link(p1,p2,k1,k2):
    distance=math.hypot(hav(p1,p2),p2[2]-p1[2])
    fspl=32.45+20*math.log10(freq)+20*math.log10(max(distance,1)/1000)
    lo,hi,heights=grid_intervals(p1,p2)
    zlo=p1[2]+lo*(p2[2]-p1[2]); zhi=p1[2]+hi*(p2[2]-p1[2])
    blocked=bool((heights>np.minimum(zlo,zhi)+1e-8).any())
    pt1,g1=params[k1];pt2,g2=params[k2]
    margin=min(pt1,pt2)+g1+g2-loss-fspl-(obs if blocked else 0)-threshold
    return margin,blocked

comm_checks=[]; failed_points=[]
for area in sorted(set(all_rows['q3'].area_id)):
    a=(*xy(depot),depot['altitude']); b=(*xy(nodes[area]),nodes[area]['altitude']+30)
    d,z=geometry(area)
    phases=[('depot_climb',a,(a[0],a[1],z)),
            ('cruise',(a[0],a[1],z),(b[0],b[1],z)),
            ('service_descent',(b[0],b[1],z),b)]
    points=[]
    # 10 m spatial sampling can disprove continuity, but does not prove it.
    for phase,p0,p1 in phases:
        distance=math.hypot(hav(p0,p1),p1[2]-p0[2])
        n=max(2,math.ceil(distance/10)+1)
        for t0 in np.linspace(0,1,n):
            pos=tuple(p0[k]+t0*(p1[k]-p0[k]) for k in range(3))
            points.append((phase,pos))
    supported={}; margins={}; direct_count=0; any_count=0
    for name in relay_positions:
        supported[name]=0; margins[name]=float('inf')
    for phase,p in points:
        mg,_=link(p,gateway,'T','G'); direct_ok=mg>=-1e-8
        direct_count+=direct_ok
        any_ok=direct_ok
        point_margins={}
        for name,rpos in relay_positions.items():
            ma,_=link(p,rpos,'T','RA'); mb,_=link(rpos,gateway,'RB','G')
            m=min(ma,mb); point_margins[name]=m
            margins[name]=min(margins[name],m)
            ok=direct_ok or m>=-1e-8
            supported[name]+=ok; any_ok=any_ok or ok
        any_count+=any_ok
        if not any_ok:
            failed_points.append({'area_id':area,'phase':phase,'lon':p[0],'lat':p[1],
                'altitude_m':p[2],'direct_margin_db':mg,**point_margins})
    modes=sorted(set(all_rows['q3'].loc[all_rows['q3'].area_id==area,'communication_mode']))
    old_path=_path_points(depot,nodes[area],old_dem)
    comm_checks.append({'area_id':area,'points':len(points),'direct_ok_points':direct_count,
        'any_relay_or_direct_ok_points':any_count,'interrupt_points':len(points)-any_count,
        'assigned_modes':','.join(modes),'exact_cruise_m':z,
        'code_comm_cruise_m':old_path[1].z,'code_delivery_alt_m':old_path[-1].z,
        'required_delivery_alt_m':b[2],
        **{k+'_ok_points':v for k,v in supported.items()},
        **{k+'_min_margin_db':v for k,v in margins.items()}})
pd.DataFrame(comm_checks).to_csv(OUT/'q3_communication_check.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(failed_points).to_csv(OUT/'q3_failed_points.csv',index=False,encoding='utf-8-sig')
audits['communication']={'method':'10 m path sampling, all intersected DEM cells, correct endpoint interfaces; both relays optimistically always active',
    'areas':comm_checks,'failed_point_count':len(failed_points),
    'backhaul':{name:link(pos,gateway,'RB','G')[0] for name,pos in relay_positions.items()}}

q4={}
for k in (2,3):
    df=pd.read_excel(RESULTS/f'问题四_{k}批次_错峰复用优化.xlsx',sheet_name='错峰调度')
    late=[]; mode_violations=[]
    for _,r in df.iterrows():
        for ident in str(r.cargo_ids).split(','):
            b=cargo.loc[ident]; hard=[]
            if b['是否首批保障']=='是':hard.append(float(b['首批截止时间（s）'])/60)
            if b['物资类型']=='医疗物资':hard.append(float(b['期望送达时间（s）'])/60)
            deadline=min(hard) if hard else None
            if deadline is not None and r.delivery_min>deadline+1e-7:
                late.append({'cargo_id':ident,'batch':r.batch_id,'delivery_min':r.delivery_min,
                    'hard_deadline_min':deadline,'stale_on_time':bool(r.on_time)})
        old=all_rows['q3'].set_index('mission_id').loc[r.mission_id]
        if old.communication_mode!='direct':
            rel=relays.set_index('relay_id').loc[old.communication_mode]
            if r.start_min<rel.service_start_min-1e-8 or r.end_min>rel.service_end_min+1e-8:
                mode_violations.append(int(r.mission_id))
    pd.DataFrame(late).to_csv(OUT/f'q4_{k}_hard_late.csv',index=False,encoding='utf-8-sig')
    original=pd.read_excel(RESULTS/f'问题四_{k}批次_修复版.xlsx',sheet_name='分组资源')
    q4[str(k)]={'completion_min':float(df.end_min.max()),'hard_late_count':len(late),
        'hard_late_boxes':late,'all_saved_on_time_true':bool(df.on_time.all()),
        'outside_unchanged_relay_windows':mode_violations,
        'battery_conflicts_with_saved_ids':conflicts(df,'battery_id'),
        'uav_cross_group_ids':[u for u,g in df.groupby('uav_id') if g.batch_id.nunique()>1],
        'independent_resources':original.to_dict('records')}
audits['q4']=q4
write_json('audit_summary.json',audits)
print(json.dumps({q:{k:v for k,v in a.items() if not isinstance(v,(list,dict))} for q,a in audits.items() if q in files},ensure_ascii=False,indent=2))
print('Communication failed points:',len(failed_points))
print('Q4 hard late:',{k:v['hard_late_count'] for k,v in q4.items()})
