"""
Queue service for async task processing with Celery.
Provides a clean interface for adding tasks to queues.
"""
import logging
from typing import Any, Callable, Dict, Optional

from celery import current_app
from celery.result import AsyncResult

logger = logging.getLogger(__name__)


class QueueService:
    """
    Service for managing async task queues.
    Abstracts Celery for task dispatching and monitoring.
    """

    @staticmethod
    def dispatch(task_name: str, args: tuple = None, kwargs: dict = None,
                 queue: str = "default", countdown: int = 0) -> AsyncResult:
        """
        Dispatch a task to the Celery worker.
        """
        task = current_app.send_task(
            name=task_name,
            args=args or (),
            kwargs=kwargs or {},
            queue=queue,
            countdown=countdown,
        )
        logger.info(f"Dispatched task {task_name} -> {task.id}")
        return task

    @staticmethod
    def dispatch_async(task: Callable, args: tuple = None, kwargs: dict = None,
                       countdown: int = 0) -> AsyncResult:
        """
        Dispatch a task using the task function directly (async).
        """
        result = task.apply_async(
            args=args or (),
            kwargs=kwargs or {},
            countdown=countdown,
        )
        logger.info(f"Dispatched async task {task.__name__} -> {result.id}")
        return result

    @staticmethod
    def get_task_status(task_id: str) -> Dict[str, Any]:
        """
        Get the status of a task by its ID.
        """
        result = AsyncResult(task_id)
        return {
            "task_id": task_id,
            "status": result.status,
            "result": result.result if result.ready() else None,
        }

    @staticmethod
    def revoke_task(task_id: str, terminate: bool = False) -> None:
        """
        Revoke/cancel a task.
        """
        current_app.control.revoke(task_id, terminate=terminate)
        logger.info(f"Revoked task {task_id}")