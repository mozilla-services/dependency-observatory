"""add report_score_view

Revision ID: aacbf5c53b01
Revises: f385bd922f7d
Create Date: 2020-05-19 21:29:50.460514

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "aacbf5c53b01"
down_revision = "f385bd922f7d"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE OR REPLACE VIEW report_score_view AS
        SELECT reports.*, score_view.score AS score,
        CASE
        WHEN score_view.score >= 80 THEN 'A'
        WHEN score_view.score >= 60 THEN 'B'
        WHEN score_view.score >= 40 THEN 'C'
        WHEN score_view.score >= 20 THEN 'D'
        ELSE 'E'
        END as score_code
        FROM reports INNER JOIN score_view ON reports.id = score_view.id
    """
    )


def downgrade():
    op.execute("DROP VIEW report_score_view")
