import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ParameterBus } from './ParameterBus'
import { PHYSICS_OUTPUT_PARAMS } from './PhysicsOutputParams'

describe('ParameterBus', () => {
  let bus
  let core

  beforeEach(() => {
    bus  = new ParameterBus(PHYSICS_OUTPUT_PARAMS)
    core = { setParameterValueById: vi.fn() }
  })

  // ── Priority resolution ────────────────────────────────────────────────────

  it('P4 expression write wins over P1 idle write for same param', () => {
    bus.write('ParamMouthForm', 0.5,  'idle')
    bus.write('ParamMouthForm', 1.0,  'expression', 'Override')
    bus.flush(core)
    expect(core.setParameterValueById).toHaveBeenCalledWith('ParamMouthForm', 1.0)
  })

  it('P2 tracking write wins over P1 idle write', () => {
    bus.write('ParamMouthOpenY', 0.3, 'idle')
    bus.write('ParamMouthOpenY', 0.8, 'tracking', 'Override')
    bus.flush(core)
    expect(core.setParameterValueById).toHaveBeenCalledWith('ParamMouthOpenY', 0.8)
  })

  // ── Blend modes ───────────────────────────────────────────────────────────

  it('Override blend replaces lower-priority value', () => {
    bus.write('ParamBrowLForm', 0.3,  'idle')
    bus.write('ParamBrowLForm', -1.0, 'expression', 'Override')
    bus.flush(core)
    expect(core.setParameterValueById).toHaveBeenCalledWith('ParamBrowLForm', -1.0)
  })

  it('Add blend adds expression value to lower-priority value', () => {
    bus.write('ParamBrowLForm', 0.3, 'idle')
    bus.write('ParamBrowLForm', 0.5, 'expression', 'Add')
    bus.flush(core)
    expect(core.setParameterValueById).toHaveBeenCalledWith('ParamBrowLForm', expect.closeTo(0.8, 5))
  })

  it('Multiply blend multiplies lower-priority value by expression value', () => {
    bus.write('ParamEyeLSmile', 0.6, 'idle')
    bus.write('ParamEyeLSmile', 0.5, 'expression', 'Multiply')
    bus.flush(core)
    expect(core.setParameterValueById).toHaveBeenCalledWith('ParamEyeLSmile', expect.closeTo(0.3, 5))
  })

  // ── Blocklist ─────────────────────────────────────────────────────────────

  it('write to a physics output param is silently dropped', () => {
    bus.write('Param76', 0.5, 'idle')   // Ghost X — in PHYSICS_OUTPUT_PARAMS
    bus.flush(core)
    expect(core.setParameterValueById).not.toHaveBeenCalledWith('Param76', expect.anything())
  })

  it('blocklist does not affect non-physics params', () => {
    bus.write('ParamBreath', 0.7, 'idle')
    bus.flush(core)
    expect(core.setParameterValueById).toHaveBeenCalledWith('ParamBreath', 0.7)
  })

  it('Param37 (Brows Raise) is in the blocklist', () => {
    bus.write('Param37', 1.0, 'idle')
    bus.flush(core)
    expect(core.setParameterValueById).not.toHaveBeenCalledWith('Param37', expect.anything())
  })

  // ── clearProvider ─────────────────────────────────────────────────────────

  it('clearProvider removes all writes for that provider; next flush uses lower-priority value', () => {
    bus.write('ParamMouthForm', 0.3, 'idle')
    bus.write('ParamMouthForm', 1.0, 'expression', 'Override')
    bus.clearProvider('expression')
    bus.flush(core)
    expect(core.setParameterValueById).toHaveBeenCalledWith('ParamMouthForm', 0.3)
  })

  it('clearProvider on a provider with no writes does not throw', () => {
    expect(() => bus.clearProvider('expression')).not.toThrow()
  })

  // ── Multiple params ───────────────────────────────────────────────────────

  it('each param is resolved independently', () => {
    bus.write('ParamAngleX', 5.0,  'idle')
    bus.write('ParamBreath',  0.8,  'idle')
    bus.write('ParamAngleX', 10.0, 'expression', 'Override')
    bus.flush(core)
    expect(core.setParameterValueById).toHaveBeenCalledWith('ParamAngleX', 10.0)
    expect(core.setParameterValueById).toHaveBeenCalledWith('ParamBreath',  0.8)
  })

  // ── flush clears state ────────────────────────────────────────────────────

  it('flush clears writes so the next frame starts clean', () => {
    bus.write('ParamBreath', 0.5, 'idle')
    bus.flush(core)
    core.setParameterValueById.mockClear()
    bus.flush(core)
    expect(core.setParameterValueById).not.toHaveBeenCalled()
  })

  it('calling flush with no writes does not throw', () => {
    expect(() => bus.flush(core)).not.toThrow()
  })
})
