from typing import Optional

from celery.result import AsyncResult
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    String,
    Integer,
)


class PackageReportColumnsMixin:
    """
    mix into derived tables and views using PackageReport as score inputs
    and returning a superset of PackageReport columns
    """

    package = Column(String(200))
    version = Column(String(200))
    status = Column(String(200))
    release_date = Column(DateTime)
    scoring_date = Column(DateTime)
    top_score = Column(Integer)
    npmsio_score = Column(Float)
    directVulnsCritical_score = Column(Integer)
    directVulnsHigh_score = Column(Integer)
    directVulnsMedium_score = Column(Integer)
    directVulnsLow_score = Column(Integer)
    indirectVulnsCritical_score = Column(Integer)
    indirectVulnsHigh_score = Column(Integer)
    indirectVulnsMedium_score = Column(Integer)
    indirectVulnsLow_score = Column(Integer)
    authors = Column(Integer)
    contributors = Column(Integer)
    immediate_deps = Column(Integer)
    all_deps = Column(Integer)


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
    def task_status(self) -> Optional[str]:
        if self.task_id is None:
            return None
        return AsyncResult(id=self.task_id).status
