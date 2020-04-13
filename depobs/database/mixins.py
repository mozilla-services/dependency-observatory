from celery.result import AsyncResult
from sqlalchemy import (
    Column,
    String,
)


class TaskIDMixin:
    """
    mix into a table of results from a celery task to track data the root celery task that created the data

    refs:

    https://docs.celeryproject.org/en/stable/internals/reference/celery.backends.database.models.html#celery.backends.database.models.Task.configure
    https://github.com/celery/celery/blob/6215f34d2675441ef2177bd850bf5f4b442e944c/celery/backends/database/models.py#L27-L30
    """

    task_id = Column(String(155), nullable=True)

    # https://docs.celeryproject.org/en/stable/userguide/tasks.html#built-in-states
    @property
    def task_status(self) -> str:
        if self.task_id is None:
            return None
        return AsyncResult(id=self.task_id).status
