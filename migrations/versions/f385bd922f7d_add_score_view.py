"""add score_view

Revision ID: f385bd922f7d
Revises: 57caebdb2d45
Create Date: 2020-05-19 19:21:14.249642

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f385bd922f7d"
down_revision = "57caebdb2d45"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE OR REPLACE VIEW score_view AS
        SELECT reports.*,
        npmsio_score * 100 +
        CASE
        WHEN all_deps <= 5 THEN 20
        WHEN all_deps <= 20 THEN 10
        WHEN all_deps >= 500 THEN -20
        WHEN all_deps >= 100 THEN -10
        END +
        CASE WHEN "directVulnsCritical_score" > 0 THEN -20 ELSE 0 END +
        CASE WHEN "directVulnsHigh_score" > 0 THEN -10 ELSE 0 END +
        CASE WHEN "directVulnsMedium_score" > 0 THEN -5 ELSE 0 END +
        CASE WHEN "indirectVulnsCritical_score" > 0 THEN -10 ELSE 0 END +
        CASE WHEN "indirectVulnsHigh_score" > 0 THEN -7 ELSE 0 END +
        CASE WHEN "indirectVulnsMedium_score" > 0 THEN -3 ELSE 0 END
        AS score
        FROM reports
        WHERE status = 'scanned'
    """
    )


def downgrade():
    op.execute("DROP VIEW score_view")
