"""Validate portable Markdown links, issue evidence, syntax, and manifest coverage."""
from pathlib import Path
from urllib.parse import unquote,urlparse
import json,re,subprocess
ROOT=Path(__file__).resolve().parents[1];A=ROOT/'audit'
git=['git','-c','safe.directory='+ROOT.as_posix()]
manifest=json.loads((A/'MANIFEST.json').read_text(encoding='utf8'))
published={r['path'] for r in manifest['files']}|{'MANIFEST.json'}
errors=[];external_code=set();links=0
for rel in sorted(published):
    p=A/rel
    if p.suffix=='.py':compile(p.read_text(encoding='utf8'),str(p),'exec')
    if p.suffix!='.md':continue
    for target in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf8')):
        links+=1
        if re.match(r'^[A-Za-z]:[/\\]',target):errors.append((rel,'absolute local link',target));continue
        if target.startswith('https://github.com/shh-voot/set/blob/'):
            parsed=urlparse(target);parts=unquote(parsed.path).split('/');rev=parts[4];path='/'.join(parts[5:])
            external_code.add((rev,path,parsed.fragment));continue
        if target.startswith(('https:','http:','#')):continue
        clean=unquote(target.split('#',1)[0]);dest=(p.parent/clean).resolve()
        if not dest.exists():errors.append((rel,'missing target',target));continue
        if dest.is_file() and dest.is_relative_to(A.resolve()) and dest.relative_to(A.resolve()).as_posix() not in published:
            errors.append((rel,'target not in publication manifest',target))
for rev,path,fragment in external_code:
    proc=subprocess.run(git+['show',rev+':'+path],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if proc.returncode:errors.append(('source link','missing Git blob',rev+':'+path));continue
    if fragment.startswith('L') and fragment[1:].isdigit():
        if int(fragment[1:])>len(proc.stdout.splitlines()):errors.append(('source link','line outside file',path+'#'+fragment))
issues=json.loads((A/'issues.json').read_text(encoding='utf8'))['issues']
for issue in issues:
    for evidence in issue['evidence']:
        if evidence not in published:errors.append((issue['id'],'evidence not published',evidence))
print(json.dumps({'markdown_links':links,'pinned_source_links':len(external_code),'issues':len(issues),'errors':errors},ensure_ascii=False,indent=2))
raise SystemExit(1 if errors else 0)
