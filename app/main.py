"""HawaGuard API — FastAPI backend serving the demo UI and agent pipeline."""
import os
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse
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


@app.get("/api/compare")
def compare(
    station_a: str = Query(None),
    station_b: str = Query(None),
    lang: str = Query("en"),
):
    """Side-by-side reports for two stations. Pure compute — serverless-safe."""
    if lang not in ("en", "ur"):
        lang = "en"
    valid = set(orch.data.list_stations())
    missing = [n for n, v in (("station_a", station_a), ("station_b", station_b)) if not v]
    if missing:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": f"Missing required query param(s): {', '.join(missing)}"},
        )
    invalid = [s for s in (station_a, station_b) if s not in valid]
    if invalid:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": f"Unknown station(s): {', '.join(invalid)}"},
        )
    # Never 500 here: run_report returns {"ok": False, ...} on failure,
    # and both reports (good or bad) are always returned together.
    return {
        "ok": True,
        "station_a": orch.run_report(station_a, lang=lang),
        "station_b": orch.run_report(station_b, lang=lang),
    }


@app.get("/api/outdoor-planner")
def outdoor_planner(station: str = Query(...), lang: str = Query("en")):
    """🏃 Outdoor Planner — 24 hour-by-hour air-quality bands + best exercise window.

    Real complaint: 'Should I exercise outside today?'
    Pure compute over the naive 24h forecast — serverless-safe.
    """
    if lang not in ("en", "ur"):
        lang = "en"
    valid = set(orch.data.list_stations())
    if station not in valid:
        return JSONResponse(status_code=400, content={"ok": False, "error": f"Unknown station: {station}"})
    history = orch.data.history(station, hours=168)
    f = orch.analysis.forecast_24h(history)
    if not f.get("ok"):
        return {"ok": False, "error": f.get("error")}

    hours = []
    for i, pm in enumerate(f["next_24h_pm25"]):
        cat = orch.analysis.categorize(pm)["category"]
        band = "go" if cat in ("Good", "Moderate") else ("caution" if cat == "Unhealthy for Sensitive Groups" else "avoid")
        hours.append({"hour_ahead": i + 1, "pm25": pm, "category": cat, "band": band})

    # Best window: longest consecutive "go" run; else longest "caution"; else lowest-pm25 hour.
    def best_run(want):
        best = cur = None
        for h in hours:
            if h["band"] == want:
                cur = (cur[0], h["hour_ahead"]) if cur else (h["hour_ahead"], h["hour_ahead"])
                if best is None or (cur[1] - cur[0]) > (best[1] - best[0]):
                    best = cur
            else:
                cur = None
        return best

    win = best_run("go") or best_run("caution")
    if win:
        best_window = {"start_hour_ahead": win[0], "end_hour_ahead": win[1], "band": "go" if best_run("go") else "caution"}
    else:
        m = min(hours, key=lambda h: h["pm25"])
        best_window = {"start_hour_ahead": m["hour_ahead"], "end_hour_ahead": m["hour_ahead"], "band": m["band"]}

    band_advice = {
        "go": {
            "en": "Great for running, cycling and outdoor sports.",
            "ur": "Running, cycling aur outdoor khel ke liye behtareen waqt.",
        },
        "caution": {
            "en": "Light activity is OK — keep intense workouts short.",
            "ur": "Halki sargarmi theek hai — sakht workout mukhtasir rakhen.",
        },
        "avoid": {
            "en": "Move exercise indoors during these hours.",
            "ur": "In ghanton me exercise ghar ke andar karen.",
        },
    }
    return {
        "ok": True,
        "station": station,
        "lang": lang,
        "hours": hours,
        "best_window": best_window,
        "band_advice": {b: v[lang] for b, v in band_advice.items()},
        "method": f.get("method"),
    }


SYMPTOM_DISCLAIMER = {
    "en": "⚠️ This is not a medical diagnosis — it is a rule-based guess from your answers. If you have fever, severe symptoms, or things get worse, see a doctor.",
    "ur": "⚠️ Ye medical diagnosis nahi hai — sirf aap ke jawabon par mabni rule-based andaza hai. Agar bukhar ho, alamat shadeed hon ya bigar jayen to doctor se ruju karen.",
}


@app.get("/api/symptom-check")
def symptom_check(
    dry_cough: int = Query(0, ge=0, le=1),
    fever: int = Query(0, ge=0, le=1),
    worse_outdoors: int = Query(0, ge=0, le=1),
    burning_eyes: int = Query(0, ge=0, le=1),
    chest_tightness: int = Query(0, ge=0, le=1),
    cold_contact: int = Query(0, ge=0, le=1),
    station: str = Query(None),
    lang: str = Query("en"),
):
    """🩺 Symptom Checker — pollution irritation vs infection.

    Real complaint: 'Pollution cough or infection?' (people misuse medicines).
    Rule-based scoring, honest disclaimer ALWAYS included. Serverless-safe.
    """
    if lang not in ("en", "ur"):
        lang = "en"
    p = dry_cough + worse_outdoors + burning_eyes + chest_tightness  # pollution signals
    i = 3 * fever + 2 * cold_contact  # infection signals (fever weighs most)

    if i > p:
        verdict = "infection"
    elif p >= 2 and p > i:
        verdict = "pollution"
    else:
        verdict = "unclear"

    T = {
        "infection": {
            "en": ("🦠 Likely an INFECTION — see a doctor",
                   "Fever and recent sick contacts point to infection, not smog. Don't self-medicate with antibiotics without advice."),
            "ur": ("🦠 Infection ka imkan zyada hai — doctor se milen",
                   "Bukhar aur mareezon se rabta infection ki taraf ishara karta hai, smog ki taraf nahi. Mashwaray ke baghair antibiotics na len."),
        },
        "pollution": {
            "en": ("🌫️ Likely POLLUTION irritation",
                   "Worse outdoors + burning eyes with no fever is the classic smog pattern. It usually eases in cleaner air — a mask and indoor rest help."),
            "ur": ("🌫️ Smog se jalan ka imkan zyada hai",
                   "Bahar bigarna + aankhon me jalan aur bukhar na hona smog ka classic pattern hai. Saaf hawa me aaram milta hai — mask aur indoor rest madad karte hain."),
        },
        "unclear": {
            "en": ("❓ Unclear — watch and be careful",
                   "Your answers don't clearly match either pattern. Rest, monitor for a day, and see a doctor if fever appears or breathing worsens."),
            "ur": ("❓ Wazeh nahi — ehtiyat karen",
                   "Aap ke jawab kisi ek pattern se wazeh tor par match nahi kartay. Aaram karen, ek din nazar rakhen, aur bukhar aye ya saans bigray to doctor se milen."),
        },
    }
    title, reasoning = T[verdict][lang]

    context = None
    if station and station in set(orch.data.list_stations()):
        latest = orch.data.latest(station)
        if latest.get("ok"):
            cat = orch.analysis.categorize(latest["pm25"])["category"]
            if lang == "ur":
                context = f"Note: {station} par is waqt PM2.5 {latest['pm25']:.1f} hai ({cat})."
            else:
                context = f"Note: PM2.5 at {station} is currently {latest['pm25']:.1f} ({cat})."

    return {
        "ok": True,
        "verdict": verdict,
        "title": title,
        "reasoning": reasoning,
        "context": context,
        "disclaimer": SYMPTOM_DISCLAIMER[lang],
        "lang": lang,
    }


FAMILY_VERDICTS = {
    "go": {
        "en": ("✅ OK to play outside", "School as normal. Great air day for kids."),
        "ur": ("✅ Bahar khelna theek hai", "School normal. Bachon ke liye achay hawa ka din."),
    },
    "caution": {
        "en": ("⚠️ OK with breaks — watch sensitive kids", "No intense outdoor sports. Asthma/allergy kids: keep inhaler handy."),
        "ur": ("⚠️ Waqfay ke sath theek — sensitive bachon par nazar rakhen", "Sakht outdoor khel nahi. Asthma/allergy walay bachay: inhaler sath rakhen."),
    },
    "mask": {
        "en": ("😷 Mask on outdoors", "Outdoor sports moved indoors. N95/KN95 if kids must go out."),
        "ur": ("😷 Bahar mask pehnain", "Outdoor sports indoor karwain. Bahar jana ho to N95/KN95 mask."),
    },
    "indoors": {
        "en": ("🏠 Keep kids indoors", "Consider keeping sensitive kids home. No outdoor play today."),
        "ur": ("🏠 Bachon ko ghar ke andar rakhen", "Sensitive bachon ko ghar rakhne par ghor karen. Aaj bahar khel nahi."),
    },
    "emergency": {
        "en": ("🚨 Stay indoors — emergency", "Keep kids home if possible. Close windows, run purifier."),
        "ur": ("🚨 Ghar ke andar rahen — emergency", "Mumkin ho to bachon ko ghar rakhen. Khirkiyan band, purifier chalain."),
    },
}

FAMILY_TIPS = {
    "en": [
        "Kids breathe faster than adults — they inhale more pollution per kg of body weight.",
        "Morning school commute is often the worst window; a well-fitted mask helps most then.",
        "Indoor play beats outdoor play on orange/red days — no guilt, it's the healthy choice.",
        "If coughing lasts more than 2 days after a smog spell, see a pediatrician.",
    ],
    "ur": [
        "Bachay baron se tez saans lete hain — wazan ke hisab se zyada pollution andar jata hai.",
        "Subah school jatay waqt aksar hawa sab se kharab hoti hai; mask us waqt sab se zyada madad karta hai.",
        "Orange/red dinon me indoor khel behtar hai — yehi sehatmand faisla hai.",
        "Agar smog ke baad khansi 2 din se zyada rahay to bachon ke doctor se milen.",
    ],
}


@app.get("/api/family-shield")
def family_shield(station: str = Query(...), lang: str = Query("en")):
    """👨‍👩‍👧 Family Shield — 'Should my child go to school / play outside today?'

    Real complaint from parents: 'My child coughs non-stop.'
    Child-specific verdicts use STRICTER thresholds than adult guidance.
    Pure compute — serverless-safe.
    """
    if lang not in ("en", "ur"):
        lang = "en"
    valid = set(orch.data.list_stations())
    if station not in valid:
        return JSONResponse(status_code=400, content={"ok": False, "error": f"Unknown station: {station}"})
    latest = orch.data.latest(station)
    if not latest.get("ok"):
        return {"ok": False, "error": latest.get("error")}
    cat = orch.analysis.categorize(latest["pm25"])["category"]
    # Stricter for children: shift one band harsher than the adult category.
    verdict = {
        "Good": "go",
        "Moderate": "caution",
        "Unhealthy for Sensitive Groups": "mask",
        "Unhealthy": "indoors",
        "Very Unhealthy": "emergency",
        "Hazardous": "emergency",
    }.get(cat, "caution")
    title, school = FAMILY_VERDICTS[verdict][lang]
    return {
        "ok": True,
        "station": station,
        "pm25": latest["pm25"],
        "category": cat,
        "verdict": verdict,
        "title": title,
        "school_advice": school,
        "kid_tips": FAMILY_TIPS[lang],
        "timestamp": latest.get("timestamp"),
        "lang": lang,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8130")))
