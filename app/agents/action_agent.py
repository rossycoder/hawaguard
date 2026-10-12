"""ActionAgent — the "voice" of the system.

Job: turn analysis into clear, actionable guidance for ordinary people.
  - Alert level derived from the AQI category (rule-based, transparent)
  - Health recommendations per category (standard public-health guidance —
    ALWAYS rule-based, never LLM-invented, for safety)
  - A short plain-language summary, in English or Roman Urdu:
    drafted by a free-tier LLM (Groq/Gemini via app/free_llm.py) when a key
    is configured, otherwise heuristic templates.

Provider is ALWAYS labeled: "heuristic" (default, free, offline) or
e.g. "groq:llama-3.3-70b-versatile" when real AI wrote the summary.
Nothing is ever presented as AI output when it is rule-based.
"""
import os

from app import free_llm

ALERT_LEVEL = {
    "Good": "none",
    "Moderate": "watch",
    "Unhealthy for Sensitive Groups": "advisory",
    "Unhealthy": "alert",
    "Very Unhealthy": "high_alert",
    "Hazardous": "emergency",
}

RECOMMENDATIONS = {
    "Good": ["Enjoy outdoor activities as normal."],
    "Moderate": [
        "Unusually sensitive people: consider shorter outdoor workouts.",
        "Everyone else: no change needed.",
    ],
    "Unhealthy for Sensitive Groups": [
        "Children, elderly, and asthma/heart patients: limit prolonged outdoor exertion.",
        "Keep windows closed during peak hours; run air purifier if available.",
    ],
    "Unhealthy": [
        "Everyone: reduce prolonged outdoor exertion.",
        "Wear a well-fitted mask (N95/KN95) if you must go out.",
        "Schools: move sports indoors.",
    ],
    "Very Unhealthy": [
        "Avoid all outdoor exertion.",
        "Keep windows/doors closed; use air purifiers.",
        "Check on elderly neighbours and children.",
    ],
    "Hazardous": [
        "Stay indoors. This is an emergency level.",
        "Do not exercise outdoors at all.",
        "Seek medical help if you feel breathless or dizzy.",
    ],
}

URDU_INTRO = {
    "Good": "Hawa saaf hai. Bahar jao, enjoy karo!",
    "Moderate": "Hawa theek hai, lekin sensitive log ehtiyat karen.",
    "Unhealthy for Sensitive Groups": "Bachay, buzurg aur mareez bahar kam niklen.",
    "Unhealthy": "Sab log ehtiyat karen — bahar exercise na karen, mask pehnen.",
    "Very Unhealthy": "Bahar na niklen. Khirkiyan band rakhen.",
    "Hazardous": "Emergency hai — ghar ke andar rahen!",
}

# Roman Urdu translations of RECOMMENDATIONS — rule-based, same safety guarantee.
# Bug fix: previously only the intro sentence was Roman Urdu; recommendations stayed English.
RECOMMENDATIONS_UR = {
    "Good": ["Bahar ki sargarmiyan aaram se enjoy karo."],
    "Moderate": [
        "Sensitive log: bahar workout thora chhota rakhen.",
        "Baaki sab: koi tabdeeli ki zaroorat nahi.",
    ],
    "Unhealthy for Sensitive Groups": [
        "Bachay, buzurg aur asthma/dil ke mareez: bahar zyada dair ki mehnat se parhez karen.",
        "Peak hours me khirkiyan band rakhen; agar air purifier hai to chalain.",
    ],
    "Unhealthy": [
        "Sab log: bahar lambi sargarmi kam karen.",
        "Bahar jana ho to achi tarah fit mask (N95/KN95) pehnen.",
        "Schools: khel indoor karwain.",
    ],
    "Very Unhealthy": [
        "Bahar ki tamam mehnat se bachen.",
        "Khirkiyan/darwazay band rakhen; air purifier use karen.",
        "Buzurg parosiyon aur bachon ka haal poochte rahen.",
    ],
    "Hazardous": [
        "Ghar ke andar rahen. Ye emergency level hai.",
        "Bahar bilkul exercise na karen.",
        "Agar saans phoolay ya chakkar aye to fori medical madad len.",
    ],
}


class ActionAgent:
    name = "action_agent"
    role = "Convert analysis into alerts and plain-language guidance."

    def __init__(self):
        self.provider = free_llm.available_provider() or "heuristic"

    def _heuristic_summary(self, category_label, trend, forecast, lang):
        if lang == "ur":
            return (
                f"{URDU_INTRO.get(category_label, '')} "
                f"Rujhan: {trend.get('direction', '?')}. "
                f"Aglay 24 ghanton me peak ~{forecast.get('peak_pm25', '?')} tak ja sakta hai."
            )
        return (
            f"Air quality is {category_label}. Trend is {trend.get('direction', 'unknown')} "
            f"(avg {trend.get('avg_pm25', '?')} µg/m³ over the last {trend.get('hours_analyzed', '?')}h). "
            f"Peak in the next 24h is estimated around {forecast.get('peak_pm25', '?')} µg/m³."
        )

    def _llm_summary(self, category_label, trend, forecast, lang):
        """Ask the free LLM to phrase the summary. Returns (text, label) or (None, reason)."""
        if lang == "ur":
            system = ("You are a public-health communicator. Write ONE short paragraph in Roman Urdu "
                      "(Urdu written in Latin script, NOT Urdu script). Use ONLY the numbers given. "
                      "Never invent numbers. Keep it under 60 words.")
        else:
            system = ("You are a public-health communicator. Write ONE short paragraph in plain English. "
                      "Use ONLY the numbers given. Never invent numbers. Keep it under 60 words.")
        user = (f"Air quality category: {category_label}. "
                f"Trend: {trend.get('direction', 'unknown')}, "
                f"average PM2.5 {trend.get('avg_pm25', '?')} µg/m³ over last {trend.get('hours_analyzed', '?')} hours. "
                f"Estimated 24h peak: {forecast.get('peak_pm25', '?')} µg/m³. "
                f"Alert level: {ALERT_LEVEL.get(category_label, 'watch')}.")
        return free_llm.chat(system, user, max_tokens=200, temperature=0.5)

    def act(self, category_label, trend, forecast, lang="en"):
        alert = ALERT_LEVEL.get(category_label, "watch")
        # Rule-based recommendations in BOTH languages — the frontend picks by
        # current lang and can re-render on language toggle without re-running.
        recs_en = RECOMMENDATIONS.get(category_label, [])
        recs_ur = RECOMMENDATIONS_UR.get(category_label, recs_en)
        recs = recs_ur if lang == "ur" else recs_en
        provider = "heuristic"
        summary = self._heuristic_summary(category_label, trend, forecast, lang)
        sum_en = self._heuristic_summary(category_label, trend, forecast, "en")
        sum_ur = self._heuristic_summary(category_label, trend, forecast, "ur")
        if free_llm.available_provider():
            llm_text, label = self._llm_summary(category_label, trend, forecast, lang)
            if llm_text:
                summary, provider = llm_text, label
        summary_i18n = {"en": sum_en, "ur": sum_ur}
        if provider != "heuristic":
            summary_i18n[lang] = summary  # real AI text in the requested language
        return {
            "provider": provider,
            "provider_note": (
                "heuristic: rule-based on EPA breakpoints (free, offline)"
                if provider == "heuristic"
                else f"{provider}: summary drafted by real AI, alert+recommendations rule-based"
            ),
            "alert_level": alert,
            "recommendations": recs,
            "recommendations_i18n": {"en": recs_en, "ur": recs_ur},
            "summary": summary,
            "summary_i18n": summary_i18n,
            "lang": lang,
        }
