"""add interactive quiz skill columns

Revision ID: d015dd94f42e
Revises: 
Create Date: 2026-05-12 10:43:43.445784

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd015dd94f42e'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_SKILLS = '["understand","apply","analyze","evaluate","create"]'

def has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    rows = bind.execute(sa.text(f"PRAGMA table_info({table_name})")).fetchall()
    return column_name in {row[1] for row in rows}


def upgrade() -> None:
    # 1. add (nullable) columns if they don't exist:
    if not has_column("interactive_quiz", "enabled_skills"):
        # 1. add as nullable first
        op.add_column(
            "interactive_quiz",
            sa.Column(
                "enabled_skills",
                sa.Text(),
                nullable=True,
                server_default=DEFAULT_SKILLS,
            ),
        )

    # 2. backfill with DEFAULT_SKILLS
    op.execute(
        sa.text(
            """
            UPDATE interactive_quiz
            SET enabled_skills = :skills
            WHERE enabled_skills IS NULL
               OR TRIM(enabled_skills) = ''
            """
        ).bindparams(skills=DEFAULT_SKILLS)
    )

    # 3. Then make non-nullable
    with op.batch_alter_table("interactive_quiz") as batch_op:
        batch_op.alter_column(
            "enabled_skills",
            existing_type=sa.Text(),
            nullable=False,
            existing_server_default=DEFAULT_SKILLS,
        )

    # Update previously existing conversations; 'empty' bloom_skills:
    if not has_column("interactive_quiz_conversation", "bloom_skill"):
        op.add_column(
            "interactive_quiz_conversation",
            sa.Column(
                "bloom_skill", 
                sa.Text(), 
                nullable=False, 
                server_default=""
            ),
        )


def downgrade() -> None:
    if has_column("interactive_quiz_conversation", "bloom_skill"):
        op.drop_column("interactive_quiz_conversation", "bloom_skill")

    if has_column("interactive_quiz", "enabled_skills"):
        op.drop_column("interactive_quiz", "enabled_skills")