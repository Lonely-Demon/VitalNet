import { memo } from 'react'
import IntakeForm from '../pages/IntakeForm'

// Create a memoized version of IntakeForm to prevent unnecessary re-renders
const MemoizedIntakeForm = memo(IntakeForm, () => true)

export default MemoizedIntakeForm