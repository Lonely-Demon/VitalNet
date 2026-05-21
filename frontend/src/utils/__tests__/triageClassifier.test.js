import { runTriage } from '../triageClassifier'

const runMock = jest.fn()
const createTensorMock = jest.fn((_, data) => ({ data }))

jest.mock('onnxruntime-web', () => ({
  InferenceSession: {
    create: jest.fn(async () => ({
      run: runMock,
    })),
  },
  Tensor: jest.fn((type, data, dims) => ({ type, data, dims })),
  env: { wasm: { numThreads: 1 } },
}))

describe('triageClassifier', () => {
  beforeEach(() => {
    runMock.mockReset()
  })

  it('treats unknown labels as emergency review cases', async () => {
    runMock.mockResolvedValue({
      label: { data: [99] },
      probabilities: { data: [0.1, 0.2, 0.3] },
    })

    const result = await runTriage({
      patient_age: 42,
      patient_sex: 'male',
      symptoms: [],
      chief_complaint: 'Chest pain',
      complaint_duration: '1-6 hours',
      bp_systolic: 120,
      bp_diastolic: 80,
      spo2: 98,
      heart_rate: 78,
      temperature: 37.0,
      location: 'Village',
    })

    expect(result.triageLevel).toBe('EMERGENCY')
    expect(result.needsReview).toBe(true)
    expect(result.confidence).toBeNull()
  })
})
