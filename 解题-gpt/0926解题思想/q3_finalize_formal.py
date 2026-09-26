"""Finalize and fail-closed validate the Problem-3 joint-window candidate.

The candidate is generated from official data only.  This script recomputes
mission physics, assigns physical transport UAVs/batteries, checks every
sampled outbound/return path point, and verifies relay return/energy/resource
constraints before writing formal files.
"""
from pathlib import Path
import sys, json, math
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).resolve().parent))
import problem3_joint_optimizer as q
from solve_problem1_18trips import direct_mission, WEIGHT, VOLUME

RESULT=ROOT/'解题-gpt'/'结果'
OUT=ROOT/'解题-gpt'/'0926解题思想'
OUT.mkdir(parents=True,exist_ok=True)

def deadline(box):
    return (float(box['首批截止时间（s）']) if box['是否首批保障']=='是' else float(box['期望送达时间（s）']))/60.0

def load_candidate():
    missions=pd.read_excel(RESULT/'问题三_运输调度_联合窗候选.xlsx')
    relays=pd.read_excel(RESULT/'问题三_中继调度_联合窗候选.xlsx')
    return missions,relays

def assign_resources(df):
    # EDF-compatible fixed-start assignment to the official physical fleets.
    u={t:{f'U{t}{i+1:02d}':-1e9 for i in range(int(p['count']))} for t,p in q.types.items()}
    b={t:{f'{t}-BAT-{i+1:02d}':-1e9 for i in range(int(p['battery_count']))} for t,p in q.types.items()}
    out=df.sort_values(['start_min','deadline','id']).copy(); uid=[];bid=[]
    for _,r in out.iterrows():
        typ=str(r['typ']);st=float(r['start_min']);en=float(r['end_min']);ch=float(r['charge'])
        cu=[(k,v) for k,v in u[typ].items() if v<=st+1e-8]
        cb=[(k,v) for k,v in b[typ].items() if v<=st+1e-8]
        if not cu or not cb: raise ValueError(f'resource assignment failed for mission {int(r.id)}')
        ui=min(cu,key=lambda x:(x[1],x[0]))[0];bi=min(cb,key=lambda x:(x[1],x[0]))[0]
        u[typ][ui]=en;b[typ][bi]=en+ch;uid.append((int(r.id),ui));bid.append((int(r.id),bi))
    um={i:x for i,x in uid};bm={i:x for i,x in bid};df=df.copy();df['uav_id']=df['id'].map(um);df['battery_id']=df['id'].map(bm);return df

def validate():
    missions,relays=load_candidate(); missions=assign_resources(missions)
    cargo=q.cargo
    comm_rows=[]; violations=[]; late=[]; cap=[]; vol=[]
    # Recompute every mission from official cargo, type and DEM.  The joint
    # candidate may select an alternate type; keep that type only when the
    # official load/volume/energy checks accept it.
    for _,r in missions.sort_values('id').iterrows():
        ids=[x for x in str(r['cargo_ids']).split(',') if x]
        boxes=[cargo.loc[x].to_dict() for x in ids]
        typ=str(r['typ']);met=direct_mission(q.areas[str(r['area'])],q.depot,q.types[typ],boxes,q.dem)
        if not met['feasible']: violations.append({'mission_id':int(r.id),'reason':'physical_mission_infeasible','detail':met.get('reason','')})
        if abs(float(r['dur'])-float(met['total_time_min']))>1e-5 or abs(float(r['off'])-float(met['delivery_time_min']))>1e-5:
            violations.append({'mission_id':int(r.id),'reason':'candidate_physics_mismatch'})
        if float(r['delivery_min'])>min(deadline(cargo.loc[x]) for x in ids)+1e-8: late.extend(ids)
        load=sum(float(cargo.loc[x][WEIGHT]) for x in ids);volume=sum(float(cargo.loc[x][VOLUME]) for x in ids)
        if load>float(q.types[typ]['max_load_kg'])+1e-8:cap.append(int(r.id))
        if volume>float(q.types[typ]['max_volume_m3'])+1e-8:vol.append(int(r.id))
        area=str(r['area']);path=q.paths[area];out=float(met['delivery_time_min'])-float(met['operation_time_min']);op=float(met['operation_time_min']);hand=float(q.types[typ]['handoff_base_s'])/60+float(q.types[typ]['handoff_per_box_s'])/60*len(ids);ret=float(met['total_time_min'])-float(met['operation_time_min'])-out
        relay_area=next((str(x['point']) for _,x in relays.iterrows() if str(x['point']) in q.cover and area in q.cover[str(x['point'])]),None)
        for direction in ('outbound','return'):
            for i,pt in enumerate(path):
                t=(float(r['start_min'])+op+out*i/(len(path)-1)) if direction=='outbound' else (float(r['start_min'])+op+out+hand+ret*(1-i/(len(path)-1)))
                direct=q.direct_ok(pt);active=[]
                if not direct:
                    for _,z in relays.iterrows():
                        p=str(z['point']);
                        if q.relay_ok(pt,q.POINTS[p]) and float(z['a'])-1e-8<=t<=float(z['b'])+1e-8:active.append(p)
                ok=direct or bool(active)
                comm_rows.append({'mission_id':int(r.id),'area_id':area,'direction':direction,'path_index':i,'time_min':t,'direct':direct,'active_relay_points':','.join(active),'available':ok})
                if not ok: violations.append({'mission_id':int(r.id),'reason':'communication_gap','direction':direction,'path_index':i,'time_min':t})
    # Cargo uniqueness/coverage.
    ids=[]
    for _,r in missions.iterrows():ids.extend([x for x in str(r['cargo_ids']).split(',') if x])
    if len(ids)!=len(set(ids)) or set(ids)!=set(cargo.index):violations.append({'reason':'cargo_coverage','count':len(ids),'unique':len(set(ids)),'official':len(cargo)})
    relay_rows=[]
    official_components=int(q.loader.relay_energy_inventory['count']);
    for _,r in relays.iterrows():
        p=str(r['point']);one=q.q3._relay_flight_time_min(q.POINTS[p],q.gateway,q.relay_spec)/2;fl,_=q.relay_flight(q.POINTS[p]);dur=float(r['b'])-float(r['a']);energy=fl+(q.relay_spec['hover_power_kw']+q.relay_spec['comm_power_kw'])*dur/60;launch=float(r['a'])-one-float(q.relay_spec['prep_time_s'])/60-float(q.relay_spec['setup_time_s'])/60;ret=float(r['b'])+one+float(q.relay_spec['turnaround_time_s'])/60
        relay_rows.append({'relay_id':str(r['relay_id']),'point':p,'service_start_min':float(r['a']),'service_end_min':float(r['b']),'launch_min':launch,'return_end_min':ret,'flight_energy_kwh':fl,'hover_energy_kwh':energy-fl,'energy_kwh':energy,'component_required':int(math.ceil(energy/q.relay_usable-1e-12))})
    for rid in sorted(set(x['relay_id'] for x in relay_rows)):
        rr=sorted([x for x in relay_rows if x['relay_id']==rid],key=lambda x:x['launch_min'])
        for a,b in zip(rr,rr[1:]):
            if b['launch_min']<a['return_end_min']-1e-8:violations.append({'reason':'relay_overlap','relay_id':rid})
    components=sum(x['component_required'] for x in relay_rows)
    summary={'feasible_100_percent':not violations and not late and not cap and not vol and components<=official_components,'mission_count':len(missions),'cargo_count':len(set(ids)),'late_cargo_count':len(set(late)),'communication_sample_count':len(comm_rows),'communication_available_sample_count':sum(int(x['available']) for x in comm_rows),'communication_gap_count':sum(not x['available'] for x in comm_rows),'transport_completion_min':float(missions['end_min'].max()),'relay_sortie_count':len(relay_rows),'relay_energy_components_used':components,'official_relay_energy_components':official_components,'relay_energy_kwh':sum(x['energy_kwh'] for x in relay_rows),'transport_energy_kwh':float(missions['energy'].sum()),'total_energy_kwh':float(missions['energy'].sum())+sum(x['energy_kwh'] for x in relay_rows),'joint_completion_min':max(float(missions['end_min'].max()),max(x['return_end_min'] for x in relay_rows)),'violations':violations,'capacity_violation_mission_ids':cap,'volume_violation_mission_ids':vol,'relay_rows':relay_rows}
    missions.to_excel(OUT/'问题三_运输调度_正式版.xlsx',index=False);pd.DataFrame(relay_rows).to_excel(OUT/'问题三_中继调度_正式版.xlsx',index=False);pd.DataFrame(comm_rows).to_excel(OUT/'问题三_逐路径通信核验_正式版.xlsx',index=False);(OUT/'问题三_汇总_正式版.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');return summary

if __name__=='__main__':
 s=validate();print(json.dumps({k:s[k] for k in ['feasible_100_percent','late_cargo_count','communication_gap_count','relay_energy_components_used','total_energy_kwh','joint_completion_min']},ensure_ascii=False))
