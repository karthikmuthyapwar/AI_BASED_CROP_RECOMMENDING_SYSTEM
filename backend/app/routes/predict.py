import logging

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile

from backend.app.db.database import (
    create_session,
    create_user,
    get_recent_recommendations,
    get_user_by_token,
    get_user_weather_profile,
    save_recommendation,
    start_email_registration,
    update_user_language,
    update_user_weather_profile,
    verify_email_and_create_user,
)
from backend.app.model.model_service import CropModelService
from backend.app.ocr.ocr_service import SoilOCRService
from backend.app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    MessageResponse,
    RecommendationHistoryResponse,
    RegisterEmailRequest,
    RegisterRequest,
    SetLanguageRequest,
    UserResponse,
    VerifyEmailRequest,
)
from backend.app.schemas.predict import LocationInput, OCRResponse, PredictionResult, SoilInput
from backend.app.utils.email_service import send_verification_email
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


def get_current_user(authorization: str = Header(default="")) -> dict[str, str | int | None]:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


@router.post("/auth/register", response_model=UserResponse, tags=["auth"])
async def register(payload: RegisterRequest) -> UserResponse:
    try:
        user = create_user(payload.username, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return UserResponse(id=int(user["id"]), username=str(user["username"]))


@router.post("/auth/register-email", response_model=MessageResponse, tags=["auth"])
async def register_email(payload: RegisterEmailRequest) -> MessageResponse:
    try:
        code, _ = start_email_registration(payload.email, payload.username, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    try:
        sent = send_verification_email(payload.email, code)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Email sending failed")
        raise HTTPException(status_code=500, detail=f"Failed to send verification email: {exc}") from exc

    if sent:
        return MessageResponse(message="Verification code sent to your email")
    return MessageResponse(message="SMTP is not configured. Check backend logs for verification code")


@router.post("/auth/verify-email", response_model=UserResponse, tags=["auth"])
async def verify_email(payload: VerifyEmailRequest) -> UserResponse:
    try:
        user = verify_email_and_create_user(payload.email, payload.code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return UserResponse(
        id=int(user["id"]),
        username=str(user["username"]),
        email=user.get("email"),
    )


@router.post("/auth/login", response_model=AuthResponse, tags=["auth"])
async def login(payload: LoginRequest) -> AuthResponse:
    try:
        session = create_session(payload.username, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    return AuthResponse.model_validate(session)


@router.post("/auth/set-language", response_model=MessageResponse, tags=["auth"])
async def set_language(
    payload: SetLanguageRequest,
    current_user: dict[str, str | int | None] = Depends(get_current_user),
) -> MessageResponse:
    update_user_language(int(current_user["id"]), payload.language)
    return MessageResponse(message="Default language updated")


@router.get("/auth/me", response_model=UserResponse, tags=["auth"])
async def me(current_user: dict[str, str | int | None] = Depends(get_current_user)) -> UserResponse:
    return UserResponse(
        id=int(current_user["id"]),
        username=str(current_user["username"]),
        email=current_user.get("email"),
        default_language=current_user.get("default_language"),
    )


@router.get("/recent-recommendations", response_model=RecommendationHistoryResponse)
async def recent_recommendations(
    limit: int = Query(default=10, ge=1, le=50),
    current_user: dict[str, str | int | None] = Depends(get_current_user),
) -> RecommendationHistoryResponse:
    rows = get_recent_recommendations(int(current_user["id"]), limit=limit)
    return RecommendationHistoryResponse(items=rows)


@router.post("/predict", response_model=PredictionResult)
async def predict(
    payload: SoilInput,
    current_user: dict[str, str | int | None] = Depends(get_current_user),
) -> PredictionResult:
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
    save_recommendation(
        user_id=int(current_user["id"]),
        endpoint="/predict",
        input_payload=payload.model_dump(),
        weather_used=weather_used,
        top_predictions=predictions,
    )
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
async def predict_auto(
    payload: LocationInput,
    current_user: dict[str, str | int | None] = Depends(get_current_user),
) -> PredictionResult:
    model_service = get_model_service()
    if payload.city:
        lat, lon = await weather_service.geocode_city(payload.city)
    elif payload.latitude is not None and payload.longitude is not None:
        lat, lon = payload.latitude, payload.longitude
    else:
        raise HTTPException(status_code=400, detail="Provide either city or latitude/longitude")

    weather_summary: dict[str, float | str]
    used_offline_cache = False
    try:
        weather_summary = await weather_service.fetch_weather_summary(lat, lon, payload.duration_days)
        update_user_weather_profile(
            int(current_user["id"]),
            payload.city,
            float(weather_summary["avg_temperature"]),
            float(weather_summary["avg_humidity"]),
            float(weather_summary["total_rainfall"]),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Weather fetch failed, trying offline fallback")
        cached = get_user_weather_profile(int(current_user["id"]))
        if not cached:
            raise HTTPException(status_code=502, detail=f"Weather fetch failed: {exc}") from exc
        weather_summary = {
            "avg_temperature": cached["avg_temperature"],
            "avg_humidity": cached["avg_humidity"],
            "total_rainfall": cached["total_rainfall"],
            "note": "Offline fallback using cached weather profile.",
            "cached_city": cached.get("cached_city"),
        }
        used_offline_cache = True

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
    if used_offline_cache:
        weather_summary["offline_mode"] = "true"
    save_recommendation(
        user_id=int(current_user["id"]),
        endpoint="/predict-auto",
        input_payload=payload.model_dump(),
        weather_used=weather_summary,
        top_predictions=predictions,
    )
    return PredictionResult(top_predictions=predictions, weather_used=weather_summary)
