from pydantic import BaseModel
from datetime import datetime


class ProjectCreate(BaseModel):
    title: str
    visual_style: str | None = None
    music_style: str | None = None
    mood: str | None = None


class ProjectUpdate(BaseModel):
    title: str | None = None
    visual_style: str | None = None
    music_style: str | None = None
    mood: str | None = None
    style_config: dict | None = None
    model_preferences: dict | None = None
    storyboard: list | None = None


class ProjectResponse(BaseModel):
    id: int
    title: str
    status: str
    visual_style: str | None
    music_style: str | None
    mood: str | None
    style_config: dict | None
    storyboard: list | None
    character_bank: dict | None
    chat_history: list | None
    model_preferences: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskResponse(BaseModel):
    id: int
    project_id: int
    type: str
    model_name: str | None
    status: str
    result: dict | None
    quality_score: float | None
    retry_count: int
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MediaResponse(BaseModel):
    id: int
    project_id: int
    type: str
    file_url: str
    duration: float | None
    metadata_json: dict | None
    sort_order: int

    model_config = {"from_attributes": True}
