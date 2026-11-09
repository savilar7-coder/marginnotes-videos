"""Pre-render asset and export checks; standard library only, no GPU allocation."""
from pathlib import Path
import math

class RenderInputError(ValueError):
    pass

def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise RenderInputError(f"{label} must be a finite number")
    return float(value)

def _pair(value, label):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise RenderInputError(f"{label} must contain two finite numbers")
    return [_number(v, label) for v in value]

def validate_acting(shot, label):
    acting = shot.get("acting")
    if acting is None:
        return
    if not isinstance(acting, dict) or not shot.get("fig") or shot.get("clip"):
        raise RenderInputError(f"{label} acting requires a layered figure shot")
    kind = acting.get("kind")
    defaults = {
        "myshkin_answer": ([4.4, 5.9], "neck_blend", [350, 455], [235, 390], 9),
        "phone_lift": ([0.8, 2.4], "forearm_blend", [1450, 1672], [1672, 560], 16),
        "seated_lean": (None, "seat_blend", None, None, None),
    }
    if kind not in defaults:
        raise RenderInputError(f"{label} unknown acting kind: {kind}")
    interval, blend_key, blend, pivot, angle = defaults[kind]
    begin, finish = _pair(acting.get("interval", interval), f"{label} acting interval")
    if not 0 <= begin < finish <= shot["t1"] - shot["t0"]:
        raise RenderInputError(f"{label} acting interval must be positive and fit inside the shot")
    a, b = _pair(acting.get(blend_key, blend), f"{label} {blend_key}")
    if b <= a:
        raise RenderInputError(f"{label} {blend_key} must have positive width")
    _pair(acting.get("pivot", pivot), f"{label} acting pivot")
    _number(acting.get("angle_degrees", angle), f"{label} acting angle")

def validate_inputs(timeline, asset_root, start, end):
    duration = _number(timeline.get("dur"), "duration")
    start = _number(start, "start")
    end = _number(end, "end")
    fps = _number(timeline.get("fps", 30), "fps")
    if duration <= 0 or fps <= 0 or not 0 <= start < end <= duration:
        raise RenderInputError("Render range must satisfy 0 <= start < end <= duration; fps must be positive")
    shots = timeline.get("shots")
    if not isinstance(shots, list) or not shots:
        raise RenderInputError("Timeline has no shots")
    selected = []
    previous_start = -1.0
    for i, shot in enumerate(shots):
        if not isinstance(shot, dict):
            raise RenderInputError(f"Shot {i} must be an object")
        a = _number(shot.get("t0"), f"shot {i} start")
        b = _number(shot.get("t1"), f"shot {i} end")
        if not 0 <= a < b <= duration + 1/fps or a < previous_start:
            raise RenderInputError(f"Shot {i} has an invalid or out-of-order interval")
        previous_start = a
        if a < end and b > start:
            selected.append(i)
    if not selected:
        raise RenderInputError("No shot covers the requested range")
    covered = start
    for i in selected:
        shot = shots[i]
        if shot["t0"] > covered + 1/fps:
            raise RenderInputError(f"Uncovered timeline near {covered:.3f}s")
        covered = max(covered, shot["t1"])
    if covered < end - 1/fps:
        raise RenderInputError(f"Uncovered timeline after {covered:.3f}s")
    required_indices = set(selected)
    for i in selected:
        if i and shots[i].get("xfade", 0) and start < shots[i]["t0"] + shots[i]["xfade"]:
            required_indices.add(i - 1)
    root = Path(asset_root)
    required = set()
    for i in sorted(required_indices):
        shot = shots[i]
        validate_acting(shot, f"shot {i}")
        if shot.get("clip"):
            clip = Path(shot["clip"])
            required.add(clip if clip.is_absolute() else root / clip)
        else:
            plate = shot.get("plate")
            if not isinstance(plate, str) or not plate:
                raise RenderInputError(f"Shot {i} has no plate or clip")
            required.add(root / "plates" / f"{plate}.png")
            if shot.get("fig"):
                required.add(root / "plates" / f"{plate}_bg.png")
                required.add(root / "layers" / f"{plate}.png")
    missing = sorted(str(p) for p in required if not p.is_file() or p.stat().st_size == 0)
    if missing:
        raise RenderInputError(f"Missing or empty required assets ({len(missing)}):\n" + "\n".join(missing))
    return {"selected_shots": len(selected), "required_assets": len(required), "start": start, "end": end}

def finish_encoder(process, output):
    try:
        process.stdin.close()
    except BrokenPipeError:
        pass
    code = process.wait()
    if code != 0:
        raise RuntimeError(f"Encoder failed with exit code {code}; any partial output is not a finished render: {output}")
    path = Path(output)
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"Encoder returned success without a nonempty output: {output}")
