import os
from pathlib import Path
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from .job_manager import JobManager
from .validation import UploadProblem, validate_image
from .renderer_service import BACKGROUNDS, EFFECTS, RIMS

ROOT = Path(__file__).resolve().parents[1]
STATIC = Path(__file__).resolve().parent / "static"
manager = JobManager(ROOT / os.getenv("BAJI_TEMP_DIR", ".data/jobs"), int(os.getenv("BAJI_WORKERS", "1")), int(os.getenv("BAJI_JOB_TTL", "3600")))
app = FastAPI(title="吧唧生成器", docs_url=None, redoc_url=None)

@app.get("/health")
def health(): return {"status":"ok", "renderer":"obj"}

@app.post("/api/jobs", status_code=202)
async def create_job(image: UploadFile = File(...), effect: str = Form(...), rim: str = Form(...), background: str = Form(...)):
    if effect not in EFFECTS or rim not in RIMS or background not in BACKGROUNDS:
        raise HTTPException(400, "样式参数无效。")
    data = await image.read(10 * 1024 * 1024 + 1)
    try: decoded = validate_image(data)
    except UploadProblem as exc: raise HTTPException(400, str(exc))
    try: job = manager.submit(decoded, effect, rim, background)
    except ValueError: raise HTTPException(400, "样式参数无效。")
    return {"job_id":job.id, "status":job.status}

@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    job = manager.get(job_id)
    if not job: raise HTTPException(404, "任务不存在或已过期。")
    return {"job_id":job.id, "status":job.status, "error":job.error}

def artifact(job_id: str, kind: str):
    job = manager.get(job_id)
    if not job: raise HTTPException(404, "任务不存在或已过期。")
    path = getattr(job, kind, None)
    if job.status != "complete" or not path or not path.is_file(): raise HTTPException(409, "作品仍在生成中。")
    media = {"png":"image/png", "gif":"image/gif", "archive":"application/zip"}[kind]
    return FileResponse(path, media_type=media, filename=path.name)

@app.get("/api/jobs/{job_id}/png")
def png(job_id: str): return artifact(job_id, "png")
@app.get("/api/jobs/{job_id}/gif")
def gif(job_id: str): return artifact(job_id, "gif")
@app.get("/api/jobs/{job_id}/download")
def download(job_id: str): return artifact(job_id, "archive")
@app.delete("/api/jobs/{job_id}", status_code=204)
def delete(job_id: str):
    if not manager.delete(job_id): raise HTTPException(404, "任务不存在或已过期。")

app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
