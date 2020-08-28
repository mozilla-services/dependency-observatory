import logging
from typing import Iterable

import altair as alt

from depobs.database import models

log = logging.getLogger(__name__)


def package_score_reports_to_scores_histogram(
    reports: Iterable[models.PackageReport],
) -> alt.Chart:
    """
    Returns a vega spec and data to render a histogram of the
    distribution of scores for the provided package score reports
    """
    data = alt.Data(values=[dict(score=report.score) for report in reports])
    return (
        alt.Chart(data)
        .mark_bar()
        .encode(
            x=alt.X("score:O", bin=True, axis=alt.Axis(title="package score")),
            y=alt.Y("count()", axis=alt.Axis(title="count")),
        )
    )


def package_score_reports_to_score_grades_histogram(
    reports: Iterable[models.PackageReport],
) -> alt.Chart:
    """
    Returns a vega spec and data to render a histogram of the
    distribution of score grades for the provided package score reports
    """
    data = alt.Data(values=[dict(score_code=report.score_code) for report in reports])
    log.info(f"got score code data {data}")
    return (
        alt.Chart(data)
        .mark_bar()
        .encode(
            x=alt.X("score_code:O", axis=alt.Axis(title="package grade")),
            y=alt.Y("count()", axis=alt.Axis(title="count")),
        )
    )
