import {
  DEFAULT_FADE,
  EXPRESSION_DESCRIPTORS,
  EXPRESSION_FADE_TIMES,
  ExpressionParam,
  RESETTABLE_EXPRESSION_PARAMS,
} from '../ExpressionDescriptors'
import { ParameterBus } from '../ParameterBus'

const MODEL_BASE = './models/hutao/'

export class ExpressionLayer {
  private _bus: ParameterBus
  private _expressionFiles: Record<string, string>
  private _activeParams: ExpressionParam[] = []
  private _fadeIn = 1
  private _fadeInDuration = DEFAULT_FADE
  private _fadeOutDuration = DEFAULT_FADE
  private _fadeOut = 1
  private _fadingOut = false
  private _active = false
  private _timer: ReturnType<typeof setTimeout> | null = null
  private _fadeOutTimer: ReturnType<typeof setTimeout> | null = null
  private _seq = 0
  private _winkActive = false
  private _winkElapsed = 0

  constructor(bus: ParameterBus, expressionFiles: Record<string, string>) {
    this._bus = bus
    this._expressionFiles = expressionFiles
  }

  async setExpression(names: string[], duration: number): Promise<void> {
    const seq = ++this._seq
    this._cancel()

    const allParams: ExpressionParam[] = []
    let fade = DEFAULT_FADE

    for (const name of names) {
      if (EXPRESSION_DESCRIPTORS[name]) {
        if (name === 'wink') {
          this._winkActive = true
          this._winkElapsed = 0
          continue
        }
        allParams.push(...EXPRESSION_DESCRIPTORS[name].Parameters)
        if (EXPRESSION_FADE_TIMES[name] != null) {
          fade = Math.max(fade, EXPRESSION_FADE_TIMES[name])
        }
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
        /* ignore fetch error */
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
    }, Math.max(0.8, duration) * 1000)
  }

  update(elapsed: number): void {
    if (this._winkActive) {
      this._winkElapsed += elapsed
      let eyeValue = 1
      let browValue = 0
      let mouthSmileValue = 0

      if (this._winkElapsed < 0.16) {
        const p = this._winkElapsed / 0.16
        eyeValue = 1 - p
        browValue = -p
        mouthSmileValue = p
      } else if (this._winkElapsed < 0.34) {
        eyeValue = 0
        browValue = -1
        mouthSmileValue = 1
      } else if (this._winkElapsed < 0.56) {
        const p = (this._winkElapsed - 0.34) / 0.22
        eyeValue = p
        browValue = -1 + p
        mouthSmileValue = 1 - p
      } else {
        this._winkActive = false
      }

      if (this._winkActive) {
        this._bus.write('ParamEyeLOpen', eyeValue, 'expression', 'Override')
        this._bus.write('ParamBrowLForm', browValue, 'expression', 'Override')
        this._bus.write('ParamMouthForm', mouthSmileValue, 'expression', 'Override')
      }
    }

    if (!this._active || this._activeParams.length === 0) {
      // Keep toggleable model parameters resting cleanly at 0 when no expression is active
      for (const id of RESETTABLE_EXPRESSION_PARAMS) {
        this._bus.write(id, 0, 'idle', 'Override')
      }
      return
    }

    let scale: number
    if (!this._fadingOut) {
      this._fadeIn = Math.min(this._fadeIn + elapsed / this._fadeInDuration, 1)
      scale = this._fadeIn
    } else {
      this._fadeOut = Math.max(this._fadeOut - elapsed / this._fadeOutDuration, 0)
      scale = this._fadeOut
    }

    const activeIds = new Set(this._activeParams.map((p) => p.Id))
    for (const id of RESETTABLE_EXPRESSION_PARAMS) {
      if (!activeIds.has(id)) {
        this._bus.write(id, 0, 'idle', 'Override')
      }
    }

    for (const p of this._activeParams) {
      const blend = p.Blend ?? 'Override'
      const fadedValue = blend === 'Multiply' ? 1.0 + (p.Value - 1.0) * scale : p.Value * scale
      this._bus.write(p.Id, fadedValue, 'expression', blend)
    }
  }

  clear(): void {
    ++this._seq
    this._cancel()
  }

  private _cancel(): void {
    if (this._timer) clearTimeout(this._timer)
    if (this._fadeOutTimer) clearTimeout(this._fadeOutTimer)
    this._active = false
    this._winkActive = false
    this._bus.clearProvider('expression')
  }
}
