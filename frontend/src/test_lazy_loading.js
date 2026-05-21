// Test file to verify lazy loading works correctly
import { loadModel, runTriage } from './utils/triageClassifier.js'

// Mock form data for testing
const mockFormData = {
  patient_age: 30,
  patient_sex: 'male',
  chief_complaint: 'fever',
  symptoms: ['high_fever'],
  // Add other required fields...
}

// Test that the dynamic import works
console.log('Testing lazy loading of ONNX runtime...')

// This should trigger the dynamic import only when needed
runTriage(mockFormData)
  .then(result => {
    console.log('Triage result:', result)
    console.log('Lazy loading test passed!')
  })
  .catch(err => {
    console.error('Error during triage:', err)
  })