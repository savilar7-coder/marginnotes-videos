"""Read-only gate for a standard public GitHub-hosted CPU runner."""
import json
import os
from pathlib import Path
import platform
import re
from datetime import datetime, timezone


def resource_gate(inside_blender=False):
    expected = os.environ.get('EXPECTED_SHA','')
    assert re.fullmatch('[0-9a-f]{40}',expected), 'Expected exact reviewed commit required.'
    assert os.environ.get('GITHUB_SHA')==expected, 'Dispatch ref changed.'
    assert os.environ.get('GITHUB_ACTIONS')=='true', 'GitHub Actions only.'
    assert os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted', 'Hosted standard runner required.'
    assert os.environ.get('GITHUB_REPOSITORY')=='savilar7-coder/marginnotes-videos'
    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    assert event['repository']['private'] is False, 'Private repo is not the free public route.'
    assert platform.system()=='Linux' and platform.machine()=='x86_64'
    info = dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
    available = int(info['MemAvailable'].split()[0])*1024
    busy = []
    for path in Path('/proc').iterdir():
        if not path.name.isdigit() or int(path.name)==os.getpid():
            continue
        try:
            name = (path/'comm').read_text().strip()
            if name in ('blender','ffmpeg'):
                busy.append({'pid':int(path.name),'name':name})
        except (FileNotFoundError,PermissionError,ProcessLookupError):
            pass
    return {'allowed':available>=4*1024**3 and not busy,
            'execution':'standard public GitHub ubuntu-24.04 CPU job',
            'free_system_ram_gib':round(available/1024**3,3),'minimum_free_gib':4,
            'other_heavy_processes':busy,'inside_blender':inside_blender,
            'gpu_required':False,'cuda_requested':False,'cycles_device':'CPU',
            'expected_commit':expected,'time':datetime.now(timezone.utc).isoformat()}


if __name__=='__main__':
    result = resource_gate()
    print(json.dumps(result,indent=2))
    assert result['allowed'], 'Resource gate closed.'
