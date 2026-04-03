from typing import Any

from pydantic import BaseModel, Field


class SoilInput(BaseModel):
    N: float = Field(..., ge=0)
    P: float = Field(..., ge=0)
    K: float = Field(..., ge=0)
    ph: float = Field(..., ge=0, le=14)
    temperature: float = Field(...)
    humidity: float = Field(..., ge=0, le=100)
    rainfall: float = Field(..., ge=0)
    top_k: int = Field(default=3, ge=1, le=5)


class LocationInput(BaseModel):
    duration_days: int = Field(..., ge=1, le=180)
    N: float = Field(..., ge=0)
    P: float = Field(..., ge=0)
    K: float = Field(..., ge=0)
    ph: float = Field(..., ge=0, le=14)
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    top_k: int = Field(default=3, ge=1, le=5)


class PredictionResult(BaseModel):
    top_predictions: list[dict[str, Any]]
    weather_used: dict[str, Any]


class OCRResponse(BaseModel):
    extracted_values: dict[str, float | None]
    confidence: float
    confidence_level: str
    raw_text: str
