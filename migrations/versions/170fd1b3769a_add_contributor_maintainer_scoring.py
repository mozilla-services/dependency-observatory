"""Incorporate points for number of contributors/maintainers into scoring

Revision ID: 170fd1b3769a
Revises: 41041467b091
Create Date: 2020-08-04 19:26:23.376695

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "170fd1b3769a"
down_revision = "41041467b091"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("DROP VIEW report_score_view")
    op.execute("DROP VIEW score_view")
    op.execute(
        """
        CREATE OR REPLACE VIEW score_view AS
        SELECT reports.package,
           reports.version,
           reports.release_date,
           reports.scoring_date,
           reports.top_score,
           reports.npmsio_score,
           reports.npmsio_scored_package_version,
           reports."directVulnsCritical_score",
           reports."directVulnsHigh_score",
           reports."directVulnsMedium_score",
           reports."directVulnsLow_score",
           reports."indirectVulnsCritical_score",
           reports."indirectVulnsHigh_score",
           reports."indirectVulnsMedium_score",
           reports."indirectVulnsLow_score",
           reports.authors,
           reports.contributors,
           reports.immediate_deps,
           reports.all_deps,
           reports.id,
           reports.graph_id,
        npmsio_score * 100 +
        CASE
        WHEN all_deps <= 5 THEN 10
        WHEN all_deps <= 20 THEN 5
        WHEN all_deps >= 100 THEN -5
        WHEN all_deps >= 500 THEN -10
        ELSE 0
        END +
        CASE WHEN "directVulnsCritical_score" > 0 THEN -30 * "directVulnsCritical_score" ELSE 0 END +
        CASE WHEN "directVulnsHigh_score" > 0 THEN -15 * "directVulnsHigh_score" ELSE 0 END +
        CASE WHEN "directVulnsMedium_score" > 0 THEN -7 * "directVulnsMedium_score" ELSE 0 END +
        CASE WHEN "indirectVulnsCritical_score" > 0 THEN -15 * "indirectVulnsCritical_score" ELSE 0 END +
        CASE WHEN "indirectVulnsHigh_score" > 0 THEN -7 * "indirectVulnsHigh_score" ELSE 0 END +
        CASE WHEN "indirectVulnsMedium_score" > 0 THEN -4 * "indirectVulnsMedium_score" ELSE 0 END +
        CASE
        WHEN contributors < 3 THEN -5
        WHEN contributors >= 10 THEN 5
        WHEN contributors >= 20 THEN -5
        ELSE 0
        END +
        CASE
        WHEN authors = 1 THEN -10
        WHEN authors >= 5 THEN 10
        WHEN authors >= 15 THEN -10
        ELSE 0
        END
        AS score
        FROM reports
    """
    )
    op.execute(
        """
        CREATE OR REPLACE VIEW report_score_view AS
        SELECT reports.package,
           reports.version,
           reports.release_date,
           reports.scoring_date,
           reports.top_score,
           reports.npmsio_score,
           reports.npmsio_scored_package_version,
           reports."directVulnsCritical_score",
           reports."directVulnsHigh_score",
           reports."directVulnsMedium_score",
           reports."directVulnsLow_score",
           reports."indirectVulnsCritical_score",
           reports."indirectVulnsHigh_score",
           reports."indirectVulnsMedium_score",
           reports."indirectVulnsLow_score",
           reports.authors,
           reports.contributors,
           reports.immediate_deps,
           reports.all_deps,
           reports.id,
           reports.graph_id,
           score_view.score,
               CASE
                   WHEN score_view.score >= 100::double precision THEN 'A'::text
                   WHEN score_view.score >= 80::double precision THEN 'B'::text
                   WHEN score_view.score >= 60::double precision THEN 'C'::text
                   WHEN score_view.score >= 40::double precision THEN 'D'::text
                   ELSE 'E'::text
               END AS score_code
          FROM reports
            JOIN score_view ON reports.id = score_view.id
    """
    )


def downgrade():
    op.execute("DROP VIEW report_score_view")
    op.execute("DROP VIEW score_view")
    op.execute(
        """
        CREATE OR REPLACE VIEW score_view AS
        SELECT reports.package,
           reports.version,
           reports.release_date,
           reports.scoring_date,
           reports.top_score,
           reports.npmsio_score,
           reports.npmsio_scored_package_version,
           reports."directVulnsCritical_score",
           reports."directVulnsHigh_score",
           reports."directVulnsMedium_score",
           reports."directVulnsLow_score",
           reports."indirectVulnsCritical_score",
           reports."indirectVulnsHigh_score",
           reports."indirectVulnsMedium_score",
           reports."indirectVulnsLow_score",
           reports.authors,
           reports.contributors,
           reports.immediate_deps,
           reports.all_deps,
           reports.id,
           reports.graph_id,
        npmsio_score * 100 +
        CASE
        WHEN all_deps <= 5 THEN 10
        WHEN all_deps <= 20 THEN 5
        WHEN all_deps >= 100 THEN -5
        WHEN all_deps >= 500 THEN -10
        ELSE 0
        END +
        CASE WHEN "directVulnsCritical_score" > 0 THEN -30 * "directVulnsCritical_score" ELSE 0 END +
        CASE WHEN "directVulnsHigh_score" > 0 THEN -15 * "directVulnsHigh_score" ELSE 0 END +
        CASE WHEN "directVulnsMedium_score" > 0 THEN -7 * "directVulnsMedium_score" ELSE 0 END +
        CASE WHEN "indirectVulnsCritical_score" > 0 THEN -15 * "indirectVulnsCritical_score" ELSE 0 END +
        CASE WHEN "indirectVulnsHigh_score" > 0 THEN -7 * "indirectVulnsHigh_score" ELSE 0 END +
        CASE WHEN "indirectVulnsMedium_score" > 0 THEN -4 * "indirectVulnsMedium_score" ELSE 0 END
        AS score
        FROM reports
    """
    )
    op.execute(
        """
        CREATE OR REPLACE VIEW report_score_view AS
        SELECT reports.package,
           reports.version,
           reports.release_date,
           reports.scoring_date,
           reports.top_score,
           reports.npmsio_score,
           reports.npmsio_scored_package_version,
           reports."directVulnsCritical_score",
           reports."directVulnsHigh_score",
           reports."directVulnsMedium_score",
           reports."directVulnsLow_score",
           reports."indirectVulnsCritical_score",
           reports."indirectVulnsHigh_score",
           reports."indirectVulnsMedium_score",
           reports."indirectVulnsLow_score",
           reports.authors,
           reports.contributors,
           reports.immediate_deps,
           reports.all_deps,
           reports.id,
           reports.graph_id,
           score_view.score,
               CASE
                   WHEN score_view.score >= 100::double precision THEN 'A'::text
                   WHEN score_view.score >= 80::double precision THEN 'B'::text
                   WHEN score_view.score >= 60::double precision THEN 'C'::text
                   WHEN score_view.score >= 40::double precision THEN 'D'::text
                   ELSE 'E'::text
               END AS score_code
          FROM reports
            JOIN score_view ON reports.id = score_view.id
    """
    )
