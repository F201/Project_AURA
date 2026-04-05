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

let sharedApp = null
let sharedModelPromise = null
let sharedModel = null
let sharedMouthOpen = 0
let sharedExpressionOverride = null

function initSharedApp(width, height) {
  if (sharedApp) {
    sharedApp.renderer.resize(width, height)
    return
  }

  sharedApp = new PIXI.Application({
    backgroundAlpha: 0,
    width,
    height,
    antialias: true,
    resolution: window.devicePixelRatio || 2,
    autoDensity: true,
  })

  sharedModelPromise = Live2DModel.from(MODEL_URL, { autoInteract: false }).then((model) => {
    sharedModel = model
    sharedApp.stage.addChild(model)

    const logicalW = sharedApp.screen.width
    const logicalH = sharedApp.screen.height
    const autoScale = (logicalH / model.height) * 1.9
    model.scale.set(autoScale)
    model.anchor.set(0.5, 0.0)
    model.position.set(logicalW * 0.5, 0)

    const core = model.internalModel.coreModel
    let lastMs = performance.now()
    const clamp = (v, lo, hi) => v < lo ? lo : v > hi ? hi : v

    let blinkTimer = 0, blinkPhase = 0, nextBlink = 2 + Math.random() * 4
    let saccadeTimer = 0, nextSaccade = 1 + Math.random() * 2
    let eyeTargetX = 0, eyeTargetY = 0, eyeX = 0, eyeY = 0

    let moodTimer = 0, nextMoodChange = 3 + Math.random() * 4
    let mouthFormT = 0, mouthFormC = 0
    let browFormT = 0, browFormC = 0
    let browRaiseT = 0, browRaiseC = 0
    let eyeSmileT = 0, eyeSmileC = 0

    function pickMood() {
      const roll = Math.random()
      if (roll < 0.30) {
        mouthFormT = 0; browFormT = 0; browRaiseT = 0; eyeSmileT = 0
      } else if (roll < 0.60) {
        mouthFormT = 0.55 + Math.random() * 0.35
        browFormT = 0.35; browRaiseT = 0.4; eyeSmileT = 0.45
      } else if (roll < 0.80) {
        mouthFormT = -0.1; browFormT = 0.1; browRaiseT = 0.2; eyeSmileT = 0
        eyeTargetY = 0.45 + Math.random() * 0.3
        nextSaccade = saccadeTimer + 2.8
      } else {
        mouthFormT = 0.9; browFormT = 0.5; browRaiseT = 0.7; eyeSmileT = 0.25
      }
      nextMoodChange = 3 + Math.random() * 5
    }

    const currentOverrides = {}

    sharedApp.ticker.add(() => {
      if (!sharedModel) return
      const now = performance.now() / 1000
      const elapsed = Math.min((performance.now() - lastMs) / 1000, 0.1)
      lastMs = performance.now()

      core.setParameterValueById('ParamAngleX', Math.sin(now * 0.31) * 12 + Math.sin(now * 0.73) * 3)
      core.setParameterValueById('ParamAngleY', Math.sin(now * 0.19) * 5 + Math.sin(now * 0.47) * 2)
      core.setParameterValueById('ParamAngleZ', Math.sin(now * 0.13) * 5 + Math.sin(now * 0.41) * 2)
      core.setParameterValueById('ParamBodyAngleX', Math.sin(now * 0.28) * 4)
      core.setParameterValueById('ParamBodyAngleZ', Math.sin(now * 0.21) * 3)
      core.setParameterValueById('ParamBreath', Math.sin(now * 0.9) * 0.5 + 0.5)
      core.setParameterValueById('ParamMouthOpenY', sharedMouthOpen)

      moodTimer += elapsed
      if (moodTimer >= nextMoodChange) { moodTimer = 0; pickMood() }
      const lm = elapsed * 4
      mouthFormC += (mouthFormT - mouthFormC) * lm
      browFormC += (browFormT - browFormC) * lm
      browRaiseC += (browRaiseT - browRaiseC) * lm
      eyeSmileC += (eyeSmileT - eyeSmileC) * lm
      core.setParameterValueById('ParamMouthForm', mouthFormC)
      core.setParameterValueById('ParamBrowLForm', browFormC)
      core.setParameterValueById('ParamBrowRForm', browFormC)
      core.setParameterValueById('Param37', browRaiseC)
      core.setParameterValueById('ParamEyeLSmile', eyeSmileC)
      core.setParameterValueById('ParamEyeRSmile', eyeSmileC)

      saccadeTimer += elapsed
      if (saccadeTimer >= nextSaccade) {
        eyeTargetX = (Math.random() * 2 - 1) * 0.65
        const r = Math.random()
        if (r < 0.20) eyeTargetY = 0.5 + Math.random() * 0.35
        else if (r < 0.35) eyeTargetY = -0.3 - Math.random() * 0.25
        else eyeTargetY = (Math.random() * 2 - 1) * 0.4
        nextSaccade = saccadeTimer + 1.5 + Math.random() * 2.5
      }
      eyeX += (eyeTargetX - eyeX) * elapsed * 3.5
      eyeY += (eyeTargetY - eyeY) * elapsed * 3.5
      core.setParameterValueById('ParamEyeBallX', clamp(eyeX, -1, 1))
      core.setParameterValueById('ParamEyeBallY', clamp(eyeY, -1, 1))

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

      const targetOv = sharedExpressionOverride

      const overrideKeys = new Set([...Object.keys(currentOverrides), ...(targetOv ? Object.keys(targetOv) : [])])
      const lerpSpeed = elapsed * 5

      for (const id of overrideKeys) {
        let targetVal = 0
        let isIdleParam = false

        if (id === 'ParamMouthForm') { isIdleParam = true; targetVal = mouthFormC; }
        else if (id === 'ParamBrowLForm' || id === 'ParamBrowRForm') { isIdleParam = true; targetVal = browFormC; }
        else if (id === 'Param37') { isIdleParam = true; targetVal = browRaiseC; }
        else if (id === 'ParamEyeLSmile' || id === 'ParamEyeRSmile') { isIdleParam = true; targetVal = eyeSmileC; }
        else if (id === 'ParamEyeLOpen' || id === 'ParamEyeROpen') { isIdleParam = true; targetVal = core.getParameterValueById(id); }

        if (targetOv && targetOv[id] !== undefined) {
          targetVal = targetOv[id]
        }

        if (currentOverrides[id] === undefined) {
          currentOverrides[id] = isIdleParam ? targetVal : 0;
        }

        currentOverrides[id] += (targetVal - currentOverrides[id]) * lerpSpeed
        core.setParameterValueById(id, currentOverrides[id])
      }

      if (currentOverrides['Param70'] > 0) {
        const currentMouth = core.getParameterValueById('ParamMouthOpenY')
        core.setParameterValueById('ParamMouthOpenY', Math.max(currentMouth, currentOverrides['Param70'] * 0.4))
      }
    })
  }).catch((err) => {
    console.error('[AvatarRenderer] Failed to load Live2D model:', err)
  })
}

export const AvatarRenderer = forwardRef(function AvatarRenderer(props, ref) {
  const { width = 400, height = 600 } = props
  const containerRef = useRef(null)

  // ── Boot PIXI + load model ────────────────────────────────────────────────
  useEffect(() => {
    initSharedApp(width, height)

    if (sharedApp && sharedApp.view && containerRef.current) {
      containerRef.current.appendChild(sharedApp.view)
    }

    return () => {
      if (sharedApp && sharedApp.view && containerRef.current && sharedApp.view.parentNode === containerRef.current) {
        containerRef.current.removeChild(sharedApp.view)
      }
    }
  }, [width, height])

  // ── Imperative API ────────────────────────────────────────────────────────
  useImperativeHandle(ref, () => ({
    setExpression(names, duration) {
      if (!sharedModel) return

      const merged = {}
      for (const name of names) {
        const overrides = EXPRESSION_OVERRIDES[name]
        if (overrides) Object.assign(merged, overrides)
      }
      sharedExpressionOverride = Object.keys(merged).length > 0 ? merged : null

      setTimeout(() => {
        sharedExpressionOverride = null
      }, duration * 1000)
    },

    setParameter(name, value) {
      sharedModel?.internalModel.coreModel.setParameterValueById(name, value)
    },

    resetNeutral() {
      sharedExpressionOverride = null
    },

    setMouthOpen(v) {
      sharedMouthOpen = Math.max(0, Math.min(1, v))
    },
  }), [])

  return (
    <div
      ref={containerRef}
      style={{ width, height, display: 'block', overflow: 'hidden' }}
    />
  )
})
