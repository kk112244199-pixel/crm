"""Celery application — task queue for health batch, RAG ingest, etc."""
from app.core.redis_compat import apply_redis_resp2
apply_redis_resp2()

from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery(
    "montocrm",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.health_batch",
        "app.tasks.pending_expire",
        "app.tasks.eval_ragas",
        "app.tasks.rag_reindex",
        "app.tasks.dingtalk_notify",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_queues={
        "default": {},
        "health_batch": {},
    },
    beat_schedule={
        "health-batch-daily": {
            "task": "app.tasks.health_batch.run_full_health_batch",
            "schedule": crontab(hour=2, minute=0),
            "options": {"queue": "health_batch"},
        },
        "pending-expire-hourly": {
            "task": "app.tasks.pending_expire.expire_pending_actions",
            "schedule": 3600,
            "options": {"queue": "health_batch"},
        },
        "dingtalk-flush-hourly": {
            "task": "app.tasks.dingtalk_notify.flush_delayed",
            "schedule": 3600,
            "options": {"queue": "default"},
        },
        "ragas-eval-weekly": {
            "task": "app.tasks.eval_ragas.run_weekly_eval",
            "schedule": crontab(hour=0, minute=0, day_of_week=1),
            "options": {"queue": "default"},
        },
    },
)

app = celery_app