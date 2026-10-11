# 🌬️ HawaGuard — Multi-Agent AI for Clean Air Action

**Hackathon:** Code for a Billion — Bharat Agentic-AI Hackathon 2026 (Code for India)
**Track:** Climate & Sustainability
**Team:** Rozeena (solo)

## What it is

Three specialized AI agents work as a team to turn raw pollution numbers into
action ordinary people can understand:

1. **DataAgent** (the eyes) — fetches real PM2.5 measurements
2. **AnalysisAgent** (the brain) — classifies AQI, computes trends, forecasts 24h
3. **ActionAgent** (the voice) — raises alerts + gives health guidance in English or Roman Urdu

## Quick start

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8130
# open http://127.0.0.1:8130
```

## Architecture

```
User picks station → Orchestrator runs:
  DataAgent.latest()      → latest PM2.5 (real dataset)
  DataAgent.history(168h) → 7-day hourly series (real dataset)
  DataAgent.live_now()    → real-time reading (WAQI demo feed)
        ↓
  AnalysisAgent.analyze() → EPA category + least-squares trend + 24h forecast
        ↓
  ActionAgent.act()       → alert level + recommendations + plain summary
        ↓
  Unified JSON report → web UI
```

## Real vs stubbed — honest table

| Part | Status | Details |
|---|---|---|
| Pollution measurements | ✅ REAL | `data/beijing_clean.csv.gz` — 315,632 real hourly rows, 12 Beijing stations |
| Live "now" reading | ✅ REAL | WAQI API demo feed (verified working); graceful fallback if offline |
| AQI categories | ✅ REAL | US EPA PM2.5 breakpoints (standard public table) |
| Trend computation | ✅ REAL | Least-squares slope on real 7-day data |
| 24h forecast | ⚠️ HONEST BASELINE | Persistence + linear trend. Labeled as naive baseline, NOT an ML model |
| Recommendations | ⚠️ RULE-BASED | EPA-aligned guidance; provider field says `heuristic`. Optional LLM upgrade via `OPENAI_API_KEY` env var |
| Roman Urdu summaries | ✅ REAL | Hand-written templates, not machine translation |

Nothing is ever presented as AI output when it is rule-based. Nothing is invented.

## Project structure

```
app/
  main.py            # FastAPI: /api/status, /api/report, serves UI
  orchestrator.py    # data → analysis → action pipeline
  data_loader.py     # cached load of the real dataset
  agents/
    data_agent.py    # dataset + WAQI live feed
    analysis_agent.py# EPA categories, trend, forecast
    action_agent.py  # alerts, recommendations, EN/UR summaries
static/index.html    # demo UI
data/beijing_clean.csv.gz  # real measurements
```

## Roadmap to submission (deadline Nov 15, 2026)

- [ ] Register at codeforindia.org/hackathon + AgentFoundry.me (1M free tokens)
- [ ] Public GitHub repo push
- [ ] 2–3 min demo video (script in PROJECT_GUIDE.md)
- [ ] Deploy on any cloud (Render/Railway free tier) + submit via GitHub form
- [ ] Optional: Delhi data adapter, share-links, PDF report export
