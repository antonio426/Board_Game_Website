from datetime import datetime, timezone
from pydantic import BaseModel, Field


class UserBase(BaseModel):
    email: str
    display_name: str
    avatar_url: str | None = None
    auth_provider: str
    provider_id: str


class UserCreate(UserBase):
    pass


class UserOut(UserBase):
    id: str = Field(alias="_id")
    preferred_language: str = "zh"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"populate_by_name": True}
