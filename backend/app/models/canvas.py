from sqlalchemy import String, Integer, Float, ForeignKey, Text, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class Canvas(Base):
    """Stores the full Vue Flow graph state (nodes + edges JSON) for a project.
    One canvas per project, lazily created on first save.
    """
    __tablename__ = "canvases"
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_canvases_project_id"),
    )

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    # Full VueFlow graph state
    nodes: Mapped[list] = mapped_column(JSON, default=list)
    edges: Mapped[list] = mapped_column(JSON, default=list)
    # Saved viewport for restore-on-open
    viewport: Mapped[dict | None] = mapped_column(JSON, default=dict)

    project = relationship("Project", back_populates="canvas")
    shots = relationship("CanvasShot", back_populates="canvas", cascade="all, delete-orphan")


class CanvasShot(Base):
    """Tracks generation state for each shot node on the canvas.
    node_id matches the Vue Flow node id (e.g. 's1', 'shot-abc123').
    """
    __tablename__ = "canvas_shots"

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    canvas_id: Mapped[int] = mapped_column(ForeignKey("canvases.id"), index=True)
    node_id: Mapped[str] = mapped_column(String(64))  # VueFlow node id

    prompt: Mapped[str | None] = mapped_column(Text)
    model_name: Mapped[str | None] = mapped_column(String(50))
    duration: Mapped[float | None] = mapped_column(Float)
    time_anchor: Mapped[float | None] = mapped_column(Float)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    # Generation state
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    # pending -> generating -> done / failed

    # Context snapshot used for this generation (music/char/scene refs)
    canvas_context: Mapped[dict | None] = mapped_column(JSON, default=dict)

    # Links to generation infrastructure
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    media_id: Mapped[int | None] = mapped_column(ForeignKey("media.id"), nullable=True)

    canvas = relationship("Canvas", back_populates="shots")
    task = relationship("Task")
    media = relationship("Media")
