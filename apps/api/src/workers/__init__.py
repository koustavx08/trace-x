"""
Background worker package for async task processing.
"""
from .main import celery_app

__all__ = ["celery_app"]