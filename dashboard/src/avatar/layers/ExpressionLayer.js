import { EXPRESSION_DESCRIPTORS } from '../ExpressionDescriptors.js'
import { EXPRESSION_FADE_TIMES, DEFAULT_FADE } from '../ExpressionFadeTimes.js'

const MODEL_BASE = '/models/hutao/'

export class ExpressionLayer {
  constructor(bus, expressionFiles) {
    this._bus = bus
    this._expressionFiles = expressionFiles

    this._activeParams = []
    this._fadeIn = 1
    this._fadeInDuration = DEFAULT_FADE
    this._fadeOutDuration = DEFAULT_FADE
    this._fadeOut = 1
    this._fadingOut = false
    this._active = false
    this._timer = null
    this._fadeOutTimer = null
    this._seq = 0   // incremented to cancel stale async loads
    this._winkActive = false
    this._winkElapsed = 0
  }

  async setExpression(names, duration) {
    const seq = ++this._seq
    this._cancel()

    const allParams = []
    let fade = DEFAULT_FADE

    for (const name of names) {
      // Static descriptor takes priority over file lookup
      if (EXPRESSION_DESCRIPTORS[name]) {
        if (name === 'wink') {
          this._winkActive = true
          this._winkElapsed = 0
          continue
        }
        allParams.push(...EXPRESSION_DESCRIPTORS[name].Parameters)
        continue
      }
      const file = this._expressionFiles[name]
      if (!file) continue
      try {
        const resp = await fetch(MODEL_BASE + file)
        if (seq !== this._seq) return
        const desc = await resp.json()
        if (seq !== this._seq) return
        if (Array.isArray(desc.Parameters)) allParams.push(...desc.Parameters)
        const baseName = file.replace('.exp3.json', '')
        if (EXPRESSION_FADE_TIMES[baseName] != null) {
          fade = Math.max(fade, EXPRESSION_FADE_TIMES[baseName])
        }
      } catch {
        // fetch errors are non-fatal; expression simply has no params from this file
      }
    }

    if (seq !== this._seq) return

    this._activeParams = allParams
    this._fadeInDuration = fade
    this._fadeOutDuration = fade
    this._fadeIn = 0
    this._fadeOut = 1
    this._fadingOut = false
    this._active = true

    this._timer = setTimeout(() => {
      if (seq !== this._seq) return
      this._fadingOut = true
      this._fadeOutTimer = setTimeout(() => {
        if (seq !== this._seq) return
        this._active = false
        this._bus.clearProvider('expression')
      }, fade * 1000)
    }, duration * 1000)
  }

  update(elapsed) {
    if (this._winkActive) {
      this._winkElapsed += elapsed
      let eyeValue, browValue, mouthSmileValue

      if (this._winkElapsed < 0.16) {
        const progress = this._winkElapsed / 0.16
        eyeValue = 1.0 - progress
        browValue = -progress
        mouthSmileValue = progress
      } else if (this._winkElapsed < 0.31) {
        eyeValue = 0.0
        browValue = -1.0
        mouthSmileValue = 1.0
      } else if (this._winkElapsed < 0.51) {
        const progress = (this._winkElapsed - 0.31) / 0.20
        eyeValue = progress
        browValue = -1.0 + progress
        mouthSmileValue = 1.0 - progress
      } else {
        this._winkActive = false
      }

      if (this._winkActive) {
        this._bus.write('ParamEyeLOpen', eyeValue, 'expression', 'Override')
        this._bus.write('ParamBrowLForm', browValue, 'expression', 'Override')
        this._bus.write('ParamMouthForm', mouthSmileValue, 'expression', 'Override')
      }
    }

    if (!this._active || this._activeParams.length === 0) return

    let scale
    if (!this._fadingOut) {
      this._fadeIn = Math.min(this._fadeIn + elapsed / this._fadeInDuration, 1)
      scale = this._fadeIn
    } else {
      this._fadeOut = Math.max(this._fadeOut - elapsed / this._fadeOutDuration, 0)
      scale = this._fadeOut
    }

    for (const p of this._activeParams) {
      // Blend-aware fade: Multiply expressions interpolate toward neutral (1.0), not toward 0.
      const fadedValue = p.Blend === 'Multiply'
        ? 1.0 + (p.Value - 1.0) * scale
        : p.Value * scale
      this._bus.write(p.Id, fadedValue, 'expression', p.Blend ?? 'Override')
    }
  }

  get isActive() { return this._active }

  clear() {
    ++this._seq
    this._cancel()
  }

  _cancel() {
    clearTimeout(this._timer)
    clearTimeout(this._fadeOutTimer)
    this._active = false
    this._winkActive = false
    this._bus.clearProvider('expression')
  }
}
