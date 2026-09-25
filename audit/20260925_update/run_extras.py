from pathlib import Path
import os,sys,subprocess,json,time
HERE=Path(__file__).resolve().parent;RUN=HERE/'reproduction';E=HERE/'evidence'
(RUN/'结果').mkdir(exist_ok=True)
env=dict(os.environ);env['PYTHONPATH']=str(RUN);env.pop('P2_BEAM_WIDTH',None)
env['P2_ALNS_SEED']='20260926';env['P2_ALNS_ITER']='250'
status=[]
for name,script in [('root_readme_q2_retry','solve_problem2_lns.py'),
                    ('alns250','解题-gpt/问题2优化/代码/optimize_alns.py'),
                    ('alns_team_validator','解题-gpt/问题2优化/代码/validate_candidate.py')]:
    begin=time.monotonic()
    with (E/(name+'.log')).open('w',encoding='utf8') as out:
        try:
            proc=subprocess.run([sys.executable,'-X','utf8',script],cwd=RUN,env=env,stdout=out,stderr=subprocess.STDOUT,timeout=240)
            r=dict(job=name,exit_code=proc.returncode,seconds=time.monotonic()-begin)
        except subprocess.TimeoutExpired:r=dict(job=name,timeout=True,seconds=time.monotonic()-begin)
    status.append(r);(E/'extra_run_status.json').write_text(json.dumps(status,indent=2),encoding='utf8');print(json.dumps(r),flush=True)
