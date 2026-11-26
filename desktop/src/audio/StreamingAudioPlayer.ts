/**
 * Low-Latency Web Audio Streaming PCM Player
 *  1. Uses the OS native AudioContext sample rate (e.g. 48kHz) so Chromium's
 *     resampler converts 24kHz PCM AudioBuffers cleanly without WASAPI/BT crackle.
 *  2. Smart jitter pre-buffer (380ms) coalesces initial PCM chunks for gapless playback
 *     even under GPU contention.
 *  3. 4ms micro fade-in/fade-out ramps on stream edges eliminate clicks and pops.
 */

export class StreamingAudioPlayer {
  private ctx: AudioContext | null = null
  private analyser: AnalyserNode | null = null
  private gainNode: GainNode | null = null
  private nextStartTime = 0
  private activeSources = new Set<AudioBufferSourceNode>()
  private inputSampleRate = 24000
  private rafId: number | null = null
  private timeData: Float32Array<ArrayBuffer> | null = null
  private smoothedMouth = 0
  private onMouthLevel: ((level: number) => void) | null = null
  private onPlaybackState: ((playing: boolean) => void) | null = null
  private isPlaying = false

  // Jitter pre-buffer: hold initial chunks (~380ms) before starting playback
  private pendingChunks: Float32Array[] = []
  private pendingSamples = 0
  private streamStartedPlaying = false
  private readonly prebufferSec = 0.38

  private volume = 0.75
  private sinkId = ''

  constructor(
    onMouthLevel: (level: number) => void,
    onPlaybackState: (playing: boolean) => void
  ) {
    this.onMouthLevel = onMouthLevel
    this.onPlaybackState = onPlaybackState
    try {
      const savedVol = localStorage.getItem('aura_volume')
      if (savedVol !== null) this.volume = Math.max(0, Math.min(1.5, Number(savedVol)))
      const savedSink = localStorage.getItem('aura_sink_id')
      if (savedSink) this.sinkId = savedSink
    } catch { /* ignore */ }
  }

  private ensureContext(): AudioContext {
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext
      // Keep OS native hardware sample rate to prevent Windows WASAPI/Bluetooth crackling
      this.ctx = new AudioCtx()
      if (this.sinkId && typeof (this.ctx as any).setSinkId === 'function') {
        ;(this.ctx as any).setSinkId(this.sinkId).catch(() => {})
      }
      this.analyser = this.ctx.createAnalyser()
      this.analyser.fftSize = 256
      this.analyser.smoothingTimeConstant = 0.45
      this.gainNode = this.ctx.createGain()
      this.gainNode.gain.value = this.volume
      this.gainNode.connect(this.analyser)
      this.analyser.connect(this.ctx.destination)
      this.timeData = new Float32Array(this.analyser.fftSize)
      this.startMeterLoop()
    }
    if (this.ctx.state === 'suspended') {
      this.ctx.resume().catch(() => {})
    }
    return this.ctx
  }

  public beginStream(sampleRate = 24000): void {
    this.inputSampleRate = sampleRate || 24000
    this.ensureContext()
    this.pendingChunks = []
    this.pendingSamples = 0
    this.streamStartedPlaying = false
  }

  public enqueuePcm16(arrayBuffer: ArrayBuffer): void {
    const usableBytes = arrayBuffer.byteLength - (arrayBuffer.byteLength % 2)
    if (usableBytes < 2) return

    const int16 = new Int16Array(arrayBuffer, 0, usableBytes / 2)
    const float32 = new Float32Array(int16.length)
    for (let i = 0; i < int16.length; i++) {
      float32[i] = int16[i] / 32768.0
    }

    this.pendingChunks.push(float32)
    this.pendingSamples += float32.length

    if (!this.streamStartedPlaying) {
      const bufferedSec = this.pendingSamples / this.inputSampleRate
      if (bufferedSec >= this.prebufferSec) {
        this.streamStartedPlaying = true
        this.flushPending(true)
      }
    } else {
      this.flushPending(false)
    }
  }

  public endStream(): void {
    if (this.pendingSamples > 0) {
      this.flushPending(!this.streamStartedPlaying, true)
      this.streamStartedPlaying = true
    }
  }

  private flushPending(fadeInStart: boolean, fadeOutEnd = false): void {
    if (this.pendingSamples === 0) return
    const ctx = this.ensureContext()

    const merged = new Float32Array(this.pendingSamples)
    let offset = 0
    for (const c of this.pendingChunks) {
      merged.set(c, offset)
      offset += c.length
    }
    this.pendingChunks = []
    this.pendingSamples = 0

    // 4ms anti-click micro-ramps at stream start / underrun recovery / stream end
    const now = ctx.currentTime
    const recoveredFromUnderrun = this.nextStartTime < now + 0.004
    const rampSamples = Math.min(Math.floor(this.inputSampleRate * 0.004), Math.floor(merged.length / 4))
    if ((fadeInStart || recoveredFromUnderrun) && rampSamples > 0) {
      for (let i = 0; i < rampSamples; i++) {
        merged[i] *= i / rampSamples
      }
    }
    if (fadeOutEnd && rampSamples > 0) {
      for (let i = 0; i < rampSamples; i++) {
        merged[merged.length - 1 - i] *= i / rampSamples
      }
    }

    const audioBuffer = ctx.createBuffer(1, merged.length, this.inputSampleRate)
    audioBuffer.copyToChannel(merged, 0)

    const src = ctx.createBufferSource()
    src.buffer = audioBuffer
    src.connect(this.gainNode!)

    const startAt = recoveredFromUnderrun ? now + 0.045 : this.nextStartTime
    this.nextStartTime = startAt + audioBuffer.duration

    this.activeSources.add(src)
    if (!this.isPlaying) {
      this.isPlaying = true
      this.onPlaybackState?.(true)
    }

    src.onended = () => {
      this.activeSources.delete(src)
      if (this.activeSources.size === 0 && this.ctx && this.ctx.currentTime >= this.nextStartTime - 0.04) {
        this.isPlaying = false
        this.onPlaybackState?.(false)
      }
    }

    src.start(startAt)
  }

  public stop(): void {
    this.pendingChunks = []
    this.pendingSamples = 0
    this.streamStartedPlaying = false
    for (const src of this.activeSources) {
      try {
        src.stop()
        src.disconnect()
      } catch { /* ignore */ }
    }
    this.activeSources.clear()
    if (this.ctx) {
      this.nextStartTime = this.ctx.currentTime
    }
    this.isPlaying = false
    this.smoothedMouth = 0
    this.onMouthLevel?.(0)
    this.onPlaybackState?.(false)
  }

  public setVolume(vol: number): void {
    this.volume = Math.max(0, Math.min(1.5, vol))
    try {
      localStorage.setItem('aura_volume', String(this.volume))
    } catch { /* ignore */ }
    if (this.gainNode) {
      this.gainNode.gain.value = this.volume
    }
  }

  public getVolume(): number {
    return this.volume
  }

  public async setOutputDevice(deviceId: string): Promise<void> {
    this.sinkId = deviceId
    try {
      localStorage.setItem('aura_sink_id', deviceId)
    } catch { /* ignore */ }
    if (this.ctx && typeof (this.ctx as any).setSinkId === 'function') {
      try {
        await (this.ctx as any).setSinkId(deviceId)
      } catch { /* ignore */ }
    }
  }

  public getOutputDevice(): string {
    return this.sinkId
  }

  private startMeterLoop(): void {
    if (this.rafId !== null) return
    const tick = () => {
      if (this.analyser && this.timeData && this.isPlaying) {
        this.analyser.getFloatTimeDomainData(this.timeData)
        let sum = 0
        for (let i = 0; i < this.timeData.length; i++) {
          const s = this.timeData[i]
          sum += s * s
        }
        const rms = Math.sqrt(sum / this.timeData.length)
        const target = Math.min(1.0, Math.max(0, (rms - 0.012) * 5.8))
        this.smoothedMouth += (target - this.smoothedMouth) * 0.42
        this.onMouthLevel?.(this.smoothedMouth)
      } else if (this.smoothedMouth > 0.005) {
        this.smoothedMouth *= 0.72
        this.onMouthLevel?.(this.smoothedMouth)
      }
      this.rafId = requestAnimationFrame(tick)
    }
    this.rafId = requestAnimationFrame(tick)
  }

  public destroy(): void {
    this.stop()
    if (this.rafId !== null) {
      cancelAnimationFrame(this.rafId)
      this.rafId = null
    }
    if (this.ctx) {
      this.ctx.close().catch(() => {})
      this.ctx = null
    }
  }
}
