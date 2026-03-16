/**
 * AvatarRenderer — Phase 2
 * Renders the Hu Tao Live2D model on a transparent canvas using
 * pixi-live2d-display. Exposes an imperative ref API so CallOverlay
 * can drive expressions in sync with AURA's speech.
 *
 * Usage:
 *   const avatarRef = useRef(null)
 *   <AvatarRenderer ref={avatarRef} width={400} height={600} scale={0.3} />
 *   avatarRef.current.setExpression(['smile', 'shadow'], 2.3)
 *   avatarRef.current.resetNeutral()
 */

import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'
import * as PIXI from 'pixi.js'
import { Live2DModel } from 'pixi-live2d-display/cubism4'

// Register PIXI Ticker so Live2D animations update every frame
Live2DModel.registerTicker(PIXI.Ticker)

// Model path relative to dashboard/public/
const MODEL_URL = '/models/hutao/Hu Tao.model3.json'

// Expression tag → .exp3.json filename
// Source: voice-agent/model_parameters.json hotkeys + Hu_Tao__model_for_PC_/ directory
const EXPRESSION_FILES = {
  smile:        'SmileLock.exp3.json',
  sad:          'SadLock.exp3.json',
  angry:        'Angry.exp3.json',
  ghost:        'Ghost.exp3.json',
  ghost_nervous:'GhostChange.exp3.json',
  shadow:       'Shadow.exp3.json',
  pupil_shrink: 'PupilShrink.exp3.json',
  eyeshine_off: 'EyeshineOff.exp3.json',
}

export const AvatarRenderer = forwardRef(function AvatarRenderer(props, ref) {
  const { width = 400, height = 600 } = props
  const containerRef = useRef(null)
  const modelRef     = useRef(null)
  const appRef       = useRef(null)
  const mouthOpenRef = useRef(0)   // driven by lip-sync from CallOverlay

  // ── Boot PIXI + load model ────────────────────────────────────────────────
  useEffect(() => {
    let destroyed = false

    const app = new PIXI.Application({
      backgroundAlpha: 0,
      width,
      height,
      antialias: true,
      resolution: window.devicePixelRatio || 2,
      autoDensity: true,
    })
    appRef.current = app
    containerRef.current.appendChild(app.view)

    Live2DModel.from(MODEL_URL, { autoInteract: false }).then((model) => {
      if (destroyed) return   // effect cleaned up before model finished loading
      modelRef.current = model
      app.stage.addChild(model)

      // Full-screen canvas: position her in the left-center third of the viewport.
      // 1.9× height-fit zooms into upper body. Anchor is top-center so head
      // sits at Y=0. X at 30% of the full viewport keeps her off the left edge
      // and out of the way of the right-side controls overlay.
      const logicalW = app.screen.width
      const logicalH = app.screen.height
      const autoScale = (logicalH / model.height) * 1.9
      model.scale.set(autoScale)
      model.anchor.set(0.5, 0.0)
      model.position.set(logicalW * 0.5, 0)

      // ── Idle animation ─────────────────────────────────────────────────────
      // Patch coreModel.update() — the FINAL step before GPU commit.
      // This runs AFTER the motion manager has set its keyframe values, so our
      // params always overwrite whatever the motion manager tried to set.
      // (Patching internalModel.update earlier didn't work because origUpdate
      // runs the motion manager which overwrites our values before coreModel.update.)
      const core = model.internalModel.coreModel
      let lastMs = performance.now()
      const clamp = (v, lo, hi) => v < lo ? lo : v > hi ? hi : v

      // ── Completely separate timers — blink and saccade never share state ──
      let blinkTimer = 0, blinkPhase = 0, nextBlink = 2 + Math.random() * 4
      let saccadeTimer = 0, nextSaccade = 1 + Math.random() * 2
      // Eye movement: lerp slowly to target — eliminates all twitching
      let eyeTargetX = 0, eyeTargetY = 0, eyeX = 0, eyeY = 0

      // ── Mood: confirmed param IDs from Hu Tao.cdi3.json ──────────────────
      // ParamMouthForm, ParamBrowLForm/RForm, Param37 (Brows Raise),
      // ParamEyeLSmile/RSmile (eye squint) all exist in this model.
      let moodTimer = 0, nextMoodChange = 3 + Math.random() * 4
      let mouthFormT = 0,  mouthFormC = 0
      let browFormT  = 0,  browFormC  = 0    // L/R brow curve (happy=up, frown=down)
      let browRaiseT = 0,  browRaiseC = 0    // Param37: raise both brows
      let eyeSmileT  = 0,  eyeSmileC  = 0    // eye squint when smiling

      function pickMood() {
        const roll = Math.random()
        if (roll < 0.30) {                           // neutral
          mouthFormT = 0;    browFormT = 0;    browRaiseT = 0;    eyeSmileT = 0
        } else if (roll < 0.60) {                    // happy / cute smile
          mouthFormT = 0.55 + Math.random() * 0.35
          browFormT  = 0.35; browRaiseT = 0.4; eyeSmileT = 0.45
        } else if (roll < 0.80) {                    // thinking — look up
          mouthFormT = -0.1; browFormT = 0.1; browRaiseT = 0.2; eyeSmileT = 0
          eyeTargetY = 0.45 + Math.random() * 0.3   // deliberate upward glance
          nextSaccade = saccadeTimer + 2.8           // hold it
        } else {                                     // excited — big smile, raised brows
          mouthFormT = 0.9;  browFormT = 0.5; browRaiseT = 0.7; eyeSmileT = 0.25
        }
        nextMoodChange = 3 + Math.random() * 5
      }

      const origCoreUpdate = core.update.bind(core)
      core.update = function () {
        const now = performance.now() / 1000
        const elapsed = Math.min((performance.now() - lastMs) / 1000, 0.1)
        lastMs = performance.now()

        // ── Head — more amplitude so turns are clearly visible ─────────────
        core.setParameterValueById('ParamAngleX',     Math.sin(now * 0.31) * 12 + Math.sin(now * 0.73) * 3)
        core.setParameterValueById('ParamAngleY',     Math.sin(now * 0.19) *  5 + Math.sin(now * 0.47) * 2)
        core.setParameterValueById('ParamAngleZ',     Math.sin(now * 0.13) *  5 + Math.sin(now * 0.41) * 2)
        core.setParameterValueById('ParamBodyAngleX', Math.sin(now * 0.28) *  4)
        core.setParameterValueById('ParamBodyAngleZ', Math.sin(now * 0.21) *  3)
        core.setParameterValueById('ParamBreath',     Math.sin(now * 0.9)  * 0.5 + 0.5)
        core.setParameterValueById('ParamMouthOpenY', mouthOpenRef.current)

        // ── Mood tick — fast lerp so changes are clearly visible ───────────
        moodTimer += elapsed
        if (moodTimer >= nextMoodChange) { moodTimer = 0; pickMood() }
        const lm = elapsed * 4   // reach target in ~0.5s
        mouthFormC += (mouthFormT - mouthFormC) * lm
        browFormC  += (browFormT  - browFormC)  * lm
        browRaiseC += (browRaiseT - browRaiseC) * lm
        eyeSmileC  += (eyeSmileT  - eyeSmileC)  * lm
        core.setParameterValueById('ParamMouthForm', mouthFormC)
        core.setParameterValueById('ParamBrowLForm', browFormC)
        core.setParameterValueById('ParamBrowRForm', browFormC)
        core.setParameterValueById('Param37',        browRaiseC)  // Brows Raise
        core.setParameterValueById('ParamEyeLSmile', eyeSmileC)
        core.setParameterValueById('ParamEyeRSmile', eyeSmileC)

        // ── Eye saccades — own timer, slow lerp (no twitching) ────────────
        saccadeTimer += elapsed
        if (saccadeTimer >= nextSaccade) {
          eyeTargetX = (Math.random() * 2 - 1) * 0.65
          const r = Math.random()
          if      (r < 0.20) eyeTargetY =  0.5 + Math.random() * 0.35  // look up
          else if (r < 0.35) eyeTargetY = -0.3 - Math.random() * 0.25  // look down (shy)
          else               eyeTargetY = (Math.random() * 2 - 1) * 0.4
          nextSaccade = saccadeTimer + 1.5 + Math.random() * 2.5
        }
        // lerp speed 3.5 — eyes drift naturally, never snap or twitch
        eyeX += (eyeTargetX - eyeX) * elapsed * 3.5
        eyeY += (eyeTargetY - eyeY) * elapsed * 3.5
        core.setParameterValueById('ParamEyeBallX', clamp(eyeX, -1, 1))
        core.setParameterValueById('ParamEyeBallY', clamp(eyeY, -1, 1))

        // ── Blink — own timer, stays within 0–1 always ────────────────────
        blinkTimer += elapsed
        const bspd = 9
        if (blinkPhase === 0 && blinkTimer >= nextBlink) { blinkPhase = 1; blinkTimer = 0 }
        if (blinkPhase === 1) {
          const v = clamp(1 - blinkTimer * bspd, 0, 1)
          core.setParameterValueById('ParamEyeLOpen', v)
          core.setParameterValueById('ParamEyeROpen', v)
          if (v <= 0) { blinkPhase = 2; blinkTimer = 0 }
        } else if (blinkPhase === 2) {
          const v = clamp(blinkTimer * bspd, 0, 1)
          core.setParameterValueById('ParamEyeLOpen', v)
          core.setParameterValueById('ParamEyeROpen', v)
          if (v >= 1) { blinkPhase = 0; blinkTimer = 0; nextBlink = 3 + Math.random() * 5 }
        } else {
          core.setParameterValueById('ParamEyeLOpen', 1)
          core.setParameterValueById('ParamEyeROpen', 1)
        }

        origCoreUpdate()
      }

      model._origCoreUpdate = origCoreUpdate
    }).catch((err) => {
      console.error('[AvatarRenderer] Failed to load Live2D model:', err)
    })

    return () => {
      destroyed = true
      if (modelRef.current?._origCoreUpdate)
        modelRef.current.internalModel.coreModel.update = modelRef.current._origCoreUpdate
      appRef.current = null
      modelRef.current = null
      app.destroy(true)
    }
  }, []) // intentionally empty — only run once on mount

  // ── Imperative API ────────────────────────────────────────────────────────
  useImperativeHandle(ref, () => ({
    /**
     * Apply one or more expression tags for `duration` seconds,
     * then auto-reset to the default idle expression.
     * @param {string[]} names   - e.g. ['smile', 'shadow']
     * @param {number}   duration - seconds before auto-reset
     */
    setExpression(names, duration) {
      const model = modelRef.current
      if (!model) return

      for (const name of names) {
        const file = EXPRESSION_FILES[name]
        if (file) {
          model.expression(file)
        }

        // Parameter-based expressions (using actual Cubism 4 IDs from cdi3.json)
        if (name === 'wink') {
          const c = model.internalModel.coreModel
          c.setParameterValueById('ParamEyeLOpen', 0.0)
          c.setParameterValueById('ParamBrowLForm', -1.0)
          c.setParameterValueById('ParamMouthForm', 1.0)
        }
        if (name === 'tongue') {
          const c = model.internalModel.coreModel
          c.setParameterValueById('ParamMouthOpenY', 1.0)
          c.setParameterValueById('ParamMouthForm', -1.0)
        }
      }

      // Schedule auto-reset after the audio segment finishes
      setTimeout(() => {
        modelRef.current?.expression()   // no-arg = reset to default
      }, duration * 1000)
    },

    /**
     * Directly set a Live2D parameter by ID.
     * Useful for lip-sync or head-tracking integrations.
     */
    setParameter(name, value) {
      modelRef.current?.internalModel.coreModel.setParameterValueById(name, value)
    },

    /** Immediately reset to default idle expression. */
    resetNeutral() {
      modelRef.current?.expression()
    },

    /**
     * Drive mouth open from audio amplitude (0–1).
     * Called each animation frame by CallOverlay's Web Audio analyser.
     */
    setMouthOpen(v) {
      mouthOpenRef.current = Math.max(0, Math.min(1, v))
    },
  }), [])

  return (
    <div
      ref={containerRef}
      style={{ width, height, display: 'block', overflow: 'hidden' }}
    />
  )
})
