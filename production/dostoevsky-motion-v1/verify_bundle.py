from pathlib import Path
import hashlib,json,platform,subprocess
from importlib.metadata import version

root=Path(__file__).resolve().parent
manifest=json.loads((root/'input-manifest.json').read_text())
for item in manifest['files']:
    p=root/item['path']
    assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256'],item['path']
mem={line.split(':')[0]:int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith(('MemTotal:','MemAvailable:'))}
assert mem['MemAvailable']>=4*1024*1024,'Less than 4 GiB available on remote runner'
env={'execution':'remote standard Ubuntu CPU runner','free_system_ram_gib':mem['MemAvailable']/1024/1024,'total_system_ram_gib':mem['MemTotal']/1024/1024,'python':platform.python_version(),'packages':{n:version(n) for n in ['torch','numpy','pillow']},'cuda_requested':False,'input_hashes_verified':len(manifest['files']),'source_renderer_sha256':manifest['original_renderer_sha256']}
(root/'environment.json').write_text(json.dumps(env,indent=2))
print(json.dumps(env,indent=2))
