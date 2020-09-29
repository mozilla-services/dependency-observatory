import asyncio
import concurrent.futures
import functools
import logging

import flask
from flask import current_app

from depobs.database.models import (
    save_json_results,
)
from depobs.worker import gcp


log = logging.getLogger(__name__)


def save_pubsub_message(
    app: flask.Flask, message: gcp.pubsub_v1.types.PubsubMessage
) -> None:
    """
    Saves a pubsub message data to the JSONResult table and acks it.

    nacks it if saving fails.

    Requires depobs flask app context.
    """
    with app.app_context():
        try:
            # TODO: set job status when it finishes? No, do this in the runner.
            log.info(
                f"received pubsub message {message.message_id} published at {message.publish_time} with attrs {message.attributes}"
            )
            save_json_results(
                [
                    {
                        "type": "google.cloud.pubsub_v1.types.PubsubMessage",
                        "id": message.message_id,
                        "publish_time": flask.json.dumps(
                            message.publish_time
                        ),  # convert datetime
                        "attributes": dict(
                            message.attributes
                        ),  # convert from ScalarMapContainer
                        "data": flask.json.loads(message.data),
                        "size": message.size,
                    }
                ]
            )
            message.ack()
        except Exception as err:
            message.nack()
            log.error(
                f"error saving pubsub message {message} to json results table: {err}"
            )


def run_pubsub_thread(app: flask.Flask, timeout=30):
    """
    Runs a thread that:

    * subscribes to GCP pubsub output
    * saves the job output to the JSONResult table

    Requires depobs flask app context.
    """
    with app.app_context():
        future: gcp.pubsub_v1.subscriber.futures.StreamingPullFuture = (
            gcp.receive_pubsub_messages(
                current_app.config["GCP_PROJECT_ID"],
                current_app.config["JOB_STATUS_PUBSUB_TOPIC"],
                current_app.config["JOB_STATUS_PUBSUB_SUBSCRIPTION"],
                functools.partial(save_pubsub_message, app),
            )
        )
        while True:
            try:
                future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                log.debug(f"{timeout}s timeout for pubsub receiving exceeded")
            except KeyboardInterrupt:  # stop the thread on keyboard interrupt
                future.cancel()


async def save_pubsub(app: flask.Flask) -> None:
    loop = asyncio.get_running_loop()

    # run in the default loop executor
    await loop.run_in_executor(None, functools.partial(run_pubsub_thread, app))
