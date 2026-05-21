import React from 'react';
import { render, screen } from '@testing-library/react';
import OfflineBanner from '../OfflineBanner';

// Mock the getQueueCount function
jest.mock('../../lib/offlineQueue', () => ({
  getQueueCount: jest.fn().mockResolvedValue(0)
}));

// Mock navigator.onLine
Object.defineProperty(navigator, 'onLine', {
  writable: true,
  value: true
});

describe('OfflineBanner', () => {
  beforeEach(() => {
    // Reset all mocks before each test
    jest.clearAllMocks();
  });

  test('does not push content when online with no queue', async () => {
    // Mock online status and no queue items
    navigator.onLine = true;
    require('../../lib/offlineQueue').getQueueCount.mockResolvedValue(0);
    
    const { container } = render(<OfflineBanner />);
    
    // Should render nothing when online with no queue
    expect(container.firstChild).toBeNull();
  });

  test('does not push content when offline with queue', async () => {
    // Mock offline status with queue items
    navigator.onLine = false;
    require('../../lib/offlineQueue').getQueueCount.mockResolvedValue(5);
    
    const { container } = render(<OfflineBanner />);
    
    // Should render banner but not push content
    expect(container.firstChild).not.toBeNull();
    expect(container.firstChild).toHaveStyle({ position: 'fixed' });
  });

  test('uses fixed positioning to avoid content push', () => {
    navigator.onLine = false;
    require('../../lib/offlineQueue').getQueueCount.mockResolvedValue(3);
    
    const { container } = render(<OfflineBanner />);
    
    // Check that the banner uses fixed positioning
    expect(container.firstChild).toHaveClass('fixed');
  });
});