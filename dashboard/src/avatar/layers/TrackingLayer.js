export class TrackingLayer {
  constructor(bus) {
    this._bus = bus
  }

  update(mouthOpen) {
    this._bus.write('ParamMouthOpenY', mouthOpen, 'tracking')
  }
}
