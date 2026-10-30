"""Create a distributable containing source only, never runtime/private state."""
import hashlib,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
output=ROOT.parent/'windows-agent-source.zip'
files=[]
for folder in ('localagent','tests'):
    files.extend(p for p in (ROOT/folder).glob('*.py'))
for pattern in ('*.py','*.ps1','*.md','requirements*.txt','pytest.ini','config.json','.gitignore'):
    files.extend(ROOT.glob(pattern))
files=sorted(set(files))
with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
    for p in files:z.write(p,str(Path('windows-agent')/p.relative_to(ROOT)))
with zipfile.ZipFile(output) as z:
    assert z.testzip() is None
    assert not any(any(part in n.split('/') for part in ('data','logs','inbox','models','projects','backups','artifacts','resumes','.venv')) for n in z.namelist())
(output.with_suffix('.sha256')).write_text(hashlib.sha256(output.read_bytes()).hexdigest()+'  '+output.name+'\n','utf-8')
print(output)
print('Files:',len(files),'Size:',output.stat().st_size,'CRC: OK')
