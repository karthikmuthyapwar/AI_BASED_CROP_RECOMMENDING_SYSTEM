import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.app.model.model_service import CropModelService
from backend.app.ocr.ocr_service import SoilOCRService
from backend.app.schemas.predict import LocationInput, OCRResponse, PredictionResult, SoilInput
from backend.app.weather.weather_service import WeatherService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["crop-recommendation"])
_model_service: CropModelService | None = None
ocr_service: SoilOCRService | None = None
weather_service = WeatherService()


def get_model_service() -> CropModelService:
    global _model_service
    if _model_service is None:
        try:
            _model_service = CropModelService()
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Model unavailable: {exc}. Train model using scripts/train_model.py",
            ) from exc
    return _model_service


def get_ocr_service() -> SoilOCRService:
    global ocr_service
    if ocr_service is None:
        try:
            ocr_service = SoilOCRService()
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=503, detail=f"OCR service unavailable: {exc}") from exc
    return ocr_service


@router.post("/predict", response_model=PredictionResult)
async def predict(payload: SoilInput) -> PredictionResult:
    model_service = get_model_service()
    features = payload.model_dump()
    top_k = features.pop("top_k")
    predictions = model_service.predict_top_k(features, top_k=top_k)
    weather_used = {
        "avg_temperature": payload.temperature,
        "avg_humidity": payload.humidity,
        "total_rainfall": payload.rainfall,
        "note": "User provided weather-independent values.",
    }
    return PredictionResult(top_predictions=predictions, weather_used=weather_used)


@router.post("/upload", response_model=OCRResponse)
async def upload_soil_report(file: UploadFile = File(...)) -> OCRResponse:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image")
    image_bytes = await file.read()
    try:
        result = get_ocr_service().extract_soil_values(image_bytes)
    except Exception as exc:  # noqa: BLE001
        logger.exception("OCR processing failed")
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {exc}") from exc

    return OCRResponse(
        extracted_values=result.extracted_values,
        confidence=result.confidence,
        confidence_level=result.confidence_level,
        raw_text=result.raw_text,
    )


@router.post("/predict-auto", response_model=PredictionResult)
async def predict_auto(payload: LocationInput) -> PredictionResult:
    model_service = get_model_service()
    if payload.city:
        lat, lon = await weather_service.geocode_city(payload.city)
    elif payload.latitude is not None and payload.longitude is not None:
        lat, lon = payload.latitude, payload.longitude
    else:
        raise HTTPException(status_code=400, detail="Provide either city or latitude/longitude")

    try:
        weather_summary = await weather_service.fetch_weather_summary(lat, lon, payload.duration_days)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Weather fetch failed")
        raise HTTPException(status_code=502, detail=f"Weather fetch failed: {exc}") from exc

    features = {
        "N": payload.N,
        "P": payload.P,
        "K": payload.K,
        "ph": payload.ph,
        "temperature": float(weather_summary["avg_temperature"]),
        "humidity": float(weather_summary["avg_humidity"]),
        "rainfall": float(weather_summary["total_rainfall"]),
    }

    predictions = model_service.predict_top_k(features, top_k=payload.top_k)
    return PredictionResult(top_predictions=predictions, weather_used=weather_summary)
