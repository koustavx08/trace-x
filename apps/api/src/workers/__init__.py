"""
Background worker package for async task processing.
"""
from .main import app as celery_app

__all__ = ["celery_app"]