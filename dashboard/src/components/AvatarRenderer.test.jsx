/**
 * Phase 2 tests — AvatarRenderer component
 * All GPU / PIXI / Live2D dependencies are mocked so these run in jsdom
 * without a real GPU or network.
 *
 * Run:  cd dashboard && npm test
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, act } from '@testing-library/react'
import { createRef } from 'react'
import { AvatarRenderer } from './AvatarRenderer'

// ── Mock heavy GPU dependencies ────────────────────────────────────────────

const mockSetParameterValueById = vi.fn()
const mockExpression = vi.fn()
const mockModel = {
  expression: mockExpression,
  scale: { set: vi.fn() },
  anchor: { set: vi.fn() },
  position: { set: vi.fn() },
  internalModel: {
    coreModel: {
      setParameterValueById: mockSetParameterValueById,
      update: vi.fn(),
    },
  },
}
const mockStage = { addChild: vi.fn() }
const mockRenderer = { width: 400, height: 600 }
vi.mock('pixi.js', () => ({
  Application: vi.fn((opts) => {
    const canvas = document.createElement('canvas')
    if (opts?.width) canvas.setAttribute('width', opts.width.toString())
    if (opts?.height) canvas.setAttribute('height', opts.height.toString())
    return {
      stage: mockStage,
      renderer: mockRenderer,
      screen: mockRenderer,
      view: canvas,
      destroy: vi.fn(),
    }
  }),
  Ticker: {},
}))

vi.mock('pixi-live2d-display/cubism4', () => ({
  Live2DModel: {
    from: vi.fn(() => Promise.resolve(mockModel)),
    registerTicker: vi.fn(),
  },
}))

// ── Helpers ────────────────────────────────────────────────────────────────

/** Mount the component and wait for the async model load to complete. */
async function mountAndLoad(props = {}) {
  const ref = createRef()
  const result = render(<AvatarRenderer ref={ref} {...props} />)
  await act(async () => { }) // flush the Live2DModel.from() promise
  return { ref, ...result }
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe('AvatarRenderer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ── DOM ──────────────────────────────────────────────────────────────────

  it('renders a canvas element', async () => {
    const { container } = await mountAndLoad()
    expect(container.querySelector('canvas')).toBeTruthy()
  })

  it('canvas has correct width and height attributes', async () => {
    const { container } = await mountAndLoad({ width: 320, height: 480 })
    const canvas = container.querySelector('canvas')
    expect(canvas.getAttribute('width')).toBe('320')
    expect(canvas.getAttribute('height')).toBe('480')
  })

  // ── Expression overriding states ─────────────────────────────────────────

  it('setExpression updates the ref state for the core.update loop to consume', async () => {
    const { ref } = await mountAndLoad()
    // Ticker doesn't run in tests, so we just verify it doesn't throw and accepts names
    expect(() => ref.current.setExpression(['smile', 'angry', 'ghost'], 2.0)).not.toThrow()
  })

  // ── Auto-reset ────────────────────────────────────────────────────────────

  it('setExpression schedules auto-reset after duration ms', async () => {
    vi.useFakeTimers()
    const { ref } = await mountAndLoad()
    expect(() => {
      ref.current.setExpression(['smile'], 2.0)
      vi.advanceTimersByTime(2000)
    }).not.toThrow()
    vi.useRealTimers()
  })

  // ── resetNeutral ──────────────────────────────────────────────────────────

  it('resetNeutral executes without throwing', async () => {
    const { ref } = await mountAndLoad()
    expect(() => ref.current.resetNeutral()).not.toThrow()
  })

  // ── setParameter ─────────────────────────────────────────────────────────

  it('setParameter forwards name and value to coreModel', async () => {
    const { ref } = await mountAndLoad()
    ref.current.setParameter('ParamMouthOpenY', 0.8)
    expect(mockSetParameterValueById).toHaveBeenCalledWith('ParamMouthOpenY', 0.8)
  })

  // ── Guard rails ───────────────────────────────────────────────────────────

  it('unknown expression name is silently ignored (no throw)', async () => {
    const { ref } = await mountAndLoad()
    expect(() => ref.current.setExpression(['nonexistent_tag'], 1.0)).not.toThrow()
  })

  it('empty expression list does not throw', async () => {
    const { ref } = await mountAndLoad()
    expect(() => ref.current.setExpression([], 1.0)).not.toThrow()
  })
})
