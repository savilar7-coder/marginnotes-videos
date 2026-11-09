"""Bounded probe transport through job logs; no artifact/cache/repository write."""
from pathlib import Path
import base64
import hashlib
import json
import struct
import sys

folder = Path(sys.argv[1])
expected = [f'probe-{t:04.2f}.png' for t in (0,1.55,1.98,2.55,3.12,3.95,5.5)]
assert sorted(p.name for p in folder.glob('probe-*.png'))==sorted(expected)
for name in expected:
    raw = (folder/name).read_bytes()
    assert raw[:8]==b'\x89PNG\r\n\x1a\n'
    assert struct.unpack('>II',raw[16:24])==(960,540)
payloads = []
for name in ('contact-sheet.jpg','contact-sheet.json','build-receipt.json'):
    raw = (folder/name).read_bytes()
    if name.endswith('.jpg'):
        assert raw[:2]==b'\xff\xd8' and raw[-2:]==b'\xff\xd9'
        assert len(raw)<=500*1024
    else:
        assert len(raw)<=16*1024
    payloads.append((name,raw))
assert sum(len(raw) for _,raw in payloads)<=532*1024, 'Probe log payload exceeds 532 KiB cap.'
for name,raw in payloads:
    encoded = base64.b64encode(raw).decode('ascii')
    chunks = [encoded[i:i+12000] for i in range(0,len(encoded),12000)]
    meta = {'name':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'chunks':len(chunks)}
    print('CUP_PROBE_META '+json.dumps(meta,separators=(',',':')))
    for i,chunk in enumerate(chunks):
        print(f'CUP_PROBE_DATA {name} {i} {chunk}')
    print('CUP_PROBE_END '+name)
print('CUP_PROBE_COMPLETE 3')
