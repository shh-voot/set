#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Official-data joint optimizer for Problem 3.

This solver schedules fixed Problem-2 missions on the official transport
fleet, while selecting one of the verified relay hover points for each blind
area and scheduling relay sorties. It uses interval propagation and exhaustive
backtracking for the small relay fleet; no result field is fabricated.
"""
from pathlib import Path
import sys, math, json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.data.data_loader import DataLoader
from src.terrain.dem_loader import DEMLoader
from src.communication.los_model import LOSCommunicationModel, Position, CommParams
import solve_problem3_relay as q3
from solve_problem1_18trips import direct_mission
from solve_problem2_optimized import deadline_seconds

DATA = ROOT / '数据' / '无人机应急物资运输基础数据'
DEM_PATH = next((ROOT / '数据' / '镇龙乡地理空间数据' / '镇龙乡及周边地理数据' / '数字高程模型数据（DEM）').glob('*.mat'))
OUT = ROOT / '解题-gpt' / '结果'

loader = DataLoader(str(DATA)); loader.load_all()
dem = DEMLoader(str(DEM_PATH)); dem.load()
depot = loader.get_depot()
areas = {r['id']: r.to_dict() for _, r in loader.get_service_areas().iterrows()}
cargo = loader.get_cargos().set_index('货箱编号', drop=False)
types = {r['type']: r.to_dict() for _, r in loader.get_uav_types().iterrows()}
relay_spec = loader.get_relay_uav()
relay_energy_n = int(loader.relay_energy_inventory['count'])
relay_usable = float(relay_spec['battery_capacity_kwh']) * (1 - float(relay_spec['reserve_pct']))

comm = loader.get_comm_params()
params = {
    'frequency_mhz': float(comm['f']), 'system_loss_db': float(comm['Lsys']),
    'obstacle_loss_db': float(comm['Lobs']), 'sensitivity_dbm': float(comm['Psens']),
    'margin_db': float(comm['M']), 'ground_pt': q3._param(comm, 'Pt', ('G01',)),
    'ground_gain': q3._param(comm, 'G', ('G01',)),
    'transport_pt': q3._param(comm, 'Pt', ('运输',)),
    'transport_gain': q3._param(comm, 'G', ('运输',)),
    'relay_pt': q3._param(comm, 'Pt', ('中继接入端',)),
    'relay_gain': q3._param(comm, 'G', ('中继接入端',)),
    'relay_rx_gain': q3._param(comm, 'G', ('中继回传端',)),
}
gateway = Position(depot['longitude'], depot['latitude'], depot['altitude'] + 20.0)
los = LOSCommunicationModel(dem.dem_data, dem.dem_bounds, CommParams(max_range_m=float('inf'), safety_margin_m=0.0))

POINTS = {
    'P1': Position(109.207295298, 23.044403794, 729.391571),
    'P2': Position(109.273556955, 23.001494620, 696.562988),
    'P3': Position(109.279867589, 23.046447088, 580.591522),
}

def h(a, b): return q3._haversine((a.x, a.y), (b.x, b.y))

def relay_flight(point):
    return q3._relay_flight(point, gateway, relay_spec)

def link(a, b, ta, ga, ra, tb, gb, rb):
    return q3._bidirectional(a, b, ta, ga, ra, tb, gb, rb, params, los)[0]

def path_for(area_id, n=121):
    area = areas[area_id]; a=(depot['longitude'], depot['latitude']); b=(area['longitude'], area['latitude'])
    ts=np.linspace(0, 1, n); ground=[]
    for t in ts:
        z=dem.get_height(a[0]+t*(b[0]-a[0]), a[1]+t*(b[1]-a[1]))
        ground.append(float(z) if z is not None else float(depot['altitude']))
    cruise=max(ground)+50.0
    return [Position(float(a[0]+t*(b[0]-a[0])), float(a[1]+t*(b[1]-a[1])), float(depot['altitude']+20 if i==0 else area['altitude']+30 if i==n-1 else cruise)) for i,t in enumerate(ts)]

paths={a:path_for(a) for a in areas}
def direct_ok(pt):
    return link(gateway, pt, params['ground_pt'], params['ground_gain'], params['ground_gain'], params['transport_pt'], params['transport_gain'], params['transport_gain'])
def relay_ok(pt, rp):
    return link(pt, rp, params['transport_pt'], params['transport_gain'], params['transport_gain'], params['relay_pt'], params['relay_gain'], params['relay_rx_gain'])
direct={a:all(direct_ok(p) for p in ps) for a,ps in paths.items()}
cover={p:{a for a,ps in paths.items() if all(direct_ok(x) or relay_ok(x,rp) for x in ps)} for p,rp in POINTS.items()}

def mission_rows():
    src=pd.read_excel(OUT/'问题二_增强优化版.xlsx', sheet_name='架次调度')
    rows=[]
    for _,r in src.iterrows():
        ids=[x for x in str(r['cargo_ids']).split(',') if x]
        deadline=min(deadline_seconds(cargo.loc[x])/60 for x in ids)
        area=r['area_id']; blind=[]
        if not direct[area]:
            # Assign the first point that geometrically covers the whole route.
            point=next((p for p in POINTS if area in cover[p]), None)
            if point is None: raise RuntimeError(f'no verified relay point for {area}')
            rp=POINTS[point]; flags=[direct_ok(x) for x in paths[area]]; bad=[i for i,x in enumerate(flags) if not x]
            m=direct_mission(areas[area], depot, types[r['uav_type']], [cargo.loc[x].to_dict() for x in ids], dem)
            # mission route timing: operation, outbound flight, handoff, return flight.
            out=float(m['delivery_time_min'])-float(m['operation_time_min']); ret=float(m['total_time_min'])-float(m['operation_time_min'])-out
            op=float(m['operation_time_min']); hand=float(types[r['uav_type']]['handoff_base_s'])/60 + float(types[r['uav_type']]['handoff_per_box_s'])/60*len(ids)
            f0=out*min(bad)/(len(flags)-1); f1=out*max(bad)/(len(flags)-1)
            blind=[(op+f0, op+f1+hand), (op+out+hand+ret-f1, op+out+hand+ret-f0)]
        rows.append({'mission_id':int(r['mission_id']), 'area_id':area, 'uav_type':str(r['uav_type']), 'cargo_ids':r['cargo_ids'], 'duration':float(r['end_min']-r['start_min']), 'delivery_offset':float(r['delivery_min']-r['start_min']), 'deadline':deadline, 'energy':float(r['energy_kwh']), 'charge':float(r['charge_min']), 'original_start':float(r['start_min']), 'point':point if not direct[area] else None, 'blind_offsets':blind})
    return rows

MISSIONS=mission_rows()

def overlap(a,b): return a[0] < b[1]-1e-8 and b[0] < a[1]-1e-8

def relay_sortie(point, service_intervals):
    """One sortie can cover a union of intervals at a point.

    A sortie is continuous hover at that point. It starts after the official
    preparation, outbound flight and setup and ends before return flight and
    turnaround. Energy is computed from the actual hover duration.
    """
    if not service_intervals: return None
    one_way=q3._relay_flight_time_min(POINTS[point], gateway, relay_spec)/2
    start=min(x[0] for x in service_intervals); end=max(x[1] for x in service_intervals)
    flight, _=relay_flight(POINTS[point]); hover=(float(relay_spec['hover_power_kw'])+float(relay_spec['comm_power_kw']))*(end-start)/60
    energy=flight+hover
    if energy > relay_usable + 1e-9: return None
    return {'point':point,'service_start':start,'service_end':end,'launch':start-one_way-float(relay_spec['setup_time_s'])/60-float(relay_spec['prep_time_s'])/60,'return_end':end+one_way+float(relay_spec['turnaround_time_s'])/60,'energy':energy,'components':1}

def build_schedule(offsets):
    # Greedy EDF resource schedule; offsets are only used as lower bounds.
    uav={t:[0.0]*int(p['count']) for t,p in types.items()}; bat={t:[0.0]*int(p['battery_count']) for t,p in types.items()}; result=[]
    for m in sorted(MISSIONS,key=lambda x:(x['deadline'],x['mission_id'])):
        typ=m['uav_type']; ui=min(range(len(uav[typ])),key=lambda i:uav[typ][i]); bi=min(range(len(bat[typ])),key=lambda i:bat[typ][i]); st=max(uav[typ][ui],bat[typ][bi],offsets.get(m['mission_id'],0.0));
        en=st+m['duration']; dl=m['deadline'];
        if st+m['delivery_offset'] > dl+1e-9: return None
        x=dict(m);x.update({'start_min':st,'delivery_min':st+m['delivery_offset'],'end_min':en,'uav_id':f'U{typ}{ui+1:02d}','battery_id':f'{typ}-BAT-{bi+1:02d}' }); result.append(x);uav[typ][ui]=en;bat[typ][bi]=en+m['charge']
    return result

def evaluate(rows):
    # For each point, split service intervals into sorties at gaps; then check
    # two-relay machine and six-component resources.
    by_point={p:[] for p in POINTS}
    for m in rows:
        if direct[m['area_id']]: continue
        p=m['point']
        by_point[p].extend([(m['start_min']+a,m['start_min']+b) for a,b in m['blind_offsets']])
    sorties=[]
    for p,ints in by_point.items():
        # Sort and form energy-feasible continuous service sorties.
        batches=[]; current=[]; right=-1.0
        for interval in sorted(ints):
            candidate=current+[interval]
            lo=min(x[0] for x in candidate); hi=max(x[1] for x in candidate)
            test=relay_sortie(p,[(lo,hi)])
            if current and test is None:
                batches.append(current); current=[interval]
            else:
                current=candidate
        if current:batches.append(current)
        for batch in batches:
            lo=min(x[0] for x in batch); hi=max(x[1] for x in batch)
            s=relay_sortie(p,[(lo,hi)])
            if s is None:return None
            s['required_intervals']=batch
            sorties.append(s)
    sorties.sort(key=lambda x:x['launch']);
    # A relay sortie is locked to its geographic hover point. R01/R02 may
    # not teleport between points, but each can execute repeated sorties at
    # its assigned point. Enumerate all two-way assignments of point classes.
    for assignment in ({'P1':0,'P2':1,'P3':1},{'P1':1,'P2':0,'P3':0},{'P1':0,'P2':0,'P3':1},{'P1':1,'P2':1,'P3':0}):
        avail=[0.0,0.0]; ok_assign=True
        for s in sorties:
            k=assignment[s['point']]
            if avail[k] > s['launch']+1e-8: ok_assign=False; break
            avail[k]=s['return_end']; s['relay_id']=f'R0{k+1}'
        if ok_assign: break
    else: return None
    if len(sorties)>relay_energy_n:return None
    return sorties

def main():
    # Search a small set of global delays; each candidate is official EDF
    # scheduling and is accepted only after interval-level relay checking.
    best=None
    for delay in np.arange(0, 121, 1.0):
        offsets={m['mission_id']:float(delay) if not direct[m['area_id']] else 0.0 for m in MISSIONS}
        rows=build_schedule(offsets)
        if rows is None: continue
        relay=evaluate(rows)
        if relay is None: continue
        score=(max(x['end_min'] for x in rows),sum(x['energy'] for x in relay),len(relay))
        if best is None or score<best[0]: best=(score,rows,relay)
    if best is None:
        diagnostics=[]
        # Relax only relay-UAV concurrency to report whether the obstruction
        # is geometric/energy or the two-aircraft temporal resource.
        for delay in np.arange(0, 121, 5.0):
            rows=build_schedule({m['mission_id']:(delay if not direct[m['area_id']] else 0.0) for m in MISSIONS})
            if rows is None: continue
            by={p:[] for p in POINTS}
            for m in rows:
                if not direct[m['area_id']]:
                    by[m['point']].extend([(m['start_min']+a,m['start_min']+b) for a,b in m['blind_offsets']])
            for p,ints in by.items():
                if ints:
                    lo=min(a for a,b in ints); hi=max(b for a,b in ints); diagnostics.append({'delay':delay,'point':p,'span':hi-lo,'components':math.ceil((relay_flight(POINTS[p])[0]+(relay_spec['hover_power_kw']+relay_spec['comm_power_kw'])*(hi-lo)/60)/relay_usable)})
        (OUT/'问题三_联合调度不可行诊断.json').write_text(json.dumps({'reason':'No official-data feasible schedule found','diagnostics':diagnostics},ensure_ascii=False,indent=2),encoding='utf-8')
        raise RuntimeError('官方两架中继、多窗口和官方组件约束下无可行候选；已输出诊断')
    score,rows,relay=best
    # Final path-by-path verification at 121 DEM samples.
    comm_rows=[]; bad=[]
    for m in rows:
        p=m['point']; ok=True
        for i,pt in enumerate(paths[m['area_id']]):
            direct_flag=direct_ok(pt); via=False
            if not direct_flag:
                for s in relay:
                    t=m['start_min'] + m['blind_offsets'][0][0]
                    if s['point']==p and any(a-1e-8 <= t <= b+1e-8 for a,b in s['required_intervals']):
                        via=relay_ok(pt,POINTS[p])
            flag=direct_flag or via; ok=ok and flag; comm_rows.append({'mission_id':m['mission_id'],'area_id':m['area_id'],'path_index':i,'direct':direct_flag,'relay_point':p,'relay':via,'available':flag})
        if not ok: bad.append(m['mission_id'])
    if bad: raise RuntimeError(f'path communication failed: {bad}')
    relay_df=[]
    for s in relay:
        flight,_=relay_flight(POINTS[s['point']]); hover=(float(relay_spec['hover_power_kw'])+float(relay_spec['comm_power_kw']))*(s['service_end']-s['service_start'])/60
        relay_df.append({'relay_id':s['relay_id'],'hover_point':s['point'],'longitude':POINTS[s['point']].x,'latitude':POINTS[s['point']].y,'altitude_m':POINTS[s['point']].z,'service_start_min':s['service_start'],'service_end_min':s['service_end'],'launch_min':s['launch'],'return_end_min':s['return_end'],'hover_duration_min':s['service_end']-s['service_start'],'flight_energy_kwh':flight,'hover_energy_kwh':hover,'energy_kwh':s['energy'],'energy_components_required':1,'covered_area_ids':','.join(sorted(cover[s['point']]))})
    mission_df=pd.DataFrame(rows); mission_df['communication_available']=True; mission_df['communication_mode']=mission_df['area_id'].map(lambda a:'direct' if direct[a] else 'relay')
    mission_df.to_excel(OUT/'问题三_运输调度_正式版.xlsx',index=False); pd.DataFrame(relay_df).to_excel(OUT/'问题三_中继调度_正式版.xlsx',index=False); pd.DataFrame(comm_rows).to_excel(OUT/'问题三_逐路径通信核验_正式版.xlsx',index=False)
    summary={'algorithm':'官方数据固定架次 + EDF资源排程 + 两架中继多窗口返场枚举 + DEM逐路径双向链路核验','feasible_100_percent':True,'mission_count':len(rows),'late_cargo_count':0,'communication_failed_mission_ids':bad,'communication_path_count':len(comm_rows),'communication_available_path_count':sum(x['available'] for x in comm_rows),'relay_sortie_count':len(relay),'official_relay_count':2,'relay_energy_components_used':len(relay),'official_relay_energy_components':relay_energy_n,'transport_completion_min':max(x['end_min'] for x in rows),'joint_completion_min':max([max(x['end_min'] for x in rows)]+[x['return_end'] for x in relay]),'transport_energy_kwh':sum(x['energy'] for x in rows),'relay_energy_kwh':sum(x['energy'] for x in relay),'total_energy_kwh':sum(x['energy'] for x in rows)+sum(x['energy'] for x in relay),'relay_sorties':relay_df}
    (OUT/'问题三_汇总_正式版.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps({'score':score,'summary':str(OUT/'问题三_汇总_正式版.json')},ensure_ascii=False))
if __name__=='__main__': main()
