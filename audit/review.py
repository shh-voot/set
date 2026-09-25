"""Portable, read-only-to-project review runner for the two frozen revisions.

Uses git archive, never checkout/reset/stash. All replay writes stay in
audit/.runs/<unique run>/, including writes made by the original solvers.
Run with a separately created Conda environment. No packages are installed here.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / 'audit'
ROUNDS = {
    '1': ('ea5e0fb57065ad843b52f9e9e3ebdbe42582b0c1', '20260925'),
    '2': ('e94e1cc70b6f342282eaa9e7d2b15aa84065e381', '20260925_update'),
}
SOLVERS = {'solve_problem1_18trips.py', 'solve_problem2_optimized.py',
           'solve_problem2_lns.py', 'solve_problem3_relay.py', 'solve_problem4_fixed.py'}


def git(*args):
    return subprocess.check_output(['git', '-c', 'safe.directory=' + ROOT.as_posix(), *args], cwd=ROOT)


def wanted(path):
    p = PurePosixPath(path)
    if path in SOLVERS:
        return True
    if path.startswith('src/'):
        return p.suffix == '.py'
    if path.startswith('数据/'):
        return p.suffix == '.xlsx' or p.name.endswith('DEM.mat')
    if path.startswith(('结果/', '解题-gpt/结果/')):
        return p.suffix in ('.xlsx', '.json') and len(p.parts) <= 3
    if path.startswith(('解题-gpt/代码/', '解题-gpt/问题2优化/', '解题-gpt/问题2优化claude/')):
        return p.suffix in ('.py', '.xlsx', '.json', '.csv')
    return False


def snapshot(revision, dest):
    names = git('ls-tree', '-r', '-z', '--name-only', revision).decode('utf-8').split('\0')
    names = [n for n in names if n and wanted(n)]
    archive = git('archive', '--format=tar', revision, '--', *names)
    dest.mkdir(parents=True)
    # Explicit extraction avoids links, traversal, or archive-controlled writes.
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:') as tar:
        for member in tar:
            rel = PurePosixPath(member.name)
            if rel.is_absolute() or '..' in rel.parts or ':' in member.name or '\\' in member.name:
                raise ValueError('Unsafe archive entry: ' + member.name)
            target = dest.joinpath(*rel.parts)
            if not target.resolve().is_relative_to(dest.resolve()):
                raise ValueError('Archive entry outside snapshot: ' + member.name)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as source, target.open('wb') as output:
                    shutil.copyfileobj(source, output)
            else:
                raise ValueError('Unsupported archive entry: ' + member.name)
    return len(names)


def verify():
    data = json.loads((AUDIT / 'MANIFEST.json').read_text(encoding='utf-8'))
    errors = []
    for record in data['files']:
        path = AUDIT / record['path']
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        if actual != record['sha256']:
            errors.append(record['path'])
    print(json.dumps({'manifest_files': len(data['files']), 'mismatches': errors}, ensure_ascii=False))
    return 1 if errors else 0


def check_expectations(out, round_id):
    d = json.loads((out/'audit_summary.json').read_text(encoding='utf-8'))
    expected = {'1': (45, 0, 28, 28), '2': (43, 3, 23, 25)}[round_id]
    actual = (d['q2']['missions'], d['q3']['load_violations'],
              d['q4']['2']['hard_late_count'], d['q4']['3']['hard_late_count'])
    checks = {'q2_count_q3_overload_q4_hard_late': actual == expected,
              'q1_unique_80': d['q1']['unique_boxes'] == 80,
              'q2_unique_80': d['q2']['unique_boxes'] == 80,
              'q3_unique_80': d['q3']['unique_boxes'] == 80,
              'two_relays_exceed_component': all(r['hover_alone_exceeds_component'] for r in d['relay_endurance'])}
    target = out/'targeted_checks.json'
    if target.exists():
        t = json.loads(target.read_text(encoding='utf-8'))
        checks['four_endpoint_failures'] = t['endpoint_fail_areas'] == ['S003','S004','S008','S014']
    addition = out/'additions_summary.json'
    if addition.exists():
        a = json.loads(addition.read_text(encoding='utf-8'))
        checks['cp_accepts_late_example'] = (a['cp_truncation_lateness']['success'] and
                                            not a['cp_truncation_lateness']['missions'][0]['on_time'])
        checks['cp_real_overlap'] = a['cp_truncation_overlap']['actual_uav_overlap_min'] > 0.08
        checks['alns_saved_candidate_80'] = a['candidates']['ALNS交付']['unique_count'] == 80
    return {'checks': checks, 'expected': expected, 'actual': actual, 'passed': all(checks.values())}


def run(round_ids, full):
    modules = ['numpy','pandas','scipy','openpyxl'] + (['ortools'] if full and '2' in round_ids else [])
    missing = [m for m in modules if importlib.util.find_spec(m) is None]
    if missing:
        raise RuntimeError('Missing audit dependencies: ' + ', '.join(missing) + '; see audit/README.md')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid.uuid4().hex[:8]
    run_dir = AUDIT/'.runs'/stamp
    run_dir.mkdir(parents=True)
    status = {'run_dir': str(run_dir), 'full': full, 'rounds': []}
    for round_id in round_ids:
        revision, folder = ROUNDS[round_id]
        dest = run_dir/('round'+round_id)
        count = snapshot(revision, dest)
        scripts = dest/'audit'/folder
        scripts.mkdir(parents=True)
        for p in (AUDIT/folder).glob('*.py'):
            shutil.copy2(p, scripts/p.name)
        (scripts/'evidence').mkdir()
        jobs = ['check_results.py']
        if full:
            jobs += (['reproduce.py','targeted_checks.py'] if round_id == '1' else
                     ['reproduce_update.py','run_extras.py','targeted_checks.py','check_additions.py'])
        record = {'round': round_id, 'revision': revision, 'snapshot_files': count, 'commands': []}
        print('Round ' + round_id + ' | ' + revision[:7] + ' | isolated snapshot ready', flush=True)
        for name in jobs:
            print('  Running ' + name, flush=True)
            with (scripts/'evidence'/('runner_'+name+'.log')).open('w',encoding='utf-8') as log:
                process = subprocess.run([sys.executable, '-X', 'utf8', str(scripts/name)],
                                         cwd=dest, stdout=log, stderr=subprocess.STDOUT, timeout=900)
            record['commands'].append({'script': name, 'exit_code': process.returncode})
            if process.returncode:
                record['error'] = 'See ' + str(scripts/'evidence'/('runner_'+name+'.log'))
                break
        if 'error' not in record:
            record['expectations'] = check_expectations(scripts/'evidence',round_id)
        status['rounds'].append(record)
        (run_dir/'run_summary.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(record,ensure_ascii=False),flush=True)
    okay = all(r.get('expectations',{}).get('passed',False) for r in status['rounds'])
    print('Replay ' + ('completed' if okay else 'needs inspection') + ': ' + str(run_dir/'run_summary.json'))
    return 0 if okay else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['verify','run'])
    parser.add_argument('--round',choices=['1','2','all'],default='all')
    parser.add_argument('--full',action='store_true',help='Also replay original solver pipelines and new experiment checks')
    args=parser.parse_args()
    if args.action == 'verify':
        return verify()
    return run(['1','2'] if args.round == 'all' else [args.round],args.full)


if __name__ == '__main__':
    raise SystemExit(main())
