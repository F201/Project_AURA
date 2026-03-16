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
  scale:  { set: vi.fn() },
  anchor: { set: vi.fn() },
  position: { set: vi.fn() },
  internalModel: {
    coreModel: { setParameterValueById: mockSetParameterValueById },
  },
}
const mockStage    = { addChild: vi.fn() }
const mockRenderer = { width: 400, height: 600 }
const mockApp = {
  stage:    mockStage,
  renderer: mockRenderer,
  destroy:  vi.fn(),
}

vi.mock('pixi.js', () => ({
  Application: vi.fn(() => mockApp),
}))

vi.mock('pixi-live2d-display', () => ({
  Live2DModel: {
    from: vi.fn(() => Promise.resolve(mockModel)),
  },
}))

// ── Helpers ────────────────────────────────────────────────────────────────

/** Mount the component and wait for the async model load to complete. */
async function mountAndLoad(props = {}) {
  const ref = createRef()
  const result = render(<AvatarRenderer ref={ref} {...props} />)
  await act(async () => {}) // flush the Live2DModel.from() promise
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

  // ── Expression file mapping ───────────────────────────────────────────────

  it('setExpression maps smile → SmileLock.exp3.json', async () => {
    const { ref } = await mountAndLoad()
    ref.current.setExpression(['smile'], 2.0)
    expect(mockExpression).toHaveBeenCalledWith('SmileLock.exp3.json')
  })

  it('setExpression maps sad → SadLock.exp3.json', async () => {
    const { ref } = await mountAndLoad()
    ref.current.setExpression(['sad'], 2.0)
    expect(mockExpression).toHaveBeenCalledWith('SadLock.exp3.json')
  })

  it('setExpression maps angry → Angry.exp3.json', async () => {
    const { ref } = await mountAndLoad()
    ref.current.setExpression(['angry'], 1.5)
    expect(mockExpression).toHaveBeenCalledWith('Angry.exp3.json')
  })

  it('setExpression maps ghost → Ghost.exp3.json', async () => {
    const { ref } = await mountAndLoad()
    ref.current.setExpression(['ghost'], 2.0)
    expect(mockExpression).toHaveBeenCalledWith('Ghost.exp3.json')
  })

  it('setExpression maps ghost_nervous → GhostChange.exp3.json', async () => {
    const { ref } = await mountAndLoad()
    ref.current.setExpression(['ghost_nervous'], 2.0)
    expect(mockExpression).toHaveBeenCalledWith('GhostChange.exp3.json')
  })

  it('setExpression maps shadow → Shadow.exp3.json', async () => {
    const { ref } = await mountAndLoad()
    ref.current.setExpression(['shadow'], 2.0)
    expect(mockExpression).toHaveBeenCalledWith('Shadow.exp3.json')
  })

  it('setExpression maps eyeshine_off → EyeshineOff.exp3.json', async () => {
    const { ref } = await mountAndLoad()
    ref.current.setExpression(['eyeshine_off'], 1.5)
    expect(mockExpression).toHaveBeenCalledWith('EyeshineOff.exp3.json')
  })

  it('setExpression maps pupil_shrink → PupilShrink.exp3.json', async () => {
    const { ref } = await mountAndLoad()
    ref.current.setExpression(['pupil_shrink'], 1.5)
    expect(mockExpression).toHaveBeenCalledWith('PupilShrink.exp3.json')
  })

  // ── Multi-expression ──────────────────────────────────────────────────────

  it('setExpression applies all tags in the list', async () => {
    const { ref } = await mountAndLoad()
    ref.current.setExpression(['smile', 'shadow'], 2.0)
    expect(mockExpression).toHaveBeenCalledWith('SmileLock.exp3.json')
    expect(mockExpression).toHaveBeenCalledWith('Shadow.exp3.json')
  })

  // ── Parameter-based expressions ───────────────────────────────────────────

  it('setExpression wink sets EyeOpenLeft=0, BrowLeftY=0, MouthSmile=1', async () => {
    const { ref } = await mountAndLoad()
    ref.current.setExpression(['wink'], 1.5)
    expect(mockSetParameterValueById).toHaveBeenCalledWith('EyeOpenLeft', 0.0)
    expect(mockSetParameterValueById).toHaveBeenCalledWith('BrowLeftY',   0.0)
    expect(mockSetParameterValueById).toHaveBeenCalledWith('MouthSmile',  1.0)
  })

  it('setExpression tongue sets MouthOpen=1, TongueOut=1, MouthSmile=0', async () => {
    const { ref } = await mountAndLoad()
    ref.current.setExpression(['tongue'], 1.5)
    expect(mockSetParameterValueById).toHaveBeenCalledWith('MouthOpen',  1.0)
    expect(mockSetParameterValueById).toHaveBeenCalledWith('TongueOut',  1.0)
    expect(mockSetParameterValueById).toHaveBeenCalledWith('MouthSmile', 0.0)
  })

  // ── Auto-reset ────────────────────────────────────────────────────────────

  it('setExpression schedules auto-reset after duration ms', async () => {
    vi.useFakeTimers()
    const { ref } = await mountAndLoad()
    ref.current.setExpression(['smile'], 2.0)
    mockExpression.mockClear()
    vi.advanceTimersByTime(2000)
    expect(mockExpression).toHaveBeenCalledWith()  // no-arg = reset to default
    vi.useRealTimers()
  })

  it('auto-reset fires after the correct delay', async () => {
    vi.useFakeTimers()
    const { ref } = await mountAndLoad()
    ref.current.setExpression(['angry'], 1.5)
    mockExpression.mockClear()
    vi.advanceTimersByTime(1499)
    expect(mockExpression).not.toHaveBeenCalled()
    vi.advanceTimersByTime(1)
    expect(mockExpression).toHaveBeenCalledWith()
    vi.useRealTimers()
  })

  // ── resetNeutral ──────────────────────────────────────────────────────────

  it('resetNeutral calls model.expression() with no arguments', async () => {
    const { ref } = await mountAndLoad()
    ref.current.resetNeutral()
    expect(mockExpression).toHaveBeenCalledWith()
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
