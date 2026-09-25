"""Run the delivered solver pipeline only inside a disposable audit copy."""
from pathlib import Path
import shutil
import subprocess
import sys
import time
import json
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
RUN=HERE/'reproduction'
RUN.mkdir(exist_ok=True)
(RUN/'.gitignore').write_text('*\n',encoding='utf-8')
shutil.copytree(ROOT/'src',RUN/'src',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
scripts=['solve_problem1_18trips.py','solve_problem2_optimized.py','solve_problem2_lns.py',
         'solve_problem3_relay.py','solve_problem4_fixed.py']
for name in scripts:shutil.copy2(ROOT/name,RUN/name)
for p in (ROOT/'数据').rglob('*'):
    if p.is_file() and (p.suffix=='.xlsx' or p.name.endswith('DEM.mat')):
        dest=RUN/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
results=[]
for name in [scripts[0],scripts[2],scripts[3],scripts[4]]:
    begin=time.monotonic()
    with (HERE/'evidence'/f'reproduce_{Path(name).stem}.log').open('w',encoding='utf-8') as log:
        try:
            proc=subprocess.run([sys.executable,'-X','utf8',name],cwd=RUN,stdout=log,stderr=subprocess.STDOUT,timeout=480)
            result=dict(script=name,exit_code=proc.returncode,seconds=time.monotonic()-begin)
        except subprocess.TimeoutExpired:
            result=dict(script=name,timeout=True,seconds=time.monotonic()-begin)
    results.append(result)
    print(json.dumps(result),flush=True)
    (HERE/'evidence'/'reproduction_status.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    if result.get('exit_code',1)!=0:break
