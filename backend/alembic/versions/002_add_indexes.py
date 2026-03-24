"""Add indexes for common query patterns

Revision ID: 002
Revises: 001
Create Date: 2026-03-24
"""
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_projects_user_id", "projects", ["user_id"])
    op.create_index("ix_projects_status", "projects", ["status"])
    op.create_index("ix_projects_visual_style", "projects", ["visual_style"])
    op.create_index("ix_tasks_project_id", "tasks", ["project_id"])
    op.create_index("ix_tasks_status", "tasks", ["status"])


def downgrade() -> None:
    op.drop_index("ix_tasks_status", "tasks")
    op.drop_index("ix_tasks_project_id", "tasks")
    op.drop_index("ix_projects_visual_style", "projects")
    op.drop_index("ix_projects_status", "projects")
    op.drop_index("ix_projects_user_id", "projects")
