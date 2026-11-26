const PRIORITY: Record<string, number> = {
  idle: 1,
  tracking: 2,
  interaction: 3,
  expression: 4,
}

interface ParamWrite {
  value: number
  provider: string
  priority: number
  blendMode: 'Override' | 'Add' | 'Multiply'
}

export class ParameterBus {
  private _blocked: Set<string>
  private _writes: Map<string, ParamWrite[]> = new Map()

  constructor(physicsOutputParams: Set<string>) {
    this._blocked = physicsOutputParams
  }

  write(
    id: string,
    value: number,
    provider: string,
    blendMode: 'Override' | 'Add' | 'Multiply' = 'Override'
  ): void {
    if (this._blocked.has(id)) return
    let arr = this._writes.get(id)
    if (!arr) {
      arr = []
      this._writes.set(id, arr)
    }
    arr.push({
      value,
      provider,
      priority: PRIORITY[provider] ?? 0,
      blendMode,
    })
  }

  clearProvider(provider: string): void {
    for (const [id, writes] of this._writes) {
      const filtered = writes.filter((w) => w.provider !== provider)
      if (filtered.length === 0) this._writes.delete(id)
      else this._writes.set(id, filtered)
    }
  }

  flush(core: any): void {
    for (const [id, writes] of this._writes) {
      if (writes.length === 0) continue
      const sorted = [...writes].sort((a, b) => a.priority - b.priority)
      let resolved = sorted[0].value
      for (let i = 1; i < sorted.length; i++) {
        const { value, blendMode } = sorted[i]
        if (blendMode === 'Add') resolved += value
        else if (blendMode === 'Multiply') resolved *= value
        else resolved = value
      }
      core.setParameterValueById(id, resolved)
    }
    this._writes.clear()
  }
}
