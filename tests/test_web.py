import io, time, zipfile
from pathlib import Path
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from app.main import app
from app.validation import MAX_BYTES, UploadProblem, validate_image
from app.job_manager import JobManager

client = TestClient(app)

def encoded(fmt="PNG", size=(80, 60), mode="RGBA"):
    im=Image.new(mode,size,(220,70,110,180) if mode=="RGBA" else (220,70,110)); b=io.BytesIO(); im.save(b,fmt); return b.getvalue()

def test_01_home_opens(): assert client.get("/").status_code == 200
def test_02_health_obj(): assert client.get("/health").json()["renderer"] == "obj"
def test_03_upload_button_exists(): assert 'id="start"' in client.get("/").text
@pytest.mark.parametrize("fmt",["PNG","JPEG","WEBP"])
def test_04_06_supported_static_formats(fmt):
    mode="RGB" if fmt=="JPEG" else "RGBA"; assert validate_image(encoded(fmt,mode=mode)).size==(80,60)
def test_07_gif_first_frame():
    b=io.BytesIO(); a=Image.new("RGB",(12,12),"red"); z=Image.new("RGB",(12,12),"blue"); a.save(b,"GIF",save_all=True,append_images=[z]); assert validate_image(b.getvalue()).getpixel((1,1))[:3] == (255,0,0)
def test_08_over_10mb_rejected():
    with pytest.raises(UploadProblem,match="10MB"): validate_image(b"x"*(MAX_BYTES+1))
def test_09_non_image_rejected():
    with pytest.raises(UploadProblem,match="暂不支持"): validate_image(b"not an image")
def test_10_transparency_preserved(): assert validate_image(encoded()).getpixel((0,0))[3] == 180
def test_11_arbitrary_ratio(): assert validate_image(encoded(size=(211,53))).size == (211,53)
def test_12_exif_orientation():
    im=Image.new("RGB",(40,20),"red"); ex=im.getexif(); ex[274]=6; b=io.BytesIO(); im.save(b,"JPEG",exif=ex); assert validate_image(b.getvalue()).size==(20,40)
def test_13_crop_is_circle(): assert 'border-radius:50%' in Path('app/static/styles.css').read_text(encoding='utf-8')
def test_14_crop_constraints_present(): assert 'function constrain()' in Path('app/static/app.js').read_text(encoding='utf-8')
def test_15_cancel_resets(): assert "[data-action=cancel]" in Path('app/static/app.js').read_text(encoding='utf-8')
def test_16_confirm_enters_styles(): assert "show('styles')" in Path('app/static/app.js').read_text(encoding='utf-8')
def test_17_single_choice_groups():
    js=Path('app/static/app.js').read_text(encoding='utf-8'); assert 'type="radio"' in js and all(f"name=\"{n}" not in js for n in ('bad','wrong'))
def test_18_defaults():
    js=Path('app/static/app.js').read_text(encoding='utf-8'); assert "choices.effects,'glossy'" in js and "choices.rims,'silver'" in js and "choices.backgrounds,'white'" in js
def test_19_generate_params():
    js=Path('app/static/app.js').read_text(encoding='utf-8'); assert all(f"fd.append('{x}'" in js for x in ('image','effect','rim','background'))
def test_20_real_obj_contract():
    s=Path('app/renderer_service.py').read_text(encoding='utf-8'); assert 'render_static' in s and '"obj"' in s and 'save_rotation' in s
def test_21_output_sizes_contract():
    s=Path('app/renderer_service.py').read_text(encoding='utf-8'); assert 'prepare(image, 1024)' in s and 'animation_size: int = 640' in s
def test_22_gif_rotation_contract():
    s=Path('app/renderer_service.py').read_text(encoding='utf-8'); assert 'animation_frames: int = 58' in s
def test_23_restart_clears(): assert "$('#restart').onclick=reset" in Path('app/static/app.js').read_text(encoding='utf-8')
def test_24_error_hides_paths(monkeypatch):
    import app.job_manager as jm
    def boom(*a,**k): raise RuntimeError('C:\\secret\\file')
    monkeypatch.setattr(jm,'render_job',boom); m=JobManager(Path('.data/test-errors'),1); j=m.submit(Image.new('RGBA',(10,10)),'glossy','silver','white')
    for _ in range(50):
        if j.status=='failed': break
        time.sleep(.01)
    assert j.error=='生成失败，请稍后重试。' and 'secret' not in j.error; m.delete(j.id)
def test_25_zip_contains_both(tmp_path):
    p=tmp_path/'x.zip'; a=tmp_path/'a.png'; b=tmp_path/'a.gif'; a.write_bytes(b'p'); b.write_bytes(b'g')
    with zipfile.ZipFile(p,'w') as z:z.write(a,a.name);z.write(b,b.name)
    with zipfile.ZipFile(p) as z: assert set(z.namelist())=={'a.png','a.gif'}
def test_26_cleanup_expired(tmp_path):
    m=JobManager(tmp_path,1,ttl=1)
    from app.job_manager import Job
    j=Job('a'*32,tmp_path/('a'*32),created_at=time.time()-5); j.directory.mkdir();m.jobs[j.id]=j;m.cleanup();assert j.id not in m.jobs
def test_27_path_traversal_blocked(): assert client.get('/api/jobs/../../etc/png').status_code in (404,405)
def test_28_mobile_no_overflow_rule():
    css=Path('app/static/styles.css').read_text(encoding='utf-8'); assert '@media(max-width:720px)' in css and 'max-width:90vw' in css
