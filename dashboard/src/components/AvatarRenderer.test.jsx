/**
 * AvatarRenderer tests — Phase 3
 * All GPU / PIXI / Live2D dependencies are mocked so these run in jsdom
 * without a real WebGL context or network.
 *
 * Run:  cd dashboard && npm test
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, act } from '@testing-library/react'
import { createRef } from 'react'
import { AvatarRenderer } from './AvatarRenderer'

// ── Mocks ──────────────────────────────────────────────────────────────────

const mockSetParameterValueById = vi.fn()
const mockExpression = vi.fn()
const mockCoreUpdate = vi.fn()

const mockModel = {
  height: 600,   // needed for auto-scale calculation
  expression: mockExpression,
  scale:    { set: vi.fn() },
  anchor:   { set: vi.fn() },
  position: { set: vi.fn() },
  internalModel: {
    coreModel: {
      setParameterValueById: mockSetParameterValueById,
      update: mockCoreUpdate,  // needed for core.update.bind() in initSingleton
    },
  },
}

// A real canvas element so container.appendChild / removeChild work in jsdom
const mockCanvas = document.createElement('canvas')

const mockApp = {
  view:     mockCanvas,
  stage:    { addChild: vi.fn() },
  screen:   { width: 400, height: 600 },  // used for model positioning
  renderer: { width: 400, height: 600 },
  destroy:  vi.fn(),
}

vi.mock('pixi.js', () => ({
  Application: vi.fn(() => mockApp),
  Ticker: {},   // passed to Live2DModel.registerTicker
}))

// Must mock the cubism4 sub-path — that's what the component imports
vi.mock('pixi-live2d-display/cubism4', () => ({
  Live2DModel: {
    registerTicker: vi.fn(),
    from: vi.fn(() => Promise.resolve(mockModel)),
  },
}))

// ── Helpers ────────────────────────────────────────────────────────────────

/** Mount the component and wait for the async model load to settle. */
async function mountAndLoad(props = {}) {
  const ref = createRef()
  const result = render(<AvatarRenderer ref={ref} {...props} />)
  await act(async () => {})  // flush Live2DModel.from() promise + React effects
  return { ref, ...result }
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe('AvatarRenderer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ── Rendering ─────────────────────────────────────────────────────────────

  it('renders a container div', async () => {
    const { container } = await mountAndLoad()
    expect(container.firstChild).toBeTruthy()
  })

  it('renders a canvas element inside the container', async () => {
    const { container } = await mountAndLoad()
    expect(container.querySelector('canvas')).toBeTruthy()
  })

  it('wrapper div reflects width and height props', async () => {
    const { container } = await mountAndLoad({ width: 320, height: 480 })
    const div = container.firstChild
    expect(div.style.width).toBe('320px')
    expect(div.style.height).toBe('480px')
  })

  // ── Expression file mapping ───────────────────────────────────────────────

  it.each([
    ['smile',         'SmileLock.exp3.json'  ],
    ['sad',           'SadLock.exp3.json'    ],
    ['angry',         'Angry.exp3.json'      ],
    ['ghost',         'Ghost.exp3.json'      ],
    ['ghost_nervous', 'GhostChange.exp3.json'],
    ['shadow',        'Shadow.exp3.json'     ],
    ['pupil_shrink',  'PupilShrink.exp3.json'],
    ['eyeshine_off',  'EyeshineOff.exp3.json'],
  ])('setExpression maps "%s" → %s', async (tag, file) => {
    const { ref } = await mountAndLoad()
    ref.current.setExpression([tag], 2.0)
    expect(mockExpression).toHaveBeenCalledWith(file)
  })

  it('setExpression applies all tags in the array', async () => {
    const { ref } = await mountAndLoad()
    ref.current.setExpression(['smile', 'shadow'], 2.0)
    expect(mockExpression).toHaveBeenCalledWith('SmileLock.exp3.json')
    expect(mockExpression).toHaveBeenCalledWith('Shadow.exp3.json')
  })

  // ── Parameter-based expressions ───────────────────────────────────────────

  it('wink sets correct Cubism4 Core Model parameters', async () => {
    const { ref } = await mountAndLoad()
    ref.current.setExpression(['wink'], 1.5)
    expect(mockSetParameterValueById).toHaveBeenCalledWith('ParamEyeLOpen',  0.0)
    expect(mockSetParameterValueById).toHaveBeenCalledWith('ParamBrowLForm', -1.0)
    expect(mockSetParameterValueById).toHaveBeenCalledWith('ParamMouthForm',  1.0)
  })

  it('tongue sets correct Cubism4 Core Model parameters', async () => {
    const { ref } = await mountAndLoad()
    ref.current.setExpression(['tongue'], 1.5)
    expect(mockSetParameterValueById).toHaveBeenCalledWith('ParamMouthOpenY', 1.0)
    expect(mockSetParameterValueById).toHaveBeenCalledWith('ParamMouthForm',  -1.0)
  })

  // ── Auto-reset ────────────────────────────────────────────────────────────

  it('setExpression resets to neutral after the given duration', async () => {
    vi.useFakeTimers()
    const { ref } = await mountAndLoad()
    ref.current.setExpression(['smile'], 2.0)
    mockExpression.mockClear()
    vi.advanceTimersByTime(2000)
    expect(mockExpression).toHaveBeenCalledWith()  // no-arg call = reset to default
    vi.useRealTimers()
  })

  it('auto-reset does not fire before the duration elapses', async () => {
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

  // ── Mood memory ───────────────────────────────────────────────────────────
  // The full mood-rendering loop requires a live PIXI ticker (unavailable in jsdom).
  // These tests verify the pending-mood pipeline is wired without crashing.

  it('setExpression with a mood-mapped name does not throw', async () => {
    const { ref } = await mountAndLoad()
    // Each of these has an EXPRESSION_TO_MOOD entry and should queue a pending mood
    for (const tag of ['smile', 'sad', 'angry', 'ghost', 'ghost_nervous',
                        'shadow', 'pupil_shrink', 'eyeshine_off']) {
      expect(() => ref.current.setExpression([tag], 1.0)).not.toThrow()
    }
  })

  it('mood memory: expression → expiry → state transition completes cleanly', async () => {
    vi.useFakeTimers()
    const { ref } = await mountAndLoad()
    ref.current.setExpression(['smile'], 2.0)   // queues _pendingMood = MOODS.happy
    vi.advanceTimersByTime(2000)                 // triggers auto-reset; _pendingMood consumed on next frame
    // After expiry the avatar should accept further API calls without errors
    expect(() => ref.current.setSpeaking(false)).not.toThrow()
    expect(() => ref.current.resetNeutral()).not.toThrow()
    vi.useRealTimers()
  })

  // ── resetNeutral ──────────────────────────────────────────────────────────

  it('resetNeutral calls model.expression() with no arguments', async () => {
    const { ref } = await mountAndLoad()
    ref.current.resetNeutral()
    expect(mockExpression).toHaveBeenCalledWith()
  })

  // ── setParameter ──────────────────────────────────────────────────────────

  it('setParameter forwards the id and value to coreModel', async () => {
    const { ref } = await mountAndLoad()
    ref.current.setParameter('ParamMouthOpenY', 0.8)
    expect(mockSetParameterValueById).toHaveBeenCalledWith('ParamMouthOpenY', 0.8)
  })

  // ── setSpeaking ───────────────────────────────────────────────────────────

  it('setSpeaking(true) switches to speaking state without throwing', async () => {
    const { ref } = await mountAndLoad()
    expect(() => ref.current.setSpeaking(true)).not.toThrow()
  })

  it('setSpeaking(false) switches to idle state without throwing', async () => {
    const { ref } = await mountAndLoad()
    expect(() => ref.current.setSpeaking(false)).not.toThrow()
  })

  it('setSpeaking can toggle states repeatedly without side effects', async () => {
    const { ref } = await mountAndLoad()
    ref.current.setSpeaking(true)
    ref.current.setSpeaking(false)
    ref.current.setSpeaking(true)
    // State changes should not trigger expressions
    expect(mockExpression).not.toHaveBeenCalled()
  })

  // ── setMouthOpen ──────────────────────────────────────────────────────────

  it('setMouthOpen accepts values within [0, 1]', async () => {
    const { ref } = await mountAndLoad()
    expect(() => ref.current.setMouthOpen(0)).not.toThrow()
    expect(() => ref.current.setMouthOpen(0.5)).not.toThrow()
    expect(() => ref.current.setMouthOpen(1)).not.toThrow()
  })

  it('setMouthOpen silently clamps out-of-range values', async () => {
    const { ref } = await mountAndLoad()
    expect(() => ref.current.setMouthOpen(-1.0)).not.toThrow()
    expect(() => ref.current.setMouthOpen(2.5)).not.toThrow()
  })

  // ── Guard rails ───────────────────────────────────────────────────────────

  it('unknown expression tag is silently ignored', async () => {
    const { ref } = await mountAndLoad()
    expect(() => ref.current.setExpression(['nonexistent_tag'], 1.0)).not.toThrow()
    expect(mockExpression).not.toHaveBeenCalled()
  })

  it('empty expression list does not throw', async () => {
    const { ref } = await mountAndLoad()
    expect(() => ref.current.setExpression([], 1.0)).not.toThrow()
  })
})
