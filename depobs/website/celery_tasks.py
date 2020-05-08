from collections import namedtuple

from flask import current_app

from depobs.website.do import create_celery_app


def get_celery_tasks(filter_prefix: str = "depobs.worker.tasks."):
    """Returns the celery app configured and bound to the Flask app.

    Web views should use it in a flask application context to kick off
    celery tasks without creating import cycles.
    """
    if not hasattr(current_app, "tasks"):
        import depobs.worker.tasks

        celery_app = create_celery_app(
            current_app,
            tasks=[
                getattr(depobs.worker.tasks, task_name)
                for task_name in current_app.config["WEB_TASK_NAMES"]
            ],
        )
        request_tasks = {
            task_name.replace(filter_prefix, ""): task
            for task_name, task in celery_app.tasks.items()
            if task_name.startswith(filter_prefix)
        }
        # convert request_tasks dict to namedtuple so it behaves like the
        # module
        # type ignores below ref: https://github.com/python/mypy/issues/848
        Tasks = namedtuple("celery_tasks", request_tasks.keys())  # type: ignore
        current_app.tasks = Tasks(**request_tasks)  # type: ignore
    return current_app.tasks
