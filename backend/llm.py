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
import logging
import asyncio
from pathlib import Path

import groq
from groq import AsyncGroq  # Use async client — non-blocking event loop
from json_repair import repair_json

from config import settings

logger = logging.getLogger("vitalnet")

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

MAX_RETRIES_PER_MODEL = 1   # 1 retry = 2 total attempts per tier before downgrade

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
        logger.warning("[WARN] google-generativeai not installed — Gemini fallback disabled")

# ─── System prompt — cached at module load, never re-read from disk ──────────

try:
    _SYSTEM_PROMPT: str = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
except FileNotFoundError:
    logger.error(
        "[CRITICAL] System prompt not found at %s. Using minimal fallback prompt.",
        SYSTEM_PROMPT_PATH,
    )
    _SYSTEM_PROMPT = (
        "You are a clinical triage assistant. Analyse the patient data and return a JSON briefing "
        "with keys: triage_level, primary_risk_driver, differential_diagnoses, red_flags, "
        "recommended_immediate_actions, recommended_tests, uncertainty_flags, disclaimer. "
        "CRITICAL: Your response MUST be a single valid JSON object only. Do not wrap it in "
        "markdown code blocks. Do not add any explanatory text before or after the JSON. "
        "Do not use trailing commas."
    )


# ─── JSON parser with auto-repair ────────────────────────────────────────────

def _parse_llm_json(raw: str) -> dict:
    """
    Parse LLM JSON output with auto-repair for common formatting errors:
    trailing commas, markdown code fences, unescaped quotes, etc.
    Raises json.JSONDecodeError only if repair also fails.
    """
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        repaired = repair_json(raw, return_objects=True)
        if isinstance(repaired, dict):
            return repaired
        raise   # re-raise original error — repair produced a non-dict


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
        timeout=15,   # Bumped from 8s: 70B JSON generation can take 8–12s under load
    )
    return _parse_llm_json(response.choices[0].message.content)


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
    return _parse_llm_json(response.text)


# ─── Main entry point — fully async ─────────────────────────────────────────

async def generate_briefing(form_data: dict, triage_result: dict) -> dict:
    """
    Generate a clinical briefing using the 4-tier fallback chain.
    Never raises — always returns a usable briefing dict.
    Triage level from classifier is enforced on every output path.

    Intra-tier retry: if a model fails due to a JSON parse error (stray
    markdown fence, trailing comma etc.), retries the SAME model once before
    downgrading to an inferior tier. A formatting artifact should not degrade
    clinical reasoning quality.
    """
    if not _groq_client and not _gemini_configured:
        logger.warning("No LLM API keys configured — returning fallback briefing.")
        return _fallback_briefing(triage_result)

    patient_context = _build_patient_context(form_data, triage_result)

    # ── Tier 1 & 2: Groq models ───────────────────────────────────────────────
    if _groq_client:
        for model in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]:
            for attempt in range(MAX_RETRIES_PER_MODEL + 1):
                try:
                    briefing = await _call_groq(model, patient_context)
                    logger.info("Briefing via Groq/%s (attempt %d)", model, attempt + 1)
                    return _enforce_schema(briefing, triage_result)
                except groq.RateLimitError:
                    logger.warning("Rate limit on Groq/%s — moving to next tier", model)
                    await asyncio.sleep(0.5)
                    break   # rate limit is not retriable within the same tier
                except json.JSONDecodeError:
                    if attempt < MAX_RETRIES_PER_MODEL:
                        logger.warning(
                            "JSON parse error on Groq/%s (attempt %d) — retrying same model",
                            model, attempt + 1,
                        )
                        await asyncio.sleep(0.3)
                        continue
                    logger.warning(
                        "JSON parse error on Groq/%s after %d attempts — downgrading",
                        model, MAX_RETRIES_PER_MODEL + 1,
                    )
                    break
                except (groq.APIConnectionError, groq.InternalServerError):
                    logger.warning("Connection/server error on Groq/%s — moving to next tier", model)
                    break
                except Exception as e:
                    logger.warning("Unexpected error on Groq/%s: %s — moving to next tier", model, e)
                    break

    # ── Tier 3 & 4: Gemini models ─────────────────────────────────────────────
    if _gemini_configured:
        for model in ["gemini-2.5-flash", "gemini-2.5-flash-lite"]:
            for attempt in range(MAX_RETRIES_PER_MODEL + 1):
                try:
                    briefing = await _call_gemini(model, patient_context)
                    logger.info("Briefing via Gemini/%s (attempt %d)", model, attempt + 1)
                    return _enforce_schema(briefing, triage_result)
                except json.JSONDecodeError:
                    if attempt < MAX_RETRIES_PER_MODEL:
                        logger.warning(
                            "JSON parse error on Gemini/%s (attempt %d) — retrying same model",
                            model, attempt + 1,
                        )
                        await asyncio.sleep(0.3)
                        continue
                    logger.warning(
                        "JSON parse error on Gemini/%s after %d attempts — downgrading",
                        model, MAX_RETRIES_PER_MODEL + 1,
                    )
                    break
                except Exception as e:
                    logger.warning("Error on Gemini/%s: %s — moving to next tier", model, e)
                    await asyncio.sleep(0.5)
                    break

    # ── All tiers exhausted ───────────────────────────────────────────────────
    logger.warning("All LLM tiers exhausted — returning fallback briefing. Triage badge intact.")
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
