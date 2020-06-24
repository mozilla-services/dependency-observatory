import contextlib
import logging
from typing import Dict, Generator, List, Optional, TypedDict

import kubernetes


log = logging.getLogger(__name__)


class KubeJobConfig(TypedDict):
    """
    A subset of options to run a k8s Job:

    V1Job
    V1JobSpec
    V1PodTemplateSpec
    V1Container
    """

    # k8s namespace to create pods e.g. "default"
    namespace: str

    # k8s container and Job name should be unique per run
    name: str

    # container image to run
    image_name: str

    # container args to pass to the image entrypoint
    args: List[str]

    # env vars
    env: Dict[str, str]

    # service account name to run the job pod with
    service_account_name: str


def get_client() -> kubernetes.client:
    kubernetes.config.load_incluster_config()
    return kubernetes.client


def create_job(job_config: KubeJobConfig,) -> kubernetes.client.V1Job:
    get_client()
    # Configureate Pod template container
    container = kubernetes.client.V1Container(
        name=job_config["name"],
        image=job_config["image_name"],
        image_pull_policy="IfNotPresent",
        args=job_config["args"],
        env=[dict(name=k, value=v) for (k, v) in job_config["env"].items()],
    )
    pod_spec_kwargs = dict(
        restart_policy="Never",
        containers=[container],
        service_account_name=job_config["service_account_name"],
    )

    # Create and configurate a spec section
    template = kubernetes.client.V1PodTemplateSpec(
        metadata=kubernetes.client.V1ObjectMeta(labels={}),
        spec=kubernetes.client.V1PodSpec(**pod_spec_kwargs),
    )

    # Create the specification of deployment
    spec = kubernetes.client.V1JobSpec(template=template, backoff_limit=4)

    # Instantiate the job object
    job_obj = kubernetes.client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=kubernetes.client.V1ObjectMeta(name=job_config["name"]),
        spec=spec,
    )
    job = kubernetes.client.BatchV1Api().create_namespaced_job(
        body=job_obj, namespace=job_config["namespace"]
    )
    return job


def read_job(namespace: str, name: str) -> kubernetes.client.models.v1_job.V1Job:
    return (
        kubernetes.client.BatchV1Api()
        .list_namespaced_job(namespace=namespace, label_selector=f"job-name={name}",)
        .items[0]
    )


def read_job_status(
    namespace: str, name: str
) -> kubernetes.client.models.v1_job_status.V1JobStatus:
    # TODO: figure out status only perms for:
    # .read_namespaced_job_status(name=job_name, namespace=job_config["namespace"])
    return read_job(namespace, name).status


def delete_job(namespace: str, name: str):
    return kubernetes.client.BatchV1Api().delete_namespaced_job(
        name=name,
        namespace=namespace,
        body=kubernetes.client.V1DeleteOptions(
            propagation_policy="Foreground", grace_period_seconds=5
        ),
    )


def get_job_pod(namespace: str, name: str) -> kubernetes.client.V1Pod:
    return (
        kubernetes.client.CoreV1Api()
        .list_namespaced_pod(namespace=namespace, label_selector=f"job-name={name}",)
        .items[0]
    )


def read_job_logs(
    namespace: str, name: str, read_logs_kwargs: Optional[Dict] = None
) -> str:
    read_logs_kwargs = dict() if read_logs_kwargs is None else read_logs_kwargs
    job_pod_name = get_job_pod(namespace, name).metadata.name

    log.info(f"reading logs from pod {job_pod_name} for job {namespace} {name}")
    return kubernetes.client.CoreV1Api().read_namespaced_pod_log(
        name=job_pod_name, namespace=namespace, **read_logs_kwargs
    )


def watch_job(
    namespace: str, name: str
) -> Generator[kubernetes.client.V1WatchEvent, None, None]:
    log.info(f"watching job pod for job {namespace} {name}")
    for event in kubernetes.watch.Watch().stream(
        kubernetes.client.BatchV1Api().list_namespaced_job,
        namespace=namespace,
        label_selector=f"job-name={name}",
    ):
        yield event


def watch_job_pods(
    namespace: str, name: str
) -> Generator[kubernetes.client.V1WatchEvent, None, None]:
    log.info(f"watching job pod for job {namespace} {name}")
    for event in kubernetes.watch.Watch().stream(
        kubernetes.client.CoreV1Api().list_namespaced_pod,
        namespace=namespace,
        label_selector=f"job-name={name}",
    ):
        yield event


def tail_job_logs(namespace: str, name: str) -> Generator[str, None, None]:
    job_pod_name = get_job_pod(namespace, name).metadata.name
    log.info(f"tailing logs from pod {job_pod_name} for job {namespace} {name}")
    for line in kubernetes.watch.Watch().stream(
        kubernetes.client.CoreV1Api().read_namespaced_pod_log,
        namespace=namespace,
        name=job_pod_name,
    ):
        yield line


@contextlib.contextmanager
def run_job(
    job_config: KubeJobConfig,
) -> Generator[kubernetes.client.V1Job, None, None]:
    """
    Creates and runs a k8s job with provided config and yields the job api response

    Deletes the job when then context manager exits
    """
    job = create_job(job_config)
    try:
        yield job
    finally:
        kubernetes.client.BatchV1Api().delete_namespaced_job(
            name=job_config["name"],
            namespace=job_config["namespace"],
            body=kubernetes.client.V1DeleteOptions(
                propagation_policy="Foreground", grace_period_seconds=5
            ),
        )
