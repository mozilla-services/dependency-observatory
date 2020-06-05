import contextlib
from typing import Dict, Generator, List, Optional, TypedDict

import kubernetes as k8s


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


def get_client() -> k8s.client:
    k8s.config.load_incluster_config()
    return k8s.client


@contextlib.contextmanager
def run_job(job_config: KubeJobConfig,) -> Generator[k8s.client.V1Job, None, None]:
    """
    Starts a k8s job with provided config and yields the job api response

    Deletes the job when then context manager exits
    """
    get_client()

    # Configureate Pod template container
    container = k8s.client.V1Container(
        name=job_config["name"],
        image=job_config["image_name"],
        image_pull_policy="IfNotPresent",
        args=job_config["args"],
        env=[dict(name=k, value=v) for (k, v) in job_config["env"].items()],
    )
    # Create and configurate a spec section
    template = k8s.client.V1PodTemplateSpec(
        metadata=k8s.client.V1ObjectMeta(labels={}),
        spec=k8s.client.V1PodSpec(restart_policy="Never", containers=[container]),
    )

    # Create the specification of deployment
    spec = k8s.client.V1JobSpec(template=template, backoff_limit=4)

    # Instantiate the job object
    job_obj = k8s.client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=k8s.client.V1ObjectMeta(name=job_config["name"]),
        spec=spec,
    )
    job = k8s.client.BatchV1Api().create_namespaced_job(
        body=job_obj, namespace=job_config["namespace"]
    )
    try:
        yield job
    finally:
        k8s.client.BatchV1Api().delete_namespaced_job(
            name=job_config["name"],
            namespace=job_config["namespace"],
            body=k8s.client.V1DeleteOptions(
                propagation_policy="Foreground", grace_period_seconds=5
            ),
        )
