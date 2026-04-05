from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI-Based Multilingual Crop Recommendation System"
    model_path: str = "backend/app/model/model.pkl"
    openweather_api_key: str = ""
    weather_base_url: str = "https://api.openweathermap.org"
    geocode_limit: int = 1

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_sender: str = ""
    smtp_use_tls: bool = True
    expose_verification_code_in_response: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
