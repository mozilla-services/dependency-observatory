import asyncio
import logging

import kubernetes


from depobs.worker import k8s


log = logging.getLogger(__name__)


class ScanTypeConfig:
    """
    Defines how to run a scan of a given type.
    """

    name = None

    def run(self):
        raise NotImplementedError()


async def run_job_to_completion(
    job_config: k8s.KubeJobConfig,
    scan_id: int,
) -> kubernetes.client.models.v1_job.V1Job:
    job_name = job_config["name"]
    log.info(f"scan {scan_id} starting job {job_name} with config {job_config}")
    with k8s.run_job(job_config) as job:
        log.info(f"scan {scan_id} started job {job}")
        await asyncio.sleep(1)
        job = k8s.read_job(
            job_config["namespace"], job_name, context_name=job_config["context_name"]
        )
        log.info(f"scan {scan_id} got initial job status {job.status}")
        while True:
            if job.status.failed:
                log.error(f"scan {scan_id} k8s job {job_name} failed")
                return job
            if job.status.succeeded:
                log.info(f"scan {scan_id} k8s job {job_name} succeeded")
                return job
            if not job.status.active:
                log.error(
                    f"scan {scan_id} k8s job {job_name} stopped/not active (did not fail or succeed)"
                )
                return job

            await asyncio.sleep(5)
            job = k8s.read_job(
                job_config["namespace"],
                job_name,
                context_name=job_config["context_name"],
            )
            log.info(f"scan {scan_id} got job status {job.status}")
