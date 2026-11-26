import { ParameterBus } from '../ParameterBus'

const MOODS = {
  neutral: { mouthForm: 0, browForm: 0, browRaise: 0, eyeSmile: 0 },
  happy: { mouthForm: 0.65, browForm: 0.3, browRaise: 0.45, eyeSmile: 0.55 },
  curious: { mouthForm: 0.2, browForm: -0.1, browRaise: 0.5, eyeSmile: 0 },
  playful: { mouthForm: 0.9, browForm: 0.5, browRaise: 0.7, eyeSmile: 0.3 },
  sleepy: { mouthForm: -0.05, browForm: 0.1, browRaise: -0.15, eyeSmile: 0 },
  thinking: { mouthForm: 0.1, browForm: -0.2, browRaise: 0.35, eyeSmile: 0 },
}

type MoodKey = keyof typeof MOODS

const MOOD_POOLS: Record<'idle' | 'speaking', Array<[MoodKey, number]>> = {
  idle: [
    ['neutral', 0.15],
    ['happy', 0.38],
    ['curious', 0.2],
    ['playful', 0.15],
    ['sleepy', 0.06],
    ['thinking', 0.06],
  ],
  speaking: [
    ['neutral', 0.1],
    ['happy', 0.45],
    ['curious', 0.2],
    ['playful', 0.2],
    ['thinking', 0.05],
  ],
}

function pickWeightedMood(state: 'idle' | 'speaking') {
  const pool = MOOD_POOLS[state]
  const r = Math.random()
  let acc = 0
  for (const [key, w] of pool) {
    acc += w
    if (r < acc) return MOODS[key]
  }
  return MOODS.happy
}

function expDecay(current: number, target: number, halfLife: number, dt: number): number {
  return target + (current - target) * Math.pow(0.5, dt / halfLife)
}

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v))

export class IdleLayer {
  private _bus: ParameterBus
  private _blinkTimer = 0
  private _blinkPhase = 0
  private _nextBlink = 2 + Math.random() * 3
  private _dblBlinkPending = false
  private _dblBlinkTimer = 0
  private _nextDblBlink = 10 + Math.random() * 10

  private _moodTimer = 0
  private _nextMoodChange = 3 + Math.random() * 4
  private _currentMood = MOODS.happy
  private _mouthFormC = 0.4
  private _browFormC = 0.2
  private _browRaiseC = 0.2
  private _eyeSmileC = 0.3

  private _tiltTimer = 0
  private _nextTilt = 6 + Math.random() * 8
  private _tiltTarget = 0
  private _tiltC = 0
  private _tiltHolding = false
  private _tiltHoldTimer = 0
  private _tiltHoldDuration = 0
  private _nodPhase = 0

  constructor(bus: ParameterBus) {
    this._bus = bus
  }

  update(elapsed: number, speaking: boolean): void {
    const bus = this._bus
    const now = performance.now() / 1000
    const halfLife = speaking ? 0.2 : 0.28

    // Breathing
    bus.write('ParamBreath', Math.sin(now * (speaking ? 1.15 : 0.75)) * 0.5 + 0.5, 'idle')

    // Organic idle head & body sway
    const swayAmt = speaking ? 0.35 : 0.9
    const bX = (Math.sin(now * 0.31) * 8 + Math.sin(now * 0.73) * 2.5) * swayAmt
    const bY = (Math.sin(now * 0.19) * 4 + Math.sin(now * 0.47) * 1.8) * swayAmt
    const bZ = (Math.sin(now * 0.13) * 4.5 + Math.sin(now * 0.41) * 1.8) * swayAmt

    let nodY = 0
    if (speaking) {
      this._nodPhase += elapsed * 2.8
      nodY = Math.sin(this._nodPhase) * 3.8
    } else {
      this._nodPhase = 0
    }

    if (!speaking) {
      this._tiltTimer += elapsed
      if (!this._tiltHolding && this._tiltTimer >= this._nextTilt) {
        this._tiltTarget = (Math.random() < 0.5 ? 1 : -1) * (6 + Math.random() * 6)
        this._tiltTimer = 0
        this._nextTilt = 6 + Math.random() * 8
        this._tiltHolding = true
        this._tiltHoldTimer = 0
        this._tiltHoldDuration = 0.9 + Math.random() * 0.8
      }
    }
    if (this._tiltHolding) {
      this._tiltHoldTimer += elapsed
      if (this._tiltHoldTimer >= this._tiltHoldDuration) {
        this._tiltTarget = 0
        this._tiltHolding = false
      }
    }
    this._tiltC += (this._tiltTarget - this._tiltC) * elapsed * (this._tiltTarget !== 0 ? 5.5 : 2.2)

    bus.write('ParamAngleX', bX, 'idle')
    bus.write('ParamAngleY', bY + nodY, 'idle')
    bus.write('ParamAngleZ', bZ + this._tiltC, 'idle')
    bus.write('ParamBodyAngleX', Math.sin(now * 0.28) * 3.5 * swayAmt, 'idle')
    bus.write('ParamBodyAngleZ', Math.sin(now * 0.21) * 2.8 * swayAmt, 'idle')

    // Mood interpolation
    this._moodTimer += elapsed
    if (this._moodTimer >= this._nextMoodChange) {
      this._moodTimer = 0
      this._nextMoodChange = speaking ? 2 + Math.random() * 2.5 : 3.5 + Math.random() * 5
      this._currentMood = pickWeightedMood(speaking ? 'speaking' : 'idle')
    }

    this._mouthFormC = expDecay(this._mouthFormC, this._currentMood.mouthForm, halfLife, elapsed)
    this._browFormC = expDecay(this._browFormC, this._currentMood.browForm, halfLife, elapsed)
    this._browRaiseC = expDecay(this._browRaiseC, this._currentMood.browRaise, halfLife, elapsed)
    this._eyeSmileC = expDecay(this._eyeSmileC, this._currentMood.eyeSmile, halfLife, elapsed)

    const mfBoost = speaking ? 0.2 : 0
    const browTotal = clamp(this._browFormC + this._browRaiseC, -1, 1)
    bus.write('ParamMouthForm', clamp(this._mouthFormC + mfBoost, -1, 1), 'idle')
    bus.write('ParamBrowLForm', browTotal, 'idle')
    bus.write('ParamBrowRForm', browTotal, 'idle')
    bus.write('ParamEyeLSmile', this._eyeSmileC, 'idle')
    bus.write('ParamEyeRSmile', this._eyeSmileC, 'idle')

    // Double-blink & blink state machine
    if (!speaking) {
      this._dblBlinkTimer += elapsed
      if (this._dblBlinkTimer >= this._nextDblBlink) {
        this._dblBlinkPending = true
        this._dblBlinkTimer = 0
        this._nextDblBlink = 10 + Math.random() * 12
      }
    }

    const isSleepy = this._currentMood === MOODS.sleepy
    const bspd = speaking ? 11 : isSleepy ? 6 : 9
    this._blinkTimer += elapsed

    if (this._blinkPhase === 0 && this._blinkTimer >= this._nextBlink) {
      this._blinkPhase = 1
      this._blinkTimer = 0
    }

    if (this._blinkPhase === 1) {
      const v = clamp(1 - this._blinkTimer * bspd, 0, 1)
      bus.write('ParamEyeLOpen', v, 'idle')
      bus.write('ParamEyeROpen', v, 'idle')
      if (v <= 0) {
        this._blinkPhase = 2
        this._blinkTimer = 0
      }
    } else if (this._blinkPhase === 2) {
      const v = clamp(this._blinkTimer * bspd, 0, 1)
      bus.write('ParamEyeLOpen', v, 'idle')
      bus.write('ParamEyeROpen', v, 'idle')
      if (v >= 1) {
        this._blinkPhase = 0
        this._blinkTimer = 0
        if (this._dblBlinkPending) {
          this._nextBlink = 0.06 + Math.random() * 0.08
          this._dblBlinkPending = false
        } else if (isSleepy) {
          this._nextBlink = 1.6 + Math.random() * 2.0
        } else if (speaking) {
          this._nextBlink = 3.8 + Math.random() * 2.8
        } else {
          this._nextBlink = 3.0 + Math.random() * 4.5
        }
      }
    } else {
      const restOpen = isSleepy ? 0.74 : 1.0
      bus.write('ParamEyeLOpen', restOpen, 'idle')
      bus.write('ParamEyeROpen', restOpen, 'idle')
    }
  }
}
