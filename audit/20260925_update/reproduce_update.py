"""Run the new delivery without editing sources, inside an isolated copy."""
from pathlib import Path
import shutil,subprocess,sys,time,json,os
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
RUN=HERE/'reproduction'; E=HERE/'evidence'
RUN.mkdir(exist_ok=True);(RUN/'.gitignore').write_text('*\n',encoding='utf8')
shutil.copytree(ROOT/'src',RUN/'src',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
for name in ('solve_problem1_18trips.py','solve_problem2_optimized.py','solve_problem2_lns.py','solve_problem3_relay.py','solve_problem4_fixed.py'):
    shutil.copy2(ROOT/name,RUN/name)
for folder in ('代码','问题2优化','问题2优化claude'):
    shutil.copytree(ROOT/'解题-gpt'/folder,RUN/'解题-gpt'/folder,dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__','*.png','*.xlsx'))
for p in (ROOT/'数据').rglob('*'):
    if p.is_file() and (p.suffix=='.xlsx' or p.name.endswith('DEM.mat')):
        dest=RUN/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
(RUN/'解题-gpt/结果').mkdir(exist_ok=True)
env=dict(os.environ);env['PYTHONPATH']=str(RUN);env.pop('P2_BEAM_WIDTH',None)
jobs=[('delivery_q1','解题-gpt/代码/solve_problem1_18trips.py'),
      ('delivery_q2','解题-gpt/代码/solve_problem2_lns.py'),
      ('delivery_q3','解题-gpt/代码/solve_problem3_relay.py'),
      ('delivery_q4','解题-gpt/代码/solve_problem4_fixed.py'),
      ('root_readme_q2','solve_problem2_lns.py')]
status=[]
for name,script in jobs:
    t=time.monotonic()
    with (E/(name+'.log')).open('w',encoding='utf8') as log:
        try:
            p=subprocess.run([sys.executable,'-X','utf8',script],cwd=RUN,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180)
            r=dict(job=name,script=script,exit_code=p.returncode,seconds=time.monotonic()-t)
        except subprocess.TimeoutExpired:r=dict(job=name,timeout=True,seconds=time.monotonic()-t)
    status.append(r); print(json.dumps(r),flush=True)
    (E/'reproduction_status.json').write_text(json.dumps(status,indent=2),encoding='utf8')
