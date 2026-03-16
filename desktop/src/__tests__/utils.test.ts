import { describe, it, expect } from 'vitest'
import {
  parseEmotion,
  stripEmotionTags,
  splitSentences,
  detectLanguage,
  estimateDuration,
} from '../llm/utils'

describe('parseEmotion', () => {
  it('extracts single emotion tag', () => {
    expect(parseEmotion('[smile] Hello there')).toEqual(['smile'])
  })
  it('extracts multiple emotion tags', () => {
    expect(parseEmotion('[smile, shadow] Hello')).toEqual(['smile', 'shadow'])
  })
  it('trims whitespace from emotion names', () => {
    expect(parseEmotion('[ smile , angry ] Text')).toEqual(['smile', 'angry'])
  })
  it('returns empty array when no tag present', () => {
    expect(parseEmotion('Hello without any tag')).toEqual([])
  })
  it('returns empty array for empty string', () => {
    expect(parseEmotion('')).toEqual([])
  })
  it('handles ghost_nervous tag', () => {
    expect(parseEmotion('[ghost_nervous] Oh no!')).toEqual(['ghost_nervous'])
  })
  it('handles eyeshine_off tag', () => {
    expect(parseEmotion('[eyeshine_off] ...')).toEqual(['eyeshine_off'])
  })
  it('lowercases all emotion names', () => {
    expect(parseEmotion('[SMILE] Hi')).toEqual(['smile'])
  })
})

describe('stripEmotionTags', () => {
  it('removes emotion tag prefix', () => {
    expect(stripEmotionTags('[smile] Hello world')).toBe('Hello world')
  })
  it('removes multi-emotion tag prefix', () => {
    expect(stripEmotionTags('[sad, angry] I am upset')).toBe('I am upset')
  })
  it('leaves text unchanged when no tag', () => {
    expect(stripEmotionTags('Plain text')).toBe('Plain text')
  })
  it('handles leading whitespace before tag', () => {
    expect(stripEmotionTags('  [smile] Hi')).toBe('Hi')
  })
  it('returns empty string when only a tag', () => {
    expect(stripEmotionTags('[smile]')).toBe('')
  })
})

describe('splitSentences', () => {
  it('splits on English period', () => {
    const { complete, remainder } = splitSentences('Hello. World')
    expect(complete).toContain('Hello')
    expect(remainder).toBe(' World')
  })
  it('splits on Japanese period', () => {
    const { complete, remainder } = splitSentences('こんにちは。世界')
    expect(complete.length).toBe(1)
    expect(remainder).toBe('世界')
  })
  it('splits on exclamation and question marks', () => {
    const { complete } = splitSentences('Yes! Really? Okay.')
    expect(complete.length).toBe(3)
  })
  it('returns empty complete when no sentence boundary', () => {
    const { complete, remainder } = splitSentences('No boundary here')
    expect(complete).toHaveLength(0)
    expect(remainder).toBe('No boundary here')
  })
  it('multiple consecutive sentences all complete', () => {
    const { complete } = splitSentences('One. Two. Three. ')
    expect(complete.length).toBe(3)
  })
  it('empty string returns empty complete and empty remainder', () => {
    const { complete, remainder } = splitSentences('')
    expect(complete).toHaveLength(0)
    expect(remainder).toBe('')
  })
})

describe('detectLanguage', () => {
  it('detects Japanese hiragana', () => {
    expect(detectLanguage('こんにちは')).toBe('Japanese')
  })
  it('detects Japanese kanji', () => {
    expect(detectLanguage('私は猫が好きです')).toBe('Japanese')
  })
  it('detects English', () => {
    expect(detectLanguage('Hello world')).toBe('English')
  })
  it('mixed text with Japanese → Japanese', () => {
    expect(detectLanguage('Hello 世界')).toBe('Japanese')
  })
  it('empty string → English', () => {
    expect(detectLanguage('')).toBe('English')
  })
})

describe('estimateDuration', () => {
  it('returns at least 1.5 seconds for very short text', () => {
    expect(estimateDuration('Hi')).toBeGreaterThanOrEqual(1.5)
  })
  it('returns exactly 1.5 for empty string', () => {
    expect(estimateDuration('')).toBe(1.5)
  })
  it('scales with text length', () => {
    const short = estimateDuration('Hi')
    const long = estimateDuration(
      'Hello, this is a much longer sentence that takes more time to say aloud.'
    )
    expect(long).toBeGreaterThan(short)
  })
  it('30-char text gives 2 seconds', () => {
    expect(estimateDuration('123456789012345678901234567890')).toBe(2.0)
  })
})
