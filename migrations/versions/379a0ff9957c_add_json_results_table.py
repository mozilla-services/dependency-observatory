"""add json_results table

Revision ID: 379a0ff9957c
Revises: 5752b9d007c3
Create Date: 2020-06-12 21:01:04.569822

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "379a0ff9957c"
down_revision = "5752b9d007c3"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "json_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "inserted_at",
            sa.DateTime(),
            server_default=sa.text("TIMEZONE('utc', CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("json_results")
    # ### end Alembic commands ###
