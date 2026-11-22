import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ParameterBus } from '../avatar/ParameterBus'
import { ExpressionLayer } from '../avatar/layers/ExpressionLayer'
import { PHYSICS_OUTPUT_PARAMS } from '../avatar/PhysicsOutputParams'

describe('ParameterBus & ExpressionLayer', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('blocks writes to physics output parameters', () => {
    const bus = new ParameterBus(PHYSICS_OUTPUT_PARAMS)
    const setParameterValueById = vi.fn()
    bus.write('ParamAngleX2', 10, 'idle', 'Override')
    bus.write('ParamMouthForm', 0.8, 'expression', 'Override')
    bus.flush({ setParameterValueById })

    expect(setParameterValueById).not.toHaveBeenCalledWith('ParamAngleX2', expect.anything())
    expect(setParameterValueById).toHaveBeenCalledWith('ParamMouthForm', 0.8)
  })

  it('resolves priority order (expression overrides idle)', () => {
    const bus = new ParameterBus(new Set())
    const setParameterValueById = vi.fn()
    bus.write('ParamMouthForm', 0.2, 'idle', 'Override')
    bus.write('ParamMouthForm', -0.85, 'expression', 'Override')
    bus.flush({ setParameterValueById })

    expect(setParameterValueById).toHaveBeenCalledWith('ParamMouthForm', -0.85)
  })

  it('applies built-in inline descriptors (Ghost, Angry, tongue) without network fetch', async () => {
    const bus = new ParameterBus(new Set())
    const layer = new ExpressionLayer(bus, {})
    const setParameterValueById = vi.fn()

    await layer.setExpression(['Ghost', 'tongue'], 4.0)
    layer.update(1.0) // completes fade-in
    bus.flush({ setParameterValueById })

    expect(setParameterValueById).toHaveBeenCalledWith('Param80', 1.0)
    expect(setParameterValueById).toHaveBeenCalledWith('Param70', 1.0)
  })

  it('resets toggleable expression params to 0 when cleared', async () => {
    const bus = new ParameterBus(new Set())
    const layer = new ExpressionLayer(bus, {})
    const setParameterValueById = vi.fn()

    await layer.setExpression(['EyeshineOff', 'Shadow'], 3.0)
    layer.update(1.0)
    bus.flush({ setParameterValueById })
    expect(setParameterValueById).toHaveBeenCalledWith('Param3', 1.0)
    expect(setParameterValueById).toHaveBeenCalledWith('Param2', 1.0)

    setParameterValueById.mockClear()
    layer.clear()
    layer.update(0.016)
    bus.flush({ setParameterValueById })
    expect(setParameterValueById).toHaveBeenCalledWith('Param3', 0)
    expect(setParameterValueById).toHaveBeenCalledWith('Param2', 0)
  })
})
