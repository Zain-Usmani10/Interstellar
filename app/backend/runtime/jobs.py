"""Planning jobs: run the NASA owner's route search off the event loop, one at a time.

Adapter contract (owned by @sadattanzim01/claude):

    app.backend.planner.run_search(params: dict,
                                   progress: Callable[[float], None],
                                   cancelled: Callable[[], bool]) -> list[dict]

``params`` is the validated request body. The function returns MissionPlan dicts (valid
against mission_plan.schema.json, with plan_sha256 set). It should call ``progress`` with
0..1 and stop early when ``cancelled()`` is true. Until that module exists, submitting a job
answers PLANNER_UNAVAILABLE; nothing is faked.
"""
from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

from .events import EventHub
from .stores import PlanStore

MAX_PENDING = 4


class PlannerUnavailable(Exception):
    pass


def _load_search():
    try:
        from app.backend.planner import run_search      # type: ignore[import-not-found]
        return run_search
    except Exception as err:                            # noqa: BLE001
        raise PlannerUnavailable(str(err)) from None


class JobManager:
    def __init__(self, plans: PlanStore, hub: EventHub):
        self.plans, self.hub = plans, hub
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="planner")

    def available(self) -> bool:
        try:
            _load_search()
            return True
        except PlannerUnavailable:
            return False

    def submit(self, params: dict) -> dict:
        search = _load_search()
        with self._lock:
            pending = sum(1 for j in self._jobs.values() if j["status"] in ("queued", "running"))
            if pending >= MAX_PENDING:
                raise OverflowError("planning queue is full")
            job = {"job_id": str(uuid.uuid4()), "status": "queued", "progress": 0.0,
                   "plan_ids": [], "error": None, "_cancel": threading.Event()}
            self._jobs[job["job_id"]] = job
        self._pool.submit(self._run, job, search, params)
        return self.view(job)

    def _run(self, job: dict, search, params: dict) -> None:
        if job["_cancel"].is_set():
            return
        self._update(job, status="running")
        try:
            plans = search(params, lambda f: self._update(job, progress=float(f)), job["_cancel"].is_set)
            if job["_cancel"].is_set():
                return
            ids = [self.plans.add(plan) for plan in plans]     # rejects plans that fail the contract
            self._update(job, status="done", progress=1.0, plan_ids=ids)
        except Exception as err:                               # noqa: BLE001 - report, never fake a plan
            self._update(job, status="failed", error=str(err))

    def _update(self, job: dict, **changes) -> None:
        with self._lock:
            job.update(changes)
        self.hub.publish("job_update", self.view(job))

    def cancel(self, job_id: str) -> dict | None:
        job = self._jobs.get(job_id)
        if job is None:
            return None
        job["_cancel"].set()
        if job["status"] in ("queued", "running"):
            self._update(job, status="cancelled")
        return self.view(job)

    def get(self, job_id: str) -> dict | None:
        job = self._jobs.get(job_id)
        return self.view(job) if job else None

    @staticmethod
    def view(job: dict) -> dict:
        return {k: v for k, v in job.items() if not k.startswith("_")}

    def shutdown(self) -> None:
        for job in self._jobs.values():
            job["_cancel"].set()
        self._pool.shutdown(wait=False, cancel_futures=True)
