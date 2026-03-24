"""Add index on media.project_id

Revision ID: 003
Revises: 002
Create Date: 2026-03-24
"""
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_media_project_id", "media", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_media_project_id", "media")
