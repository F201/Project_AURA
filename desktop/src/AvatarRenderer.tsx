/**
 * AvatarRenderer — desktop version (TypeScript)
 * Same logic as dashboard/src/components/AvatarRenderer.jsx but typed.
 * Renders the Hu Tao Live2D model on a transparent canvas and exposes
 * an imperative ref API for expression control.
 */

import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'
import * as PIXI from 'pixi.js'
import { Live2DModel } from 'pixi-live2d-display'

const MODEL_URL = './models/hutao/Hu Tao.model3.json'

// Expression tag → .exp3.json filename
const EXPRESSION_FILES: Record<string, string> = {
  smile:        'SmileLock.exp3.json',
  sad:          'SadLock.exp3.json',
  angry:        'Angry.exp3.json',
  ghost:        'Ghost.exp3.json',
  ghost_nervous:'GhostChange.exp3.json',
  shadow:       'Shadow.exp3.json',
  pupil_shrink: 'PupilShrink.exp3.json',
  eyeshine_off: 'EyeshineOff.exp3.json',
}

export interface AvatarHandle {
  setExpression(names: string[], duration: number): void
  setParameter(name: string, value: number): void
  resetNeutral(): void
}

interface Props {
  width?:  number
  height?: number
  scale?:  number
}

export const AvatarRenderer = forwardRef<AvatarHandle, Props>(
  function AvatarRenderer({ width = 400, height = 580, scale = 0.3 }, ref) {
    const canvasRef = useRef<HTMLCanvasElement>(null)
    const modelRef  = useRef<any>(null)
    const appRef    = useRef<PIXI.Application | null>(null)

    useEffect(() => {
      const app = new PIXI.Application({
        view:            canvasRef.current!,
        backgroundAlpha: 0,
        width,
        height,
        antialias:       true,
      })
      appRef.current = app

      Live2DModel.from(MODEL_URL, { autoInteract: false }).then((model) => {
        modelRef.current = model
        app.stage.addChild(model as any)
        model.scale.set(scale)
        model.anchor.set(0.5, 1.0)
        model.position.set(app.renderer.width / 2, app.renderer.height)
      }).catch((err: Error) => {
        console.error('[AvatarRenderer] Failed to load Live2D model:', err)
      })

      return () => {
        appRef.current = null
        modelRef.current = null
        app.destroy(false)
      }
    }, [])

    useImperativeHandle(ref, () => ({
      setExpression(names, duration) {
        const model = modelRef.current
        if (!model) return

        for (const name of names) {
          const file = EXPRESSION_FILES[name]
          if (file) model.expression(file)

          if (name === 'wink') {
            const c = model.internalModel.coreModel
            c.setParameterValueById('EyeOpenLeft', 0.0)
            c.setParameterValueById('BrowLeftY',   0.0)
            c.setParameterValueById('MouthSmile',  1.0)
          }
          if (name === 'tongue') {
            const c = model.internalModel.coreModel
            c.setParameterValueById('MouthOpen',  1.0)
            c.setParameterValueById('TongueOut',  1.0)
            c.setParameterValueById('MouthSmile', 0.0)
          }
        }

        setTimeout(() => modelRef.current?.expression(), duration * 1000)
      },

      setParameter(name, value) {
        modelRef.current?.internalModel.coreModel.setParameterValueById(name, value)
      },

      resetNeutral() {
        modelRef.current?.expression()
      },
    }), [])

    return (
      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        style={{ display: 'block' }}
      />
    )
  }
)
