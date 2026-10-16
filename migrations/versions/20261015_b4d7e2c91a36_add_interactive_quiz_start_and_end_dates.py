"""add interactive quiz start and end dates

Revision ID: b4d7e2c91a36
Revises: d015dd94f42e
Create Date: 2026-10-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4d7e2c91a36'
down_revision: Union[str, Sequence[str], None] = 'd015dd94f42e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    rows = bind.execute(sa.text(f"PRAGMA table_info({table_name})")).fetchall()
    return column_name in {row[1] for row in rows}


def upgrade() -> None:
    # Both columns are nullable and NULL means 'always available', so no
    # backfill is needed and existing quizzes keep their current behavior.
    if not has_column("interactive_quiz", "start_date"):
        op.add_column(
            "interactive_quiz",
            sa.Column("start_date", sa.DateTime(), nullable=True),
        )
    if not has_column("interactive_quiz", "end_date"):
        op.add_column(
            "interactive_quiz",
            sa.Column("end_date", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    # batch_alter_table is used because it is the safe way to drop columns
    # on SQLite
    if has_column("interactive_quiz", "start_date"):
        with op.batch_alter_table("interactive_quiz") as batch_op:
            batch_op.drop_column("start_date")
    if has_column("interactive_quiz", "end_date"):
        with op.batch_alter_table("interactive_quiz") as batch_op:
            batch_op.drop_column("end_date")
