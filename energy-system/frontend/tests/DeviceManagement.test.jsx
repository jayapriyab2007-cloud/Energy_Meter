import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import DeviceManagement from '../src/pages/DeviceManagement'

vi.mock('../src/api', () => ({
  api: vi.fn().mockImplementation((path) => {
    if (path.startsWith('/devices')) {
      return Promise.resolve([
        {
          id: 1,
          name: 'ESP32_Test_01',
          meter_id: 1,
          enabled: true,
          last_seen: Date.now() / 1000,
          online: true,
        },
      ])
    }
    if (path.startsWith('/meters')) {
      return Promise.resolve([
        { id: 1, meter_id: 'METER_A101', name: 'Meter A101', measurement_level: 'room' },
      ])
    }
    return Promise.resolve([])
  }),
}))

describe('DeviceManagement Component', () => {
  it('renders registered devices and online status', async () => {
    render(<DeviceManagement admin={true} />)
    expect(screen.getByText('IoT device management')).toBeInTheDocument()
    expect(await screen.findByText('ESP32_Test_01')).toBeInTheDocument()
    expect(screen.getByText('Online')).toBeInTheDocument()
  })
})

