import logging
from typing import Dict, Generator, Optional, Tuple

from google.api_core.exceptions import AlreadyExists, GoogleAPICallError, RetryError
from google.cloud import pubsub_v1


log = logging.getLogger(__name__)


def create_pubsub_topic(project_id: str, topic_id: str) -> None:
    """
    Creates a pubsub topic with the provided project_id and topic_id

    Catches AlreadyExists 409 errors.
    """
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(project_id, topic_id)
    log.info(f"creating topic with path {topic_path}")
    try:
        topic = publisher.create_topic(topic_path)
        log.info(f"created pubsub topic {topic} at {topic_path}")
    except AlreadyExists as err:
        log.info(f"pubsub topic with path {topic_path} already exists. Error: {err}")


def subscribe_to_pubsub_topic(
    project_id: str, topic_id: str, subscription_id: str,
) -> Tuple[pubsub_v1.subscriber.client.Client, str]:
    """
    Creates a subscription on a pubsub topic with the provided
    project_id, topic_id, and subscription_id.

    Catches AlreadyExists 409 errors.
    """
    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(project_id, subscription_id)
    topic_path = subscriber.topic_path(project_id, topic_id)
    try:
        subscriber.create_subscription(subscription_path, topic_path)
        log.info(
            f"pubsub subscription with path {subscription_path} and topic path {topic_path}"
        )
    except AlreadyExists as err:
        log.info(
            f"pubsub subscription with path {subscription_path} and topic path {topic_path} already exists. Error: {err}"
        )
    return subscriber, subscription_path


def subscribe_and_poll(
    project_id: str, topic_id: str, subscription_id: str
) -> Generator[Optional[Dict], None, None]:
    """
    Subscribes to the pubsub topic ID and polls for responses yielding
    received messages (possibly redundant messages) and acking them
    when the next message is received

    """
    subscriber, subscription_path = subscribe_to_pubsub_topic(
        project_id, topic_id, subscription_id,
    )
    max_messages = 10
    timeout = 15
    while True:
        log.info(
            f"polling for messages from {subscription_path} (max_msgs={max_messages}, timeout={timeout})"
        )
        try:
            response: pubsub_v1.types.PullResponse = subscriber.pull(
                subscription_path, max_messages=max_messages, timeout=timeout
            )
        except RetryError as err:
            log.info(f"got gapi retry error {err}")
            continue
        except GoogleAPICallError as err:
            log.error(f"got generic gapi call error {err}")
            continue

        for message in response.received_messages:
            # TODO: have receiver send whether to ack each message or not back
            # ack: bool = yield message
            # if ack:
            #     subscriber.acknowledge(subscription_path, message.ack_id)
            yield message
            log.info(f"acking message with ack_id: {message.ack_id}")
            subscriber.acknowledge(subscription_path, [message.ack_id])
