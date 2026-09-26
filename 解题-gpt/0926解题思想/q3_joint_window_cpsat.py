from pathlib import Path
import sys, math
import pandas as pd
from ortools.sat.python import cp_model
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).resolve().parent))
import problem3_joint_optimizer as q
from solve_problem1_18trips import direct_mission
from src.battery.charging_model_correct import calculate_charging_time

S=10
src=pd.read_excel(ROOT/'解题-gpt'/'结果'/'问题二_增强优化版.xlsx',sheet_name='架次调度')
mode_df=pd.read_excel(ROOT/'解题-gpt'/'结果'/'问题三_运输调度_CPSAT模式候选.xlsx')
mode_map={int(r.id):str(r.uav_type) for _,r in mode_df.iterrows()}
MISSIONS=[]
for _,r in src.iterrows():
 i=int(r.mission_id);ids=[x for x in str(r.cargo_ids).split(',') if x];typ=mode_map[i];p=q.types[typ]
 met=direct_mission(q.areas[r.area_id],q.depot,p,[q.cargo.loc[x].to_dict() for x in ids],q.dem)
 if not met['feasible']:
  # Preserve official physical feasibility: candidate mode switches are
  # accepted only when load, volume and energy all pass the same decoder.
  typ=str(r['uav_type']);p=q.types[typ];met=direct_mission(q.areas[r.area_id],q.depot,p,[q.cargo.loc[x].to_dict() for x in ids],q.dem)
 soc=1-float(met['energy_kwh'])/float(p['battery_capacity_kwh']);ch=calculate_charging_time(soc,1,float(p['full_charge_time_min']))
 m=next(x for x in q.MISSIONS if x['mission_id']==i);point=None;blind=[]
 if not q.direct[r.area_id]:
  point=next((p for p in q.POINTS if r.area_id in q.cover[p]),None)
  flags=[q.direct_ok(x) for x in q.paths[r.area_id]];bad=[j for j,z in enumerate(flags) if not z]
  out=float(met['delivery_time_min'])-float(met['operation_time_min']);ret=float(met['total_time_min'])-float(met['operation_time_min'])-out;op=float(met['operation_time_min']);hand=float(p['handoff_base_s'])/60+float(p['handoff_per_box_s'])/60*len(ids)
  blind=[(op+out*min(bad)/(len(flags)-1),op+out*max(bad)/(len(flags)-1)+hand),(op+out+hand+ret-out*max(bad)/(len(flags)-1),op+out+hand+ret-out*min(bad)/(len(flags)-1))]
 MISSIONS.append({'id':i,'area':r.area_id,'typ':typ,'cargo_ids':r.cargo_ids,'dur':float(met['total_time_min']),'off':float(met['delivery_time_min']),'deadline':m['deadline'],'charge':float(ch),'energy':float(met['energy_kwh']),'point':point,'blind':blind})

def window_candidates():
 out=[]
 for p in q.POINTS:
  one=q.q3._relay_flight_time_min(q.POINTS[p],q.gateway,q.relay_spec)/2;fl,_=q.relay_flight(q.POINTS[p])
  for a in range(10,231,5):
   for d in range(15,131,5):
    b=a+d;energy=fl+(q.relay_spec['hover_power_kw']+q.relay_spec['comm_power_kw'])*d/60
    if energy>q.relay_usable+1e-9:continue
    launch=a-one-float(q.relay_spec['prep_time_s'])/60-float(q.relay_spec['setup_time_s'])/60
    if launch < -1e-9:continue
    fit=[]
    for m in MISSIONS:
     if m['point']!=p:continue
     lo=min(x for x,y in m['blind']);hi=max(y for x,y in m['blind'])
     if a-lo<=b-hi+1e-9:fit.append(m['id'])
    if fit:
     ret=b+one+float(q.relay_spec['turnaround_time_s'])/60
     out.append({'point':p,'a':a,'b':b,'launch':launch,'return':ret,'energy':energy,'fit':fit})
 return out

W=window_candidates();print('windows',len(W),flush=True)

def solve(limit=120):
 model=cp_model.CpModel();H=int(360*S);starts={m['id']:model.NewIntVar(0,H,f's{m["id"]}') for m in MISSIONS};ends={m['id']:model.NewIntVar(0,H,f'e{m["id"]}') for m in MISSIONS}
 ints={t:[] for t in q.types};bats={t:[] for t in q.types};assigns={}
 for m in MISSIONS:
  d=int(math.ceil(m['dur']*S));c=int(math.ceil(m['charge']*S));model.Add(ends[m['id']]==starts[m['id']]+d);model.Add(starts[m['id']]+int(math.floor(m['off']*S))<=int(math.floor(m['deadline']*S)))
  ints[m['typ']].append(model.NewIntervalVar(starts[m['id']],d,ends[m['id']],f'i{m["id"]}'));bats[m['typ']].append(model.NewIntervalVar(starts[m['id']],d+c,ends[m['id']]+c,f'b{m["id"]}'))
  if m['point']:
   eligible=[]
   lo=min(x for x,y in m['blind']);hi=max(y for x,y in m['blind'])
   for wi,w in enumerate(W):
    if m['id'] not in w['fit'] or w['point']!=m['point']:continue
    v=model.NewBoolVar(f'y{m["id"]}_{wi}');assigns[(m['id'],wi)]=v;eligible.append(v)
    model.Add(starts[m['id']]>=int(math.ceil((w['a']-lo)*S))).OnlyEnforceIf(v);model.Add(starts[m['id']]<=int(math.floor((w['b']-hi)*S))).OnlyEnforceIf(v)
   if not eligible:return None
   model.AddExactlyOne(eligible)
 for typ,p in q.types.items():model.AddCumulative(ints[typ],[1]*len(ints[typ]),int(p['count']));model.AddCumulative(bats[typ],[1]*len(bats[typ]),int(p['battery_count']))
 xrelay=[];sel=[]
 for wi,w in enumerate(W):
  uses=[v for (mi,j),v in assigns.items() if j==wi]
  if not uses:continue
  z=model.NewBoolVar(f'z{wi}');sel.append((wi,z))
  model.AddMaxEquality(z,uses)
  xr=[]
  for r in range(2):
   x=model.NewBoolVar(f'x{wi}_{r}');xr.append(x);model.Add(x<=z)
  model.Add(sum(xr)==z);xrelay.append((wi,w,xr))
 model.Add(sum(z for wi,z in sel)<=6)
 for r in range(2):
  rr=[]
  for wi,w,xr in xrelay:
   st=int(math.ceil(w['launch']*S));dur=int(math.ceil((w['return']-w['launch'])*S));rr.append(model.NewOptionalIntervalVar(st,dur,st+dur,xr[r],f'r{r}_{wi}'))
  model.AddNoOverlap(rr)
 makespan=model.NewIntVar(0,H,'makespan');model.AddMaxEquality(makespan,list(ends.values()));model.Minimize(makespan*1000+sum(z for wi,z in sel)*10)
 solver=cp_model.CpSolver();solver.parameters.max_time_in_seconds=limit;solver.parameters.num_search_workers=8;status=solver.Solve(model)
 if status not in (cp_model.FEASIBLE,cp_model.OPTIMAL):print('status',solver.StatusName(status));return None
 rows=[]
 for m in MISSIONS:
  st=solver.Value(starts[m['id']])/S;en=solver.Value(ends[m['id']])/S;x=dict(m);x.update(start_min=st,end_min=en,delivery_min=st+m['off']);rows.append(x)
 relay=[]
 for wi,w,xr in xrelay:
  z=next(z for k,z in sel if k==wi)
  if solver.Value(z):relay.append(dict(w,relay_id='R01' if solver.Value(xr[0]) else 'R02'))
 return rows,relay

if __name__=='__main__':
 sol=solve(180);print('solution',bool(sol))
 if sol:
  rows,relay=sol;print('relay',[(x['point'],x['a'],x['b'],x['relay_id'],round(x['energy'],3)) for x in relay]);print('makespan',max(x['end_min'] for x in rows),'joint',max([max(x['end_min'] for x in rows)]+[x['return'] for x in relay]));pd.DataFrame(rows).to_excel(ROOT/'解题-gpt'/'结果'/'问题三_运输调度_联合窗候选.xlsx',index=False);pd.DataFrame(relay).to_excel(ROOT/'解题-gpt'/'结果'/'问题三_中继调度_联合窗候选.xlsx',index=False)
