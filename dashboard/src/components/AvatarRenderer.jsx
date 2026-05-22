/**
 * AvatarRenderer — Phase 3 (ParameterBus architecture gated by USE_PARAMETER_BUS)
 *
 * New path (USE_PARAMETER_BUS = true):
 *   ParameterBus → priority-resolved single write per param per frame
 *   IdleLayer (P1), TrackingLayer (P2), ExpressionLayer (P4)
 *   Physics output params blocklisted — never manually overridden
 *   Expression fade-in / fade-out, blend mode parity with VTube Studio
 *   Blink runs freely; expression P4 wins eye params during wink etc.
 *   expDecay replaces framerate-dependent lerp
 *
 * Old path (USE_PARAMETER_BUS = false):
 *   Original code - kept intact, no regressions.
 *
 * Ref API (both paths):
 *   setExpression(names[], duration)
 *   setSpeaking(bool)
 *   setMouthOpen(0–1)
 *   setParameter(id, value)
 *   resetNeutral()
 */

import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'
import * as PIXI from 'pixi.js'
import { Live2DModel } from 'pixi-live2d-display/cubism4'

import { ParameterBus } from '../avatar/ParameterBus.js'
import { PHYSICS_OUTPUT_PARAMS } from '../avatar/PhysicsOutputParams.js'
import { IdleLayer } from '../avatar/layers/IdleLayer.js'
import { TrackingLayer } from '../avatar/layers/TrackingLayer.js'
import { ExpressionLayer } from '../avatar/layers/ExpressionLayer.js'

// Flip to true + delete old path + delete this constant once QA passes all acceptance criteria.
const USE_PARAMETER_BUS = true

Live2DModel.registerTicker(PIXI.Ticker)

const MODEL_URL = '/models/hutao/Hu Tao.model3.json'

const EXPRESSION_FILES = {
  smile: 'SmileLock.exp3.json',
  sad: 'SadLock.exp3.json',
  angry: 'Angry.exp3.json',
  ghost: 'Ghost.exp3.json',
  ghost_nervous: 'GhostChange.exp3.json',
  shadow: 'Shadow.exp3.json',
  pupil_shrink: 'PupilShrink.exp3.json',
  eyeshine_off: 'EyeshineOff.exp3.json',
  blush: 'SmileLock.exp3.json',
  embarrassed: 'GhostChange.exp3.json',
}

const EXPRESSION_TO_MOOD = {
  smile: 'happy',
  sad: 'neutral',
  angry: 'thinking',
  ghost: 'playful',
  ghost_nervous: 'curious',
  shadow: 'thinking',
  pupil_shrink: 'curious',
  eyeshine_off: 'sleepy',
  wink: 'playful',
}

const STATE = { IDLE: 'idle', SPEAKING: 'speaking' }

const MOODS = {
  neutral: { mouthForm: 0, browForm: 0, browRaise: 0, eyeSmile: 0 },
  happy: { mouthForm: 0.65, browForm: 0.30, browRaise: 0.45, eyeSmile: 0.55 },
  curious: { mouthForm: 0.20, browForm: -0.10, browRaise: 0.50, eyeSmile: 0 },
  playful: { mouthForm: 0.90, browForm: 0.50, browRaise: 0.70, eyeSmile: 0.30 },
  sleepy: { mouthForm: -0.05, browForm: 0.10, browRaise: -0.15, eyeSmile: 0 },
  thinking: { mouthForm: 0.10, browForm: -0.20, browRaise: 0.35, eyeSmile: 0 },
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

// ── Module-scoped singleton ────────────────────────────────────────────────────
let _app = null
let _model = null
let _loaded = false
let _mouthOpen = 0
let _state = STATE.IDLE

// Old-path only
let _expressionActive = false
let _pendingMood = null

// New-path only
let _bus = null
let _idleLayer = null
let _trackingLayer = null
let _expressionLayer = null

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
      const autoScale = (logicalH / model.height) * 1.4
      model.scale.set(autoScale)
      model.anchor.set(0.5, 0.0)
      model.position.set(logicalW * 0.5, 0)

      const core = model.internalModel.coreModel
      const origCoreUpdate = core.update.bind(core)
      const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v))

      if (USE_PARAMETER_BUS) {
        // ── New path ─────────────────────────────────────────────────────────
        // Neutralise SDK ExpressionManager so it writes zeros at step 3 each frame.
        // Our bus flush at step 7 overwrites those zeros with the correct values.
        _model.expression(null)

        _bus = new ParameterBus(PHYSICS_OUTPUT_PARAMS)
        _idleLayer = new IdleLayer(_bus)
        _trackingLayer = new TrackingLayer(_bus)
        _expressionLayer = new ExpressionLayer(_bus, EXPRESSION_FILES)

        let lastMs = performance.now()

        core.update = function () {
          const elapsed = Math.min((performance.now() - lastMs) / 1000, 0.1)
          lastMs = performance.now()

          _idleLayer.update(elapsed, _state)
          _trackingLayer.update(_mouthOpen)
          _expressionLayer.update(elapsed)
          _bus.flush(core)
          origCoreUpdate()
        }

      } else {
        // ── Old path (Phase 3, unchanged) ────────────────────────────────────
        let lastMs = performance.now()

        let blinkTimer = 0, blinkPhase = 0, nextBlink = 2 + Math.random() * 3
        let dblBlinkPending = false
        let dblBlinkTimer = 0, nextDblBlink = 10 + Math.random() * 10

        let saccadeTimer = 0, nextSaccade = 1 + Math.random() * 2
        let eyeTargetX = 0, eyeTargetY = 0, eyeX = 0, eyeY = 0

        let moodTimer = 0, nextMoodChange = 3 + Math.random() * 4
        let currentMood = MOODS.happy
        let mouthFormC = 0, browFormC = 0, browRaiseC = 0, eyeSmileC = 0

        let tiltTimer = 0, nextTilt = 6 + Math.random() * 8
        let tiltTarget = 0, tiltC = 0
        let tiltHolding = false, tiltHoldTimer = 0, tiltHoldDuration = 0

        let nodPhase = 0

        core.update = function () {
          const now = performance.now() / 1000
          const elapsed = Math.min((performance.now() - lastMs) / 1000, 0.1)
          lastMs = performance.now()

          const speaking = _state === STATE.SPEAKING
          const lerpSpd = speaking ? 5.0 : 3.5

          core.setParameterValueById('ParamBreath',
            Math.sin(now * (speaking ? 1.1 : 0.75)) * 0.5 + 0.5)

          const swayAmt = speaking ? 0.35 : 1.0
          const bX = (Math.sin(now * 0.31) * 12 + Math.sin(now * 0.73) * 3) * swayAmt
          const bY = (Math.sin(now * 0.19) * 5 + Math.sin(now * 0.47) * 2) * swayAmt
          const bZ = (Math.sin(now * 0.13) * 5 + Math.sin(now * 0.41) * 2) * swayAmt

          let nodY = 0
          if (speaking) { nodPhase += elapsed * 2.6; nodY = Math.sin(nodPhase) * 3.5 }
          else { nodPhase = 0 }

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

          core.setParameterValueById('ParamMouthOpenY', _mouthOpen)

          if (!_expressionActive) {
            if (_pendingMood) {
              currentMood = _pendingMood
              _pendingMood = null
              moodTimer = 0
              nextMoodChange = 3 + Math.random() * 3
            }

            moodTimer += elapsed
            if (moodTimer >= nextMoodChange) {
              moodTimer = 0
              nextMoodChange = speaking ? 2 + Math.random() * 2.5 : 3 + Math.random() * 5
              currentMood = pickWeightedMood(_state)

              if (currentMood === MOODS.curious) { eyeTargetY = 0.45 + Math.random() * 0.30; nextSaccade = saccadeTimer + 3 }
              if (currentMood === MOODS.thinking) { eyeTargetX = -(0.4 + Math.random() * 0.3); eyeTargetY = 0.4 + Math.random() * 0.3; nextSaccade = saccadeTimer + 4 }
            }

            const lm = elapsed * lerpSpd
            mouthFormC += (currentMood.mouthForm - mouthFormC) * lm
            browFormC += (currentMood.browForm - browFormC) * lm
            browRaiseC += (currentMood.browRaise - browRaiseC) * lm
            eyeSmileC += (currentMood.eyeSmile - eyeSmileC) * lm

            const mfBoost = speaking ? 0.20 : 0
            core.setParameterValueById('ParamMouthForm', clamp(mouthFormC + mfBoost, -1, 1))
            core.setParameterValueById('ParamBrowLForm', browFormC)
            core.setParameterValueById('ParamBrowRForm', browFormC)
            core.setParameterValueById('Param37', browRaiseC)
            core.setParameterValueById('ParamEyeLSmile', eyeSmileC)
            core.setParameterValueById('ParamEyeRSmile', eyeSmileC)
          }

          saccadeTimer += elapsed
          if (saccadeTimer >= nextSaccade) {
            if (speaking) {
              eyeTargetX = (Math.random() * 2 - 1) * 0.25
              eyeTargetY = (Math.random() * 2 - 1) * 0.15
              nextSaccade = saccadeTimer + 0.8 + Math.random() * 1.0
            } else {
              eyeTargetX = (Math.random() * 2 - 1) * 0.65
              const r = Math.random()
              if (r < 0.20) eyeTargetY = 0.5 + Math.random() * 0.35
              else if (r < 0.35) eyeTargetY = -0.3 - Math.random() * 0.25
              else eyeTargetY = (Math.random() * 2 - 1) * 0.4
              nextSaccade = saccadeTimer + 1.5 + Math.random() * 2.5
            }
          }
          const gzSpd = speaking ? 5.0 : 3.5
          eyeX += (eyeTargetX - eyeX) * elapsed * gzSpd
          eyeY += (eyeTargetY - eyeY) * elapsed * gzSpd
          core.setParameterValueById('ParamEyeBallX', clamp(eyeX, -1, 1))
          core.setParameterValueById('ParamEyeBallY', clamp(eyeY, -1, 1))

          if (!speaking) {
            dblBlinkTimer += elapsed
            if (dblBlinkTimer >= nextDblBlink) {
              dblBlinkPending = true
              dblBlinkTimer = 0
              nextDblBlink = 10 + Math.random() * 12
            }
          }

          const isSleepy = currentMood === MOODS.sleepy
          const bspd = speaking ? 11 : (isSleepy ? 6 : 9)
          blinkTimer += elapsed

          if (blinkPhase === 0 && blinkTimer >= nextBlink && !_expressionActive) {
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
                nextBlink = 0.06 + Math.random() * 0.08
                dblBlinkPending = false
              } else if (isSleepy) {
                nextBlink = 1.5 + Math.random() * 2.0
              } else if (speaking) {
                nextBlink = 4.0 + Math.random() * 3.0
              } else { nextBlink = 3.0 + Math.random() * 5.0 }
            }
          } else {
            if (!_expressionActive) {
              const restOpen = isSleepy ? 0.72 : 1.0
              core.setParameterValueById('ParamEyeLOpen', restOpen)
              core.setParameterValueById('ParamEyeROpen', restOpen)
            }
          }

          origCoreUpdate()
        }
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

      if (USE_PARAMETER_BUS) {
        _expressionLayer.setExpression(names, duration)
        return
      }

      // ── Old path ────────────────────────────────────────────────────────────
      _expressionActive = true

      for (const name of names) {
        const moodKey = EXPRESSION_TO_MOOD[name]
        if (moodKey) { _pendingMood = MOODS[moodKey]; break }
      }

      for (const name of names) {
        const file = EXPRESSION_FILES[name]
        if (file) _model.expression(file)

        const c = _model.internalModel.coreModel
        if (name === 'wink') {
          const startTime = performance.now()
          const winkInterval = setInterval(() => {
            if (!_loaded || !_model) {
              clearInterval(winkInterval)
              return
            }
            const elapsed = (performance.now() - startTime) / 1000
            const core = _model.internalModel.coreModel
            if (elapsed < 0.16) {
              const progress = elapsed / 0.16
              core.setParameterValueById('ParamEyeLOpen', 1.0 - progress)
              core.setParameterValueById('ParamBrowLForm', -progress)
              core.setParameterValueById('ParamMouthForm', progress)
            } else if (elapsed < 0.31) {
              core.setParameterValueById('ParamEyeLOpen', 0.0)
              core.setParameterValueById('ParamBrowLForm', -1.0)
              core.setParameterValueById('ParamMouthForm', 1.0)
            } else if (elapsed < 0.51) {
              const progress = (elapsed - 0.31) / 0.20
              core.setParameterValueById('ParamEyeLOpen', progress)
              core.setParameterValueById('ParamBrowLForm', -1.0 + progress)
              core.setParameterValueById('ParamMouthForm', 1.0 - progress)
            } else {
              core.setParameterValueById('ParamEyeLOpen', 1.0)
              core.setParameterValueById('ParamBrowLForm', 0.0)
              core.setParameterValueById('ParamMouthForm', 0.0)
              clearInterval(winkInterval)
            }
          }, 16)
        } else if (name === 'tongue') {
          c.setParameterValueById('ParamMouthOpenY', 1.0)
          c.setParameterValueById('ParamMouthForm', -1.0)
        } else if (name === 'pouting') {
          c.setParameterValueById('ParamMouthForm', -1.0)
          c.setParameterValueById('ParamBrowLForm', -1.0)
          c.setParameterValueById('ParamBrowRForm', -1.0)
        } else if (name === 'curious idle') {
          c.setParameterValueById('ParamBrowLForm', 0.5)
          c.setParameterValueById('ParamBrowRForm', -0.5)
        } else if (name === 'pleading') {
          c.setParameterValueById('ParamBrowLY', 1.0)
          c.setParameterValueById('ParamBrowRY', 1.0)
          c.setParameterValueById('ParamMouthForm', -0.5)
        }
      }

      setTimeout(() => {
        _expressionActive = false
        if (_model) {
          _model.expression()
          const c = _model.internalModel.coreModel
          c.setParameterValueById('ParamEyeLOpen', 1.0)
          c.setParameterValueById('ParamEyeROpen', 1.0)
          c.setParameterValueById('ParamBrowLForm', 0.0)
          c.setParameterValueById('ParamBrowRForm', 0.0)
          c.setParameterValueById('ParamBrowLY', 0.0)
          c.setParameterValueById('ParamBrowRY', 0.0)
          c.setParameterValueById('ParamMouthForm', 0.0)
        }
      }, duration * 1000)
    },

    setSpeaking(active) {
      _state = active ? STATE.SPEAKING : STATE.IDLE
    },

    setParameter(name, value) {
      _model?.internalModel.coreModel.setParameterValueById(name, value)
    },

    resetNeutral() {
      if (USE_PARAMETER_BUS) {
        _expressionLayer?.clear()
        return
      }
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
