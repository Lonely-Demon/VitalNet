"""
VitalNet Enhanced Clinical Feature Engineering
Transforms raw patient data into clinically meaningful features for ML classification.
"""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any, Dict, List

from app.ml.model_contract import RED_FLAG_RULES, SYMPTOM_NORMALIZATION_MAP


class ClinicalFeatureEngineer:
    """Advanced feature engineering for clinical triage data."""

    def __init__(self):
        self.high_risk_complaints = {
            "chest pain",
            "chest tightness",
            "difficulty breathing",
            "breathlessness",
            "altered consciousness",
            "confusion",
            "severe bleeding",
            "seizure",
            "unconscious",
            "stroke",
            "anaphylaxis",
            "acute abdomen",
            "severe abdominal pain",
            "difficulty speaking",
            "swelling of face throat",
            "facial droop",
        }

        self.trauma_indicators = {
            "injury",
            "trauma",
            "fall",
            "accident",
            "hit",
            "cut",
            "burned",
            "fracture",
            "wound",
        }

        self.obstetric_complaints = {
            "pregnancy",
            "pregnant",
            "delivery",
            "labor",
            "bleeding",
            "contractions",
            "baby",
            "birth",
        }

        self.critical_symptoms = {
            "chest_pain",
            "breathlessness",
            "altered_consciousness",
            "severe_bleeding",
            "seizure",
            "high_fever",
        }

    @staticmethod
    def _is_missing_number(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str) and not value.strip():
            return True
        try:
            return not math.isfinite(float(value))
        except (TypeError, ValueError):
            return True

    @staticmethod
    def _coerce_number(value: Any, fallback: float) -> float:
        if ClinicalFeatureEngineer._is_missing_number(value):
            return float(fallback)
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(fallback)

    @staticmethod
    def _text_value(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _normalize_symptom(symptom: Any) -> str:
        raw = str(symptom or "").strip().lower()
        if not raw:
            return ""

        cleaned = (
            raw.replace("_", " ")
            .replace("/", " ")
            .replace("-", " ")
        )
        cleaned = re.sub(r"[^a-z0-9 ]+", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return SYMPTOM_NORMALIZATION_MAP.get(cleaned, cleaned.replace(" ", "_"))

    def _normalize_symptoms(self, symptoms: Any) -> List[str]:
        if isinstance(symptoms, str):
            raw_symptoms = [symptoms]
        else:
            raw_symptoms = list(symptoms or [])

        normalized: List[str] = []
        seen = set()
        for symptom in raw_symptoms:
            canonical = self._normalize_symptom(symptom)
            if canonical and canonical not in seen:
                normalized.append(canonical)
                seen.add(canonical)
        return normalized

    def _prepare_feature_input(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        sanitized = dict(raw_data)
        sanitized["symptoms"] = self._normalize_symptoms(raw_data.get("symptoms", []))
        sanitized["patient_age"] = self._coerce_number(raw_data.get("patient_age"), 0.0)
        sanitized["patient_sex"] = self._text_value(raw_data.get("patient_sex")).lower()
        sanitized["chief_complaint"] = self._text_value(raw_data.get("chief_complaint"))
        sanitized["complaint_duration"] = self._text_value(raw_data.get("complaint_duration"))
        sanitized["location"] = self._text_value(raw_data.get("location"))
        sanitized["known_conditions"] = self._text_value(raw_data.get("known_conditions"))
        sanitized["observations"] = self._text_value(raw_data.get("observations"))
        sanitized["current_medications"] = self._text_value(raw_data.get("current_medications"))

        sanitized["bp_systolic"] = self._coerce_number(raw_data.get("bp_systolic"), 110.0)
        sanitized["bp_diastolic"] = self._coerce_number(raw_data.get("bp_diastolic"), 70.0)
        sanitized["spo2"] = self._coerce_number(raw_data.get("spo2"), 94.0)
        sanitized["heart_rate"] = self._coerce_number(raw_data.get("heart_rate"), 88.0)
        sanitized["temperature"] = self._coerce_number(raw_data.get("temperature"), 37.2)

        sanitized["_missing_vital_count"] = sum(
            1
            for field in ("bp_systolic", "bp_diastolic", "spo2", "heart_rate", "temperature")
            if self._is_missing_number(raw_data.get(field))
        )
        sanitized["_missing_vital_penalty"] = float(sanitized["_missing_vital_count"]) * 0.75
        sanitized["_red_flags"] = self.detect_red_flags(sanitized)
        return sanitized

    def detect_red_flags(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        symptoms = self._normalize_symptoms(raw_data.get("symptoms", []))
        complaint = self._text_value(raw_data.get("chief_complaint")).lower()

        matched_rules: List[str] = []
        matched_symptoms: List[str] = []

        for rule_name, rule in RED_FLAG_RULES.items():
            symptom_hit = bool(set(rule["symptoms"]) & set(symptoms))
            complaint_hit = any(term in complaint for term in rule["complaint_terms"])
            if symptom_hit or complaint_hit:
                matched_rules.append(rule_name)
                matched_symptoms.extend(sorted(set(rule["symptoms"]) & set(symptoms)))

        return {
            "red_flags": matched_rules,
            "matched_symptoms": sorted(set(matched_symptoms)),
            "must_escalate": bool(matched_rules),
            "requires_human_review": bool(matched_rules),
        }

    def engineer_features(self, raw_data: Dict[str, Any]) -> Dict[str, float]:
        """Engineer comprehensive clinical features from raw patient data."""
        safe_data = self._prepare_feature_input(raw_data)
        features: Dict[str, float] = {}

        features.update(self._extract_basic_features(safe_data))
        features.update(self._engineer_vital_features(safe_data))
        features.update(self._engineer_symptom_features(safe_data))
        features.update(self._engineer_age_specific_features(safe_data))
        features.update(self._engineer_contextual_features(safe_data))

        return features

    def _extract_basic_features(self, raw_data: Dict[str, Any]) -> Dict[str, float]:
        symptoms = raw_data.get("symptoms", [])

        return {
            "age": float(raw_data.get("patient_age", 0.0)),
            "sex": 1.0 if raw_data.get("patient_sex") == "male" else 0.0 if raw_data.get("patient_sex") == "female" else -1.0,
            "bp_systolic": float(raw_data.get("bp_systolic", 110.0)),
            "bp_diastolic": float(raw_data.get("bp_diastolic", 70.0)),
            "spo2": float(raw_data.get("spo2", 94.0)),
            "heart_rate": float(raw_data.get("heart_rate", 88.0)),
            "temperature": float(raw_data.get("temperature", 37.2)),
            "symptom_count": float(len([s for s in symptoms if s in self.critical_symptoms])),
            "chest_pain": 1.0 if "chest_pain" in symptoms else 0.0,
            "breathlessness": 1.0 if "breathlessness" in symptoms else 0.0,
            "altered_consciousness": 1.0 if "altered_consciousness" in symptoms else 0.0,
            "severe_bleeding": 1.0 if "severe_bleeding" in symptoms else 0.0,
            "seizure": 1.0 if "seizure" in symptoms else 0.0,
            "high_fever": 1.0 if "high_fever" in symptoms else 0.0,
        }

    def _engineer_vital_features(self, raw_data: Dict[str, Any]) -> Dict[str, float]:
        bp_sys = float(raw_data.get("bp_systolic", 110.0))
        bp_dia = float(raw_data.get("bp_diastolic", 70.0))
        hr = float(raw_data.get("heart_rate", 88.0))
        spo2 = float(raw_data.get("spo2", 94.0))
        temp = float(raw_data.get("temperature", 37.2))
        age = float(raw_data.get("patient_age", 0.0))
        missing_penalty = float(raw_data.get("_missing_vital_penalty", 0.0))

        pulse_pressure = bp_sys - bp_dia if bp_sys > 0 and bp_dia > 0 else 40.0
        map_pressure = (bp_sys + 2 * bp_dia) / 3 if bp_sys > 0 and bp_dia > 0 else 93.0
        shock_index = hr / bp_sys if bp_sys > 0 and hr > 0 else 0.6
        spo2_age_ratio = spo2 / max(age, 1.0) if spo2 > 0 else 0.0
        temp_deviation = abs(temp - 37.2) if temp > 0 else 0.0

        return {
            "pulse_pressure": float(pulse_pressure),
            "mean_arterial_pressure": float(map_pressure),
            "shock_index": float(shock_index),
            "spo2_age_ratio": float(spo2_age_ratio),
            "temp_deviation": float(temp_deviation),
            "cardiac_risk_score": self._calculate_cardiac_risk(raw_data) + missing_penalty,
            "respiratory_distress_score": self._calculate_resp_distress(raw_data) + missing_penalty,
            "hemodynamic_instability": self._calculate_hemodynamic_score(raw_data) + missing_penalty,
            "sepsis_risk_score": self._calculate_sepsis_risk(raw_data) + missing_penalty,
            "pediatric_adjustment": self._pediatric_vital_adjustment(raw_data),
            "geriatric_adjustment": self._geriatric_vital_adjustment(raw_data),
            "pregnancy_adjustment": self._pregnancy_adjustment(raw_data),
        }

    def _engineer_symptom_features(self, raw_data: Dict[str, Any]) -> Dict[str, float]:
        symptoms = raw_data.get("symptoms", [])
        bp_sys = float(raw_data.get("bp_systolic", 110.0))

        chest_pain = 1.0 if "chest_pain" in symptoms else 0.0
        breathlessness = 1.0 if "breathlessness" in symptoms else 0.0
        altered_consciousness = 1.0 if "altered_consciousness" in symptoms else 0.0
        severe_bleeding = 1.0 if "severe_bleeding" in symptoms else 0.0
        seizure = 1.0 if "seizure" in symptoms else 0.0
        high_fever = 1.0 if "high_fever" in symptoms else 0.0

        red_flag_boost = 1.5 if self.detect_red_flags(raw_data)["must_escalate"] else 0.0

        return {
            "cardiopulmonary_cluster": chest_pain * breathlessness,
            "neurological_cluster": altered_consciousness * seizure,
            "hemorrhagic_cluster": severe_bleeding * (1.0 if bp_sys < 90 else 0.0),
            "infectious_cluster": high_fever * len(symptoms),
            "symptom_severity_score": self._calculate_symptom_severity(symptoms) + red_flag_boost,
            "symptom_duration_risk": self._map_duration_to_risk(raw_data.get("complaint_duration", "")),
            "chief_complaint_risk": self._map_complaint_to_risk(raw_data.get("chief_complaint", "")),
            "comorbidity_multiplier": self._calculate_comorbidity_risk(raw_data.get("known_conditions", "")),
        }

    def _engineer_age_specific_features(self, raw_data: Dict[str, Any]) -> Dict[str, float]:
        return {
            "pediatric_fever_risk": self._pediatric_fever_assessment(raw_data),
            "elderly_fall_risk": self._elderly_fall_assessment(raw_data),
            "adult_cardiac_risk": self._adult_cardiac_assessment(raw_data),
            "obstetric_emergency_risk": self._obstetric_assessment(raw_data),
            "trauma_severity_score": self._trauma_assessment(raw_data),
            "mental_health_crisis": self._mental_health_assessment(raw_data),
        }

    def _engineer_contextual_features(self, raw_data: Dict[str, Any]) -> Dict[str, float]:
        return {
            "time_of_day_risk": self._time_based_risk(),
            "seasonal_risk": self._seasonal_disease_risk(),
            "geographic_risk": self._geographic_disease_risk(raw_data.get("location", "")),
            "epidemic_alert_level": 0.0,
            "healthcare_accessibility": self._healthcare_access_score(raw_data.get("location", "")),
        }

    def _calculate_cardiac_risk(self, raw_data: Dict[str, Any]) -> float:
        age = float(raw_data.get("patient_age", 0.0))
        bp_sys = float(raw_data.get("bp_systolic", 110.0))
        hr = float(raw_data.get("heart_rate", 88.0))
        symptoms = raw_data.get("symptoms", [])

        risk_score = 0.0
        if age > 65:
            risk_score += 2.0
        elif age > 45:
            risk_score += 1.0

        if bp_sys > 160:
            risk_score += 2.0
        if hr > 100 or hr < 60:
            risk_score += 1.5
        if "chest_pain" in symptoms:
            risk_score += 3.0
        if "breathlessness" in symptoms:
            risk_score += 1.5
        if self.detect_red_flags(raw_data)["must_escalate"]:
            risk_score += 1.0

        return min(risk_score, 10.0)

    def _calculate_resp_distress(self, raw_data: Dict[str, Any]) -> float:
        spo2 = float(raw_data.get("spo2", 94.0))
        hr = float(raw_data.get("heart_rate", 88.0))
        symptoms = raw_data.get("symptoms", [])

        score = 0.0
        if spo2 < 90:
            score += 4.0
        elif spo2 < 94:
            score += 2.0
        if hr > 110:
            score += 1.5
        if "breathlessness" in symptoms:
            score += 3.0
        if self.detect_red_flags(raw_data)["must_escalate"]:
            score += 1.0

        return score

    def _calculate_hemodynamic_score(self, raw_data: Dict[str, Any]) -> float:
        bp_sys = float(raw_data.get("bp_systolic", 110.0))
        bp_dia = float(raw_data.get("bp_diastolic", 70.0))
        hr = float(raw_data.get("heart_rate", 88.0))

        score = 0.0
        if bp_sys < 90:
            score += 4.0
        elif bp_sys > 180:
            score += 2.0

        if hr > 130:
            score += 3.0
        elif hr < 50:
            score += 2.0

        if bp_sys > 0:
            shock_index = hr / bp_sys
            if shock_index > 1.0:
                score += 3.0
            elif shock_index > 0.8:
                score += 1.5

        if bp_sys > 0 and bp_dia > 0 and bp_dia >= bp_sys:
            score += 2.5

        return score

    def _calculate_sepsis_risk(self, raw_data: Dict[str, Any]) -> float:
        temp = float(raw_data.get("temperature", 37.2))
        bp_sys = float(raw_data.get("bp_systolic", 110.0))
        hr = float(raw_data.get("heart_rate", 88.0))
        symptoms = raw_data.get("symptoms", [])

        score = 0.0
        if temp > 38.0 or temp < 36.0:
            score += 1.0
        if bp_sys < 100:
            score += 2.0
        if hr > 90:
            score += 1.0
        if "altered_consciousness" in symptoms:
            score += 2.0
        if "high_fever" in symptoms:
            score += 1.5

        return score

    def _pediatric_vital_adjustment(self, raw_data: Dict[str, Any]) -> float:
        age = float(raw_data.get("patient_age", 0.0))
        if age >= 18:
            return 0.0

        hr = float(raw_data.get("heart_rate", 88.0))
        temp = float(raw_data.get("temperature", 37.2))
        adjustment = 0.0

        if age < 2:
            if hr > 160 or hr < 100:
                adjustment += 2.0
        elif age < 6:
            if hr > 140 or hr < 80:
                adjustment += 1.5
        elif age < 12:
            if hr > 120 or hr < 70:
                adjustment += 1.0

        if temp > 38.5:
            adjustment += 2.0

        return adjustment

    def _geriatric_vital_adjustment(self, raw_data: Dict[str, Any]) -> float:
        age = float(raw_data.get("patient_age", 0.0))
        if age < 65:
            return 0.0

        bp_sys = float(raw_data.get("bp_systolic", 110.0))
        temp = float(raw_data.get("temperature", 37.2))

        adjustment = 0.0
        if temp < 36.5:
            adjustment += 1.5
        if bp_sys < 100:
            adjustment += 2.0
        if age > 80:
            adjustment += 1.0

        return adjustment

    def _pregnancy_adjustment(self, raw_data: Dict[str, Any]) -> float:
        age = float(raw_data.get("patient_age", 0.0))
        sex = raw_data.get("patient_sex", "")
        conditions = self._text_value(raw_data.get("known_conditions")).lower()
        complaint = self._text_value(raw_data.get("chief_complaint")).lower()

        if sex != "female" or age < 15 or age > 45:
            return 0.0

        adjustment = 0.0
        if any(term in conditions for term in ["pregnan", "expecting"]):
            adjustment += 1.0
        if any(term in complaint for term in self.obstetric_complaints):
            adjustment += 2.0

        return adjustment

    def _calculate_symptom_severity(self, symptoms: List[str]) -> float:
        severity_weights = {
            "altered_consciousness": 4.0,
            "severe_bleeding": 4.0,
            "seizure": 4.0,
            "chest_pain": 3.0,
            "breathlessness": 3.0,
            "high_fever": 2.0,
            "severe_abdominal_pain": 4.0,
            "persistent_vomiting": 2.5,
            "weakness_one_side": 4.0,
            "difficulty_speaking": 4.0,
            "swelling_face_throat": 4.5,
            "anaphylaxis": 5.0,
            "stroke": 5.0,
            "acute_abdomen": 5.0,
        }

        total_severity = sum(severity_weights.get(symptom, 1.0) for symptom in symptoms)
        return min(total_severity, 15.0)

    def _map_duration_to_risk(self, duration: str) -> float:
        duration_lower = (duration or "").lower().replace("–", "-")

        if "less than 1 hour" in duration_lower or "< 1 hour" in duration_lower:
            return 3.0
        if "1-6 hours" in duration_lower:
            return 2.5
        if "6-24 hours" in duration_lower:
            return 2.0
        if "1-3 days" in duration_lower:
            return 1.5
        if "more than 3 days" in duration_lower or "> 3 days" in duration_lower:
            return 1.0
        return 1.5

    def _map_complaint_to_risk(self, complaint: str) -> float:
        complaint_lower = self._text_value(complaint).lower()

        red_flags = self.detect_red_flags({"chief_complaint": complaint_lower, "symptoms": []})
        if red_flags["must_escalate"]:
            return 5.0

        for high_risk in self.high_risk_complaints:
            if high_risk in complaint_lower:
                return 4.0

        for trauma in self.trauma_indicators:
            if trauma in complaint_lower:
                return 3.0

        return 1.0

    def _calculate_comorbidity_risk(self, conditions: str) -> float:
        if not conditions:
            return 1.0

        conditions_lower = self._text_value(conditions).lower()
        high_risk_conditions = [
            "diabetes",
            "heart",
            "cardiac",
            "hypertension",
            "kidney",
            "renal",
            "copd",
            "asthma",
            "cancer",
            "stroke",
            "liver",
        ]

        risk_count = sum(1 for condition in high_risk_conditions if condition in conditions_lower)
        return min(1.0 + (risk_count * 0.5), 3.0)

    def _pediatric_fever_assessment(self, raw_data: Dict[str, Any]) -> float:
        age = float(raw_data.get("patient_age", 0.0))
        temp = float(raw_data.get("temperature", 37.2))
        symptoms = raw_data.get("symptoms", [])

        if age >= 18:
            return 0.0

        score = 0.0
        if age < 0.25:
            if temp > 38.0:
                score += 4.0
        elif age < 2:
            if temp > 39.0:
                score += 3.0
        else:
            if temp > 40.0:
                score += 2.0

        if "high_fever" in symptoms:
            score += 1.0

        return score

    def _elderly_fall_assessment(self, raw_data: Dict[str, Any]) -> float:
        age = float(raw_data.get("patient_age", 0.0))
        complaint = self._text_value(raw_data.get("chief_complaint")).lower()

        if age < 65:
            return 0.0

        score = 0.0
        if age > 75:
            score += 1.0
        if age > 85:
            score += 2.0

        fall_keywords = ["fall", "fell", "slip", "trip", "dizzy", "weakness"]
        if any(keyword in complaint for keyword in fall_keywords):
            score += 3.0

        return score

    def _adult_cardiac_assessment(self, raw_data: Dict[str, Any]) -> float:
        age = float(raw_data.get("patient_age", 0.0))
        if age < 18 or age > 65:
            return 0.0

        return self._calculate_cardiac_risk(raw_data) * 0.8

    def _obstetric_assessment(self, raw_data: Dict[str, Any]) -> float:
        age = float(raw_data.get("patient_age", 0.0))
        sex = raw_data.get("patient_sex", "")
        complaint = self._text_value(raw_data.get("chief_complaint")).lower()

        if sex != "female" or age < 15 or age > 45:
            return 0.0

        score = 0.0
        for obstetric_term in self.obstetric_complaints:
            if obstetric_term in complaint:
                score += 2.0
                break

        if "bleeding" in complaint:
            score += 1.5

        return score

    def _trauma_assessment(self, raw_data: Dict[str, Any]) -> float:
        complaint = self._text_value(raw_data.get("chief_complaint")).lower()
        bp_sys = float(raw_data.get("bp_systolic", 110.0))
        hr = float(raw_data.get("heart_rate", 88.0))

        score = 0.0
        for trauma_term in self.trauma_indicators:
            if trauma_term in complaint:
                score += 2.0
                break

        if bp_sys < 90:
            score += 3.0
        if hr > 120:
            score += 2.0

        return score

    def _mental_health_assessment(self, raw_data: Dict[str, Any]) -> float:
        complaint = self._text_value(raw_data.get("chief_complaint")).lower()
        symptoms = raw_data.get("symptoms", [])

        score = 0.0
        mental_health_terms = [
            "suicid",
            "depress",
            "anxiety",
            "panic",
            "psycho",
            "mental",
            "confused",
            "agitat",
            "violent",
        ]

        for term in mental_health_terms:
            if term in complaint:
                score += 2.0
                break

        if "altered_consciousness" in symptoms:
            score += 1.0

        return score

    def _time_based_risk(self) -> float:
        hour = datetime.now().hour
        if 22 <= hour or hour <= 6:
            return 1.5
        if 18 <= hour <= 22:
            return 1.2
        return 1.0

    def _seasonal_disease_risk(self) -> float:
        month = datetime.now().month
        if month in [12, 1, 2]:
            return 1.3
        if month in [6, 7, 8]:
            return 1.2
        return 1.0

    def _geographic_disease_risk(self, location: str) -> float:
        return 1.0

    def _healthcare_access_score(self, location: str) -> float:
        location_lower = self._text_value(location).lower()
        rural_terms = ["village", "rural", "remote", "tribal"]
        urban_terms = ["city", "town", "urban", "metro"]

        if any(term in location_lower for term in rural_terms):
            return 0.5
        if any(term in location_lower for term in urban_terms):
            return 1.0
        return 0.7
