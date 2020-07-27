from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

# from flask import current_app
import marshmallow
import marshmallow_dataclass

from depobs.worker import validators


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
    kwargs: Dict[str, Union[None, int, float, str]] = field(default_factory=dict)


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
            "validate": marshmallow.validate.Regexp(validators.NPM_PACKAGE_VERSION_RE)
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
    status: Optional[str]


ScanSchema = marshmallow_dataclass.class_schema(Scan)


@dataclass
class JSONResult:
    """
    A package scan
    """

    id: int

    data: Dict[str, Any]


JSONResultSchema = marshmallow_dataclass.class_schema(JSONResult)
