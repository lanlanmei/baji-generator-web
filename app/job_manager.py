import shutil, threading, time, uuid, zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from PIL import Image
from .renderer_service import render_job

@dataclass
class Job:
    id: str
    directory: Path
    status: str = "queued"
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    png: Path | None = None
    gif: Path | None = None
    archive: Path | None = None

class JobManager:
    def __init__(self, root: Path, workers: int = 1, ttl: int = 3600):
        self.root, self.ttl = root, ttl
        self.root.mkdir(parents=True, exist_ok=True)
        self.jobs: dict[str, Job] = {}
        self.lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=max(1, workers), thread_name_prefix="baji")

    def submit(self, image: Image.Image, effect: str, rim: str, background: str) -> Job:
        self.cleanup()
        job_id = uuid.uuid4().hex
        job = Job(job_id, self.root / job_id)
        with self.lock: self.jobs[job_id] = job
        self.executor.submit(self._run, job, image.copy(), effect, rim, background)
        return job

    def _run(self, job, image, effect, rim, background):
        job.status = "processing"
        try:
            job.png, job.gif = render_job(image, effect, rim, background, job.directory)
            job.archive = job.directory / f"baji-{effect}-{rim}-{background}.zip"
            with zipfile.ZipFile(job.archive, "w", zipfile.ZIP_DEFLATED) as z:
                z.write(job.png, job.png.name); z.write(job.gif, job.gif.name)
            job.status = "complete"
        except Exception:
            job.error = "生成失败，请稍后重试。"
            job.status = "failed"

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id) if len(job_id) == 32 and job_id.isalnum() else None

    def delete(self, job_id: str) -> bool:
        with self.lock: job = self.jobs.pop(job_id, None)
        if not job: return False
        shutil.rmtree(job.directory, ignore_errors=True)
        return True

    def cleanup(self):
        cutoff = time.time() - self.ttl
        for jid, job in list(self.jobs.items()):
            if job.created_at < cutoff and job.status != "processing": self.delete(jid)
