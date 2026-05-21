export const MODEL_VERSION = '2.0.0'
export const FEATURE_SCHEMA_VERSION = 'v45-2026-03-30'
export const EXPECTED_ONNX_SHA256 = '3e26c57592b7312667fcaa8d01c7d46f7b350718ba2d6795de103d6a25530a68'
export const CONFIDENCE_FLOOR = 0.72
export const UNCERTAINTY_FLOOR = 0.1

export const SYMPTOM_NORMALIZATION_MAP = {
  'chest pain': 'chest_pain',
  'chest tightness': 'chest_pain',
  'difficulty breathing': 'breathlessness',
  breathlessness: 'breathlessness',
  'shortness of breath': 'breathlessness',
  'altered consciousness': 'altered_consciousness',
  'altered consciousness / confusion': 'altered_consciousness',
  confusion: 'altered_consciousness',
  'severe bleeding': 'severe_bleeding',
  'heavy bleeding': 'severe_bleeding',
  seizure: 'seizure',
  'high fever': 'high_fever',
  fever: 'high_fever',
  'severe abdominal pain': 'severe_abdominal_pain',
  'abdominal pain': 'severe_abdominal_pain',
  'persistent vomiting': 'persistent_vomiting',
  vomiting: 'persistent_vomiting',
  'weakness on one side': 'weakness_one_side',
  'weakness one side': 'weakness_one_side',
  'difficulty speaking': 'difficulty_speaking',
  'slurred speech': 'difficulty_speaking',
  'swelling of face throat': 'swelling_face_throat',
  'swelling face throat': 'swelling_face_throat',
  anaphylaxis: 'anaphylaxis',
  stroke: 'stroke',
  'acute abdomen': 'acute_abdomen',
}

export const RED_FLAG_RULES = {
  stroke_syndrome: {
    symptoms: ['weakness_one_side', 'difficulty_speaking', 'altered_consciousness'],
    complaintTerms: ['stroke', 'slurred speech', 'facial droop', 'one sided weakness'],
  },
  anaphylaxis: {
    symptoms: ['swelling_face_throat', 'breathlessness'],
    complaintTerms: ['anaphylaxis', 'allergic reaction', 'throat swelling', 'hives'],
  },
  acute_abdomen: {
    symptoms: ['severe_abdominal_pain', 'persistent_vomiting'],
    complaintTerms: ['acute abdomen', 'severe abdominal pain', 'rigid abdomen'],
  },
}
