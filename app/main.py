"""HawaGuard API — FastAPI backend serving the demo UI and agent pipeline."""
import os
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .orchestrator import Orchestrator

app = FastAPI(title="HawaGuard", description="Multi-agent AI for clean air action")
orch = Orchestrator()

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/status")
def status():
    return {
        "ok": True,
        "project": "HawaGuard",
        "agents": ["data_agent", "analysis_agent", "action_agent"],
        "stations": orch.data.list_stations(),
        "action_provider": orch.action.provider,
        "data_note": "All measurements are real (Beijing cleaned dataset + WAQI live feed).",
    }


@app.get("/api/report")
def report(station: str = Query(...), lang: str = Query("en")):
    if lang not in ("en", "ur"):
        lang = "en"
    return orch.run_report(station, lang=lang)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8130")))
