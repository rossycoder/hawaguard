"""AnalysisAgent — the "brain" of the system.

Job: turn raw PM2.5 numbers into understanding.
  - US EPA AQI category for a PM2.5 value (standard breakpoints, no invention)
  - 7-day trend via least-squares slope on real hourly data
  - Simple 24-hour forecast: persistence + trend extrapolation, honestly labeled
    as a naive baseline (not a claimed ML model)
"""
from statistics import mean

# US EPA PM2.5 breakpoints (µg/m³) — standard, public knowledge
AQI_BANDS = [
    (0, 12.0, "Good", "Air quality is satisfactory."),
    (12.1, 35.4, "Moderate", "Acceptable; unusually sensitive people should watch."),
    (35.5, 55.4, "Unhealthy for Sensitive Groups",
     "Children, elderly and people with lung/heart disease should limit outdoor exertion."),
    (55.5, 150.4, "Unhealthy",
     "Everyone may feel effects; sensitive groups should avoid outdoor exertion."),
    (150.5, 250.4, "Very Unhealthy",
     "Health alert: everyone should avoid outdoor exertion."),
    (250.5, float("inf"), "Hazardous",
     "Emergency: everyone should stay indoors."),
]


class AnalysisAgent:
    name = "analysis_agent"
    role = "Classify AQI, compute trends, and produce an honest 24h forecast."

    def categorize(self, pm25):
        for lo, hi, label, note in AQI_BANDS:
            if lo <= pm25 <= hi:
                return {"pm25": pm25, "category": label, "guidance": note}
        return {"pm25": pm25, "category": "Unknown", "guidance": ""}

    def trend(self, history):
        """Least-squares slope of PM2.5 over the given hourly history."""
        vals = [h["pm25"] for h in history]
        n = len(vals)
        if n < 24:
            return {"ok": False, "error": "Need at least 24 hours of data"}
        xs = list(range(n))
        xbar, ybar = mean(xs), mean(vals)
        denom = sum((x - xbar) ** 2 for x in xs)
        slope = sum((x - xbar) * (y - ybar) for x, y in zip(xs, vals)) / denom if denom else 0.0
        return {
            "ok": True,
            "slope_per_hour": round(slope, 3),
            "direction": "rising" if slope > 0.5 else ("falling" if slope < -0.5 else "stable"),
            "avg_pm25": round(ybar, 1),
            "max_pm25": round(max(vals), 1),
            "hours_analyzed": n,
        }

    def forecast_24h(self, history):
        """Naive 24h forecast: last value + trend slope. Labeled as baseline."""
        if len(history) < 24:
            return {"ok": False, "error": "Need at least 24 hours of data"}
        vals = [h["pm25"] for h in history]
        t = self.trend(history)
        last = vals[-1]
        preds = [max(0.0, round(last + t["slope_per_hour"] * h, 1)) for h in range(1, 25)]
        return {
            "ok": True,
            "method": "naive baseline: persistence + linear trend (not an ML model)",
            "next_24h_pm25": preds,
            "peak_pm25": max(preds),
            "peak_hour_ahead": preds.index(max(preds)) + 1,
        }

    def analyze(self, latest_pm25, history):
        cat = self.categorize(latest_pm25)
        t = self.trend(history)
        f = self.forecast_24h(history)
        return {"category": cat, "trend": t, "forecast": f}
