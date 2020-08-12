"""add view for previous scoring algorithm

Revision ID: 63f04096672e
Revises: 170fd1b3769a
Create Date: 2020-08-11 15:32:55.548058

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "63f04096672e"
down_revision = "170fd1b3769a"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE OR REPLACE VIEW score_view_v0 AS
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
        npmsio_score * 100 +
        CASE
        WHEN all_deps <= 5 THEN 20
        WHEN all_deps <= 20 THEN 10
        WHEN all_deps >= 500 THEN -20
        WHEN all_deps >= 100 THEN -10
        ELSE 0
        END +
        CASE WHEN "directVulnsCritical_score" > 0 THEN -20 ELSE 0 END +
        CASE WHEN "directVulnsHigh_score" > 0 THEN -10 ELSE 0 END +
        CASE WHEN "directVulnsMedium_score" > 0 THEN -5 ELSE 0 END +
        CASE WHEN "indirectVulnsCritical_score" > 0 THEN -10 ELSE 0 END +
        CASE WHEN "indirectVulnsHigh_score" > 0 THEN -7 ELSE 0 END +
        CASE WHEN "indirectVulnsMedium_score" > 0 THEN -3 ELSE 0 END
        AS score
        FROM reports
    """
    )
    op.execute(
        """
        CREATE OR REPLACE VIEW report_score_view_v0 AS
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
           score_view_v0.score,
               CASE
                   WHEN score_view_v0.score >= 80::double precision THEN 'A'::text
                   WHEN score_view_v0.score >= 60::double precision THEN 'B'::text
                   WHEN score_view_v0.score >= 40::double precision THEN 'C'::text
                   WHEN score_view_v0.score >= 20::double precision THEN 'D'::text
                   ELSE 'E'::text
               END AS score_code
          FROM reports
            JOIN score_view_v0 ON reports.id = score_view_v0.id
    """
    )


def downgrade():
    op.execute("DROP VIEW report_score_view_v0")
    op.execute("DROP VIEW score_view_v0")
