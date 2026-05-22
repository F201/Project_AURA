const STATE = { IDLE: 'idle', SPEAKING: 'speaking' }

const MOODS = {
  neutral:  { mouthForm: 0,     browForm: 0,     browRaise: 0,     eyeSmile: 0    },
  happy:    { mouthForm: 0.65,  browForm: 0.30,  browRaise: 0.45,  eyeSmile: 0.55 },
  curious:  { mouthForm: 0.20,  browForm: -0.10, browRaise: 0.50,  eyeSmile: 0    },
  playful:  { mouthForm: 0.90,  browForm: 0.50,  browRaise: 0.70,  eyeSmile: 0.30 },
  sleepy:   { mouthForm: -0.05, browForm: 0.10,  browRaise: -0.15, eyeSmile: 0    },
  thinking: { mouthForm: 0.10,  browForm: -0.20, browRaise: 0.35,  eyeSmile: 0    },
}

const MOOD_POOLS = {
  [STATE.IDLE]: [
    ['neutral', 0.15], ['happy', 0.35], ['curious', 0.20],
    ['playful', 0.10], ['sleepy', 0.10], ['thinking', 0.10],
  ],
  [STATE.SPEAKING]: [
    ['neutral', 0.10], ['happy', 0.45], ['curious', 0.20],
    ['playful', 0.20], ['thinking', 0.05],
  ],
}

function pickWeightedMood(state) {
  const pool = MOOD_POOLS[state] ?? MOOD_POOLS[STATE.IDLE]
  const r = Math.random()
  let acc = 0
  for (const [key, w] of pool) { acc += w; if (r < acc) return MOODS[key] }
  return MOODS.neutral
}

// Framerate-independent exponential decay — replaces elapsed * lerpSpd Euler approximation.
function expDecay(current, target, halfLife, dt) {
  return target + (current - target) * Math.pow(0.5, dt / halfLife)
}

const HALF_LIFE_SPEAKING = 0.20   // equivalent feel to old lerpSpd=5.0
const HALF_LIFE_IDLE     = 0.28   // equivalent feel to old lerpSpd=3.5

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v))

export class IdleLayer {
  constructor(bus) {
    this._bus = bus

    // Blink
    this._blinkTimer       = 0
    this._blinkPhase       = 0
    this._nextBlink        = 2 + Math.random() * 3
    this._dblBlinkPending  = false
    this._dblBlinkTimer    = 0
    this._nextDblBlink     = 10 + Math.random() * 10

    // Saccade
    this._saccadeTimer  = 0
    this._nextSaccade   = 1 + Math.random() * 2
    this._eyeTargetX    = 0
    this._eyeTargetY    = 0
    this._eyeX          = 0
    this._eyeY          = 0

    // Mood
    this._moodTimer      = 0
    this._nextMoodChange = 3 + Math.random() * 4
    this._currentMood    = MOODS.happy
    this._mouthFormC     = 0
    this._browFormC      = 0
    this._browRaiseC     = 0
    this._eyeSmileC      = 0

    // Head tilt (idle micro-animation)
    this._tiltTimer        = 0
    this._nextTilt         = 6 + Math.random() * 8
    this._tiltTarget       = 0
    this._tiltC            = 0
    this._tiltHolding      = false
    this._tiltHoldTimer    = 0
    this._tiltHoldDuration = 0

    // Speaking nod
    this._nodPhase = 0
  }

  update(elapsed, state) {
    const bus     = this._bus
    const now     = performance.now() / 1000
    const speaking = state === STATE.SPEAKING
    const halfLife = speaking ? HALF_LIFE_SPEAKING : HALF_LIFE_IDLE

    // ── Breathing ────────────────────────────────────────────────────────────
    bus.write('ParamBreath',
      Math.sin(now * (speaking ? 1.1 : 0.75)) * 0.5 + 0.5, 'idle')

    // ── Head movement ─────────────────────────────────────────────────────────
    const swayAmt = speaking ? 0.35 : 1.0
    const bX = (Math.sin(now * 0.31) * 12 + Math.sin(now * 0.73) * 3) * swayAmt
    const bY = (Math.sin(now * 0.19) * 5  + Math.sin(now * 0.47) * 2) * swayAmt
    const bZ = (Math.sin(now * 0.13) * 5  + Math.sin(now * 0.41) * 2) * swayAmt

    let nodY = 0
    if (speaking) {
      this._nodPhase += elapsed * 2.6
      nodY = Math.sin(this._nodPhase) * 3.5
    } else {
      this._nodPhase = 0
    }

    // Cute idle head tilt
    if (!speaking) {
      this._tiltTimer += elapsed
      if (!this._tiltHolding && this._tiltTimer >= this._nextTilt) {
        this._tiltTarget       = (Math.random() < 0.5 ? 1 : -1) * (7 + Math.random() * 7)
        this._tiltTimer        = 0
        this._nextTilt         = 6 + Math.random() * 8
        this._tiltHolding      = true
        this._tiltHoldTimer    = 0
        this._tiltHoldDuration = 0.9 + Math.random() * 0.8
      }
    }
    if (this._tiltHolding) {
      this._tiltHoldTimer += elapsed
      if (this._tiltHoldTimer >= this._tiltHoldDuration) {
        this._tiltTarget  = 0
        this._tiltHolding = false
      }
    }
    this._tiltC += (this._tiltTarget - this._tiltC) * elapsed * (this._tiltTarget !== 0 ? 6.0 : 2.2)

    bus.write('ParamAngleX',    bX, 'idle')
    bus.write('ParamAngleY',    bY + nodY, 'idle')
    bus.write('ParamAngleZ',    bZ + this._tiltC, 'idle')
    bus.write('ParamBodyAngleX', Math.sin(now * 0.28) * 4 * swayAmt, 'idle')
    bus.write('ParamBodyAngleZ', Math.sin(now * 0.21) * 3 * swayAmt, 'idle')

    // ── Mood interpolation ────────────────────────────────────────────────────
    this._moodTimer += elapsed
    if (this._moodTimer >= this._nextMoodChange) {
      this._moodTimer      = 0
      this._nextMoodChange = speaking ? 2 + Math.random() * 2.5 : 3 + Math.random() * 5
      this._currentMood    = pickWeightedMood(state)

      if (this._currentMood === MOODS.curious) {
        this._eyeTargetY  = 0.45 + Math.random() * 0.30
        this._nextSaccade = this._saccadeTimer + 3
      }
      if (this._currentMood === MOODS.thinking) {
        this._eyeTargetX  = -(0.4 + Math.random() * 0.3)
        this._eyeTargetY  = 0.4 + Math.random() * 0.3
        this._nextSaccade = this._saccadeTimer + 4
      }
    }

    this._mouthFormC = expDecay(this._mouthFormC, this._currentMood.mouthForm, halfLife, elapsed)
    this._browFormC  = expDecay(this._browFormC,  this._currentMood.browForm,  halfLife, elapsed)
    this._browRaiseC = expDecay(this._browRaiseC, this._currentMood.browRaise, halfLife, elapsed)
    this._eyeSmileC  = expDecay(this._eyeSmileC,  this._currentMood.eyeSmile,  halfLife, elapsed)

    const mfBoost = speaking ? 0.20 : 0
    // browRaise folded as additive offset into brow form params;
    // physics Setting31 propagates it to Param37 with natural lag.
    const browTotal = clamp(this._browFormC + this._browRaiseC, -1, 1)
    bus.write('ParamMouthForm', clamp(this._mouthFormC + mfBoost, -1, 1), 'idle')
    bus.write('ParamBrowLForm', browTotal, 'idle')
    bus.write('ParamBrowRForm', browTotal, 'idle')
    bus.write('ParamEyeLSmile', this._eyeSmileC, 'idle')
    bus.write('ParamEyeRSmile', this._eyeSmileC, 'idle')

    // ── Saccade ───────────────────────────────────────────────────────────────
    this._saccadeTimer += elapsed
    if (this._saccadeTimer >= this._nextSaccade) {
      if (speaking) {
        this._eyeTargetX  = (Math.random() * 2 - 1) * 0.25
        this._eyeTargetY  = (Math.random() * 2 - 1) * 0.15
        this._nextSaccade = this._saccadeTimer + 0.8 + Math.random() * 1.0
      } else {
        this._eyeTargetX = (Math.random() * 2 - 1) * 0.65
        const r = Math.random()
        if      (r < 0.20) this._eyeTargetY =  0.5 + Math.random() * 0.35
        else if (r < 0.35) this._eyeTargetY = -0.3 - Math.random() * 0.25
        else               this._eyeTargetY =  (Math.random() * 2 - 1) * 0.4
        this._nextSaccade = this._saccadeTimer + 1.5 + Math.random() * 2.5
      }
    }
    const gzSpd = speaking ? 5.0 : 3.5
    this._eyeX += (this._eyeTargetX - this._eyeX) * elapsed * gzSpd
    this._eyeY += (this._eyeTargetY - this._eyeY) * elapsed * gzSpd
    bus.write('ParamEyeBallX', clamp(this._eyeX, -1, 1), 'idle')
    bus.write('ParamEyeBallY', clamp(this._eyeY, -1, 1), 'idle')

    // ── Double-blink scheduler (idle only) ────────────────────────────────────
    if (!speaking) {
      this._dblBlinkTimer += elapsed
      if (this._dblBlinkTimer >= this._nextDblBlink) {
        this._dblBlinkPending = true
        this._dblBlinkTimer   = 0
        this._nextDblBlink    = 10 + Math.random() * 12
      }
    }

    // ── Blink ─────────────────────────────────────────────────────────────────
    // Expression eye params write at P4 — bus priority ensures expression wins,
    // so blink can run its state machine freely; visual output is overridden when needed.
    const isSleepy = this._currentMood === MOODS.sleepy
    const bspd     = speaking ? 11 : (isSleepy ? 6 : 9)
    this._blinkTimer += elapsed

    if (this._blinkPhase === 0 && this._blinkTimer >= this._nextBlink) {
      this._blinkPhase = 1
      this._blinkTimer = 0
    }

    if (this._blinkPhase === 1) {
      const v = clamp(1 - this._blinkTimer * bspd, 0, 1)
      bus.write('ParamEyeLOpen', v, 'idle')
      bus.write('ParamEyeROpen', v, 'idle')
      if (v <= 0) { this._blinkPhase = 2; this._blinkTimer = 0 }

    } else if (this._blinkPhase === 2) {
      const v = clamp(this._blinkTimer * bspd, 0, 1)
      bus.write('ParamEyeLOpen', v, 'idle')
      bus.write('ParamEyeROpen', v, 'idle')
      if (v >= 1) {
        this._blinkPhase = 0
        this._blinkTimer = 0
        if (this._dblBlinkPending) {
          this._nextBlink       = 0.06 + Math.random() * 0.08
          this._dblBlinkPending = false
        } else if (isSleepy) {
          this._nextBlink = 1.5 + Math.random() * 2.0
        } else if (speaking) {
          this._nextBlink = 4.0 + Math.random() * 3.0
        } else {
          this._nextBlink = 3.0 + Math.random() * 5.0
        }
      }

    } else {
      // Resting open — sleepy: heavy-lidded at 72%
      const restOpen = isSleepy ? 0.72 : 1.0
      bus.write('ParamEyeLOpen', restOpen, 'idle')
      bus.write('ParamEyeROpen', restOpen, 'idle')
    }
  }
}
