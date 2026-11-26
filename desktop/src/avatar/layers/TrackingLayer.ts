import { ParameterBus } from '../ParameterBus'

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v))

/**
 * Tracking & Physical Interaction Layer:
 *  - 60fps Audio RMS lip-sync (ParamMouthOpenY)
 *  - Global desktop cursor tracking (eyes + gentle head & body follow)
 *  - Spring-damped drag sway physics when moved across the screen
 *  - Headpat reaction (happy closed eyes + smile + gentle lean)
 */
export class TrackingLayer {
  private _bus: ParameterBus
  private _lookTargetX = 0
  private _lookTargetY = 0
  private _lookX = 0
  private _lookY = 0

  private _swayPos = 0
  private _swayVel = 0
  private _headpatWeight = 0
  private _headpatActive = false

  constructor(bus: ParameterBus) {
    this._bus = bus
  }

  setCursorLook(nx: number, ny: number): void {
    this._lookTargetX = clamp(nx, -1, 1)
    this._lookTargetY = clamp(ny, -1, 1)
  }

  addDragImpulse(vx: number, _vy: number): void {
    this._swayVel += clamp(vx * 0.55, -24, 24)
  }

  setHeadpat(active: boolean): void {
    this._headpatActive = active
  }

  update(elapsed: number, mouthOpen: number): void {
    const dt = Math.min(elapsed, 0.08)

    // Lip-sync
    this._bus.write('ParamMouthOpenY', clamp(mouthOpen, 0, 1), 'tracking', 'Override')

    // Smooth cursor gaze & subtle head follow
    const gazeSpeed = 6.5
    this._lookX += (this._lookTargetX - this._lookX) * Math.min(1, dt * gazeSpeed)
    this._lookY += (this._lookTargetY - this._lookY) * Math.min(1, dt * gazeSpeed)

    this._bus.write('ParamEyeBallX', clamp(this._lookX * 0.9, -1, 1), 'tracking', 'Override')
    this._bus.write('ParamEyeBallY', clamp(this._lookY * 0.75, -1, 1), 'tracking', 'Override')
    this._bus.write('ParamAngleX', this._lookX * 14, 'tracking', 'Add')
    this._bus.write('ParamAngleY', this._lookY * 10, 'tracking', 'Add')
    this._bus.write('ParamBodyAngleX', this._lookX * 4.5, 'tracking', 'Add')

    // Damped spring physics while dragging the overlay
    const stiffness = 62
    const damping = 7.5
    const accel = -stiffness * this._swayPos - damping * this._swayVel
    this._swayVel += accel * dt
    this._swayPos = clamp(this._swayPos + this._swayVel * dt, -26, 26)

    if (Math.abs(this._swayPos) > 0.05) {
      this._bus.write('ParamAngleZ', -this._swayPos, 'interaction', 'Add')
      this._bus.write('ParamBodyAngleZ', -this._swayPos * 0.45, 'interaction', 'Add')
    }

    // Headpat smoothing
    const targetPat = this._headpatActive ? 1 : 0
    this._headpatWeight += (targetPat - this._headpatWeight) * Math.min(1, dt * 8)
    if (this._headpatWeight > 0.02) {
      const w = this._headpatWeight
      this._bus.write('ParamEyeLOpen', 1 - w, 'interaction', 'Multiply')
      this._bus.write('ParamEyeROpen', 1 - w, 'interaction', 'Multiply')
      this._bus.write('ParamEyeLSmile', w, 'interaction', 'Override')
      this._bus.write('ParamEyeRSmile', w, 'interaction', 'Override')
      this._bus.write('ParamMouthForm', 0.85 * w, 'interaction', 'Override')
      this._bus.write('ParamAngleY', -7 * w, 'interaction', 'Add')
      this._bus.write('ParamAngleZ', 6 * w, 'interaction', 'Add')
    }
  }
}
