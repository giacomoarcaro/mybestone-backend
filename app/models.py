from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None

    @classmethod
    def get_user(cls, username: str):
        # TODO: Implement actual user database lookup
        # For now, return a dummy user
        if username == "test":
            return cls(username=username, email="test@example.com", full_name="Test User")
        return None

    @classmethod
    def authenticate_user(cls, username: str, password: str):
        # TODO: Implement actual user authentication
        # For now, accept test/test as credentials
        if username == "test" and password == "test":
            return cls.get_user(username)
        return None

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class VideoResult(BaseModel):
    video_id: str
    title: str
    description: str
    thumbnail_path: str
    similarity_score: float
    published_at: datetime
    channel_title: str 