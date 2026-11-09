"""Original six-second kitchen acting test. Run only after launch preflight passes.

Example: blender --background --factory-startup --python build_cup_scene.py --
    --out PATH --mode probes --quality preview
No downloaded assets, external generation, narration or public publishing.
"""
import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from cup_motion import DURATION, FPS, pose
from cloud_preflight import resource_gate


def args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=HERE/'rendered')
    parser.add_argument('--mode', choices=['probes'], default='probes')
    parser.add_argument('--quality', choices=['preview'], default='preview')
    parser.add_argument('--engine', choices=['cycles'], default='cycles')
    return parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])


def make_contact_sheet(bpy, scene, folder):
    from array import array
    import hashlib
    times = (0, 1.55, 1.98, 2.55, 3.12, 3.95, 5.5)
    tile_w, tile_h, columns, rows = 320, 180, 4, 2
    width, height = tile_w*columns, tile_h*rows
    pixels = array('f', [0.035, 0.025, 0.02, 1.0])*(width*height)
    tiles = []
    for index, time in enumerate(times):
        path = folder/f'probe-{time:04.2f}.png'
        im = bpy.data.images.load(str(path), check_existing=False)
        im.scale(tile_w, tile_h)
        src = array('f', [0.0])*(tile_w*tile_h*4)
        im.pixels.foreach_get(src)
        col, row = index % columns, index // columns
        # Blender image buffers start at bottom left; manifest rows start at top.
        y0 = (rows-1-row)*tile_h
        for y in range(tile_h):
            dst_start = ((y0+y)*width+col*tile_w)*4
            src_start = y*tile_w*4
            pixels[dst_start:dst_start+tile_w*4] = src[src_start:src_start+tile_w*4]
        bpy.data.images.remove(im)
        tiles.append({'time':time,'column':col,'row_from_top':row,'source':path.name})
    atlas = bpy.data.images.new('Seven probes contact sheet', width=width, height=height, alpha=False)
    atlas.pixels.foreach_set(pixels)
    atlas.update()
    scene.render.image_settings.file_format = 'JPEG'
    scene.render.image_settings.color_mode = 'RGB'
    output = folder/'contact-sheet.jpg'
    for quality in (70, 50, 30):
        scene.render.image_settings.quality = quality
        atlas.save_render(str(output), scene=scene)
        if output.stat().st_size <= 500*1024:
            break
    assert output.stat().st_size <= 500*1024, 'Contact sheet exceeds 500 KiB.'
    data = {'status':'UNREVIEWED_PROBE_CONTACT_SHEET','width':width,'height':height,
            'tiles':tiles,'bytes':output.stat().st_size,'jpeg_quality':quality,
            'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
            'limits':'Seven sampled frames only; no continuous-motion or artistic approval.'}
    (folder/'contact-sheet.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
    return data


def main():
    opt = args()
    gate = resource_gate(inside_blender=True)
    if not gate['allowed']:
        raise RuntimeError('Resource gate closed: '+json.dumps(gate))
    import bpy
    from mathutils import Vector

    opt.out.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, int(DURATION*FPS)
    scene.render.fps = FPS
    scene.render.resolution_x, scene.render.resolution_y = (960, 540) if opt.quality == 'preview' else (1920, 1080)
    scene.render.resolution_percentage = 100
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 2
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.film_transparent = False
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 12
    scene.cycles.use_denoising = False
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.05
    scene.cycles.max_bounces = 3
    scene.cycles.diffuse_bounces = 2
    scene.cycles.glossy_bounces = 1
    scene.render.threads = 2
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    world = bpy.data.worlds.new('Warm room')
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.22, 0.17, 0.13, 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.55
    world.color = (0.12, 0.09, 0.07)

    def rgb(hex_color):
        vals = [int(hex_color[i:i+2], 16)/255 for i in (1, 3, 5)]
        return tuple(v/12.92 if v <= 0.04045 else ((v+0.055)/1.055)**2.4 for v in vals)+(1.0,)

    def material(name, color, grain=False):
        m = bpy.data.materials.new(name)
        m.diffuse_color = rgb(color)
        m.use_nodes = True
        tree = m.node_tree
        bsdf = tree.nodes.get('Principled BSDF')
        bsdf.inputs['Base Color'].default_value = rgb(color)
        bsdf.inputs['Roughness'].default_value = 1.0
        if grain:
            tex = tree.nodes.new('ShaderNodeTexNoise')
            tex.inputs['Scale'].default_value = 165.0
            tex.inputs['Detail'].default_value = 0.0
            ramp = tree.nodes.new('ShaderNodeValToRGB')
            ramp.color_ramp.elements[0].position = 0.32
            ramp.color_ramp.elements[0].color = rgb('#b47e63')
            ramp.color_ramp.elements[1].position = 0.58
            ramp.color_ramp.elements[1].color = rgb(color)
            tree.links.new(tex.outputs['Fac'], ramp.inputs['Fac'])
            tree.links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
        return m

    paper = material('Peach ceramic and paper', '#edbea0', True)
    ink = material('Charcoal ink', '#302a27')
    shade = material('Warm clay shadow', '#b47e63')
    light = material('Paper edge highlight', '#f6d6b9')
    skin = material('Hand peach with grain', '#edbea0', True)

    def empty(name):
        o = bpy.data.objects.new(name, None)
        scene.collection.objects.link(o)
        return o

    def cube(name, loc, scale, mat, bevel=0, parent=None):
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
        o = bpy.context.object
        o.name = name
        o.dimensions = scale
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        if bevel:
            mod = o.modifiers.new('Soft physical edge', 'BEVEL')
            mod.width, mod.segments = bevel, 3
        o.data.materials.append(mat)
        o.parent = parent
        return o

    def tube(name, points, radius, mat, parent=None):
        curve = bpy.data.curves.new(name, 'CURVE')
        curve.dimensions = '3D'
        curve.resolution_u = 12
        curve.bevel_depth = radius
        curve.bevel_resolution = 3
        curve.use_fill_caps = True
        spline = curve.splines.new('BEZIER')
        spline.bezier_points.add(len(points)-1)
        for p, co in zip(spline.bezier_points, points):
            p.co = co
            p.handle_left_type = p.handle_right_type = 'AUTO'
        o = bpy.data.objects.new(name, curve)
        scene.collection.objects.link(o)
        o.data.materials.append(mat)
        o.parent = parent
        return o

    def ellipsoid(name, loc, scale, mat, parent=None):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=1, location=loc)
        o = bpy.context.object
        o.name = name
        o.scale = scale
        o.data.materials.append(mat)
        o.parent = parent
        for p in o.data.polygons:
            p.use_smooth = True
        return o

    def lathe(name, profile, mat, parent=None, inner_mat=None, inner_start=999):
        n = 64
        verts = [(r*math.cos(2*math.pi*i/n), r*math.sin(2*math.pi*i/n), z) for r, z in profile for i in range(n)]
        faces = [(j*n+i, j*n+(i+1)%n, (j+1)*n+(i+1)%n, (j+1)*n+i) for j in range(len(profile)-1) for i in range(n)]
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(verts, [], faces)
        mesh.update()
        o = bpy.data.objects.new(name, mesh)
        scene.collection.objects.link(o)
        o.data.materials.append(mat)
        if inner_mat:
            o.data.materials.append(inner_mat)
        for i, poly in enumerate(mesh.polygons):
            poly.use_smooth = True
            if inner_mat and i//n >= inner_start:
                poly.material_index = 1
        o.parent = parent
        return o

    # Fixed room: source-layout continuity, simplified original geometry.
    cube('Counter surface', (0, 0.25, -0.11), (6.5, 4.0, 0.22), paper, .035)
    cube('Window night', (-0.3, 2.2, 1.85), (5.6, .10, 3.1), ink)
    for x in (-2.9, -.2, 2.4):
        cube('Window mullion', (x, 2.10, 1.85), (.065, .08, 3.15), paper)
    cube('Window sill', (-.2, 2.04, .35), (5.8, .30, .14), shade)
    for x, height in ((-2.5,.65),(-1.8,.9),(-.9,.5),(.3,.75),(1.2,.55),(1.8,.83)):
        cube('Night building', (x, 2.02, .65+height/2), (.45,.08,height), shade)
        for dz in (.2,.4):
            cube('Window light', (x-.08,1.97,.65+dz), (.045,.025,.06), light)
    cube('Sink dark basin', (-1.9,-.43,.008), (1.75,1.48,.018), ink, .18)
    tube('Sink border', [(-2.8,-1.2,.035),(-1.02,-1.2,.035),(-1.02,.35,.035),(-2.8,.35,.035),(-2.8,-1.2,.035)], .035, shade)
    tube('Faucet', [(-2.3,.65,.0),(-2.3,.65,1.65),(-2.3,.4,1.9),(-2.3,-.05,1.75),(-2.3,-.05,1.48)], .075, ink)
    plate = lathe('Empty plate', [(0,.025),(.57,.025),(.75,.07),(.79,.11),(.75,.13),(.55,.06),(0,.06)], paper)
    plate.location = (1.3,.70,0)
    phone = cube('Untouched face-down phone', (1.35,-.70,.055), (.70,1.20,.09), ink, .055)
    phone.rotation_euler.z = -.20
    for x,y in ((1.15,-.38),(1.34,-.38),(1.15,-.57)):
        ellipsoid('Phone rear lens', (x,y,.108), (.067,.067,.012), shade)
    # The cloth is thin enough that physical contact still uses counter z=0.
    # No cloth underneath the cup: avoids an unmodeled collision thickness.
    cube('Folded towel beside sink', (-.66,.25,.025), (.36,1.1,.04), shade,.02)

    cup_rig = empty('Cup transfer rig')
    hand_rig = empty('Hand transfer rig')
    cup = lathe('Hollow ceramic cup', [(0,-.39),(.31,-.39),(.33,-.34),(.42,.36),(.42,.39),(.35,.39),(.27,-.28),(0,-.28)], paper, cup_rig, ink, 5)
    tube('Left cup handle', [(-.34,0,.24),(-.66,0,.26),(-.78,0,.0),(-.65,0,-.26),(-.33,0,-.24)], .064, paper, cup_rig)
    lathe('Cup bottom foot', [(.20,-.39),(.27,-.39)], shade, cup_rig)

    # Body grip: thumb on the near side, four curled fingers around the far side.
    # Hand uses local cup coordinates and remains rigidly supported during transfer.
    palm = ellipsoid('Palm', (.65,.04,.06), (.26,.23,.13), skin, hand_rig)
    tube('Wrist', [(.78,.04,.04),(1.10,.03,.04),(1.44,.03,.04)], .13, skin, hand_rig)
    tube('Sleeve', [(1.27,.03,.04),(1.60,.03,.04),(3.0,.03,.04)], .19, ink, hand_rig)
    for x in (1.33,1.40):
        tube('Cuff seam', [(x,-.15,-.08),(x,-.17,.08),(x,-.03,.21),(x,.16,.08)], .012, shade, hand_rig)
    fingers = []
    # Cubic Bezier tubes retain three bend landmarks and rounded ends.
    # Contact tips lie close to the cup's sloping exterior; visual fit remains a review gate.
    for i in range(4):
        z = .22-i*.105
        finger_radius = .049 if i<3 else .043
        cup_radius_at_tip = .33+(.42-.33)*(z+.34)/.70
        tip_y = math.sqrt((cup_radius_at_tip+finger_radius-.006)**2-.10**2)
        pts = [(.67,.17,z),(.51,.36,z+.07),(.22,tip_y+.04,z+.06),(.10,tip_y,z)]
        o = tube(('Index','Middle','Ring','Little')[i]+' finger', pts, finger_radius, skin, hand_rig)
        fingers.append((o, 1))
        ellipsoid('Finger nail '+str(i), (.10,tip_y+finger_radius-.006,z), (.048,.012,.038), light, o)
    thumb = tube('Thumb', [(.70,-.08,.01),(.59,-.29,.13),(.37,-.40,.16),(.19,-.410,.13)], .067, skin, hand_rig)
    fingers.append((thumb,-1))
    ellipsoid('Thumb nail', (.20,-.469,.145), (.065,.012,.045), light, thumb)

    bpy.ops.object.camera_add(location=(4.2,-7.4,4.6))
    camera = bpy.context.object
    camera.name = 'Locked kitchen camera'
    camera.rotation_euler = (Vector((.15,.25,.7))-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = 4.75
    scene.camera = camera
    bpy.ops.object.light_add(type='AREA', location=(-2,-3,6))
    key = bpy.context.object
    key.name = 'Window key'
    key.data.energy = 700
    key.data.size = 4
    key.rotation_euler = (Vector((0,0,0))-key.location).to_track_quat('-Z','Y').to_euler()

    # Bake each display frame. A fixed camera makes the object's true change assessable.
    for frame in range(1, scene.frame_end+1):
        p = pose((frame-1)/FPS)
        for rig, prefix in ((cup_rig,'cup'),(hand_rig,'hand')):
            rig.location = p[prefix+'_location']
            rig.rotation_euler = (p[prefix+'_angle'],0,0)
            rig.keyframe_insert('location', frame=frame)
            rig.keyframe_insert('rotation_euler', frame=frame)
        for finger, side in fingers:
            finger.location.y = side*.16*p['finger_opening']
            finger.location.x = .10*p['finger_opening']
            finger.keyframe_insert('location', frame=frame)
    for label, t in [('Grip',1.55),('Lifted',1.98),('Inverted',3.12),('Set down',3.95),('Released',4.28)]:
        scene.timeline_markers.new(label, frame=round(t*FPS)+1)
    scene.frame_set(1)
    scene['status'] = 'UNREVIEWED ACTING TEST — not selected for release'
    scene['source_layout'] = 'local-cut1/plates/k1.png; cup rebuilt upright; phone/plate untouched'
    scene['film_start_seconds'] = 3.80
    blend = opt.out/'cup-turn-acting-test.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    receipt = {'status':'BUILT_NOT_VISUALLY_APPROVED','blender_version':bpy.app.version_string,
               'mode':opt.mode,'quality':opt.quality,'engine':scene.render.engine,'resource_gate':gate,
               'blend':str(blend),'seconds':DURATION,'frames':scene.frame_end,'audio':False}
    if opt.mode == 'probes':
        for time in (0,1.55,1.98,2.55,3.12,3.95,5.5):
            scene.frame_set(round(time*FPS)+1)
            scene.render.filepath = str(opt.out/f'probe-{time:04.2f}.png')
            bpy.ops.render.render(write_still=True)
        receipt['status'] = 'PROBES_RENDERED_NOT_VISUALLY_APPROVED'
    receipt['contact_sheet'] = make_contact_sheet(bpy, scene, opt.out)
    (opt.out/'build-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt,indent=2))


if __name__ == '__main__':
    main()
