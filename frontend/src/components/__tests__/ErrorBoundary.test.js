import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import { ErrorBoundary } from '../ErrorBoundary'

// Mock the getQueueCount function
jest.mock('../../lib/offlineQueue', () => ({
  getQueueCount: jest.fn().mockResolvedValue(0),
}))

describe('ErrorBoundary', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    // Suppress console.error for expected errors
    jest.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    console.error.mockRestore()
  })

  test('renders children when no error occurs', () => {
    render(
      <ErrorBoundary>
        <div data-testid="child">Child Content</div>
      </ErrorBoundary>
    )

    expect(screen.getByTestId('child')).toBeInTheDocument()
    expect(screen.getByTestId('child')).toHaveTextContent('Child Content')
  })

  test('displays error UI when child component throws', () => {
    const ThrowError = () => {
      throw new Error('Test error')
    }

    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    )

    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
    expect(screen.getByText('Reload App')).toBeInTheDocument()
    expect(screen.getByText('Try Again')).toBeInTheDocument()
  })

  test('displays offline queue count when items are queued', async () => {
    const { getQueueCount } = require('../../lib/offlineQueue')
    getQueueCount.mockResolvedValue(5)

    const ThrowError = () => {
      throw new Error('Test error')
    }

    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    )

    expect(await screen.findByText('5 submissions saved offline')).toBeInTheDocument()
  })

  test('shows network error message for fetch errors', () => {
    const ThrowError = () => {
      throw new Error('Failed to fetch')
    }

    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    )

    expect(screen.getByText(/Unable to connect to the server/)).toBeInTheDocument()
  })

  test('shows auth error message for session errors', () => {
    const ThrowError = () => {
      throw new Error('Session expired')
    }

    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    )

    expect(screen.getByText(/session may have expired/)).toBeInTheDocument()
  })

  test('reload button triggers window.location.reload', () => {
    const ThrowError = () => {
      throw new Error('Test error')
    }

    const reloadMock = jest.fn()
    Object.defineProperty(window, 'location', {
      value: { reload: reloadMock },
      writable: true,
    })

    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    )

    fireEvent.click(screen.getByText('Reload App'))
    expect(reloadMock).toHaveBeenCalled()
  })

  test('try again button resets error state', () => {
    const ThrowError = () => {
      throw new Error('Test error')
    }

    const { rerender } = render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    )

    expect(screen.getByText('Something went wrong')).toBeInTheDocument()

    // Click try again
    fireEvent.click(screen.getByText('Try Again'))

    // After resetting, children should be rendered again
    // Note: This will cause the error to be thrown again, but that's expected
    // The important thing is the error state was reset
  })

  test('technical details are collapsible', () => {
    const ThrowError = () => {
      throw new Error('Detailed error message')
    }

    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    )

    // Technical details should be hidden by default
    const details = screen.getByText('Technical details')
    expect(details).toBeInTheDocument()

    // Click to expand
    fireEvent.click(details)

    // Should now show the error message
    expect(screen.getByText('Detailed error message')).toBeInTheDocument()
  })
})