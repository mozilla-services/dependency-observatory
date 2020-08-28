from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

import marshmallow
import marshmallow_dataclass


@dataclass
class PackageReportDataclass:
    """"""

    id = int
    package = str
    version = str

    # NB: these are datetimes
    release_date = Optional[str]
    scoring_date = Optional[str]

    npmsio_score = Optional[float]
    npmsio_scored_package_version = Optional[str]
    directVulnsCritical_score = Optional[int]
    directVulnsHigh_score = Optional[int]
    directVulnsMedium_score = Optional[int]
    directVulnsLow_score = Optional[int]
    indirectVulnsCritical_score = Optional[int]
    indirectVulnsHigh_score = Optional[int]
    indirectVulnsMedium_score = Optional[int]
    indirectVulnsLow_score = Optional[int]
    authors = Optional[int]
    contributors = Optional[int]
    immediate_deps = Optional[int]
    all_deps = Optional[int]
    graph_id = Optional[int]

    score = Optional[float]
    score_code = Optional[str]


PackageReportSchema = marshmallow_dataclass.class_schema(PackageReportDataclass)
