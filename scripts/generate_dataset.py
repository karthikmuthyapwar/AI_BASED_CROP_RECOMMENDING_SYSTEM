from __future__ import annotations

import csv
import random
from pathlib import Path

random.seed(42)

PROFILE = {
    "rice": dict(N=(80, 100), P=(35, 50), K=(35, 50), t=(20, 30), h=(75, 90), ph=(5.5, 7.0), r=(180, 250)),
    "maize": dict(N=(60, 90), P=(40, 60), K=(20, 40), t=(18, 30), h=(55, 75), ph=(5.5, 7.5), r=(60, 120)),
    "chickpea": dict(N=(20, 45), P=(55, 75), K=(60, 85), t=(16, 27), h=(40, 60), ph=(6.0, 8.0), r=(30, 80)),
    "cotton": dict(N=(90, 130), P=(35, 55), K=(35, 60), t=(22, 34), h=(45, 70), ph=(5.8, 8.0), r=(50, 110)),
    "banana": dict(N=(70, 110), P=(65, 90), K=(70, 110), t=(24, 35), h=(70, 90), ph=(5.5, 7.8), r=(120, 220)),
    "mango": dict(N=(15, 40), P=(15, 35), K=(20, 45), t=(24, 36), h=(45, 75), ph=(5.5, 7.5), r=(70, 140)),
    "lentil": dict(N=(15, 35), P=(45, 70), K=(45, 65), t=(10, 25), h=(45, 70), ph=(6.0, 8.0), r=(35, 90)),
}


def sample_value(low: float, high: float, decimals: int = 2) -> float:
    return round(random.uniform(low, high), decimals)


rows: list[dict[str, float | str]] = []
for crop, p in PROFILE.items():
    for _ in range(40):
        rows.append(
            {
                "N": int(sample_value(*p["N"], decimals=0)),
                "P": int(sample_value(*p["P"], decimals=0)),
                "K": int(sample_value(*p["K"], decimals=0)),
                "temperature": sample_value(*p["t"]),
                "humidity": sample_value(*p["h"]),
                "ph": sample_value(*p["ph"]),
                "rainfall": sample_value(*p["r"]),
                "label": crop,
            }
        )

out_path = Path("backend/data/crop_recommendation.csv")
out_path.parent.mkdir(parents=True, exist_ok=True)
with out_path.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=["N", "P", "K", "temperature", "humidity", "ph", "rainfall", "label"],
    )
    writer.writeheader()
    writer.writerows(rows)

print(f"Generated {len(rows)} rows at {out_path}")
