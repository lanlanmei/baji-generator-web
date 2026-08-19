"""Executed inside Blender; import the master once and render all requested yaws."""
import argparse,math,sys
from pathlib import Path
import bpy

def args():
    raw=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    p=argparse.ArgumentParser(); p.add_argument('--model'); p.add_argument('--texture'); p.add_argument('--output'); p.add_argument('--size',type=int); p.add_argument('--rim'); p.add_argument('--background'); p.add_argument('--effect'); p.add_argument('--angles'); p.add_argument('--transparent',action='store_true'); return p.parse_args(raw)

def material(name,color,metallic,roughness,image=None):
    m=bpy.data.materials.new(name); m.use_nodes=True; bsdf=m.node_tree.nodes.get('Principled BSDF'); bsdf.inputs['Base Color'].default_value=(*color,1); bsdf.inputs['Metallic'].default_value=metallic; bsdf.inputs['Roughness'].default_value=roughness
    if image:
        tex=m.node_tree.nodes.new('ShaderNodeTexImage'); tex.image=bpy.data.images.load(image); m.node_tree.links.new(tex.outputs['Color'],bsdf.inputs['Base Color']); m.node_tree.links.new(tex.outputs['Alpha'],bsdf.inputs['Alpha'])
    return m

def main():
    a=args(); bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    try: bpy.ops.wm.obj_import(filepath=a.model)
    except Exception: bpy.ops.import_scene.obj(filepath=a.model,use_split_groups=True,use_split_objects=True)
    imported=[o for o in bpy.context.scene.objects if o.type=='MESH']; root=bpy.data.objects.new('BadgeTurntable',None); bpy.context.scene.collection.objects.link(root)
    rim_color={'silver':(.62,.66,.69),'gold':(.72,.47,.12),'black':(.035,.04,.05)}[a.rim]
    rough={'glossy':.20,'white-ceramic':.24,'brushed-silver-glitter':.34,'surface-holographic':.18,'star-holographic':.19,'matte-frosted':.62,'fluffy-cookie':.78}.get(a.effect,.22)
    front=material('front_art',(1,1,1),.0,rough,a.texture); rim=material('rim_metal',rim_color,.78,.23); back=material('back_metal',(.48,.53,.57),.72,.38)
    for obj in imported:
        obj.parent=root; lower=obj.name.lower(); chosen=front if 'front_art' in lower else (rim if 'rim' in lower else back); obj.data.materials.clear(); obj.data.materials.append(chosen)
        if chosen==front:
            uv=obj.data.uv_layers.new(name='FrontUV') if not obj.data.uv_layers else obj.data.uv_layers.active
            for poly in obj.data.polygons:
                for li in poly.loop_indices:
                    co=obj.data.vertices[obj.data.loops[li].vertex_index].co; uv.data[li].uv=((co.y/58)+.5,(co.z/58)+.5)
    world=bpy.context.scene.world or bpy.data.worlds.new('Studio'); bpy.context.scene.world=world; world.use_nodes=True; rgba=[int(x)/255 for x in a.background.split(',')]; world.node_tree.nodes['Background'].inputs['Color'].default_value=(*rgba[:3],1); world.node_tree.nodes['Background'].inputs['Strength'].default_value=.75
    def area(name,location,energy,size):
        data=bpy.data.lights.new(name,'AREA'); data.energy=energy; data.shape='DISK'; data.size=size; ob=bpy.data.objects.new(name,data); bpy.context.scene.collection.objects.link(ob); ob.location=location; ob.rotation_euler=(0,math.pi/2,0); return ob
    area('Key',(45,-35,38),850,32); area('Fill',(20,38,12),420,28); area('Rear',(-35,8,28),520,24)
    camera_data=bpy.data.cameras.new('Camera'); camera=bpy.data.objects.new('Camera',camera_data); bpy.context.scene.collection.objects.link(camera); camera.location=(90,0,0); camera.rotation_euler=(math.pi/2,0,math.pi/2); camera_data.type='ORTHO'; camera_data.ortho_scale=72; bpy.context.scene.camera=camera
    scene=bpy.context.scene; scene.render.engine='BLENDER_EEVEE_NEXT' if hasattr(bpy.types,'BLENDER_EEVEE_NEXT') else 'BLENDER_EEVEE'; scene.render.resolution_x=scene.render.resolution_y=a.size; scene.render.resolution_percentage=100; scene.render.image_settings.file_format='PNG'; scene.render.image_settings.color_mode='RGBA'; scene.render.film_transparent=a.transparent
    out=Path(a.output); out.mkdir(parents=True,exist_ok=True)
    for i,angle in enumerate(float(x) for x in a.angles.split(',')):
        root.rotation_euler[2]=angle; scene.render.filepath=str(out/f'frame-{i:04d}.png'); bpy.ops.render.render(write_still=True)
if __name__=='__main__': main()

