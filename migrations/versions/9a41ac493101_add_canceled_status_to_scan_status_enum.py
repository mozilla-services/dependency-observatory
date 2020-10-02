"""add canceled status to scan status enum

Revision ID: 9a41ac493101
Revises: 4363b7a9ada6
Create Date: 2020-10-02 16:52:51.649004

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "9a41ac493101"
down_revision = "4363b7a9ada6"
branch_labels = None
depends_on = None


def upgrade():
    # https://github.com/sqlalchemy/alembic/issues/278
    op.execute("ALTER TYPE scan_status_enum ADD value 'canceled' AFTER 'succeeded'")


def downgrade():
    # remove references to the deprecated value
    op.execute("UPDATE scans SET status = 'failed' WHERE status = 'canceled'")

    # rename the existing type
    op.execute("ALTER TYPE scan_status_enum RENAME TO scan_status_enum_old")

    # create the new type
    op.execute(
        "CREATE TYPE scan_status_enum AS ENUM('queued', 'started', 'failed', 'succeeded')"
    )

    # update the columns to use the new type
    op.execute(
        "ALTER TABLE scans ALTER COLUMN status TYPE scan_status_enum USING status::text::scan_status_enum"
    )

    # remove the old type
    op.execute("DROP TYPE scan_status_enum_old")
