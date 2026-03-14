"""
VitalNet Enhanced Clinical Feature Engineering
Transforms raw patient data into clinically meaningful features for ML classification
"""

import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional
import re

class ClinicalFeatureEngineer:
    """
    Advanced feature engineering for clinical triage data
    Transforms 14 basic features into 45+ clinical features
    """

    def __init__(self):
        self.high_risk_complaints = {
            'chest pain', 'chest tightness', 'difficulty breathing',
            'breathlessness', 'altered consciousness', 'confusion',
            'severe bleeding', 'seizure', 'unconscious'
        }

        self.trauma_indicators = {
            'injury', 'trauma', 'fall', 'accident', 'hit', 'cut',
            'burned', 'fracture', 'wound'
        }

        self.obstetric_complaints = {
            'pregnancy', 'pregnant', 'delivery', 'labor', 'bleeding',
            'contractions', 'baby', 'birth'
        }

    def engineer_features(self, raw_data: Dict[str, Any]) -> Dict[str, float]:
        """
        Engineer comprehensive clinical features from raw patient data

        Args:
            raw_data: Dictionary containing patient data

        Returns:
            Dictionary of engineered features
        """
        features = {}

        # Extract basic features (14 original)
        features.update(self._extract_basic_features(raw_data))

        # Vital sign ratios and derivatives (12 features)
        features.update(self._engineer_vital_features(raw_data))

        # Symptom interaction features (8 features)
        features.update(self._engineer_symptom_features(raw_data))

        # Age-specific clinical rules (6 features)
        features.update(self._engineer_age_specific_features(raw_data))

        # Contextual features (5 features)
        features.update(self._engineer_contextual_features(raw_data))

        return features

    def _extract_basic_features(self, raw_data: Dict[str, Any]) -> Dict[str, float]:
        """Extract the original 14 basic features"""
        symptoms = raw_data.get('symptoms', [])

        return {
            'age': float(raw_data.get('patient_age', -1)),
            'sex': 1.0 if raw_data.get('patient_sex') == 'male' else 0.0 if raw_data.get('patient_sex') == 'female' else -1.0,
            'bp_systolic': float(raw_data.get('bp_systolic', -1) or -1),
            'bp_diastolic': float(raw_data.get('bp_diastolic', -1) or -1),
            'spo2': float(raw_data.get('spo2', -1) or -1),
            'heart_rate': float(raw_data.get('heart_rate', -1) or -1),
            'temperature': float(raw_data.get('temperature', -1) or -1),
            'symptom_count': float(len([s for s in symptoms if s in [
                'chest_pain', 'breathlessness', 'altered_consciousness',
                'severe_bleeding', 'seizure', 'high_fever'
            ]])),
            'chest_pain': 1.0 if 'chest_pain' in symptoms else 0.0,
            'breathlessness': 1.0 if 'breathlessness' in symptoms else 0.0,
            'altered_consciousness': 1.0 if 'altered_consciousness' in symptoms else 0.0,
            'severe_bleeding': 1.0 if 'severe_bleeding' in symptoms else 0.0,
            'seizure': 1.0 if 'seizure' in symptoms else 0.0,
            'high_fever': 1.0 if 'high_fever' in symptoms else 0.0,
        }

    def _engineer_vital_features(self, raw_data: Dict[str, Any]) -> Dict[str, float]:
        """Engineer vital sign-derived features"""
        bp_sys = raw_data.get('bp_systolic') or 120
        bp_dia = raw_data.get('bp_diastolic') or 80
        hr = raw_data.get('heart_rate') or 75
        spo2 = raw_data.get('spo2') or 97
        temp = raw_data.get('temperature') or 37.0
        age = raw_data.get('patient_age') or 40

        # Calculate derived metrics
        pulse_pressure = bp_sys - bp_dia if bp_sys > 0 and bp_dia > 0 else 40
        map_pressure = (bp_sys + 2 * bp_dia) / 3 if bp_sys > 0 and bp_dia > 0 else 93
        shock_index = hr / bp_sys if bp_sys > 0 and hr > 0 else 0.6

        return {
            'pulse_pressure': float(pulse_pressure),
            'mean_arterial_pressure': float(map_pressure),
            'shock_index': float(shock_index),
            'spo2_age_ratio': float(spo2 / max(age, 1)) if spo2 > 0 and age > 0 else 2.4,
            'temp_deviation': float(abs(temp - 37.0)) if temp > 0 else 0.0,
            'cardiac_risk_score': self._calculate_cardiac_risk(raw_data),
            'respiratory_distress_score': self._calculate_resp_distress(raw_data),
            'hemodynamic_instability': self._calculate_hemodynamic_score(raw_data),
            'sepsis_risk_score': self._calculate_sepsis_risk(raw_data),
            'pediatric_adjustment': self._pediatric_vital_adjustment(raw_data),
            'geriatric_adjustment': self._geriatric_vital_adjustment(raw_data),
            'pregnancy_adjustment': self._pregnancy_adjustment(raw_data)
        }

    def _engineer_symptom_features(self, raw_data: Dict[str, Any]) -> Dict[str, float]:
        """Engineer symptom interaction features"""
        symptoms = raw_data.get('symptoms', [])
        bp_sys = raw_data.get('bp_systolic', 120)

        chest_pain = 1.0 if 'chest_pain' in symptoms else 0.0
        breathlessness = 1.0 if 'breathlessness' in symptoms else 0.0
        altered_consciousness = 1.0 if 'altered_consciousness' in symptoms else 0.0
        severe_bleeding = 1.0 if 'severe_bleeding' in symptoms else 0.0
        seizure = 1.0 if 'seizure' in symptoms else 0.0
        high_fever = 1.0 if 'high_fever' in symptoms else 0.0

        return {
            'cardiopulmonary_cluster': chest_pain * breathlessness,
            'neurological_cluster': altered_consciousness * seizure,
            'hemorrhagic_cluster': severe_bleeding * (1.0 if bp_sys < 90 else 0.0),
            'infectious_cluster': high_fever * len(symptoms),
            'symptom_severity_score': self._calculate_symptom_severity(symptoms),
            'symptom_duration_risk': self._map_duration_to_risk(raw_data.get('complaint_duration', '')),
            'chief_complaint_risk': self._map_complaint_to_risk(raw_data.get('chief_complaint', '')),
            'comorbidity_multiplier': self._calculate_comorbidity_risk(raw_data.get('known_conditions', ''))
        }

    def _engineer_age_specific_features(self, raw_data: Dict[str, Any]) -> Dict[str, float]:
        """Engineer age-specific clinical features"""
        age = raw_data.get('patient_age', 40)
        sex = raw_data.get('patient_sex', '')

        return {
            'pediatric_fever_risk': self._pediatric_fever_assessment(raw_data),
            'elderly_fall_risk': self._elderly_fall_assessment(raw_data),
            'adult_cardiac_risk': self._adult_cardiac_assessment(raw_data),
            'obstetric_emergency_risk': self._obstetric_assessment(raw_data),
            'trauma_severity_score': self._trauma_assessment(raw_data),
            'mental_health_crisis': self._mental_health_assessment(raw_data)
        }

    def _engineer_contextual_features(self, raw_data: Dict[str, Any]) -> Dict[str, float]:
        """Engineer contextual features"""
        return {
            'time_of_day_risk': self._time_based_risk(),
            'seasonal_risk': self._seasonal_disease_risk(),
            'geographic_risk': self._geographic_disease_risk(raw_data.get('location', '')),
            'epidemic_alert_level': 0.0,  # Placeholder for epidemic monitoring
            'healthcare_accessibility': self._healthcare_access_score(raw_data.get('location', ''))
        }

    # Helper methods for feature calculations
    def _calculate_cardiac_risk(self, raw_data: Dict[str, Any]) -> float:
        """Calculate cardiac risk score"""
        age = raw_data.get('patient_age', 40)
        bp_sys = raw_data.get('bp_systolic', 120)
        hr = raw_data.get('heart_rate', 75)
        symptoms = raw_data.get('symptoms', [])

        risk_score = 0.0

        # Age factor
        if age > 65:
            risk_score += 2.0
        elif age > 45:
            risk_score += 1.0

        # Vital signs
        if bp_sys > 160:
            risk_score += 2.0
        if hr > 100 or hr < 60:
            risk_score += 1.5

        # Symptoms
        if 'chest_pain' in symptoms:
            risk_score += 3.0
        if 'breathlessness' in symptoms:
            risk_score += 1.5

        return min(risk_score, 10.0)  # Cap at 10

    def _calculate_resp_distress(self, raw_data: Dict[str, Any]) -> float:
        """Calculate respiratory distress score"""
        spo2 = raw_data.get('spo2', 97)
        hr = raw_data.get('heart_rate', 75)
        symptoms = raw_data.get('symptoms', [])

        score = 0.0

        if spo2 < 90:
            score += 4.0
        elif spo2 < 94:
            score += 2.0

        if hr > 110:
            score += 1.5

        if 'breathlessness' in symptoms:
            score += 3.0

        return score

    def _calculate_hemodynamic_score(self, raw_data: Dict[str, Any]) -> float:
        """Calculate hemodynamic instability score"""
        bp_sys = raw_data.get('bp_systolic', 120)
        bp_dia = raw_data.get('bp_diastolic', 80)
        hr = raw_data.get('heart_rate', 75)

        score = 0.0

        if bp_sys < 90:
            score += 4.0
        elif bp_sys > 180:
            score += 2.0

        if hr > 130:
            score += 3.0
        elif hr < 50:
            score += 2.0

        # Shock index
        if bp_sys > 0:
            shock_index = hr / bp_sys
            if shock_index > 1.0:
                score += 3.0
            elif shock_index > 0.8:
                score += 1.5

        return score

    def _calculate_sepsis_risk(self, raw_data: Dict[str, Any]) -> float:
        """Calculate sepsis risk score (simplified qSOFA)"""
        temp = raw_data.get('temperature', 37.0)
        bp_sys = raw_data.get('bp_systolic', 120)
        hr = raw_data.get('heart_rate', 75)
        symptoms = raw_data.get('symptoms', [])

        score = 0.0

        # Temperature
        if temp > 38.0 or temp < 36.0:
            score += 1.0

        # Hypotension
        if bp_sys < 100:
            score += 2.0

        # Tachycardia
        if hr > 90:
            score += 1.0

        # Altered consciousness
        if 'altered_consciousness' in symptoms:
            score += 2.0

        # High fever symptom
        if 'high_fever' in symptoms:
            score += 1.5

        return score

    def _pediatric_vital_adjustment(self, raw_data: Dict[str, Any]) -> float:
        """Adjust vital sign interpretation for pediatric patients"""
        age = raw_data.get('patient_age', 40)
        if age >= 18:
            return 0.0

        hr = raw_data.get('heart_rate', 75)
        temp = raw_data.get('temperature', 37.0)

        adjustment = 0.0

        # Pediatric heart rate norms
        if age < 2:
            if hr > 160 or hr < 100:
                adjustment += 2.0
        elif age < 6:
            if hr > 140 or hr < 80:
                adjustment += 1.5
        elif age < 12:
            if hr > 120 or hr < 70:
                adjustment += 1.0

        # Pediatric fever is more concerning
        if temp > 38.5:
            adjustment += 2.0

        return adjustment

    def _geriatric_vital_adjustment(self, raw_data: Dict[str, Any]) -> float:
        """Adjust vital sign interpretation for geriatric patients"""
        age = raw_data.get('patient_age', 40)
        if age < 65:
            return 0.0

        bp_sys = raw_data.get('bp_systolic', 120)
        temp = raw_data.get('temperature', 37.0)

        adjustment = 0.0

        # Elderly often have blunted fever response
        if temp < 36.5:
            adjustment += 1.5

        # Elderly more susceptible to hypotension
        if bp_sys < 100:
            adjustment += 2.0

        # Age factor
        if age > 80:
            adjustment += 1.0

        return adjustment

    def _pregnancy_adjustment(self, raw_data: Dict[str, Any]) -> float:
        """Adjust for pregnancy-related physiological changes"""
        age = raw_data.get('patient_age', 40)
        sex = raw_data.get('patient_sex', '')
        conditions = raw_data.get('known_conditions', '').lower()
        complaint = raw_data.get('chief_complaint', '').lower()

        if sex != 'female' or age < 15 or age > 45:
            return 0.0

        adjustment = 0.0

        # Pregnancy indicators
        if any(term in conditions for term in ['pregnan', 'expecting']):
            adjustment += 1.0
        if any(term in complaint for term in self.obstetric_complaints):
            adjustment += 2.0

        return adjustment

    def _calculate_symptom_severity(self, symptoms: List[str]) -> float:
        """Calculate overall symptom severity score"""
        severity_weights = {
            'altered_consciousness': 4.0,
            'severe_bleeding': 4.0,
            'seizure': 4.0,
            'chest_pain': 3.0,
            'breathlessness': 3.0,
            'high_fever': 2.0
        }

        total_severity = sum(severity_weights.get(symptom, 1.0) for symptom in symptoms)
        return min(total_severity, 15.0)  # Cap at 15

    def _map_duration_to_risk(self, duration: str) -> float:
        """Map complaint duration to risk score"""
        duration_lower = duration.lower()

        if 'less than 1 hour' in duration_lower or '< 1 hour' in duration_lower:
            return 3.0  # Acute onset is concerning
        elif '1-6 hours' in duration_lower or '1–6 hours' in duration_lower:
            return 2.5
        elif '6-24 hours' in duration_lower or '6–24 hours' in duration_lower:
            return 2.0
        elif '1-3 days' in duration_lower or '1–3 days' in duration_lower:
            return 1.5
        elif 'more than 3 days' in duration_lower or '> 3 days' in duration_lower:
            return 1.0
        else:
            return 1.5  # Default

    def _map_complaint_to_risk(self, complaint: str) -> float:
        """Map chief complaint to risk score"""
        complaint_lower = complaint.lower()

        for high_risk in self.high_risk_complaints:
            if high_risk in complaint_lower:
                return 4.0

        for trauma in self.trauma_indicators:
            if trauma in complaint_lower:
                return 3.0

        return 1.0  # Default risk

    def _calculate_comorbidity_risk(self, conditions: str) -> float:
        """Calculate comorbidity risk multiplier"""
        if not conditions:
            return 1.0

        conditions_lower = conditions.lower()
        high_risk_conditions = [
            'diabetes', 'heart', 'cardiac', 'hypertension', 'kidney', 'renal',
            'copd', 'asthma', 'cancer', 'stroke', 'liver'
        ]

        risk_count = sum(1 for condition in high_risk_conditions if condition in conditions_lower)
        return min(1.0 + (risk_count * 0.5), 3.0)  # Cap at 3.0

    def _pediatric_fever_assessment(self, raw_data: Dict[str, Any]) -> float:
        """Assess fever risk in pediatric patients"""
        age = raw_data.get('patient_age', 40)
        temp = raw_data.get('temperature', 37.0)
        symptoms = raw_data.get('symptoms', [])

        if age >= 18:
            return 0.0

        score = 0.0

        # Age-specific fever thresholds
        if age < 0.25:  # < 3 months
            if temp > 38.0:
                score += 4.0
        elif age < 2:  # < 2 years
            if temp > 39.0:
                score += 3.0
        else:
            if temp > 40.0:
                score += 2.0

        if 'high_fever' in symptoms:
            score += 1.0

        return score

    def _elderly_fall_assessment(self, raw_data: Dict[str, Any]) -> float:
        """Assess fall risk in elderly patients"""
        age = raw_data.get('patient_age', 40)
        complaint = raw_data.get('chief_complaint', '').lower()

        if age < 65:
            return 0.0

        score = 0.0

        if age > 75:
            score += 1.0
        if age > 85:
            score += 2.0

        fall_keywords = ['fall', 'fell', 'slip', 'trip', 'dizzy', 'weakness']
        if any(keyword in complaint for keyword in fall_keywords):
            score += 3.0

        return score

    def _adult_cardiac_assessment(self, raw_data: Dict[str, Any]) -> float:
        """Assess cardiac risk in adults"""
        age = raw_data.get('patient_age', 40)
        if age < 18 or age > 65:
            return 0.0

        return self._calculate_cardiac_risk(raw_data) * 0.8  # Scaled for adults

    def _obstetric_assessment(self, raw_data: Dict[str, Any]) -> float:
        """Assess obstetric emergency risk"""
        age = raw_data.get('patient_age', 40)
        sex = raw_data.get('patient_sex', '')
        complaint = raw_data.get('chief_complaint', '').lower()

        if sex != 'female' or age < 15 or age > 45:
            return 0.0

        score = 0.0

        for obstetric_term in self.obstetric_complaints:
            if obstetric_term in complaint:
                score += 2.0
                break

        # Bleeding in reproductive age women
        if 'bleeding' in complaint:
            score += 1.5

        return score

    def _trauma_assessment(self, raw_data: Dict[str, Any]) -> float:
        """Assess trauma severity"""
        complaint = raw_data.get('chief_complaint', '').lower()
        bp_sys = raw_data.get('bp_systolic', 120)
        hr = raw_data.get('heart_rate', 75)

        score = 0.0

        for trauma_term in self.trauma_indicators:
            if trauma_term in complaint:
                score += 2.0
                break

        # Hemodynamic compromise
        if bp_sys < 90:
            score += 3.0
        if hr > 120:
            score += 2.0

        return score

    def _mental_health_assessment(self, raw_data: Dict[str, Any]) -> float:
        """Assess mental health crisis indicators"""
        complaint = raw_data.get('chief_complaint', '').lower()
        symptoms = raw_data.get('symptoms', [])

        score = 0.0

        mental_health_terms = [
            'suicid', 'depress', 'anxiety', 'panic', 'psycho', 'mental',
            'confused', 'agitat', 'violent'
        ]

        for term in mental_health_terms:
            if term in complaint:
                score += 2.0
                break

        if 'altered_consciousness' in symptoms:
            score += 1.0

        return score

    def _time_based_risk(self) -> float:
        """Calculate time-of-day risk factor"""
        hour = datetime.now().hour

        # Higher risk during off-hours when staffing is reduced
        if 22 <= hour or hour <= 6:
            return 1.5
        elif 18 <= hour <= 22:
            return 1.2
        else:
            return 1.0

    def _seasonal_disease_risk(self) -> float:
        """Calculate seasonal disease risk"""
        month = datetime.now().month

        # Winter months - respiratory infections
        if month in [12, 1, 2]:
            return 1.3
        # Summer months - heat-related illness, vector-borne diseases
        elif month in [6, 7, 8]:
            return 1.2
        else:
            return 1.0

    def _geographic_disease_risk(self, location: str) -> float:
        """Calculate geographic disease risk (placeholder)"""
        # This would integrate with epidemiological data
        # For now, return baseline risk
        return 1.0

    def _healthcare_access_score(self, location: str) -> float:
        """Score healthcare accessibility (lower score = less accessible)"""
        location_lower = location.lower()

        # Rural indicators
        rural_terms = ['village', 'rural', 'remote', 'tribal']
        if any(term in location_lower for term in rural_terms):
            return 0.5  # Lower accessibility

        # Urban indicators
        urban_terms = ['city', 'town', 'urban', 'metro']
        if any(term in location_lower for term in urban_terms):
            return 1.0  # Better accessibility

        return 0.7  # Default