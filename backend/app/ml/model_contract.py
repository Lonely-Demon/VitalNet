"""Shared clinical triage model contract constants.

Keep the backend feature pipeline and the frontend ONNX client aligned.
"""

MODEL_VERSION = "2.0.0"
FEATURE_SCHEMA_VERSION = "v45-2026-03-30"

EXPECTED_ENHANCED_PKL_SHA256 = "3f661afed8f042899843cf0556975dc20efb7df0c99752e6f6439ade25f7cfb5"
EXPECTED_ONNX_SHA256 = "3e26c57592b7312667fcaa8d01c7d46f7b350718ba2d6795de103d6a25530a68"

CONFIDENCE_FLOOR = 0.72
UNCERTAINTY_FLOOR = 0.10
LIVE_DRIFT_WINDOW = 50

SYMPTOM_NORMALIZATION_MAP = {
    "chest pain": "chest_pain",
    "chest tightness": "chest_pain",
    "difficulty breathing": "breathlessness",
    "breathlessness": "breathlessness",
    "shortness of breath": "breathlessness",
    "altered consciousness": "altered_consciousness",
    "altered consciousness / confusion": "altered_consciousness",
    "confusion": "altered_consciousness",
    "severe bleeding": "severe_bleeding",
    "heavy bleeding": "severe_bleeding",
    "seizure": "seizure",
    "high fever": "high_fever",
    "fever": "high_fever",
    "severe abdominal pain": "severe_abdominal_pain",
    "abdominal pain": "severe_abdominal_pain",
    "persistent vomiting": "persistent_vomiting",
    "vomiting": "persistent_vomiting",
    "weakness on one side": "weakness_one_side",
    "weakness one side": "weakness_one_side",
    "difficulty speaking": "difficulty_speaking",
    "slurred speech": "difficulty_speaking",
    "swelling of face throat": "swelling_face_throat",
    "swelling face throat": "swelling_face_throat",
    "anaphylaxis": "anaphylaxis",
    "stroke": "stroke",
    "acute abdomen": "acute_abdomen",
}

RED_FLAG_RULES = {
    "stroke_syndrome": {
        "symptoms": {"weakness_one_side", "difficulty_speaking", "altered_consciousness"},
        "complaint_terms": {"stroke", "slurred speech", "facial droop", "one sided weakness"},
    },
    "anaphylaxis": {
        "symptoms": {"swelling_face_throat", "breathlessness"},
        "complaint_terms": {"anaphylaxis", "allergic reaction", "throat swelling", "hives"},
    },
    "acute_abdomen": {
        "symptoms": {"severe_abdominal_pain", "persistent_vomiting"},
        "complaint_terms": {"acute abdomen", "severe abdominal pain", "rigid abdomen"},
    },
}
