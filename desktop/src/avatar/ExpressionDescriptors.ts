export interface ExpressionParam {
  Id: string
  Value: number
  Blend?: 'Override' | 'Add' | 'Multiply'
}

/**
 * Built-in Cubism 4 expression descriptors inlined from the bundled Live2D model's
 * .exp3.json and .cdi3.json definitions so they trigger with 0ms latency and never
 * fail under Electron's file:// protocol.
 */
const SMILE_LOCK: ExpressionParam[] = [
  { Id: 'ParamMouthForm', Value: 1.0, Blend: 'Override' },
  { Id: 'ParamEyeLSmile', Value: 0.75, Blend: 'Override' },
  { Id: 'ParamEyeRSmile', Value: 0.75, Blend: 'Override' },
]

const SAD_LOCK: ExpressionParam[] = [
  { Id: 'ParamMouthForm', Value: -1.0, Blend: 'Override' },
  { Id: 'ParamBrowLForm', Value: -1.0, Blend: 'Override' },
  { Id: 'ParamBrowRForm', Value: -1.0, Blend: 'Override' },
  { Id: 'ParamBrowLAngle', Value: 0.85, Blend: 'Override' },
  { Id: 'ParamBrowRAngle', Value: 0.85, Blend: 'Override' },
  { Id: 'ParamEyeLSmile', Value: 0.0, Blend: 'Override' },
  { Id: 'ParamEyeRSmile', Value: 0.0, Blend: 'Override' },
]

const ANGRY: ExpressionParam[] = [
  { Id: 'ParamMouthForm', Value: -0.85, Blend: 'Override' },
  { Id: 'ParamEyeLSmile', Value: 0.0, Blend: 'Override' },
  { Id: 'ParamEyeRSmile', Value: 0.0, Blend: 'Override' },
  { Id: 'ParamBrowLAngle', Value: -1.0, Blend: 'Override' },
  { Id: 'ParamBrowRAngle', Value: -1.0, Blend: 'Override' },
  { Id: 'ParamBrowLForm', Value: -0.7, Blend: 'Override' },
  { Id: 'ParamBrowRForm', Value: -0.7, Blend: 'Override' },
]

const GHOST: ExpressionParam[] = [
  { Id: 'Param80', Value: 1.0, Blend: 'Override' }, // Companion ghost prop visible
]

const GHOST_CHANGE: ExpressionParam[] = [
  { Id: 'Param80', Value: 1.0, Blend: 'Override' }, // Companion ghost prop visible
  { Id: 'Param75', Value: 1.0, Blend: 'Override' }, // Companion ghost alternate/nervous face
]

const SHADOW: ExpressionParam[] = [
  { Id: 'Param2', Value: 1.0, Blend: 'Override' }, // Dramatic forehead shadow
]

const PUPIL_SHRINK: ExpressionParam[] = [
  { Id: 'Param38', Value: 1.0, Blend: 'Override' }, // Shocked/startled pupils
  { Id: 'ParamEyeLOpen', Value: 1.0, Blend: 'Override' },
  { Id: 'ParamEyeROpen', Value: 1.0, Blend: 'Override' },
]

const EYESHINE_OFF: ExpressionParam[] = [
  { Id: 'Param3', Value: 1.0, Blend: 'Override' }, // Blank / deadpan eyes
  { Id: 'ParamEyeLSmile', Value: 0.0, Blend: 'Override' },
  { Id: 'ParamEyeRSmile', Value: 0.0, Blend: 'Override' },
]

const TONGUE: ExpressionParam[] = [
  { Id: 'Param70', Value: 1.0, Blend: 'Override' }, // Built-in TongueOut parameter
  { Id: 'ParamMouthOpenY', Value: 0.85, Blend: 'Override' },
  { Id: 'ParamMouthForm', Value: 0.8, Blend: 'Override' },
  { Id: 'ParamEyeLSmile', Value: 0.65, Blend: 'Override' },
  { Id: 'ParamEyeRSmile', Value: 0.65, Blend: 'Override' },
]

const POUTING: ExpressionParam[] = [
  { Id: 'ParamMouthForm', Value: -1.0, Blend: 'Override' },
  { Id: 'ParamBrowLForm', Value: -0.85, Blend: 'Override' },
  { Id: 'ParamBrowRForm', Value: -0.85, Blend: 'Override' },
  { Id: 'ParamBrowLAngle', Value: -0.45, Blend: 'Override' },
  { Id: 'ParamBrowRAngle', Value: -0.45, Blend: 'Override' },
  { Id: 'ParamEyeLSmile', Value: 0.0, Blend: 'Override' },
  { Id: 'ParamEyeRSmile', Value: 0.0, Blend: 'Override' },
]

const BLUSH: ExpressionParam[] = [
  { Id: 'ParamEyeLSmile', Value: 0.85, Blend: 'Override' },
  { Id: 'ParamEyeRSmile', Value: 0.85, Blend: 'Override' },
  { Id: 'ParamMouthForm', Value: 0.75, Blend: 'Override' },
  { Id: 'ParamBrowLAngle', Value: 0.4, Blend: 'Override' },
  { Id: 'ParamBrowRAngle', Value: 0.4, Blend: 'Override' },
]

const PLEADING: ExpressionParam[] = [
  { Id: 'ParamBrowLAngle', Value: 0.85, Blend: 'Override' },
  { Id: 'ParamBrowRAngle', Value: 0.85, Blend: 'Override' },
  { Id: 'ParamBrowLForm', Value: -0.6, Blend: 'Override' },
  { Id: 'ParamBrowRForm', Value: -0.6, Blend: 'Override' },
  { Id: 'ParamMouthForm', Value: -0.45, Blend: 'Override' },
]

const CURIOUS: ExpressionParam[] = [
  { Id: 'ParamBrowLForm', Value: 0.6, Blend: 'Override' },
  { Id: 'ParamBrowRForm', Value: -0.45, Blend: 'Override' },
]

export const EXPRESSION_DESCRIPTORS: Record<string, { Parameters: ExpressionParam[] }> = {
  // Exact built-in Live2D action names (for LLM function calling)
  SmileLock: { Parameters: SMILE_LOCK },
  SadLock: { Parameters: SAD_LOCK },
  Angry: { Parameters: ANGRY },
  Ghost: { Parameters: GHOST },
  GhostChange: { Parameters: GHOST_CHANGE },
  Shadow: { Parameters: SHADOW },
  PupilShrink: { Parameters: PUPIL_SHRINK },
  EyeshineOff: { Parameters: EYESHINE_OFF },
  // Lowercase aliases
  smile: { Parameters: SMILE_LOCK },
  sad: { Parameters: SAD_LOCK },
  angry: { Parameters: ANGRY },
  ghost: { Parameters: GHOST },
  ghost_nervous: { Parameters: GHOST_CHANGE },
  shadow: { Parameters: SHADOW },
  pupil_shrink: { Parameters: PUPIL_SHRINK },
  eyeshine_off: { Parameters: EYESHINE_OFF },
  // Procedural expressions
  wink: {
    Parameters: [
      { Id: 'ParamEyeLOpen', Value: 0.0, Blend: 'Override' },
      { Id: 'ParamBrowLForm', Value: -1.0, Blend: 'Override' },
      { Id: 'ParamMouthForm', Value: 1.0, Blend: 'Override' },
    ],
  },
  tongue: { Parameters: TONGUE },
  pouting: { Parameters: POUTING },
  blush: { Parameters: BLUSH },
  pleading: { Parameters: PLEADING },
  curious: { Parameters: CURIOUS },
}

// Toggle params not driven by IdleLayer — explicitly reset to 0 when no expression uses them
export const RESETTABLE_EXPRESSION_PARAMS = [
  'Param2',
  'Param3',
  'Param38',
  'Param70',
  'Param75',
  'Param80',
  'ParamBrowLAngle',
  'ParamBrowRAngle',
]

export const EXPRESSION_FADE_TIMES: Record<string, number> = {
  SmileLock: 0.35,
  SadLock: 0.35,
  Shadow: 0.35,
  EyeshineOff: 0.35,
  Angry: 0.3,
  PupilShrink: 0.25,
  Ghost: 0.3,
  GhostChange: 0.25,
}

export const DEFAULT_FADE = 0.35
