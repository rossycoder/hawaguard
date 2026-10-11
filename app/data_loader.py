"""Loads the real Beijing air-quality dataset (cached in memory).

The file data/beijing_clean.csv.gz is Rozeena's Week-1 cleaned dataset:
315,632 hourly rows, 12 monitoring stations, pollutants + weather.
No fake data — every number below comes from these real measurements.
"""
import gzip
import csv
from functools import lru_cache
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "beijing_clean.csv.gz"


@lru_cache(maxsize=1)
def load_dataset():
    """Return list of row dicts sorted by time. Cached after first load."""
    rows = []
    with gzip.open(DATA_PATH, "rt") as f:
        for r in csv.DictReader(f):
            try:
                rows.append({
                    "year": int(r["year"]),
                    "month": int(r["month"]),
                    "day": int(r["day"]),
                    "hour": int(r["hour"]),
                    "station": r["station"],
                    "pm25": float(r["PM2.5"]),
                    "pm10": float(r["PM10"]),
                    "so2": float(r["SO2"]),
                    "no2": float(r["NO2"]),
                    "co": float(r["CO"]),
                    "o3": float(r["O3"]),
                    "temp": float(r["TEMP"]),
                })
            except (ValueError, KeyError):
                continue
    rows.sort(key=lambda r: (r["year"], r["month"], r["day"], r["hour"]))
    return rows


def stations():
    return sorted({r["station"] for r in load_dataset()})
