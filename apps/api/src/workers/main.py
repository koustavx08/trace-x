"""
Celery worker configuration for background task processing.
"""

import os

from celery import Celery
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
        "src.workers.tasks.wallet_analysis": {"queue": "analysis"},
        "src.workers.tasks.report_generation": {"queue": "reports"},
        "src.workers.tasks.graph_sync": {"queue": "graph"},
        "src.workers.tasks.entity_enrichment": {"queue": "enrichment"},
    },
    task_default_queue="default",
    task_queues=(
        Queue("default", routing_key="default"),
        Queue("analysis", routing_key="analysis"),
        Queue("reports", routing_key="reports"),
        Queue("graph", routing_key="graph"),
        Queue("enrichment", routing_key="enrichment"),
    ),
)

# Auto-discover tasks
celery_app.autodiscover_tasks(
    [
        "src.workers.tasks",
    ]
)

if __name__ == "__main__":
    celery_app.start()
