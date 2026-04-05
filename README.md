# AI-Based Multilingual Crop Recommendation System for Farmers

Production-ready full-stack system that combines:
- **Machine Learning (RandomForestClassifier)** for crop recommendation
- **OCR (EasyOCR + OpenCV)** to read soil report images
- **Weather intelligence (OpenWeather Geocoding + Forecast)**
- **GPS/City based location flow**
- **Multilingual UI + Voice guidance** in English, Hindi, Telugu

## Project Structure

```text
backend/
├── app/
│   ├── model/
│   │   ├── __init__.py
│   │   └── model_service.py
│   ├── ocr/
│   │   ├── __init__.py
│   │   └── ocr_service.py
│   ├── weather/
│   │   ├── __init__.py
│   │   └── weather_service.py
│   ├── routes/
│   │   ├── __init__.py
│   │   └── predict.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── predict.py
│   ├── utils/
│   │   ├── __init__.py
│   │   └── logger.py
│   ├── config.py
│   └── main.py
├── data/
│   └── crop_recommendation.csv
frontend/
├── css/styles.css
├── i18n/{en,hi,te}.json
├── js/app.js
└── index.html
scripts/
├── generate_dataset.py
└── train_model.py
requirements.txt
```

## Dataset
Columns used exactly as requested:
- `N`, `P`, `K`, `temperature`, `humidity`, `ph`, `rainfall`, `label`

Sample row (generated profile-based dataset):

| N  | P  | K  | temperature | humidity | ph  | rainfall | label |
|----|----|----|-------------|----------|-----|----------|-------|
| 90 | 42 | 43 | 20.87       | 82.00    | 6.5 | 202.93   | rice  |

## Setup

1. Create virtual environment and install dependencies:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Configure weather key:
```bash
cat > .env <<'EOF'
OPENWEATHER_API_KEY=your_openweather_api_key_here
# Optional: set to false in production to avoid returning OTP in API response
EXPOSE_VERIFICATION_CODE_IN_RESPONSE=true
EOF
```

3. Generate sample dataset (already committed but reproducible):
```bash
python scripts/generate_dataset.py
```

4. Train model and save `model.pkl`:
```bash
python scripts/train_model.py
```

5. Run backend:
```bash
uvicorn backend.app.main:app --reload --port 8000
```

6. Serve frontend (example):
```bash
python -m http.server 5500 --directory frontend
```
Then open `http://localhost:5500`.

### Quick start (run backend + frontend together)

If you want one command to start everything and open the UI automatically:

```bash
python start_project.py
```

Windows users can also double-click:

```bat
start_project.bat
```

> Note: Opening `frontend/index.html` directly from file explorer (`file://...`) will not start Python backend services. Use the quick-start command above.

## API Endpoints

### Authentication Flow

1) Register a unique user:
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"farmer1","password":"StrongPass123"}'
```

2) Login and receive bearer token:
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"farmer1","password":"StrongPass123"}'
```

3) Use token for protected recommendation endpoints:
```bash
curl -X GET http://localhost:8000/auth/me \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

### 1) `POST /predict`
Manual direct prediction endpoint using full features.
Requires `Authorization: Bearer <ACCESS_TOKEN>`.

Example:
```bash
curl -X POST http://localhost:8000/predict \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "N":90,"P":42,"K":43,
    "temperature":26.5,"humidity":78.0,
    "ph":6.5,"rainfall":180.0,
    "top_k":3
  }'
```

### 2) `POST /upload`
OCR extraction from image.

```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@soil_report.jpg"
```

### 3) `POST /predict-auto`
Location + duration + soil values; weather is fetched automatically.
Requires `Authorization: Bearer <ACCESS_TOKEN>`.

```bash
curl -X POST http://localhost:8000/predict-auto \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "N":90,"P":42,"K":43,"ph":6.5,
    "city":"Hyderabad",
    "duration_days":90,
    "top_k":3
  }'
```

### 4) `GET /recent-recommendations`
Returns only the logged-in user's recent searches with timestamps (privacy scoped per user).

```bash
curl -X GET "http://localhost:8000/recent-recommendations?limit=10" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

## OCR Confidence Behavior
- **High** (`>=0.75`): Auto-fill directly.
- **Medium** (`0.45-0.74`): Auto-fill and ask verification.
- **Low** (`<0.45`): Show fallback message for manual entry.

## Weather Logic
- City name is geocoded to latitude/longitude.
- Forecast is fetched via OpenWeather One Call.
- Features derived for model input:
  - Average temperature
  - Average humidity
  - Total rainfall
- If duration exceeds forecast range, extrapolation note is returned.

## Voice + Multilingual UI
- Supported languages: **en**, **hi**, **te**.
- UI strings from JSON files.
- Browser `SpeechSynthesis` provides spoken instructions + results, language-synced.

## Error Handling & Logging
- Structured FastAPI HTTP errors with clear details.
- Logging enabled in backend startup and service operations.

## Production Notes
- Use a process manager (systemd/supervisord) or Docker for deployment.
- Put backend behind reverse proxy (Nginx/Traefik).
- Restrict CORS to known frontend domains in production.
- Add authentication/rate limiting for public exposure.
