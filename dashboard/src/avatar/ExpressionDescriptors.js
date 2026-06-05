// Static expression descriptors for non-file expressions.
// Shape matches the Cubism 4 exp3.json Parameters array so ExpressionLayer
// treats file-based and code-defined expressions identically.
export const EXPRESSION_DESCRIPTORS = {
  wink: {
    Parameters: [
      { Id: 'ParamEyeLOpen',  Value: 0.0,  Blend: 'Override' },
      { Id: 'ParamBrowLForm', Value: -1.0, Blend: 'Override' },
      { Id: 'ParamMouthForm', Value: 1.0,  Blend: 'Override' },
    ],
  },
  tongue: {
    Parameters: [
      { Id: 'ParamMouthOpenY', Value: 1.0,  Blend: 'Override' },
      { Id: 'ParamMouthForm',  Value: -1.0, Blend: 'Override' },
    ],
  },
  pouting: {
    Parameters: [
      { Id: 'ParamMouthForm',  Value: -1.0, Blend: 'Override' },
      { Id: 'ParamBrowLForm',  Value: -1.0, Blend: 'Override' },
      { Id: 'ParamBrowRForm',  Value: -1.0, Blend: 'Override' },
    ],
  },
  'curious idle': {
    Parameters: [
      { Id: 'ParamBrowLForm', Value: 0.5,  Blend: 'Override' },
      { Id: 'ParamBrowRForm', Value: -0.5, Blend: 'Override' },
    ],
  },
  pleading: {
    Parameters: [
      { Id: 'ParamBrowLY',    Value: 1.0,  Blend: 'Override' },
      { Id: 'ParamBrowRY',    Value: 1.0,  Blend: 'Override' },
      { Id: 'ParamMouthForm', Value: -0.5, Blend: 'Override' },
    ],
  },
}
