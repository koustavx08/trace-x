"""
Celery worker configuration for background task processing.
"""

import os

from celery import Celery
from celery.schedules import crontab
from kombu import Queue

# Celery configuration
celery_app = Celery("tracex_worker")

celery_app.conf.update(
    broker_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    result_backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=100,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_routes={
        # ponytail: these never matched -- shared_task with no explicit
        # name= gets named "<module>.<function name>", i.e. the "_task"
        # suffix below was missing, so every task silently fell through to
        # task_default_queue regardless of this routing table.
        "src.workers.tasks.wallet_analysis_task": {"queue": "analysis"},
        "src.workers.tasks.report_generation_task": {"queue": "reports"},
        "src.workers.tasks.graph_sync_task": {"queue": "graph"},
        "src.workers.tasks.entity_enrichment_task": {"queue": "enrichment"},
    },
    task_default_queue="default",
    task_queues=(
        Queue("default", routing_key="default"),
        Queue("analysis", routing_key="analysis"),
        Queue("reports", routing_key="reports"),
        Queue("graph", routing_key="graph"),
        Queue("enrichment", routing_key="enrichment"),
    ),
    beat_schedule={
        "cleanup-stale-investigations": {
            "task": "src.workers.tasks.cleanup_stale_investigations",
            "schedule": crontab(minute=0),  # hourly
        },
        "periodic-entity-sync": {
            "task": "src.workers.tasks.periodic_entity_sync",
            "schedule": crontab(minute=0, hour="*/6"),
        },
    },
)

# Auto-discover tasks
celery_app.autodiscover_tasks(
    [
        "src.workers.tasks",
    ]
)

if __name__ == "__main__":
    celery_app.start()
