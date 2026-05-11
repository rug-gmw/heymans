"""add chat quiz skill columns

Revision ID: b663c806da2b
Revises: 
Create Date: 2026-05-11 09:27:40.374820

"""
from alembic import op
import sqlalchemy as sa

revision = "b663c806da2b"     
down_revision = None
branch_labels = None
depends_on = None

DEFAULT_SKILLS = '["understand","apply","analyze","evaluate","create"]'

def has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    rows = bind.execute(sa.text(f"PRAGMA table_info({table_name})")).fetchall()
    return column_name in {row[1] for row in rows}


def upgrade() -> None:
    if not has_column("interactive_quiz", "enabled_skills"):
        op.add_column(
            "interactive_quiz",
            sa.Column(
                "enabled_skills",
                sa.Text(),
                nullable=True,
                server_default=DEFAULT_SKILLS,
            ),
        )

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

    if not has_column("interactive_quiz_conversation", "bloom_skill"):
        op.add_column(
            "interactive_quiz_conversation",
            sa.Column("bloom_skill", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    if has_column("interactive_quiz_conversation", "bloom_skill"):
        op.drop_column("interactive_quiz_conversation", "bloom_skill")

    if has_column("interactive_quiz", "enabled_skills"):
        op.drop_column("interactive_quiz", "enabled_skills")