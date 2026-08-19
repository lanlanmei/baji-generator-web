import math, sys, tempfile, unittest
from pathlib import Path
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageStat

ROOT=Path(__file__).parents[1]; sys.path.insert(0,str(ROOT/'scripts'))
import render_baji
from badge_base import RIM_RATIO, apply_dome_lighting, film_highlight_layer, make_badge_object
from animation import THICKNESS_RATIO, _back, geometry_for_angle, projection_lut, render_rotation
from model_renderer import (DEFAULT_CONFIG,SURFACE_BACK,SURFACE_FRONT,SURFACE_RIM,SURFACE_SIDE,
    back_depth,build_validation_mesh,front_depth,geometry_for_angle as curved_geometry,
    radial_derivative,render_model,validate_geometry)
from model_backend import capabilities,render_rotation as render_backend_rotation,select_backend
from obj_renderer import ACCESSORY_SURFACE,MODEL,load_accessory_mesh,model_metadata,render_obj

class RendererTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory(); self.d=Path(self.t.name)
    def tearDown(self):self.t.cleanup()
    def make(self,name,size=(300,300),mode='RGB',fmt=None):
        im=Image.new(mode,size,(35,90,180,0) if mode=='RGBA' else (35,90,180)); d=ImageDraw.Draw(im); d.ellipse((size[0]*.2,size[1]*.1,size[0]*.8,size[1]*.85),fill=(240,120,80,220) if mode=='RGBA' else (240,120,80)); p=self.d/name; im.save(p,format=fmt); return p
    def run_cli(self,inputs,*extra):return render_baji.main([*(str(x) for x in inputs),'--output',str(self.d/'out'),*extra])
    def test_formats_and_shapes(self):
        files=[self.make('a.png'),self.make('b.jpg',(520,260)),self.make('c.webp',(220,480)),self.make('d.gif',(240,240),fmt='GIF'),self.make('alpha.png',(280,360),'RGBA')]
        self.assertEqual(self.run_cli(files,'--effects','glossy','--size','1024','--no-animation'),0); self.assertEqual(len(list((self.d/'out').glob('*.png'))),5)
        for p in (self.d/'out').glob('*.png'):
            with Image.open(p) as im:self.assertEqual(im.size,(1024,1024)); self.assertEqual(im.mode,'RGBA')
    def test_pixel_low_res_default_seven(self):
        p=self.make('pixel.png',(16,16)); self.assertEqual(self.run_cli([p],'--no-animation'),0); self.assertEqual(len(list((self.d/'out').glob('*.png'))),7)
    def test_multiple_presets_backgrounds_rims_and_alpha(self):
        p=self.make('a.png','RGBA') if False else self.make('a.png',mode='RGBA')
        for rim,bg in [('silver','transparent'),('gold','light-gray'),('black','mist-pink')]:
            self.assertEqual(self.run_cli([p],'--effects','white-ceramic','star-holographic','--rim',rim,'--background',bg,'--no-animation'),0)
        outs=list((self.d/'out').glob('*.png')); self.assertEqual(len(outs),6)
        alpha=[x for x in outs if 'transparent' in x.name][0]
        with Image.open(alpha) as im:self.assertLess(im.getchannel('A').getextrema()[0],255)
    def test_2048(self):
        p=self.make('hd.jpg'); self.assertEqual(self.run_cli([p],'--effects','matte-frosted','--size','2048','--no-animation'),0)
        with Image.open(next((self.d/'out').glob('*.png'))) as im:self.assertEqual(im.size,(2048,2048))
    def test_over_10mb_and_bad_args(self):
        p=self.d/'huge.png'; p.write_bytes(b'0'*(10*1024*1024+1)); self.assertEqual(self.run_cli([p],'--effects','glossy','--no-animation'),2)
        q=self.make('ok.png'); self.assertEqual(self.run_cli([q],'--effects','nope','--no-animation'),2)

    def test_animation_default_and_metadata(self):
        p=self.make('spin.png'); self.assertEqual(self.run_cli([p],'--effects','glossy','--animation-size','256','--animation-frames','12','--animation-duration','50'),0)
        self.assertEqual(len(list((self.d/'out').glob('*.png'))),1); gifs=list((self.d/'out').glob('*.gif')); self.assertEqual(len(gifs),1)
        with Image.open(gifs[0]) as im:
            self.assertTrue(im.is_animated); self.assertEqual(im.n_frames,12); self.assertEqual(im.info.get('loop'),0); self.assertEqual(im.size,(256,256))
            frames=[]
            for i in (0,3,6,9,11): im.seek(i); frames.append(im.convert('RGB').copy())
            self.assertGreater(sum(ImageChops.difference(frames[0],x).getbbox() is not None for x in frames[1:]),2)

    def test_default_seven_png_and_gif(self):
        p=self.make('all.png',(64,64)); self.assertEqual(self.run_cli([p],'--animation-size','128','--animation-frames','8'),0)
        self.assertEqual(len(list((self.d/'out').glob('*.png'))),7); self.assertEqual(len(list((self.d/'out').glob('*.gif'))),7)

    def test_no_animation_and_thin_uniform_rims(self):
        p=self.make('rim.png')
        for rim in ('silver','gold','black'):
            self.assertEqual(self.run_cli([p],'--effects','glossy','--rim',rim,'--no-animation'),0)
        self.assertFalse(list((self.d/'out').glob('*.gif')))
        self.assertGreaterEqual(RIM_RATIO,.006); self.assertLessEqual(RIM_RATIO,.012)

    def test_v12_actual_geometry_and_inner_border(self):
        art=Image.new('RGBA',(256,256),(220,35,45,255)); obj=make_badge_object(art,512,'silver',highlights=False)
        row=[obj.getpixel((x,256)) for x in range(512)]; start=next(i for i,p in enumerate(row) if p[3]>20)
        art_start=next(i for i in range(start,256) if row[i][0]>180 and row[i][1]<100)
        metal_end=max(i for i in range(start,art_start) if row[i][1]>100 and row[i][2]>100)
        self.assertLess(art_start-metal_end,metal_end-start+1)
        alpha=obj.getchannel('A'); box=alpha.getbbox(); self.assertLessEqual(abs((box[0]+box[2])-512),2); self.assertLessEqual(abs((box[1]+box[3])-512),2)

    def test_v12_rotation_center_connected_profile_and_views(self):
        art=Image.new('RGBA',(192,192),(230,70,90,255)); frames=render_rotation(art,192,'silver',(255,255,255,255),False,(255,255,255,255),16,40)
        boxes=[]
        for frame in frames:
            rgb=frame.convert('RGB'); pix=rgb.load(); mask=Image.new('L',rgb.size); md=ImageDraw.Draw(mask)
            for y in range(0,165):
                runs=[]; active=False; x0=0
                for x in range(192):
                    r,g,b=pix[x,y]; hit=max(abs(r-255),abs(g-255),abs(b-255))>18
                    if hit and not active:x0=x; active=True
                    if active and (not hit or x==191):runs.append((x0,x if not hit else x+1)); active=False
                for a,bx in runs:md.line((a,y,bx,y),fill=255)
            boxes.append(mask.filter(ImageFilter.MaxFilter(3)).getbbox())
        centers=[(b[0]+b[2])/2 for b in boxes if b]; self.assertLess(max(centers)-min(centers),192*.06)
        self.assertGreater(boxes[4][2]-boxes[4][0],4); self.assertGreater(boxes[0][2]-boxes[0][0],192*.72)
        self.assertNotEqual(frames[0].tobytes(),frames[4].tobytes()); self.assertNotEqual(frames[4].tobytes(),frames[8].tobytes())

    def test_v13_highlight_is_white_alpha_only_and_never_darkens(self):
        high=film_highlight_layer(512); colors=high.get_flattened_data()
        self.assertTrue(any(a>0 for r,g,b,a in colors)); self.assertTrue(all(min(r,g,b)>=245 for r,g,b,a in colors if a>0))
        white=Image.new('RGBA',(512,512),(255,255,255,255)); lit=apply_dome_lighting(white); combined=Image.alpha_composite(lit,high)
        self.assertGreaterEqual(min(ImageStat.Stat(lit.convert('RGB')).extrema[0]),240)
        for before,after in zip(lit.convert('RGB').get_flattened_data(),combined.convert('RGB').get_flattened_data()): self.assertTrue(all(a>=b for a,b in zip(after,before)))

    def test_v13_thin_rounded_side_and_flat_back(self):
        self.assertGreaterEqual(THICKNESS_RATIO,.016); self.assertLessEqual(THICKNESS_RATIO,.022)
        side=geometry_for_angle(320,3.14159265/2)[0]; ys,xs=np.nonzero(side); self.assertGreater(xs.max()-xs.min()+1,5)
        top=ys.min()+1; self.assertGreater(np.count_nonzero(side[top]),1)
        back=_back(320,'silver').convert('RGB').crop((90,90,230,230)); stat=ImageStat.Stat(back); self.assertLess(max(v[1]-v[0] for v in stat.extrema),75)

    def test_v14_monotonic_projection_and_all_58_geometry_masks(self):
        lut=projection_lut(1025); self.assertTrue(np.all(np.diff(lut)>0))
        art=Image.new('RGBA',(192,192),(225,55,85,255)); frames,masks=render_rotation(art,192,'silver',(255,255,255,255),False,(255,255,255,255),58,40,return_masks=True)
        self.assertEqual(len(frames),58); areas=[]; widths=[]; centers=[]
        for index,mask in enumerate(masks):
            ys,xs=np.nonzero(mask); self.assertGreater(len(xs),0,index); areas.append(len(xs)); widths.append(xs.max()-xs.min()+1); centers.append((xs.min()+xs.max())/2)
            active_rows=np.flatnonzero(mask.any(axis=1)); self.assertGreater(len(active_rows),0)
            for y in active_rows:
                row=np.flatnonzero(mask[y]); self.assertEqual(len(row),row[-1]-row[0]+1,(index,int(y)))
            left=np.array([np.flatnonzero(mask[y])[0] for y in active_rows]); right=np.array([np.flatnonzero(mask[y])[-1] for y in active_rows])
            self.assertLessEqual(np.max(np.abs(np.diff(left))),8,index); self.assertLessEqual(np.max(np.abs(np.diff(right))),8,index)
        self.assertLess(max(centers)-min(centers),3); self.assertLess(max(abs(np.diff(areas))),max(areas)*.13)
        self.assertLess(abs(widths[14]-widths[43]),5); self.assertLess(abs(areas[14]-areas[43]),max(areas)*.04)
        for i in list(range(11,18))+list(range(40,47)): self.assertGreater(areas[i],192*.015)

    def test_v14_front_back_transition_rules(self):
        eps=.001
        for degrees,expected in ((0,1),(87,1),(89,0),(90,0),(91,0),(93,-1),(180,-1),(267,-1),(269,0),(270,0),(271,0),(273,1)):
            kind=geometry_for_angle(256,math.radians(degrees))[2]
            self.assertEqual(kind,expected,degrees)
        for rim in ('silver','gold','black'):
            masks=[geometry_for_angle(160,a)[0] for a in (math.pi/2,3*math.pi/2)]; self.assertLess(abs(masks[0].sum()-masks[1].sum()),10,rim)

    def test_v14_silver_gold_black_side_pixels(self):
        art=Image.new('RGBA',(128,128),(230,80,110,255)); samples=[]
        for rim in ('silver','gold','black'):
            frames,masks=render_rotation(art,128,rim,(255,255,255,255),False,(255,255,255,255),8,40,return_masks=True); side=np.array(frames[2].convert('RGB')); pixels=side[masks[2]]
            self.assertGreater(len(pixels),100,rim); samples.append(tuple(np.mean(pixels,axis=0).round().astype(int)))
        self.assertEqual(len(set(samples)),3)

    def test_v15_profile_depth_and_continuity(self):
        c=DEFAULT_CONFIG; r=np.linspace(0,1,4097,dtype=np.float32); front=front_depth(r,c); back=back_depth(r,c)
        self.assertGreater(front[0],front[-1]); self.assertLess(back.max()-back.min(),front.max()-front.min())
        self.assertLess(np.abs(np.diff(front)).max(),.004); self.assertLess(np.abs(np.diff(back)).max(),.001)
        self.assertAlmostEqual(float(front_depth(np.array([c.front_art_radius-1e-5]),c)[0]),float(front_depth(np.array([c.front_art_radius+1e-5]),c)[0]),places=3)
        self.assertAlmostEqual(float(front[-1]),c.body_thickness_ratio*.5-c.rim_roll_depth_ratio,places=4)

    def test_v15_normals_finite_and_connections(self):
        report=validate_geometry(); self.assertGreater(report['front_center'],report['front_edge'])
        r=np.linspace(0,1,3000,dtype=np.float32); df=radial_derivative(front_depth,r); db=radial_derivative(back_depth,r)
        self.assertTrue(np.isfinite(np.r_[df,db]).all()); self.assertLess(np.abs(np.diff(df[:-20])).max(),.08)
        self.assertLess(abs(float(db[-1])),.03)

    def test_v15_validation_mesh_indices_uv_and_degeneracy(self):
        mesh=build_validation_mesh(); p=mesh['position']; tri=mesh['triangles']; uv=mesh['uv']
        self.assertTrue(np.isfinite(p).all()); self.assertTrue(np.isfinite(mesh['normal']).all()); self.assertGreaterEqual(tri.min(),0); self.assertLess(tri.max(),len(p))
        a=p[tri[:,1]]-p[tri[:,0]]; b=p[tri[:,2]]-p[tri[:,0]]; area=np.linalg.norm(np.cross(a,b),axis=1)
        self.assertLess(np.mean(area<1e-8),.04); self.assertLess(np.max(np.abs(np.diff(uv.reshape(2,33,128,2),axis=1))),.04)

    def test_v15_zbuffer_front_side_back_visibility(self):
        art=Image.new('RGBA',(160,160),(240,30,40,255))
        expected=((0,SURFACE_FRONT),(90,SURFACE_SIDE),(180,SURFACE_BACK),(270,SURFACE_SIDE))
        for deg,kind in expected:
            _,buf=render_model(art,160,'silver',(255,255,255,255),False,math.radians(deg),return_buffers=True)
            center=buf['surface'][80,80]; self.assertEqual(int(center),kind,deg)
        _,front=render_model(art,160,return_buffers=True); self.assertFalse(np.any(front['surface']==SURFACE_BACK))
        _,back=render_model(art,160,theta=math.pi,return_buffers=True); self.assertFalse(np.any(back['surface']==SURFACE_FRONT))

    def test_v15_all_58_single_connected_solid_masks(self):
        areas=[]
        for i in range(58):
            mask=curved_geometry(144,2*math.pi*i/58)[0]; ys=np.flatnonzero(mask.any(axis=1)); self.assertGreater(len(ys),0,i); areas.append(mask.sum())
            for y in ys:
                row=np.flatnonzero(mask[y]); self.assertEqual(len(row),row[-1]-row[0]+1,(i,int(y)))
            left=np.array([np.flatnonzero(mask[y])[0] for y in ys]); right=np.array([np.flatnonzero(mask[y])[-1] for y in ys])
            self.assertLessEqual(np.max(np.abs(np.diff(left))),8,i); self.assertLessEqual(np.max(np.abs(np.diff(right))),8,i)
        self.assertLess(max(abs(np.diff(areas))),max(areas)*.14)

    def test_v15_danger_frames_and_side_mirror(self):
        masks=[curved_geometry(192,2*math.pi*i/58)[0] for i in range(58)]
        for i in list(range(11,18))+list(range(40,47)): self.assertGreater(masks[i].sum(),300,i)
        a=masks[round(58/4)]; b=np.fliplr(masks[round(58*3/4)]); self.assertLess(np.mean(a!=b),.006)
        ys,xs=np.nonzero(a); self.assertGreater(xs.max()-xs.min()+1,8)

    def test_v15_static_matches_gif_first_frame(self):
        art=Image.new('RGBA',(256,256),(70,130,210,255)); static=render_model(art,256,'silver',(255,255,255,255),False,0).convert('RGB')
        gif=render_rotation(art,256,'silver',(255,255,255,255),False,(255,255,255,255),8,40)[0].convert('RGB')
        rms=np.sqrt(np.mean((np.asarray(static,dtype=np.float32)-np.asarray(gif,dtype=np.float32))**2)); self.assertLess(rms,8)

    def test_v15_front_texture_cannot_leak_to_back_or_side(self):
        red=Image.new('RGBA',(192,192),(255,0,0,255))
        for deg in (90,180,270):
            im,buf=render_model(red,192,'silver',(255,255,255,255),False,math.radians(deg),return_buffers=True); arr=np.asarray(im.convert('RGB')); pixels=arr[buf['mask']]
            self.assertLess(np.mean((pixels[:,0]>220)&(pixels[:,1]<50)),.002,deg)

    def test_v15_rim_geometry_shared_by_silver_gold_black(self):
        art=Image.new('RGBA',(192,192),(80,130,200,255)); masks=[]; colors=[]
        for rim in ('silver','gold','black'):
            im,b=render_model(art,192,rim,(255,255,255,255),False,math.pi/4,return_buffers=True); masks.append(b['mask']); arr=np.asarray(im.convert('RGB')); sel=(b['surface']==SURFACE_RIM)|(b['surface']==SURFACE_SIDE); colors.append(tuple(arr[sel].mean(axis=0).round()))
        self.assertTrue(all(np.array_equal(masks[0],m) for m in masks[1:])); self.assertEqual(len(set(colors)),3)

    def test_v15_white_surface_clean_and_highlight_additive(self):
        white=Image.new('RGBA',(320,320),(255,255,255,255)); im,b=render_model(white,320,'silver',(255,255,255,255),False,0,return_buffers=True); arr=np.asarray(im.convert('RGB'))
        face=arr[b['surface']==SURFACE_FRONT]; self.assertGreater(face.min(),225); self.assertGreater(np.percentile(face,5),238)
        row=arr[160,:,0]; sel=b['surface'][160]==SURFACE_FRONT; values=row[sel].astype(float); self.assertLess(np.abs(np.diff(values,2)).max(),18)

    def test_v15_transparent_alpha_and_back_accessory_interface(self):
        art=Image.new('RGBA',(256,256),(50,100,180,255)); im,b=render_model(art,256,'silver',(0,0,0,0),True,0,return_buffers=True)
        alpha=np.asarray(im.getchannel('A')); self.assertEqual(alpha[b['mask']].min(),255); self.assertEqual(alpha[0,0],0)
        self.assertIsNone(DEFAULT_CONFIG.back_accessory)

    def test_model_asset_dimensions_axis_groups_and_materials(self):
        self.assertTrue(MODEL.is_file()); meta=model_metadata(); lo=meta['bounds_min']; hi=meta['bounds_max']
        self.assertAlmostEqual(float(hi[1]-lo[1]),58,places=3); self.assertAlmostEqual(float(hi[2]-lo[2]),58,places=3)
        self.assertGreater(hi[0],0); self.assertLess(lo[0],0); self.assertLess(float(hi[0]-lo[0]),10)
        self.assertEqual(meta['materials'],{'front_art','rim_metal','back_metal'}); self.assertEqual(meta['mtllib'],'badge_master.mtl')
        self.assertTrue({'pin_needle','pin_hinge','pin_clasp','hinge_foot','clasp_foot'}<=meta['groups'])

    def test_model_asset_has_no_absolute_path_secret_or_api(self):
        model_dir=MODEL.parent; text='\n'.join(x.read_text(encoding='utf-8',errors='ignore') for x in model_dir.iterdir() if x.is_file())
        lowered=text.lower(); forbidden=('hi'+'3d','access'+'_'+'key','secret'+'_'+'key','http'+':/'+'/','https'+':/'+'/')
        for token in forbidden:self.assertNotIn(token,lowered)
        self.assertNotRegex(text,r'[A-Za-z]:\\'); self.assertTrue((model_dir/'badge_master.mtl').is_file())

    def test_accessory_mesh_indices_finite_and_non_degenerate(self):
        p,n,t=load_accessory_mesh(); self.assertTrue(np.isfinite(p).all()); self.assertTrue(np.isfinite(n).all()); self.assertGreaterEqual(t.min(),0); self.assertLess(t.max(),len(p))
        area=np.linalg.norm(np.cross(p[t[:,1]]-p[t[:,0]],p[t[:,2]]-p[t[:,0]]),axis=1); self.assertLess(np.mean(area<1e-9),.08); self.assertGreater(len(t),5000)

    def test_backend_auto_priority_and_three_layer_fallback(self):
        self.assertEqual(select_backend('auto',{'blender':True,'obj':True,'glb':True,'pillow':True}),'blender')
        self.assertEqual(select_backend('auto',{'blender':False,'obj':True,'glb':False,'pillow':True}),'obj')
        self.assertEqual(select_backend('auto',{'blender':False,'obj':False,'glb':True,'pillow':True}),'glb')
        self.assertEqual(select_backend('auto',{'blender':False,'obj':False,'glb':False,'pillow':True}),'pillow')
        self.assertEqual(select_backend('pillow',{'pillow':True}),'pillow')

    def test_explicit_unavailable_blender_and_glb_are_clear(self):
        with self.assertRaisesRegex(ValueError,'Blender.*not installed'): select_backend('blender',{'blender':False})
        with self.assertRaisesRegex(ValueError,'GLB.*runtime'): select_backend('glb',{'glb':False})

    def test_obj_front_back_occlusion_pin_and_recess(self):
        art=Image.new('RGBA',(256,256),(250,30,40,255)); front,fb=render_obj(art,256,'silver',(255,255,255,255),False,0,return_buffers=True); back,bb=render_obj(art,256,'silver',(255,255,255,255),False,math.pi,return_buffers=True)
        self.assertFalse(np.any(fb['surface']==ACCESSORY_SURFACE)); self.assertGreater(np.count_nonzero(bb['surface']==ACCESSORY_SURFACE),40)
        arr=np.asarray(back.convert('RGB')); pin=arr[bb['surface']==ACCESSORY_SURFACE]; self.assertGreater(pin.mean(),100)
        self.assertFalse(np.any(bb['surface']==SURFACE_FRONT)); self.assertLess(float(bb['depth'][128,128]),float(bb['depth'][128,40]))

    def test_obj_silver_gold_black_share_geometry(self):
        art=Image.new('RGBA',(192,192),(80,140,210,255)); masks=[]; colors=[]
        for rim in ('silver','gold','black'):
            image,b=render_obj(art,192,rim,(255,255,255,255),False,math.pi/4,return_buffers=True); masks.append(b['mask']); arr=np.asarray(image.convert('RGB')); colors.append(tuple(arr[b['surface']==SURFACE_RIM].mean(0).round()))
        self.assertTrue(all(np.array_equal(masks[0],m) for m in masks[1:])); self.assertEqual(len(set(colors)),3)

    def test_obj_backgrounds_transparent_alpha_and_sizes(self):
        art=Image.new('RGBA',(256,256),(220,230,240,255))
        for size,bg,transparent in ((256,(255,255,255,255),False),(320,(223,216,232,255),False),(256,(0,0,0,0),True)):
            image=render_obj(art,size,'silver',bg,transparent); self.assertEqual(image.size,(size,size)); self.assertEqual(image.mode,'RGBA')
            if transparent:self.assertEqual(image.getpixel((0,0))[3],0)

    def test_obj_texture_never_leaks_to_back_or_side(self):
        red=Image.new('RGBA',(192,192),(255,0,0,255))
        for angle in (math.pi/2,math.pi,3*math.pi/2):
            image,b=render_obj(red,192,'silver',(255,255,255,255),False,angle,return_buffers=True); pixels=np.asarray(image.convert('RGB'))[b['mask']]
            self.assertLess(np.mean((pixels[:,0]>220)&(pixels[:,1]<50)),.003)

    def test_obj_58_frame_gif_key_views_masks_and_loop(self):
        art=Image.new('RGBA',(128,128),(60,130,220,255)); frames,masks,chosen=render_backend_rotation(art,128,'silver',(255,255,255,255),False,'glossy',58,'obj',True)
        self.assertEqual(chosen,'obj'); self.assertEqual(len(frames),58); centers=[]
        for i,mask in enumerate(masks):
            ys,xs=np.nonzero(mask); self.assertGreater(len(xs),0,i); centers.append(((xs.min()+xs.max())/2,(ys.min()+ys.max())/2))
            for y in np.flatnonzero(mask.any(1)):
                row=np.flatnonzero(mask[y]); self.assertEqual(len(row),row[-1]-row[0]+1,(i,int(y)))
        self.assertLessEqual(np.ptp(np.asarray(centers)[:,0]),4); self.assertLess(np.ptp(np.asarray(centers)[:,1]),3)
        for i in (0,7,14,22,29,36,44,51,57): self.assertEqual(frames[i].size,(128,128))
        diff=np.asarray(ImageChops.difference(frames[0].convert('RGB'),frames[-1].convert('RGB')),dtype=np.float32); self.assertLess(np.sqrt(np.mean(diff*diff)),18)

    def test_cli_preset_backend_and_gif_mime(self):
        p=self.make('backend.png',(200,160)); self.assertEqual(self.run_cli([p],'--preset','glossy','--backend','obj','--animation-size','128','--animation-frames','8'),0)
        png=list((self.d/'out').glob('*.png')); gif=list((self.d/'out').glob('*.gif')); self.assertEqual((len(png),len(gif)),(1,1))
        import mimetypes; self.assertEqual(mimetypes.guess_type(gif[0].name)[0],'image/gif')
        with Image.open(gif[0]) as im:self.assertTrue(im.is_animated); self.assertEqual(im.n_frames,8)

    def test_six_material_styles_render_on_obj_front(self):
        art=Image.new('RGBA',(128,128),(120,150,190,255)); means=[]
        for effect in ('white-ceramic','brushed-silver-glitter','surface-holographic','star-holographic','matte-frosted','fluffy-cookie'):
            image=render_obj(art,128,'silver',(255,255,255,255),False,.28,effect); means.append(tuple(np.asarray(image.convert('RGB')).mean((0,1)).round(2)))
        self.assertGreater(len(set(means)),2)

if __name__=='__main__':unittest.main()
