"""add missing sequences

Revision ID: 5c9047774d37
Revises: aacbf5c53b01
Create Date: 2020-05-21 21:04:08.624287

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "5c9047774d37"
down_revision = "aacbf5c53b01"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SEQUENCE package_version_id_seq")
    op.execute("CREATE SEQUENCE package_version_link_id_seq")
    op.execute("CREATE SEQUENCE package_graphs_id_seq")
    op.execute("CREATE SEQUENCE advisories_id_seq")
    op.execute("CREATE SEQUENCE npmsio_score_id_seq")
    op.execute("CREATE SEQUENCE npm_registry_entry_id_seq")


def downgrade():
    op.execute("DROP SEQUENCE package_version_id_seq")
    op.execute("DROP SEQUENCE package_version_link_id_seq")
    op.execute("DROP SEQUENCE package_graphs_id_seq")
    op.execute("DROP SEQUENCE advisories_id_seq")
    op.execute("DROP SEQUENCE npmsio_score_id_seq")
    op.execute("DROP SEQUENCE npm_registry_entry_id_seq")
