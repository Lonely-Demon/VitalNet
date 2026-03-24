"""
VitalNet LLM Briefing Generator — async, 4-tier fallback
Tier 1: Groq Llama-3.3-70B (primary, ~2s)
Tier 2: Groq Llama-3.1-8B  (on Groq rate limit)
Tier 3: Gemini 2.5 Flash    (on both Groq models exhausted)
Tier 4: Gemini 2.5 Flash-Lite (on Gemini Flash rate limit)
All tiers share the same output schema enforcement.
The triage_level from the ML classifier is locked — no LLM can override it.
"""
import json
import asyncio
from pathlib import Path

import groq
from groq import AsyncGroq  # Use async client — non-blocking event loop

from config import settings

# ─── Module-level constants ──────────────────────────────────────────────────

SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "clinical_system_prompt.txt"

FIXED_DISCLAIMER = (
    "AI-generated clinical briefing for decision support only. "
    "Requires qualified medical examination and physician judgment "
    "before any clinical action."
)

REQUIRED_FIELDS = [
    "triage_level", "primary_risk_driver", "differential_diagnoses",
    "red_flags", "recommended_immediate_actions", "recommended_tests",
    "uncertainty_flags", "disclaimer",
]

LIST_FIELDS = {
    "differential_diagnoses", "red_flags",
    "recommended_immediate_actions", "recommended_tests",
}

# ─── Clients — initialized once at module load ───────────────────────────────

_groq_client: AsyncGroq | None = None
_gemini_configured: bool = False

if settings.groq_api_key:
    _groq_client = AsyncGroq(api_key=settings.groq_api_key)

if settings.gemini_api_key:
    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.gemini_api_key)
        _gemini_configured = True
    except ImportError:
        print("[WARN] google-generativeai not installed — Gemini fallback disabled")

# ─── System prompt — cached at module load, never re-read from disk ──────────

_SYSTEM_PROMPT: str = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


# ─── Patient context builder ──────────────────────────────────────────────────

def _build_patient_context(form_data: dict, triage_result: dict) -> str:
    def fmt(val, unit=""):
        return f"{val}{unit}" if val is not None and val != -1 else "Not recorded"

    symptoms = form_data.get("symptoms", [])
    symptoms_str = ", ".join(symptoms) if symptoms else "None reported"

    return f"""PATIENT CONTEXT:
- Age: {form_data.get('patient_age')} years
- Sex: {form_data.get('patient_sex')}
- Location: {form_data.get('location')}
- Chief Complaint: {form_data.get('chief_complaint')}
- Duration: {form_data.get('complaint_duration')}
- BP: {fmt(form_data.get('bp_systolic'))}/{fmt(form_data.get('bp_diastolic'))} mmHg
- SpO2: {fmt(form_data.get('spo2'), '%')}
- Heart Rate: {fmt(form_data.get('heart_rate'), ' bpm')}
- Temperature: {fmt(form_data.get('temperature'), '°C')}
- Symptoms reported: {symptoms_str}
- ASHA observations: {form_data.get('observations') or 'None recorded'}
- Known conditions: {form_data.get('known_conditions') or 'None reported'}
- Current medications: {form_data.get('current_medications') or 'None reported'}

TRIAGE CLASSIFICATION (from ML classifier — locked, do not override):
Level: {triage_result['triage_level']}
Confidence: {triage_result['confidence_score']:.2f}
Primary signal: {triage_result['risk_driver']}"""


# ─── Schema enforcement ───────────────────────────────────────────────────────

def _enforce_schema(briefing: dict, triage_result: dict) -> dict:
    """
    Hard-lock the triage level and disclaimer, ensure all required fields exist.
    This runs on every LLM output regardless of which tier produced it.
    """
    briefing["triage_level"] = triage_result["triage_level"]  # SAFETY: LLM cannot override
    briefing["disclaimer"] = FIXED_DISCLAIMER
    for field in REQUIRED_FIELDS:
        if field not in briefing:
            briefing[field] = [] if field in LIST_FIELDS else "Not available"
    return briefing


# ─── Groq async call ─────────────────────────────────────────────────────────

async def _call_groq(model: str, patient_context: str) -> dict:
    """Attempt one Groq model call. Raises on failure — caller handles retry."""
    response = await _groq_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": patient_context},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=1000,
        timeout=8,
    )
    return json.loads(response.choices[0].message.content)


# ─── Gemini async call ────────────────────────────────────────────────────────

async def _call_gemini(model_name: str, patient_context: str) -> dict:
    """
    Attempt a Gemini model call using the native async API.
    Uses generate_content_async() — NOT asyncio.to_thread().
    The google-generativeai SDK natively supports async; wrapping with
    asyncio.to_thread() would waste a thread pool worker unnecessarily.
    Raises on failure — caller handles retry.
    """
    import google.generativeai as genai
    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=_SYSTEM_PROMPT,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.1,
            max_output_tokens=1000,
        ),
    )
    # Use native async method — avoids thread pool overhead
    response = await model.generate_content_async(patient_context)
    return json.loads(response.text)


# ─── Main entry point — fully async ─────────────────────────────────────────

async def generate_briefing(form_data: dict, triage_result: dict) -> dict:
    """
    Generate a clinical briefing using the 4-tier fallback chain.
    Never raises — always returns a usable briefing dict.
    Triage level from classifier is enforced on every output path.
    """
    if not _groq_client and not _gemini_configured:
        print("⚠ No LLM API keys configured — returning fallback briefing.")
        return _fallback_briefing(triage_result)

    patient_context = _build_patient_context(form_data, triage_result)

    # ── Tier 1 & 2: Groq models ───────────────────────────────────────────────
    if _groq_client:
        for model in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]:
            try:
                briefing = await _call_groq(model, patient_context)
                print(f"✓ Briefing generated via Groq/{model}")
                return _enforce_schema(briefing, triage_result)
            except groq.RateLimitError:
                print(f"Rate limit on Groq/{model} — trying next tier")
                await asyncio.sleep(0.5)   # Brief pause before next attempt
                continue
            except (groq.APIConnectionError, groq.InternalServerError):
                print(f"Connection/server error on Groq/{model} — trying next tier")
                continue
            except json.JSONDecodeError:
                print(f"JSON parse error on Groq/{model} — trying next tier")
                continue
            except Exception as e:
                print(f"Unexpected error on Groq/{model}: {e} — trying next tier")
                continue

    # ── Tier 3 & 4: Gemini models ─────────────────────────────────────────────
    if _gemini_configured:
        for model in ["gemini-2.5-flash", "gemini-2.5-flash-lite"]:
            try:
                briefing = await _call_gemini(model, patient_context)
                print(f"✓ Briefing generated via Gemini/{model}")
                return _enforce_schema(briefing, triage_result)
            except json.JSONDecodeError:
                print(f"JSON parse error on Gemini/{model} — trying next tier")
                continue
            except Exception as e:
                # Catches Gemini quota errors, connection errors, etc.
                print(f"Error on Gemini/{model}: {e} — trying next tier")
                await asyncio.sleep(0.5)
                continue

    # ── All tiers exhausted ───────────────────────────────────────────────────
    print("⚠ All LLM tiers exhausted — returning fallback briefing. Triage badge intact.")
    return _fallback_briefing(triage_result)


# ─── Fallback briefing ────────────────────────────────────────────────────────

def _fallback_briefing(triage_result: dict) -> dict:
    return {
        "triage_level":                 triage_result["triage_level"],
        "primary_risk_driver":          triage_result["risk_driver"],
        "differential_diagnoses":       ["LLM briefing unavailable — triage from ML classifier is intact"],
        "red_flags":                    [],
        "recommended_immediate_actions": ["Refer patient to PHC doctor for in-person evaluation"],
        "recommended_tests":            [],
        "uncertainty_flags":            "LLM briefing could not be generated. Triage level and risk driver from ML classifier remain valid.",
        "disclaimer":                   FIXED_DISCLAIMER,
        "_model_used":                  "fallback",
    }
