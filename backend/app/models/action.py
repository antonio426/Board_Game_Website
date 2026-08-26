from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


class ActionType(str, Enum):
    VIEW = "view"
    CLICK = "click"
    WISHLIST = "wishlist"
    OWN = "own"
    FAVORITE = "favorite"
    RATE = "rate"
    SEARCH = "search"


class UserActionCreate(BaseModel):
    bgg_id: int
    action_type: ActionType
    duration_sec: int = 0
    rating: int | None = None
    search_query: str | None = None
    metadata: dict = {}


class UserActionOut(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    bgg_id: int
    action_type: ActionType
    duration_sec: int = 0
    rating: int | None = None
    search_query: str | None = None
    metadata: dict = {}
    created_at: datetime

    model_config = {"populate_by_name": True}
