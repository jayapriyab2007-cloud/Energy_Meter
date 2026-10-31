import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import MeterManagement from '../src/pages/MeterManagement'

vi.mock('../src/api', () => ({
  api: vi.fn().mockImplementation((path) => {
    if (path.startsWith('/meters')) {
      return Promise.resolve([
        {
          id: 1,
          meter_id: 'METER_A101',
          name: 'Meter Room A101',
          measurement_level: 'room',
          block: 'A',
          floor: 1,
          room_id: 1,
          data_source: 'simulated',
          enabled: true,
        },
      ])
    }
    return Promise.resolve([])
  }),
}))

describe('MeterManagement Component', () => {
  it('renders meter list table heading and data', async () => {
    render(<MeterManagement admin={true} />)
    expect(screen.getByText('Meter management')).toBeInTheDocument()
    expect(await screen.findByText('METER_A101')).toBeInTheDocument()
    expect(screen.getByText('Register new meter')).toBeInTheDocument()
  })
})

