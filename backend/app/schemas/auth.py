from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: int
    username: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: str
    user: UserResponse


class RecommendationHistoryItem(BaseModel):
    id: int
    endpoint: str
    input_payload: dict
    weather_used: dict
    top_predictions: list[dict]
    created_at: str


class RecommendationHistoryResponse(BaseModel):
    items: list[RecommendationHistoryItem]
