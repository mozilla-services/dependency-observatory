from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import marshmallow
import marshmallow_dataclass

from depobs.database.enums import ScanStatusEnum
from depobs.worker import validators


@dataclass
class ScanScoreNPMDepFilesRequestParams:
    """
    create_job request params for a scan_score_npm_dep_files job
    """

    scan_type: str = field(
        metadata={
            "validate": marshmallow.validate.Equal("scan_score_npm_dep_files"),
        }
    )
    package_manager: str = field(
        metadata={"validate": marshmallow.validate.Equal("npm")}
    )
    manifest_url: str = field(
        metadata={
            "validate": marshmallow.validate.URL(
                schemes={"http", "https"},
            ),
        }
    )
    lockfile_url: Optional[str] = field(
        metadata={
            "validate": marshmallow.validate.URL(
                schemes={"http", "https"},
            ),
        }
    )
    shrinkwrap_url: Optional[str] = field(
        metadata={
            "validate": marshmallow.validate.URL(
                schemes={"http", "https"},
            ),
        }
    )


ScanScoreNPMDepFilesRequestParamsSchema = marshmallow_dataclass.class_schema(
    ScanScoreNPMDepFilesRequestParams
)


@dataclass
class ScanScoreNPMPackageRequestParams:
    """
    create_job request params for a scan_score_npm_package job
    """

    scan_type: str = field(
        metadata={
            "validate": marshmallow.validate.Equal("scan_score_npm_package"),
        }
    )
    package_manager: str = field(
        metadata={"validate": marshmallow.validate.Equal("npm")}
    )
    package_name: str = field(
        metadata={
            "validate": marshmallow.validate.Regexp(validators.NPM_PACKAGE_NAME_RE)
        }
    )
    package_versions_type: str = field(
        metadata={
            "validate": marshmallow.validate.OneOf(
                choices=["specific-version", "releases", "latest"]
            ),
        }
    )
    package_version: Optional[str] = field(
        metadata={
            "validate": marshmallow.validate.Regexp(validators.NPM_PACKAGE_VERSION_RE)
        }
    )


ScanScoreNPMPackageRequestParamsSchema = marshmallow_dataclass.class_schema(
    ScanScoreNPMPackageRequestParams
)


@dataclass
class JobParams:
    """
    create_job request params
    """

    name: str = field(
        # TODO: find a clean way to add class names from config
        # metadata={
        #     "validate": marshmallow.validate.OneOf(
        #         choices=current_app.config["WEB_JOB_CONFIGS"]
        #     )
        # }
    )
    args: List[str] = field(default_factory=list)
    kwargs: Dict[str, Any] = field(default_factory=dict)


JobParamsSchema = marshmallow_dataclass.class_schema(JobParams)


@dataclass
class PackageReportParams:
    """
    Request parameters to fetch a package report
    """

    package_manager: str = field(
        metadata={"validate": marshmallow.validate.Equal("npm")}
    )
    package_name: str = field(
        metadata={
            "validate": marshmallow.validate.Regexp(validators.NPM_PACKAGE_NAME_RE)
        }
    )
    package_version: Optional[str] = field(
        metadata={
            "validate": lambda v: v == "latest"
            or marshmallow.validate.Regexp(validators.NPM_PACKAGE_VERSION_RE)(v)
        }
    )


PackageReportParamsSchema = marshmallow_dataclass.class_schema(PackageReportParams)


@dataclass
class Scan:
    """
    A package scan
    """

    id: int

    # blob of scan name, version, args, and kwargs
    params: Dict[str, Any]

    # scan status
    status: Optional[ScanStatusEnum]


ScanSchema = marshmallow_dataclass.class_schema(Scan)


@dataclass
class JSONResult:
    """
    A package scan
    """

    id: int

    data: Dict[str, Any]


JSONResultSchema = marshmallow_dataclass.class_schema(JSONResult)
