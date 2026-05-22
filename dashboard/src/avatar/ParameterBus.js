// Priority table — higher number wins per parameter each frame.
const PRIORITY = { idle: 1, tracking: 2, expression: 4 }

export class ParameterBus {
  constructor(physicsOutputParams) {
    this._blocked = physicsOutputParams        // Set<string>
    this._writes  = new Map()                  // paramId → write[]
  }

  // Register a desired value for this frame.  Writes to blocklisted params are silently dropped.
  write(id, value, provider, blendMode = 'Override') {
    if (this._blocked.has(id)) return
    if (!this._writes.has(id)) this._writes.set(id, [])
    this._writes.get(id).push({ value, provider, priority: PRIORITY[provider] ?? 0, blendMode })
  }

  // Remove all pending writes from one provider (call before re-writing a new expression).
  clearProvider(provider) {
    for (const [id, writes] of this._writes) {
      const filtered = writes.filter(w => w.provider !== provider)
      if (filtered.length === 0) this._writes.delete(id)
      else this._writes.set(id, filtered)
    }
  }

  // Resolve winners and write exactly once per parameter to the core model, then clear.
  flush(core) {
    for (const [id, writes] of this._writes) {
      if (writes.length === 0) continue

      // Sort ascending so higher-priority entries layer on top
      const sorted = [...writes].sort((a, b) => a.priority - b.priority)
      let resolved = sorted[0].value

      for (let i = 1; i < sorted.length; i++) {
        const { value, blendMode } = sorted[i]
        if (blendMode === 'Add')      resolved += value
        else if (blendMode === 'Multiply') resolved *= value
        else                          resolved  = value  // Override
      }

      core.setParameterValueById(id, resolved)
    }
    this._writes.clear()
  }
}
