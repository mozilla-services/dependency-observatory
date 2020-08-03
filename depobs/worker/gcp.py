import logging
from typing import Callable, Dict, Generator, Optional, Tuple

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


def receive_pubsub_messages(
    project_id: str,
    topic_id: str,
    subscription_id: str,
    callback: Callable[[pubsub_v1.types.PubsubMessage], None],
) -> pubsub_v1.subscriber.futures.StreamingPullFuture:
    """
    Starts a background thread that subscribes to the pubsub topic ID
    and calls the callback param on each message. Returns the pubsub
    StreamingPullFuture.

    The callback should:

    * call .ack() or .nack() on each message
    * be idempotent since messages might be delivered twice
    * not raise exceptions unless it wants to stop receiving messages

    """
    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(project_id, subscription_id)
    log.info(
        f"starting thread to receive messages from {subscription_path} and call {callback} on them"
    )
    future: pubsub_v1.subscriber.futures.StreamingPullFuture = subscriber.subscribe(
        subscription_path, callback
    )
    return future
