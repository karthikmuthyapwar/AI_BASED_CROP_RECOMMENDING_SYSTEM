from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)


class RegisterEmailRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)


class SetLanguageRequest(BaseModel):
    language: str = Field(..., pattern="^(en|hi|te)$")


class MessageResponse(BaseModel):
    message: str


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: int
    username: str
    email: str | None = None
    default_language: str | None = None


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
