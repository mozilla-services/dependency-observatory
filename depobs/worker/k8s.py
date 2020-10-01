import logging
from typing import Dict, List, Optional, TypedDict

import kubernetes


log = logging.getLogger(__name__)


class KubeSecretVolume(TypedDict):

    secret_name: str

    name: str


class KubeVolumeMount(TypedDict):

    mount_path: str

    name: str


class KubeJobConfig(TypedDict):
    """
    A subset of options to run a k8s Job:

    V1Job
    V1JobSpec
    V1PodTemplateSpec
    V1Container
    """

    # k8s config context name to use (to access other clusters)
    context_name: str

    # k8s namespace to create pods e.g. "default"
    namespace: str

    # k8s container and Job name should be unique per run
    name: str

    # number of retries before marking this job failed
    backoff_limit: int

    # container image to run
    image_name: str

    # container args to pass to the image entrypoint
    args: List[str]

    # env vars
    env: Dict[str, str]

    # service account name to run the job pod with
    service_account_name: str

    # container volume_mounts
    volume_mounts: List[KubeVolumeMount]

    # volumes with secret sources
    secrets: List[KubeSecretVolume]


def get_api_client(context_name: Optional[str] = None) -> kubernetes.client.ApiClient:
    """
    Returns the k8s ApiClient using the provided context name

    Defaults to the in cluster config when context_name is None.
    """
    if context_name is None:
        kubernetes.config.load_incluster_config()
    else:
        kubernetes.config.load_kube_config(context=context_name)
    return kubernetes.client.ApiClient(configuration=kubernetes.client.Configuration())


def create_job(
    job_config: KubeJobConfig,
) -> kubernetes.client.V1Job:
    api_client = get_api_client(job_config["context_name"])
    # Configureate Pod template container
    container = kubernetes.client.V1Container(
        name=job_config["name"],
        image=job_config["image_name"],
        image_pull_policy="IfNotPresent",
        args=job_config["args"],
        env=[dict(name=k, value=v) for (k, v) in job_config["env"].items()],
        volume_mounts=[
            kubernetes.client.V1VolumeMount(
                mount_path=volume_mount["mount_path"], name=volume_mount["name"]
            )
            for volume_mount in job_config["volume_mounts"]
        ],
    )

    pod_spec_kwargs = dict(
        restart_policy="Never",
        containers=[container],
        service_account_name=job_config["service_account_name"],
        security_context=kubernetes.client.V1PodSecurityContext(
            run_as_user=10001, run_as_group=10001
        ),
        volumes=[
            kubernetes.client.V1Volume(
                name=secret["name"],
                secret=kubernetes.client.V1SecretVolumeSource(
                    secret_name=secret["secret_name"],
                ),
            )
            for secret in job_config["secrets"]
        ],
    )

    # Create and configurate a spec section
    template = kubernetes.client.V1PodTemplateSpec(
        metadata=kubernetes.client.V1ObjectMeta(labels={}),
        spec=kubernetes.client.V1PodSpec(**pod_spec_kwargs),
    )

    # Create the specification of deployment
    spec = kubernetes.client.V1JobSpec(
        template=template,
        backoff_limit=job_config["backoff_limit"],
    )

    # Instantiate the job object
    job_obj = kubernetes.client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=kubernetes.client.V1ObjectMeta(name=job_config["name"]),
        spec=spec,
    )
    job = kubernetes.client.BatchV1Api(api_client=api_client).create_namespaced_job(
        namespace=job_config["namespace"],
        body=job_obj,
    )
    return job
