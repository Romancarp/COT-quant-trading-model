from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from config import COT_SCHED_DAY, COT_SCHED_ENABLED, COT_SCHED_HOUR, COT_SCHED_MINUTE, COT_SCHED_TZ, INGEST_RUN_ON_STARTUP
from cot_ingestion.service import COTIngestionService

_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> BackgroundScheduler | None:
    global _scheduler
    if not COT_SCHED_ENABLED:
        return None
    if _scheduler:
        return _scheduler

    svc = COTIngestionService()
    scheduler = BackgroundScheduler(timezone=COT_SCHED_TZ)
    scheduler.add_job(
        svc.run_weekly_sync,
        CronTrigger(day_of_week=COT_SCHED_DAY, hour=COT_SCHED_HOUR, minute=COT_SCHED_MINUTE),
        id="cot_weekly_sync",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.start()

    if INGEST_RUN_ON_STARTUP:
        scheduler.add_job(svc.run_weekly_sync, id="cot_startup_sync", replace_existing=True)

    _scheduler = scheduler
    return _scheduler
