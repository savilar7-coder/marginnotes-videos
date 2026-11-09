"""Validate exact prepared scripts before launching Blender."""
from pathlib import Path
import ast
import hashlib
import json

HERE = Path(__file__).resolve().parent
manifest = json.loads((HERE/'input-manifest.json').read_text())
expected = manifest['files']
actual = {p.name for p in HERE.glob('*.py')}
assert actual==set(expected),(actual,set(expected))
for name,digest in expected.items():
    p = HERE/name
    assert hashlib.sha256(p.read_bytes()).hexdigest()==digest,name
    ast.parse(p.read_text(encoding='utf-8'),filename=name)
source = (HERE/'build_cup_scene_cpu.py').read_text()
assert "choices=['probes']" in source
assert "scene.cycles.device = 'CPU'" in source
assert "bpy.ops.render.render(animation=True)" not in source
print('Verified '+str(len(expected))+' exact source files; seven-probe CPU-only branch.')
