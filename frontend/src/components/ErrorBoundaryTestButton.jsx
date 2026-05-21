/**
 * Manual Test Component for Error Boundary
 * 
 * To test the Error Boundary:
 * 1. Temporarily import this component in App.jsx
 * 2. Add it inside AppInner or one of the panels
 * 3. Click the button to trigger an error
 * 4. Verify the error boundary catches it and shows fallback UI
 * 5. Remove this component after testing
 */

import { useState } from 'react'

function BuggyComponent({ shouldCrash }) {
  if (shouldCrash) {
    // This will throw an error and be caught by ErrorBoundary
    throw new Error('Intentional crash for testing ErrorBoundary')
  }
  return <div className="text-routine">Component is working fine!</div>
}

export default function ErrorBoundaryTestButton() {
  const [crash, setCrash] = useState(false)

  return (
    <div className="p-4 bg-card rounded-lg">
      <h3 className="text-text font-semibold mb-2">Error Boundary Test</h3>
      <p className="text-text2 text-sm mb-3">
        Click the button below to simulate a component crash and test the Error Boundary.
      </p>
      <button
        onClick={() => setCrash(true)}
        className="py-2 px-4 bg-emergency text-white rounded-lg hover:bg-emergency/90 transition-colors text-sm font-medium"
      >
        Trigger Error
      </button>
      <div className="mt-3">
        <BuggyComponent shouldCrash={crash} />
      </div>
    </div>
  )
}
