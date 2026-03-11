import os
import json
import groq
from pathlib import Path
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# LLM model priority chain — ordered by preference
# Primary: 70B for best clinical reasoning (1K requests/day free tier limit)
# Fallback: 8B instant — activates automatically on RateLimitError (14.4K req/day)
MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]

SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "clinical_system_prompt.txt"

FIXED_DISCLAIMER = (
    "AI-generated clinical briefing for decision support only. "
    "Requires qualified medical examination and physician judgment "
    "before any clinical action."
)


def _load_system_prompt() -> str:
    with open(SYSTEM_PROMPT_PATH, "r") as f:
        return f.read()


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


def generate_briefing(form_data: dict, triage_result: dict) -> dict:
    """
    Call Groq LLM and return parsed briefing JSON.
    Iterates through MODELS list in order — moves to next model on rate limit or connection error.
    On all models exhausted: returns safe fallback briefing. Never raises. Never crashes the endpoint.
    """
    system_prompt = _load_system_prompt()
    patient_context = _build_patient_context(form_data, triage_result)

    for model in MODELS:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": patient_context},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=1000,
                timeout=8,
            )

            briefing = json.loads(response.choices[0].message.content)

            # Safety enforcement — classifier triage level is locked, LLM cannot override
            briefing["triage_level"] = triage_result["triage_level"]
            briefing["disclaimer"] = FIXED_DISCLAIMER

            # Ensure all required schema fields exist
            required_fields = [
                "triage_level", "primary_risk_driver", "differential_diagnoses",
                "red_flags", "recommended_immediate_actions", "recommended_tests",
                "uncertainty_flags", "disclaimer"
            ]
            for field in required_fields:
                if field not in briefing:
                    briefing[field] = [] if field in (
                        "differential_diagnoses", "red_flags",
                        "recommended_immediate_actions", "recommended_tests"
                    ) else "Not available"

            print(f"✓ Briefing generated via {model}")
            return briefing

        except groq.RateLimitError:
            print(f"Rate limit (429) on {model} — trying next model in chain")
            continue

        except groq.APIConnectionError as e:
            print(f"Connection error on {model}: {e.__cause__} — trying next model")
            continue

        except groq.InternalServerError as e:
            print(f"Server error ({e.status_code}) on {model} — trying next model")
            continue

        except json.JSONDecodeError as e:
            print(f"JSON parse error on {model}: {e} — trying next model")
            continue

        except Exception as e:
            print(f"Unexpected error on {model}: {e} — trying next model")
            continue

    # All models in chain exhausted
    print("⚠ All models exhausted — returning fallback briefing. Triage badge intact.")
    return _fallback_briefing(triage_result)


def _fallback_briefing(triage_result: dict) -> dict:
    """
    Safe fallback when all LLM models are unavailable.
    Triage level and risk driver from classifier are still valid and displayed.
    """
    return {
        "triage_level": triage_result["triage_level"],
        "primary_risk_driver": triage_result["risk_driver"],
        "differential_diagnoses": ["LLM briefing unavailable — triage classification from ML classifier is intact"],
        "red_flags": [],
        "recommended_immediate_actions": ["Refer patient to PHC doctor for in-person evaluation"],
        "recommended_tests": [],
        "uncertainty_flags": "LLM briefing could not be generated. Triage level and risk driver are from the ML classifier and remain valid.",
        "disclaimer": FIXED_DISCLAIMER,
    }
