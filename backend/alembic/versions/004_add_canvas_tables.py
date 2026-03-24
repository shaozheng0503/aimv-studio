"""Add canvas and canvas_shots tables

Revision ID: 004
Revises: 003
Create Date: 2026-03-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "canvases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("nodes", postgresql.JSON(), nullable=False, server_default="[]"),
        sa.Column("edges", postgresql.JSON(), nullable=False, server_default="[]"),
        sa.Column("viewport", postgresql.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_canvases"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name="fk_canvases_project_id_projects"),
        sa.UniqueConstraint("project_id", name="uq_canvases_project_id"),
    )
    op.create_index("ix_canvases_project_id", "canvases", ["project_id"])

    op.create_table(
        "canvas_shots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("canvas_id", sa.Integer(), nullable=False),
        sa.Column("node_id", sa.String(64), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("model_name", sa.String(50), nullable=True),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("time_anchor", sa.Float(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("canvas_context", postgresql.JSON(), nullable=True),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("media_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_canvas_shots"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name="fk_canvas_shots_project_id_projects"),
        sa.ForeignKeyConstraint(["canvas_id"], ["canvases.id"], name="fk_canvas_shots_canvas_id_canvases"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], name="fk_canvas_shots_task_id_tasks"),
        sa.ForeignKeyConstraint(["media_id"], ["media.id"], name="fk_canvas_shots_media_id_media"),
    )
    op.create_index("ix_canvas_shots_project_id", "canvas_shots", ["project_id"])
    op.create_index("ix_canvas_shots_canvas_id", "canvas_shots", ["canvas_id"])
    op.create_index("ix_canvas_shots_status", "canvas_shots", ["status"])


def downgrade() -> None:
    op.drop_index("ix_canvas_shots_status", "canvas_shots")
    op.drop_index("ix_canvas_shots_canvas_id", "canvas_shots")
    op.drop_index("ix_canvas_shots_project_id", "canvas_shots")
    op.drop_table("canvas_shots")
    op.drop_index("ix_canvases_project_id", "canvases")
    op.drop_table("canvases")
