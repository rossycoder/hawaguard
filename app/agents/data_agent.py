"""DataAgent — the "eyes" of the system.

Job: fetch real pollution measurements from available sources.
Sources (all real, nothing invented):
  1. Local cleaned Beijing dataset (315k hourly rows) — primary, works offline.
  2. WAQI live API (demo token) — a real "right now" reading when online.
If the live API is unreachable, the agent says so and falls back to the
latest dataset reading, clearly labeled.
"""
import urllib.request
import urllib.error
import json

from ..data_loader import load_dataset, stations


class DataAgent:
    name = "data_agent"
    role = "Fetch real PM2.5 measurements from trusted sources."

    def __init__(self):
        self._stations = None

    def list_stations(self):
        if self._stations is None:
            self._stations = stations()
        return self._stations

    def latest(self, station):
        """Most recent PM2.5 reading for a station from the real dataset."""
        rows = [r for r in load_dataset() if r["station"] == station]
        if not rows:
            return {"ok": False, "error": f"Unknown station: {station}"}
        r = rows[-1]
        return {
            "ok": True,
            "source": "beijing_clean_dataset (real measurements)",
            "station": station,
            "pm25": r["pm25"],
            "timestamp": f"{r['year']}-{r['month']:02d}-{r['day']:02d} {r['hour']:02d}:00",
            "temp_c": r["temp"],
        }

    def history(self, station, hours=168):
        """Last N hours of PM2.5 for a station (default 7 days). Real data."""
        rows = [r for r in load_dataset() if r["station"] == station]
        return [
            {"pm25": r["pm25"], "hour": r["hour"], "day": r["day"], "month": r["month"]}
            for r in rows[-hours:]
        ]

    def live_now(self):
        """A real live reading via the WAQI demo feed (Beijing)."""
        try:
            req = urllib.request.Request(
                "https://api.waqi.info/feed/beijing/?token=demo",
                headers={"User-Agent": "HawaGuard/1.0"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            if data.get("status") == "ok":
                return {
                    "ok": True,
                    "source": "WAQI live API (demo token) — real current reading",
                    "aqi": data["data"]["aqi"],
                    "station": data["data"].get("city", {}).get("name", "Beijing"),
                }
            return {"ok": False, "error": "WAQI returned non-ok status"}
        except (urllib.error.URLError, OSError, ValueError, KeyError) as e:
            return {"ok": False, "error": f"Live feed unreachable: {e}"}
