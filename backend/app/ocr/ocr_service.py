import logging
import re
from dataclasses import dataclass

import cv2
import easyocr
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class OCRExtraction:
    extracted_values: dict[str, float | None]
    confidence: float
    confidence_level: str
    raw_text: str


class SoilOCRService:
    def __init__(self) -> None:
        self.reader = easyocr.Reader(["en"], gpu=False)

    @staticmethod
    def preprocess_image(image_bytes: bytes) -> np.ndarray:
        np_img = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Invalid image file")

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        denoised = cv2.bilateralFilter(gray, 11, 17, 17)
        thresh = cv2.adaptiveThreshold(
            denoised,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            2,
        )
        return thresh

    @staticmethod
    def _normalize_text(text: str) -> str:
        text = text.replace("\n", " ")
        text = re.sub(r"\s+", " ", text)
        return text.lower().strip()

    @staticmethod
    def _extract_value(text: str, keys: list[str]) -> float | None:
        key_pattern = "|".join(re.escape(k) for k in keys)
        pattern = rf"(?:{key_pattern})\s*[:=-]?\s*([0-9]+(?:\.[0-9]+)?)"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            return None
        return float(match.group(1))

    def extract_soil_values(self, image_bytes: bytes) -> OCRExtraction:
        processed = self.preprocess_image(image_bytes)
        results = self.reader.readtext(processed)

        if not results:
            return OCRExtraction(
                extracted_values={"N": None, "P": None, "K": None, "ph": None},
                confidence=0.0,
                confidence_level="low",
                raw_text="",
            )

        texts = [item[1] for item in results]
        confidences = [float(item[2]) for item in results]

        combined = self._normalize_text(" ".join(texts))

        extracted = {
            "N": self._extract_value(combined, ["n", "nitrogen"]),
            "P": self._extract_value(combined, ["p", "phosphorus"]),
            "K": self._extract_value(combined, ["k", "potassium"]),
            "ph": self._extract_value(combined, ["ph", "p.h", "soil ph"]),
        }

        found_ratio = sum(v is not None for v in extracted.values()) / len(extracted)
        avg_conf = float(np.mean(confidences)) if confidences else 0.0
        final_conf = round((0.6 * avg_conf) + (0.4 * found_ratio), 4)

        if final_conf >= 0.75:
            level = "high"
        elif final_conf >= 0.45:
            level = "medium"
        else:
            level = "low"

        logger.info("OCR extracted %s with confidence %s (%s)", extracted, final_conf, level)

        return OCRExtraction(
            extracted_values=extracted,
            confidence=final_conf,
            confidence_level=level,
            raw_text=combined,
        )
