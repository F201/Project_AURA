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

/**
 * Per-expression Cubism 4 parameter overrides.
 * Applied smoothly every frame in coreModel.update() to flawlessly
 * override the base idle animation values.
 */
const EXPRESSION_OVERRIDES = {
  smile: { ParamMouthForm: 1.0, ParamEyeLSmile: 0.9, ParamEyeRSmile: 0.9, Param37: 0.4 },
  sad: { ParamMouthForm: -1.0, ParamBrowLForm: -1.0, ParamBrowRForm: -1.0, ParamBrowLAngle: 0.75, ParamBrowRAngle: 0.75 },
  angry: { ParamMouthForm: -0.5, ParamEyeRSmile: 0.0, ParamEyeLSmile: 0.0, ParamBrowLAngle: -1.0, ParamBrowRAngle: -1.0, ParamBrowRForm: -0.5, ParamBrowLForm: -0.5 },
  ghost: { Param80: 1.0 },
  ghost_nervous: { Param75: 1.0 },
  shadow: { Param2: 1.0 },
  pupil_shrink: { Param38: 1.0 },
  eyeshine_off: { Param3: 1.0 },
  wink: { ParamEyeLOpen: 0.0, ParamEyeLSmile: 1.0, ParamBrowLForm: 0.5, ParamMouthForm: 0.5 },
  tongue: { Param70: 1.0, ParamMouthForm: -1.0 },  // Param70 = TongueOut mesh
}

export const AvatarRenderer = forwardRef(function AvatarRenderer(props, ref) {
  const { width = 400, height = 600 } = props
  const containerRef = useRef(null)
  const modelRef = useRef(null)
  const appRef = useRef(null)
  const mouthOpenRef = useRef(0)             // driven by lip-sync
  const expressionOverrideRef = useRef(null)          // null = idle; {} = active override

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
      const core = model.internalModel.coreModel
      let lastMs = performance.now()
      const clamp = (v, lo, hi) => v < lo ? lo : v > hi ? hi : v

      // ── Completely separate timers ──
      let blinkTimer = 0, blinkPhase = 0, nextBlink = 2 + Math.random() * 4
      let saccadeTimer = 0, nextSaccade = 1 + Math.random() * 2
      let eyeTargetX = 0, eyeTargetY = 0, eyeX = 0, eyeY = 0

      // ── Mood timers ──────────────────
      let moodTimer = 0, nextMoodChange = 3 + Math.random() * 4
      let mouthFormT = 0, mouthFormC = 0
      let browFormT = 0, browFormC = 0    // L/R brow curve (happy=up, frown=down)
      let browRaiseT = 0, browRaiseC = 0    // Param37: raise both brows
      let eyeSmileT = 0, eyeSmileC = 0    // eye squint when smiling

      function pickMood() {
        const roll = Math.random()
        if (roll < 0.30) {                           // neutral
          mouthFormT = 0; browFormT = 0; browRaiseT = 0; eyeSmileT = 0
        } else if (roll < 0.60) {                    // happy / cute smile
          mouthFormT = 0.55 + Math.random() * 0.35
          browFormT = 0.35; browRaiseT = 0.4; eyeSmileT = 0.45
        } else if (roll < 0.80) {                    // thinking — look up
          mouthFormT = -0.1; browFormT = 0.1; browRaiseT = 0.2; eyeSmileT = 0
          eyeTargetY = 0.45 + Math.random() * 0.3   // deliberate upward glance
          nextSaccade = saccadeTimer + 2.8           // hold it
        } else {                                     // excited — big smile, raised brows
          mouthFormT = 0.9; browFormT = 0.5; browRaiseT = 0.7; eyeSmileT = 0.25
        }
        nextMoodChange = 3 + Math.random() * 5
      }

      // ── Expression Overrides State ─────────────────────────────────────────
      const currentOverrides = {}

      const origCoreUpdate = core.update.bind(core)
      core.update = function () {
        const now = performance.now() / 1000
        const elapsed = Math.min((performance.now() - lastMs) / 1000, 0.1)
        lastMs = performance.now()

        // ── Head — more amplitude so turns are clearly visible ─────────────
        core.setParameterValueById('ParamAngleX', Math.sin(now * 0.31) * 12 + Math.sin(now * 0.73) * 3)
        core.setParameterValueById('ParamAngleY', Math.sin(now * 0.19) * 5 + Math.sin(now * 0.47) * 2)
        core.setParameterValueById('ParamAngleZ', Math.sin(now * 0.13) * 5 + Math.sin(now * 0.41) * 2)
        core.setParameterValueById('ParamBodyAngleX', Math.sin(now * 0.28) * 4)
        core.setParameterValueById('ParamBodyAngleZ', Math.sin(now * 0.21) * 3)
        core.setParameterValueById('ParamBreath', Math.sin(now * 0.9) * 0.5 + 0.5)
        core.setParameterValueById('ParamMouthOpenY', mouthOpenRef.current)

        // ── Mood tick ───────────
        moodTimer += elapsed
        if (moodTimer >= nextMoodChange) { moodTimer = 0; pickMood() }
        const lm = elapsed * 4   // reach target in ~0.5s
        mouthFormC += (mouthFormT - mouthFormC) * lm
        browFormC += (browFormT - browFormC) * lm
        browRaiseC += (browRaiseT - browRaiseC) * lm
        eyeSmileC += (eyeSmileT - eyeSmileC) * lm
        core.setParameterValueById('ParamMouthForm', mouthFormC)
        core.setParameterValueById('ParamBrowLForm', browFormC)
        core.setParameterValueById('ParamBrowRForm', browFormC)
        core.setParameterValueById('Param37', browRaiseC)  // Brows Raise
        core.setParameterValueById('ParamEyeLSmile', eyeSmileC)
        core.setParameterValueById('ParamEyeRSmile', eyeSmileC)

        // ── Eye saccades ────────────
        saccadeTimer += elapsed
        if (saccadeTimer >= nextSaccade) {
          eyeTargetX = (Math.random() * 2 - 1) * 0.65
          const r = Math.random()
          if (r < 0.20) eyeTargetY = 0.5 + Math.random() * 0.35  // look up
          else if (r < 0.35) eyeTargetY = -0.3 - Math.random() * 0.25  // look down (shy)
          else eyeTargetY = (Math.random() * 2 - 1) * 0.4
          nextSaccade = saccadeTimer + 1.5 + Math.random() * 2.5
        }
        // lerp speed 3.5 — eyes drift naturally, never snap or twitch
        eyeX += (eyeTargetX - eyeX) * elapsed * 3.5
        eyeY += (eyeTargetY - eyeY) * elapsed * 3.5
        core.setParameterValueById('ParamEyeBallX', clamp(eyeX, -1, 1))
        core.setParameterValueById('ParamEyeBallY', clamp(eyeY, -1, 1))

        // ── Blink ────────────────────
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

        // ── Expression overrides ─────────
        const targetOv = expressionOverrideRef.current

        const overrideKeys = new Set([...Object.keys(currentOverrides), ...(targetOv ? Object.keys(targetOv) : [])])
        const lerpSpeed = elapsed * 5

        for (const id of overrideKeys) {
          let targetVal = 0
          let isIdleParam = false

          // Intercept parameters that the idle animation normally controls
          if (id === 'ParamMouthForm') { isIdleParam = true; targetVal = mouthFormC; }
          else if (id === 'ParamBrowLForm' || id === 'ParamBrowRForm') { isIdleParam = true; targetVal = browFormC; }
          else if (id === 'Param37') { isIdleParam = true; targetVal = browRaiseC; }
          else if (id === 'ParamEyeLSmile' || id === 'ParamEyeRSmile') { isIdleParam = true; targetVal = eyeSmileC; }
          else if (id === 'ParamEyeLOpen' || id === 'ParamEyeROpen') { isIdleParam = true; targetVal = core.getParameterValueById(id); } // Read blink value right before overriding

          if (targetOv && targetOv[id] !== undefined) {
            targetVal = targetOv[id]
          }

          if (currentOverrides[id] === undefined) {
            currentOverrides[id] = isIdleParam ? targetVal : 0;
          }

          currentOverrides[id] += (targetVal - currentOverrides[id]) * lerpSpeed
          core.setParameterValueById(id, currentOverrides[id])
        }

        // Special condition: TongueOut needs minimum mouth open to be visible
        if (currentOverrides['Param70'] > 0) {
          const currentMouth = core.getParameterValueById('ParamMouthOpenY')
          core.setParameterValueById('ParamMouthOpenY', Math.max(currentMouth, currentOverrides['Param70'] * 0.4))
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

      const merged = {}
      for (const name of names) {
        // Merge param overrides — held every frame until reset
        const overrides = EXPRESSION_OVERRIDES[name]
        if (overrides) Object.assign(merged, overrides)
      }
      expressionOverrideRef.current = Object.keys(merged).length > 0 ? merged : null

      setTimeout(() => {
        expressionOverrideRef.current = null
      }, duration * 1000)
    },

    /**
     * Directly set a Live2D parameter by ID.
     * Useful for lip-sync or head-tracking integrations.
     */
    setParameter(name, value) {
      modelRef.current?.internalModel.coreModel.setParameterValueById(name, value)
    },

    resetNeutral() {
      expressionOverrideRef.current = null
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
