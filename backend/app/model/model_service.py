import logging
from pathlib import Path

import joblib
import numpy as np

from backend.app.config import settings

logger = logging.getLogger(__name__)

FEATURE_ORDER = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]


class CropModelService:
    def __init__(self, model_path: str | None = None) -> None:
        self.model_path = Path(model_path or settings.model_path)
        self.model = self._load_model()

    def _load_model(self):
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Model not found at {self.model_path}. Run scripts/train_model.py first."
            )
        logger.info("Loading crop recommendation model from %s", self.model_path)
        return joblib.load(self.model_path)

    def predict_top_k(self, features: dict[str, float], top_k: int = 3) -> list[dict[str, float | str]]:
        row = [features[name] for name in FEATURE_ORDER]
        x = np.array([row], dtype=float)

        proba = self.model.predict_proba(x)[0]
        labels = self.model.classes_
        ranked_idx = np.argsort(proba)[::-1][:top_k]

        return [
            {"crop": str(labels[idx]), "probability": round(float(proba[idx]), 4)}
            for idx in ranked_idx
        ]
