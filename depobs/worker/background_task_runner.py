import asyncio
import functools
from typing import (
    Callable,
    Iterable,
    Set,
)
import logging

from flask import Flask

log = logging.getLogger(__name__)


async def run_background_tasks(
    app: Flask, task_fns: Iterable[Callable], timeout_seconds: int = 5
) -> None:
    """
    Repeatedly runs one or more tasks with the param task_name until
    the shutdown event fires.
    """
    shutdown = asyncio.Event()

    task_fns_by_name = {
        task_fn.__name__: functools.partial(task_fn, app) for task_fn in task_fns
    }
    tasks: Set[asyncio.Task] = {
        asyncio.create_task(fn(), name=name) for name, fn in task_fns_by_name.items()
    }
    log.info(f"starting initial background tasks {tasks}")
    while True:
        done, pending = await asyncio.wait(
            tasks, timeout=timeout_seconds, return_when=asyncio.FIRST_COMPLETED
        )
        assert all(isinstance(task, asyncio.Task) for task in pending)
        log.debug(
            f"background task {done} completed, running: {[task.get_name() for task in pending]}"  # type: ignore
        )
        if shutdown.is_set():
            # wait for everything to finish
            await asyncio.wait(pending, return_when=asyncio.ALL_COMPLETED)
            log.info("all background tasks finished exiting")
            break

        for task in tasks:
            if task.done():
                if task.cancelled():
                    log.warn(f"task {task.get_name()} was cancelled")
                elif task.exception():
                    log.error(f"task {task.get_name()} errored")
                    task.print_stack()
                elif task.result() is None:
                    log.debug(f"task {task.get_name()} finished with result: None")
                else:
                    log.info(
                        f"task {task.get_name()} finished with result: {task.result()}"
                    )
                log.debug(f"queuing a new {task.get_name()} task")
                tasks.remove(task)
                tasks.add(
                    asyncio.create_task(
                        task_fns_by_name[task.get_name()](), name=task.get_name()
                    )
                )
