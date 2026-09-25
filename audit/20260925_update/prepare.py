from pathlib import Path
import subprocess,json,hashlib,zipfile,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OLD=ROOT/'audit/20260925'
E=HERE/'evidence';E.mkdir(exist_ok=True)
for name in ('extract_evidence.py','check_results.py','targeted_checks.py'):
    s=(OLD/name).read_text(encoding='utf8')
    if name=='extract_evidence.py':
        s=s.replace("['git','ls-files','-z']", "['git','-c','safe.directory='+ROOT.as_posix(),'ls-files','-z']")
    if name=='targeted_checks.py':
        s=s.replace("/'reproduction/结果'", "/'reproduction/解题-gpt/结果'")
    (HERE/name).write_text(s,encoding='utf8')
git=['git','-c','safe.directory='+ROOT.as_posix()]
paths=subprocess.check_output(git+['ls-files','-z'],cwd=ROOT).decode('utf8').split('\0')
manifest=[dict(path=p,sha256=hashlib.sha256((ROOT/p).read_bytes()).hexdigest()) for p in paths if p]
(E/'post_pull_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
counts={}
lines=subprocess.check_output(git+['diff','--name-status','-z','ea5e0fb..HEAD'],cwd=ROOT).decode('utf8').split('\0')
for x in lines:
    if x in ('A','M','D') or x.startswith('R100'): counts[x]=counts.get(x,0)+1
(E/'change_counts.json').write_text(json.dumps(counts),encoding='utf8')
# Keep complete XML and rendered text from every new paper docx, including math.
ns='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
mn='{http://schemas.openxmlformats.org/officeDocument/2006/math}'
for p in (ROOT/'解题-gpt/论文').glob('*.docx'):
    with zipfile.ZipFile(p) as z:
        raw=z.read('word/document.xml');tree=ET.fromstring(raw)
        paragraphs=[]
        for i,para in enumerate(tree.iter(ns+'p'),1):
            text=''.join(e.text or '' for e in para.iter() if e.tag in (ns+'t',mn+'t'))
            if text.strip():paragraphs.append(f'P{i:04d}: {text}')
        out=E/'new_papers';out.mkdir(exist_ok=True)
        (out/(p.stem+'.txt')).write_text('\n'.join(paragraphs),encoding='utf8')
        (out/(p.stem+'.xml')).write_bytes(raw)
print(json.dumps({'tracked':len(manifest),'change_counts':counts},ensure_ascii=False))
