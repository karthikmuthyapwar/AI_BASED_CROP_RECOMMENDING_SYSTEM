import logging
from datetime import UTC, datetime, timedelta

import httpx

from backend.app.config import settings

logger = logging.getLogger(__name__)


class WeatherService:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.openweather_api_key
        self.base_url = settings.weather_base_url

    async def geocode_city(self, city: str) -> tuple[float, float]:
        if not self.api_key:
            raise ValueError("OpenWeather API key is missing")

        url = f"{self.base_url}/geo/1.0/direct"
        params = {
            "q": city,
            "limit": settings.geocode_limit,
            "appid": self.api_key,
        }
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        if not data:
            raise ValueError(f"No coordinates found for city '{city}'")
        return float(data[0]["lat"]), float(data[0]["lon"])

    async def fetch_weather_summary(self, lat: float, lon: float, duration_days: int) -> dict[str, float | int | str]:
        if not self.api_key:
            raise ValueError("OpenWeather API key is missing")

        url = f"{self.base_url}/data/3.0/onecall"
        params = {
            "lat": lat,
            "lon": lon,
            "exclude": "minutely,hourly,current,alerts",
            "units": "metric",
            "appid": self.api_key,
        }

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()

        daily = payload.get("daily", [])
        if not daily:
            raise ValueError("Weather forecast is unavailable for selected location")

        used_days = min(duration_days, len(daily))
        subset = daily[:used_days]

        avg_temp = sum(float(item["temp"]["day"]) for item in subset) / used_days
        avg_humidity = sum(float(item["humidity"]) for item in subset) / used_days
        total_rainfall = sum(float(item.get("rain", 0.0)) for item in subset)

        if duration_days > len(daily):
            multiplier = duration_days / len(daily)
            total_rainfall *= multiplier
            info = (
                f"Duration exceeded forecast window ({len(daily)} days). "
                "Used extrapolated rainfall and mean conditions."
            )
        else:
            info = "Used direct forecast values."

        logger.info(
            "Weather summary lat=%s lon=%s days=%s avg_temp=%.2f avg_humidity=%.2f total_rainfall=%.2f",
            lat,
            lon,
            duration_days,
            avg_temp,
            avg_humidity,
            total_rainfall,
        )

        return {
            "latitude": lat,
            "longitude": lon,
            "duration_days": duration_days,
            "forecast_days_used": used_days,
            "avg_temperature": round(avg_temp, 2),
            "avg_humidity": round(avg_humidity, 2),
            "total_rainfall": round(total_rainfall, 2),
            "note": info,
            "generated_at": datetime.now(UTC).isoformat(),
        }
