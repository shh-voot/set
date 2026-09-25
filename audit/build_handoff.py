"""Build portable links and a manifest for publication; does not touch solution files."""
from pathlib import Path
import hashlib,json,posixpath,re,subprocess
from urllib.parse import quote

ROOT=Path(__file__).resolve().parents[1];AUDIT=ROOT/'audit'
rounds={'20260925':'ea5e0fb57065ad843b52f9e9e3ebdbe42582b0c1',
        '20260925_update':'e94e1cc70b6f342282eaa9e7d2b15aa84065e381'}


def normalize_links():
    for folder,rev in rounds.items():
        for p in (AUDIT/folder).glob('*.md'):
            def replace(m):
                rel=m.group(1);line=m.group(2)
                if rel.startswith('audit/'):
                    target=posixpath.relpath(rel,p.parent.relative_to(ROOT).as_posix())
                    return ']('+target+')'
                return '](https://github.com/shh-voot/set/blob/'+rev+'/'+quote(rel,safe='/')+('#L'+line if line else '')+')'
            value=p.read_text(encoding='utf8')
            updated=re.sub(r'\]\(E:/workspace-e/set/(.*?)(?::(\d+))?\)',replace,value)
            if updated!=value:p.write_text(updated,encoding='utf8')


def publish_files():
    # git check-ignore is applied after audit/.gitignore's explicit log exception.
    git=['git','-c','safe.directory='+ROOT.as_posix()]
    paths=[]
    for p in AUDIT.rglob('*'):
        if not p.is_file() or p.name=='MANIFEST.json':continue
        rel=p.relative_to(AUDIT)
        if any(x in ('.runs','reproduction','__pycache__','docx_media') for x in rel.parts):continue
        paths.append(p)
    encoded=b'\0'.join(p.relative_to(ROOT).as_posix().encode('utf8') for p in paths)+b'\0'
    proc=subprocess.run(git+['check-ignore','--stdin','-z'],cwd=ROOT,input=encoded,stdout=subprocess.PIPE,check=False)
    if proc.returncode not in (0,1):raise RuntimeError('git check-ignore failed')
    ignored=set(proc.stdout.decode('utf8').split('\0'))
    return [p for p in paths if p.relative_to(ROOT).as_posix() not in ignored]


if __name__=='__main__':
    normalize_links()
    issue_data=json.loads((AUDIT/'issues.json').read_text(encoding='utf8'))
    lines=['# 合并问题清单','',
           '对应第一轮 `ea5e0fb` 与第二轮 `e94e1cc`。这里的“最新”指第二轮被审查提交，不表示后续提交未经检查也有相同问题。',
           '', 'P0：影响模型或方案可行性；P1：影响完整性、溯源或复现；P2：表达和维护问题。状态描述是审计结论，并非已修复声明。',
           '', '完整上下文见 [审计总览](README.md)、[第一轮报告](20260925/工作质量与公式溯源审查报告.md) 和 [补充报告](20260925_update/最新提交补充评估报告.md)。',
           '', '| 编号 | 级别 | 问题 |', '|---|---|---|']
    for issue in issue_data['issues']:
        lines.append('| '+issue['id']+' | '+issue['priority']+' | ['+issue['title']+'](#'+issue['id'].lower()+') |')
    for issue in issue_data['issues']:
        lines+=['','<a id="'+issue['id'].lower()+'"></a>','',
                '## '+issue['id']+' · '+issue['title'],'',
                '- **级别：** '+issue['priority'],
                '- **第一轮：** '+issue['first_round'],
                '- **第二轮：** '+issue['latest_status'],
                '- **证据说明：** '+issue['detail'],
                '- **核验材料：** '+'；'.join('['+PurePath.rsplit('/',1)[-1]+']('+PurePath+')' for PurePath in issue['evidence']),
                '- **关闭条件：** '+issue['acceptance']]
    (AUDIT/'ISSUES.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    files=[{'path':p.relative_to(AUDIT).as_posix(),'bytes':p.stat().st_size,
            'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(publish_files())]
    manifest={'schema':1,'reviewed_revisions':rounds,'files':files}
    (AUDIT/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'files':len(files),'bytes':sum(x['bytes'] for x in files)},ensure_ascii=False))
