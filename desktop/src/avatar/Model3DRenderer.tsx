/**
 * Model3DRenderer — Plug-and-Play Three.js VRM / GLB 3D Avatar Renderer
 * Drop any .vrm or .glb model into desktop/public/models/3d/ and switch
 * seamlessly between Live2D and 3D with spring bones, lip-sync, expressions, and cursor gaze.
 */
import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm'

import { AvatarHandle } from '../types'

interface Props {
  modelUrl: string | null
  width: number
  height: number
  onHoverAvatar: (hovering: boolean) => void
  onTouch: (kind: 'headpat' | 'poke' | 'shake') => void
  onOpenFolder: () => void
  onSwitchTo2D: () => void
}

const EMOTION_TO_VRM: Record<string, string> = {
  SmileLock: 'happy',
  smile: 'happy',
  blush: 'happy',
  wink: 'happy',
  Angry: 'angry',
  angry: 'angry',
  pouting: 'angry',
  SadLock: 'sad',
  sad: 'sad',
  pleading: 'sad',
  PupilShrink: 'surprised',
  pupil_shrink: 'surprised',
  Ghost: 'surprised',
  ghost: 'surprised',
  GhostChange: 'surprised',
  EyeshineOff: 'relaxed',
  eyeshine_off: 'relaxed',
}

export const Model3DRenderer = forwardRef<AvatarHandle, Props>(function Model3DRenderer(
  { modelUrl, width, height, onHoverAvatar, onTouch, onOpenFolder, onSwitchTo2D },
  ref
) {
  const mountRef = useRef<HTMLDivElement>(null)
  const vrmRef = useRef<any>(null)
  const mouthRef = useRef(0)
  const lookRef = useRef({ x: 0, y: 0 })
  const exprRef = useRef<{ name: string; until: number }>({ name: '', until: 0 })
  const dragRef = useRef({ dragging: false, lastX: 0, lastY: 0, dist: 0 })
  const [loadError, setLoadError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useImperativeHandle(
    ref,
    () => ({
      setExpression(names, duration) {
        const mapped = names.map((n) => EMOTION_TO_VRM[n]).find(Boolean) || 'happy'
        exprRef.current = { name: mapped, until: performance.now() + duration * 1000 }
      },
      setSpeaking() {},
      setMouthOpen(v) {
        mouthRef.current = v
      },
      setCursorLook(nx, ny) {
        lookRef.current = { x: nx, y: ny }
      },
      setDragImpulse() {},
      setHeadpatActive() {},
      resetNeutral() {
        exprRef.current = { name: '', until: 0 }
      },
    }),
    []
  )

  useEffect(() => {
    const container = mountRef.current
    if (!container || !modelUrl) return

    setLoadError(null)
    if (modelUrl.toLowerCase().endsWith('.pmx')) {
      setLoadError(
        'PMX detected. Convert to .vrm via Blender + VRM Add-on for full expressions & spring physics, then place the .vrm in the 3D folder.'
      )
      return
    }

    setLoading(true)
    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(28, width / height, 0.1, 20)
    camera.position.set(0, 1.32, 2.35)

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.setSize(width, height)
    renderer.setClearColor(0x000000, 0)
    container.innerHTML = ''
    container.appendChild(renderer.domElement)

    const hemi = new THREE.HemisphereLight(0xf8fafc, 0x1e1b4b, 1.35)
    scene.add(hemi)
    const dir = new THREE.DirectionalLight(0xffffff, 1.1)
    dir.position.set(1.5, 2.5, 2.0)
    scene.add(dir)

    const loader = new GLTFLoader()
    loader.register((parser) => new VRMLoaderPlugin(parser))

    let cancelled = false
    let rafId = 0

    loader.load(
      modelUrl,
      (gltf) => {
        if (cancelled) return
        setLoading(false)
        const vrm = gltf.userData.vrm
        if (vrm) {
          VRMUtils.removeUnnecessaryVertices(gltf.scene)
          VRMUtils.combineSkeletons(gltf.scene)
          VRMUtils.rotateVRM0(vrm)
          vrmRef.current = vrm
          scene.add(vrm.scene)
        } else {
          const box = new THREE.Box3().setFromObject(gltf.scene)
          const size = box.getSize(new THREE.Vector3())
          const scale = 1.55 / Math.max(size.y, 0.001)
          gltf.scene.scale.setScalar(scale)
          gltf.scene.position.y = -box.min.y * scale
          scene.add(gltf.scene)
        }
      },
      undefined,
      (err) => {
        if (!cancelled) {
          setLoading(false)
          setLoadError(`Could not load 3D model: ${err instanceof Error ? err.message : String(err)}`)
        }
      }
    )

    const clock = new THREE.Clock()
    let blinkTimer = 0
    let nextBlink = 3.2

    const animate = () => {
      rafId = requestAnimationFrame(animate)
      const dt = Math.min(clock.getDelta(), 0.08)
      const t = clock.elapsedTime
      const vrm = vrmRef.current

      if (vrm) {
        const head = vrm.humanoid?.getNormalizedBoneNode('head')
        if (head) {
          head.rotation.y = THREE.MathUtils.lerp(head.rotation.y, lookRef.current.x * 0.35, dt * 6)
          head.rotation.x = THREE.MathUtils.lerp(head.rotation.x, -lookRef.current.y * 0.2, dt * 6)
          head.rotation.z = Math.sin(t * 0.9) * 0.04
        }
        const spine = vrm.humanoid?.getNormalizedBoneNode('spine')
        if (spine) {
          spine.rotation.x = Math.sin(t * 1.4) * 0.015
        }

        const em = vrm.expressionManager
        if (em) {
          em.setValue('aa', Math.min(1, mouthRef.current * 1.1))

          blinkTimer += dt
          const blinkVal = blinkTimer > nextBlink && blinkTimer < nextBlink + 0.14 ? 1 : 0
          if (blinkTimer >= nextBlink + 0.14) {
            blinkTimer = 0
            nextBlink = 2.6 + Math.random() * 3.5
          }
          em.setValue('blink', blinkVal)

          const now = performance.now()
          for (const key of ['happy', 'angry', 'sad', 'surprised', 'relaxed']) {
            const active = exprRef.current.name === key && now < exprRef.current.until
            em.setValue(key, active ? 0.9 : 0)
          }
        }

        vrm.update(dt)
      }

      renderer.render(scene, camera)
    }
    animate()

    return () => {
      cancelled = true
      cancelAnimationFrame(rafId)
      vrmRef.current = null
      renderer.dispose()
    }
  }, [modelUrl, width, height])

  if (!modelUrl || loadError) {
    return (
      <div
        onMouseEnter={() => onHoverAvatar(true)}
        onMouseLeave={() => onHoverAvatar(false)}
        style={{
          width,
          height,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 20,
        }}
      >
        <div
          style={{
            background: 'rgba(15, 18, 32, 0.92)',
            border: '1px solid rgba(129, 140, 248, 0.45)',
            borderRadius: 18,
            padding: 18,
            textAlign: 'center',
            backdropFilter: 'blur(12px)',
            boxShadow: '0 14px 40px rgba(0,0,0,0.55)',
          }}
        >
          <div style={{ fontSize: 15, fontWeight: 700, color: '#a5b4fc', marginBottom: 8 }}>
            3D VRM / GLB Stage Ready
          </div>
          <p style={{ fontSize: 12, lineHeight: 1.5, color: '#cbd5e1', marginBottom: 14 }}>
            {loadError ||
              'Drop any .vrm or .glb 3D avatar into the 3D models folder (e.g. VRoid Studio or Blender VRM export) and AURA will load it automatically with lip-sync, blinking, and expressions.'}
          </p>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
            <button
              onClick={onOpenFolder}
              style={{
                background: '#4f46e5',
                color: '#fff',
                border: 'none',
                borderRadius: 10,
                padding: '7px 12px',
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Open 3D Folder
            </button>
            <button
              onClick={onSwitchTo2D}
              style={{
                background: 'rgba(255,255,255,0.12)',
                color: '#fff',
                border: '1px solid rgba(255,255,255,0.18)',
                borderRadius: 10,
                padding: '7px 12px',
                fontSize: 12,
                cursor: 'pointer',
              }}
            >
              Back to Live2D
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div
      ref={mountRef}
      onMouseEnter={() => onHoverAvatar(true)}
      onMouseLeave={() => {
        if (!dragRef.current.dragging) onHoverAvatar(false)
      }}
      onPointerDown={(e) => {
        e.currentTarget.setPointerCapture(e.pointerId)
        dragRef.current = { dragging: true, lastX: e.screenX, lastY: e.screenY, dist: 0 }
      }}
      onPointerMove={(e) => {
        if (!dragRef.current.dragging) return
        const dx = e.screenX - dragRef.current.lastX
        const dy = e.screenY - dragRef.current.lastY
        dragRef.current.lastX = e.screenX
        dragRef.current.lastY = e.screenY
        dragRef.current.dist += Math.hypot(dx, dy)
        window.auraDesktop?.moveWindowBy(dx, dy)
      }}
      onPointerUp={(e) => {
        if (!dragRef.current.dragging) return
        try {
          e.currentTarget.releasePointerCapture(e.pointerId)
        } catch { /* ignore */ }
        const clicked = dragRef.current.dist < 6
        dragRef.current.dragging = false
        if (clicked) onTouch('headpat')
      }}
      style={{ width, height, position: 'relative', cursor: 'grab' }}
    >
      {loading && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 12,
            color: '#c7d2fe',
          }}
        >
          Loading 3D avatar…
        </div>
      )}
    </div>
  )
})
