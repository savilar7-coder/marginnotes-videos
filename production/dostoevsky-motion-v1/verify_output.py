from pathlib import Path
import hashlib,json
from datetime import datetime,timezone
p=Path(__file__).resolve().parent/'scene.mp4'
assert p.is_file() and p.stat().st_size>1000,'No nonempty scene output'
receipt={'status':'ENCODER_COMPLETED_AWAITING_LOCAL_MEDIA_AND_VISUAL_CHECKS','created_utc':datetime.now(timezone.utc).isoformat(),'file':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'expected_seconds':6,'expected_frames':180,'audio':'intentionally silent','motion':'one eased anchored-cuff hand turn; no camera movement or loop','actual_duration_verified':False,'visually_reviewed':False}
(p.parent/'output-receipt.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt,indent=2))
