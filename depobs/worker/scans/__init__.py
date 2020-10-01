from typing import Type

from depobs.worker.scan_config import ScanConfig
from depobs.worker.scans.npm_dep_files import NPMDepFilesScan
from depobs.worker.scans.npm_package import NPMPackageScan


def scan_type_to_config(scan_type: str) -> Type[ScanConfig]:
    scan_config = {
        "scan_score_npm_dep_files": NPMDepFilesScan,
        "scan_score_npm_package": NPMPackageScan,
    }.get(scan_type, None)

    if scan_config is None:
        raise Exception(f"Cannot get config for invalid scan type {scan_type}")

    return scan_config


__all__ = [
    "NPMDepFilesScan",
    "NPMPackageScan",
    "scan_type_to_config",
]
