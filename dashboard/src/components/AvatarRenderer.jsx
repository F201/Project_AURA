/**
 * AvatarRenderer — Phase 3
 * Idle / Speaking state machine with richer moods and cute micro-animations:
 *   • 6 weighted moods per state (neutral, happy, curious, playful, sleepy, thinking)
 *   • Cute head-tilt event during idle
 *   • Occasional double-blink during idle
 *   • Sleepy: half-closed eyes, slow blink
 *   • Speaking: gentle nod, tighter saccade, snappier blink, slight smile boost
 *
 * Ref API:
 *   setExpression(names[], duration)  — play expression(s) for N seconds
 *   setSpeaking(bool)                 — switch idle ↔ speaking state
 *   setMouthOpen(0–1)                 — drive lip sync each frame
 *   setParameter(id, value)           — raw Core Model parameter override
 *   resetNeutral()                    — cancel active expression, return to idle
 */

import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'
import * as PIXI from 'pixi.js'
import { Live2DModel } from 'pixi-live2d-display/cubism4'

Live2DModel.registerTicker(PIXI.Ticker)

const MODEL_URL = '/models/hutao/Hu Tao.model3.json'

const EXPRESSION_FILES = {
  smile:         'SmileLock.exp3.json',
  sad:           'SadLock.exp3.json',
  angry:         'Angry.exp3.json',
  ghost:         'Ghost.exp3.json',
  ghost_nervous: 'GhostChange.exp3.json',
  shadow:        'Shadow.exp3.json',
  pupil_shrink:  'PupilShrink.exp3.json',
  eyeshine_off:  'EyeshineOff.exp3.json',
}

// Maps LLM-annotated expression names → the closest ambient mood.
// Applied after the expression fades so the idle baseline stays emotionally coherent.
const EXPRESSION_TO_MOOD = {
  smile:         'happy',
  sad:           'neutral',   // no sad mood — settle to calm neutral
  angry:         'thinking',  // furrowed brows, withdrawn
  ghost:         'playful',   // mischievous
  ghost_nervous: 'curious',   // uncertain, alert
  shadow:        'thinking',  // serious / dark
  pupil_shrink:  'curious',   // surprised / wide-eyed
  eyeshine_off:  'sleepy',    // dull / fatigued
  wink:          'playful',
  tongue:        'playful',
}

// ── State machine ──────────────────────────────────────────────────────────
const STATE = { IDLE: 'idle', SPEAKING: 'speaking' }

// ── Mood definitions (target parameter values) ─────────────────────────────
const MOODS = {
  neutral:  { mouthForm: 0,     browForm: 0,     browRaise: 0,     eyeSmile: 0    },
  happy:    { mouthForm: 0.65,  browForm: 0.30,  browRaise: 0.45,  eyeSmile: 0.55 },
  curious:  { mouthForm: 0.20,  browForm: -0.10, browRaise: 0.50,  eyeSmile: 0    },
  playful:  { mouthForm: 0.90,  browForm: 0.50,  browRaise: 0.70,  eyeSmile: 0.30 },
  sleepy:   { mouthForm: -0.05, browForm: 0.10,  browRaise: -0.15, eyeSmile: 0    },
  thinking: { mouthForm: 0.10,  browForm: -0.20, browRaise: 0.35,  eyeSmile: 0    },
}

// Weighted mood pool per state — [moodKey, weight], weights sum to 1.0
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
  for (const [key, w] of pool) {
    acc += w
    if (r < acc) return MOODS[key]
  }
  return MOODS.neutral
}

// ── Module-scoped Singleton State ──────────────────────────────────────────
let _app   = null
let _model = null
let _loaded = false
let _mouthOpen = 0
let _expressionActive = false
let _state = STATE.IDLE
let _pendingMood = null   // set by setExpression, consumed by update loop on expiry

function initSingleton(width, height) {
  if (_app) return

  _app = new PIXI.Application({
    backgroundAlpha: 0,
    width,
    height,
    antialias: true,
    resolution: window.devicePixelRatio || 2,
    autoDensity: true,
  })

  Live2DModel.from(MODEL_URL, { autoInteract: false })
    .then((model) => {
      _model = model
      _app.stage.addChild(model)

      const logicalW = _app.screen.width
      const logicalH = _app.screen.height
      const autoScale = (logicalH / model.height) * 1.9
      model.scale.set(autoScale)
      model.anchor.set(0.5, 0.0)
      model.position.set(logicalW * 0.5, 0)

      const core = model.internalModel.coreModel
      const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v))
      let lastMs = performance.now()

      // ── Blink state ──────────────────────────────────────────────────────
      let blinkTimer = 0, blinkPhase = 0, nextBlink = 2 + Math.random() * 3
      // Double-blink: blink twice in quick succession (cute quirk)
      let dblBlinkPending = false
      let dblBlinkTimer = 0, nextDblBlink = 10 + Math.random() * 10

      // ── Saccade state ─────────────────────────────────────────────────────
      let saccadeTimer = 0, nextSaccade = 1 + Math.random() * 2
      let eyeTargetX = 0, eyeTargetY = 0, eyeX = 0, eyeY = 0

      // ── Mood state ────────────────────────────────────────────────────────
      let moodTimer = 0, nextMoodChange = 3 + Math.random() * 4
      let currentMood = MOODS.happy
      let mouthFormC = 0, browFormC = 0, browRaiseC = 0, eyeSmileC = 0

      // ── Head tilt micro-animation (idle only) ─────────────────────────────
      // Occasionally snaps to a cute side-tilt, holds briefly, then eases back
      let tiltTimer = 0, nextTilt = 6 + Math.random() * 8
      let tiltTarget = 0, tiltC = 0
      let tiltHolding = false, tiltHoldTimer = 0, tiltHoldDuration = 0

      // ── Speaking nod ──────────────────────────────────────────────────────
      let nodPhase = 0

      const origCoreUpdate = core.update.bind(core)

      core.update = function () {
        const now     = performance.now() / 1000
        const elapsed = Math.min((performance.now() - lastMs) / 1000, 0.1)
        lastMs = performance.now()

        const speaking = _state === STATE.SPEAKING
        const lerpSpd  = speaking ? 5.0 : 3.5

        // ── Breathing ────────────────────────────────────────────────────
        // Slightly faster when speaking (more energetic)
        core.setParameterValueById('ParamBreath',
          Math.sin(now * (speaking ? 1.1 : 0.75)) * 0.5 + 0.5)

        // ── Head movement ─────────────────────────────────────────────────
        const swayAmt = speaking ? 0.35 : 1.0
        const bX = (Math.sin(now * 0.31) * 12 + Math.sin(now * 0.73) * 3) * swayAmt
        const bY = (Math.sin(now * 0.19) * 5  + Math.sin(now * 0.47) * 2) * swayAmt
        const bZ = (Math.sin(now * 0.13) * 5  + Math.sin(now * 0.41) * 2) * swayAmt

        // Gentle speaking nod — Y oscillation in rough speech rhythm
        let nodY = 0
        if (speaking) {
          nodPhase += elapsed * 2.6
          nodY = Math.sin(nodPhase) * 3.5
        } else {
          nodPhase = 0
        }

        // Cute idle head tilt — snap in quickly, ease back slowly
        if (!speaking) {
          tiltTimer += elapsed
          if (!tiltHolding && tiltTimer >= nextTilt) {
            tiltTarget = (Math.random() < 0.5 ? 1 : -1) * (7 + Math.random() * 7)
            tiltTimer = 0
            nextTilt = 6 + Math.random() * 8
            tiltHolding = true
            tiltHoldTimer = 0
            tiltHoldDuration = 0.9 + Math.random() * 0.8
          }
        }
        if (tiltHolding) {
          tiltHoldTimer += elapsed
          if (tiltHoldTimer >= tiltHoldDuration) { tiltTarget = 0; tiltHolding = false }
        }
        tiltC += (tiltTarget - tiltC) * elapsed * (tiltTarget !== 0 ? 6.0 : 2.2)

        core.setParameterValueById('ParamAngleX', bX)
        core.setParameterValueById('ParamAngleY', bY + nodY)
        core.setParameterValueById('ParamAngleZ', bZ + tiltC)
        core.setParameterValueById('ParamBodyAngleX', Math.sin(now * 0.28) * 4 * swayAmt)
        core.setParameterValueById('ParamBodyAngleZ', Math.sin(now * 0.21) * 3 * swayAmt)

        // ── Lip sync ──────────────────────────────────────────────────────
        core.setParameterValueById('ParamMouthOpenY', _mouthOpen)

        // ── Mood interpolation ────────────────────────────────────────────
        if (!_expressionActive) {
          // Expression just expired — align ambient mood to the emotion the LLM set
          if (_pendingMood) {
            currentMood = _pendingMood
            _pendingMood = null
            moodTimer = 0
            nextMoodChange = 3 + Math.random() * 3  // hold this mood for 3-6s before drifting
          }

          moodTimer += elapsed
          if (moodTimer >= nextMoodChange) {
            moodTimer = 0
            nextMoodChange = speaking
              ? 2 + Math.random() * 2.5
              : 3 + Math.random() * 5
            currentMood = pickWeightedMood(_state)

            // Curious: look upward with a lingering gaze
            if (currentMood === MOODS.curious) {
              eyeTargetY = 0.45 + Math.random() * 0.30
              nextSaccade = saccadeTimer + 3
            }
            // Thinking: look up-left (classic thinking glance)
            if (currentMood === MOODS.thinking) {
              eyeTargetX = -(0.4 + Math.random() * 0.3)
              eyeTargetY =   0.4 + Math.random() * 0.3
              nextSaccade = saccadeTimer + 4
            }
          }

          const lm = elapsed * lerpSpd
          mouthFormC += (currentMood.mouthForm - mouthFormC) * lm
          browFormC  += (currentMood.browForm   - browFormC)  * lm
          browRaiseC += (currentMood.browRaise  - browRaiseC) * lm
          eyeSmileC  += (currentMood.eyeSmile   - eyeSmileC)  * lm

          // Speaking: add a slight smile boost (engaged / expressive look)
          const mfBoost = speaking ? 0.20 : 0
          core.setParameterValueById('ParamMouthForm',  clamp(mouthFormC + mfBoost, -1, 1))
          core.setParameterValueById('ParamBrowLForm',  browFormC)
          core.setParameterValueById('ParamBrowRForm',  browFormC)
          core.setParameterValueById('Param37',         browRaiseC)
          core.setParameterValueById('ParamEyeLSmile',  eyeSmileC)
          core.setParameterValueById('ParamEyeRSmile',  eyeSmileC)
        }

        // ── Saccade ───────────────────────────────────────────────────────
        saccadeTimer += elapsed
        if (saccadeTimer >= nextSaccade) {
          if (speaking) {
            // Focus on "listener" — small central range, frequent updates
            eyeTargetX = (Math.random() * 2 - 1) * 0.25
            eyeTargetY = (Math.random() * 2 - 1) * 0.15
            nextSaccade = saccadeTimer + 0.8 + Math.random() * 1.0
          } else {
            eyeTargetX = (Math.random() * 2 - 1) * 0.65
            const r = Math.random()
            if      (r < 0.20) eyeTargetY =  0.5 + Math.random() * 0.35
            else if (r < 0.35) eyeTargetY = -0.3 - Math.random() * 0.25
            else               eyeTargetY = (Math.random() * 2 - 1) * 0.4
            nextSaccade = saccadeTimer + 1.5 + Math.random() * 2.5
          }
        }
        const gzSpd = speaking ? 5.0 : 3.5
        eyeX += (eyeTargetX - eyeX) * elapsed * gzSpd
        eyeY += (eyeTargetY - eyeY) * elapsed * gzSpd
        core.setParameterValueById('ParamEyeBallX', clamp(eyeX, -1, 1))
        core.setParameterValueById('ParamEyeBallY', clamp(eyeY, -1, 1))

        // ── Double-blink scheduler (idle only) ────────────────────────────
        if (!speaking) {
          dblBlinkTimer += elapsed
          if (dblBlinkTimer >= nextDblBlink) {
            dblBlinkPending = true
            dblBlinkTimer = 0
            nextDblBlink = 10 + Math.random() * 12
          }
        }

        // ── Blink ─────────────────────────────────────────────────────────
        const isSleepy = currentMood === MOODS.sleepy
        // Speaking: snappy blink (11). Sleepy: slow droopy blink (6). Normal: 9
        const bspd = speaking ? 11 : (isSleepy ? 6 : 9)
        blinkTimer += elapsed

        if (blinkPhase === 0 && blinkTimer >= nextBlink) {
          blinkPhase = 1; blinkTimer = 0
        }
        if (blinkPhase === 1) {
          const v = clamp(1 - blinkTimer * bspd, 0, 1)
          core.setParameterValueById('ParamEyeLOpen', v)
          core.setParameterValueById('ParamEyeROpen', v)
          if (v <= 0) { blinkPhase = 2; blinkTimer = 0 }
        } else if (blinkPhase === 2) {
          const v = clamp(blinkTimer * bspd, 0, 1)
          core.setParameterValueById('ParamEyeLOpen', v)
          core.setParameterValueById('ParamEyeROpen', v)
          if (v >= 1) {
            blinkPhase = 0; blinkTimer = 0
            if (dblBlinkPending) {
              nextBlink = 0.06 + Math.random() * 0.08  // blink again almost immediately
              dblBlinkPending = false
            } else if (isSleepy) {
              nextBlink = 1.5 + Math.random() * 2.0    // sleepy: blinks more often
            } else if (speaking) {
              nextBlink = 4.0 + Math.random() * 3.0    // speaking: eyes stay open longer
            } else {
              nextBlink = 3.0 + Math.random() * 5.0    // normal idle
            }
          }
        } else {
          // Resting open — sleepy mode: eyes only 72% open (heavy lidded)
          if (!_expressionActive) {
            const restOpen = isSleepy ? 0.72 : 1.0
            core.setParameterValueById('ParamEyeLOpen', restOpen)
            core.setParameterValueById('ParamEyeROpen', restOpen)
          }
        }

        origCoreUpdate()
      }

      _loaded = true
    })
    .catch((err) => console.error('[AvatarRenderer] Failed to load Live2D model:', err))
}

export const AvatarRenderer = forwardRef(function AvatarRenderer(props, ref) {
  const { width = 400, height = 600 } = props
  const containerRef = useRef(null)

  useEffect(() => {
    initSingleton(width, height)
    const container = containerRef.current
    if (container && _app) container.appendChild(_app.view)
    return () => {
      if (container && _app && _app.view.parentNode === container)
        container.removeChild(_app.view)
    }
  }, [width, height])

  useImperativeHandle(ref, () => ({
    setExpression(names, duration) {
      if (!_loaded || !_model) return
      _expressionActive = true

      // Queue the mood that best matches this expression — applied when it expires
      for (const name of names) {
        const moodKey = EXPRESSION_TO_MOOD[name]
        if (moodKey) { _pendingMood = MOODS[moodKey]; break }
      }

      for (const name of names) {
        const file = EXPRESSION_FILES[name]
        if (file) _model.expression(file)
        if (name === 'wink') {
          const c = _model.internalModel.coreModel
          c.setParameterValueById('ParamEyeLOpen',  0.0)
          c.setParameterValueById('ParamBrowLForm', -1.0)
          c.setParameterValueById('ParamMouthForm',  1.0)
        }
        if (name === 'tongue') {
          const c = _model.internalModel.coreModel
          c.setParameterValueById('ParamMouthOpenY', 1.0)
          c.setParameterValueById('ParamMouthForm',  -1.0)
        }
      }
      setTimeout(() => {
        _expressionActive = false
        if (_model) _model.expression()
      }, duration * 1000)
    },

    /** Switch between idle and speaking animation state */
    setSpeaking(active) {
      _state = active ? STATE.SPEAKING : STATE.IDLE
    },

    setParameter(name, value) {
      _model?.internalModel.coreModel.setParameterValueById(name, value)
    },

    resetNeutral() {
      _expressionActive = false
      _model?.expression()
    },

    setMouthOpen(v) {
      _mouthOpen = Math.max(0, Math.min(1, v))
    },
  }), [])

  return (
    <div
      ref={containerRef}
      style={{ width, height, display: 'block', overflow: 'hidden' }}
    />
  )
})
