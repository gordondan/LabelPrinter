from __future__ import annotations

import threading
import time
import uuid
from queue import Queue, Empty
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, List


class JobStatus:
    QUEUED = 'queued'
    RUNNING = 'running'
    DONE = 'done'
    ERROR = 'error'


@dataclass
class Job:
    id: str
    type: str
    status: str = JobStatus.QUEUED
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    error: Optional[str] = None
    result: Optional[Any] = None
    payload: Optional[dict] = None


class JobQueue:
    def __init__(self, max_concurrent: int = 1):
        self._jobs: Dict[str, Job] = {}
        self._q: Queue = Queue()
        self._lock = threading.Lock()
        self._worker: Optional[threading.Thread] = None
        self._stop = threading.Event()
        # Limit concurrency; default 1 ensures jobs run one at a time
        self._max_concurrent = max(1, int(max_concurrent))
        self._active = 0

    def start(self):
        if self._worker and self._worker.is_alive():
            return
        self._stop.clear()
        self._worker = threading.Thread(target=self._run, name='job-worker', daemon=True)
        self._worker.start()

    def stop(self):
        self._stop.set()
        try:
            self._q.put_nowait((None, None, None))
        except Exception:
            pass
        if self._worker:
            self._worker.join(timeout=1.0)

    def enqueue(self, job_type: str, fn: Callable[[], Any], payload: Optional[dict] = None) -> Job:
        jid = str(uuid.uuid4())
        job = Job(id=jid, type=job_type, payload=payload)
        with self._lock:
            self._jobs[jid] = job
        self._q.put((jid, job, fn))
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> List[Job]:
        with self._lock:
            # Newest first
            return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)

    def counts(self) -> Dict[str, int]:
        with self._lock:
            queued = sum(1 for j in self._jobs.values() if j.status == JobStatus.QUEUED)
            running = sum(1 for j in self._jobs.values() if j.status == JobStatus.RUNNING)
            return { 'queued': queued, 'running': running, 'total_active': queued + running }

    # --- internal ---
    def _run(self):
        workers: List[threading.Thread] = []
        while not self._stop.is_set():
            # Cleanup finished workers
            workers = [w for w in workers if w.is_alive()]
            self._active = len(workers)
            if self._active >= self._max_concurrent:
                time.sleep(0.05)
                continue
            try:
                item = self._q.get(timeout=0.5)
            except Empty:
                continue
            if not item:
                continue
            jid, job, fn = item
            if not job or not fn:
                continue

            def _exec(job: Job, fn: Callable[[], Any]):
                try:
                    job.status = JobStatus.RUNNING
                    job.started_at = time.time()
                    res = fn()
                    job.result = res
                    job.status = JobStatus.DONE
                    job.finished_at = time.time()
                except Exception as e:
                    job.error = str(e)
                    job.status = JobStatus.ERROR
                    job.finished_at = time.time()
                finally:
                    self._q.task_done()

            t = threading.Thread(target=_exec, args=(job, fn), name=f"job-{jid[:8]}", daemon=True)
            t.start()
            workers.append(t)
