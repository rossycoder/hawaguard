"""Orchestrator — runs the three agents as one pipeline.

Flow: DataAgent (fetch) → AnalysisAgent (understand) → ActionAgent (advise).
Each agent does exactly one job; the orchestrator wires them together and
returns a single unified report. This is the "multi-agent" architecture:
specialized agents, clear handoffs, no single god-function.
"""
from .agents import DataAgent, AnalysisAgent, ActionAgent


class Orchestrator:
    def __init__(self):
        self.data = DataAgent()
        self.analysis = AnalysisAgent()
        self.action = ActionAgent()

    def run_report(self, station, lang="en"):
        """Full pipeline for one monitoring station. Returns a dict report."""
        trace = []

        latest = self.data.latest(station)
        trace.append({"agent": "data_agent", "step": "latest", "ok": latest.get("ok", False)})
        if not latest.get("ok"):
            return {"ok": False, "trace": trace, "error": latest.get("error")}

        history = self.data.history(station, hours=168)
        trace.append({"agent": "data_agent", "step": "history_7d", "points": len(history)})

        analysis = self.analysis.analyze(latest["pm25"], history)
        trace.append({"agent": "analysis_agent", "step": "analyze", "ok": True})

        action = self.action.act(
            analysis["category"]["category"],
            analysis["trend"],
            analysis["forecast"],
            lang=lang,
        )
        trace.append({"agent": "action_agent", "step": "act", "ok": True})

        live = self.data.live_now()
        trace.append({"agent": "data_agent", "step": "live_now", "ok": live.get("ok", False)})

        return {
            "ok": True,
            "station": station,
            "latest": latest,
            "live": live,
            "category": analysis["category"],
            "trend": analysis["trend"],
            "forecast": analysis["forecast"],
            "action": action,
            "trace": trace,
        }
