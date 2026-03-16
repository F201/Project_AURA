/**
 * Emotion/expression utilities — ported from voice-agent/vtube_controller.py
 * detect_emotion() and format_for_tts() logic.
 */

// Matches a leading [tag] or [tag1, tag2] prefix (with optional whitespace)
const EMOTION_TAG_RE = /^\s*\[([^\]]+)\]\s*/

export function parseEmotion(sentence: string): string[] {
  const match = sentence.match(EMOTION_TAG_RE)
  if (!match) return []
  return match[1].split(',').map((s) => s.trim().toLowerCase())
}

export function stripEmotionTags(text: string): string {
  return text.replace(EMOTION_TAG_RE, '').trim()
}

// Split on sentence-ending punctuation — English + Japanese
const SENTENCE_END = /[.!?。！？]/
export function splitSentences(text: string): { complete: string[]; remainder: string } {
  const parts = text.split(SENTENCE_END)
  if (parts.length <= 1) return { complete: [], remainder: text }
  const remainder = parts.pop()!
  return { complete: parts.filter((s) => s.trim()), remainder }
}

export function detectLanguage(text: string): string {
  return /[\u3000-\u9fff]/.test(text) ? 'Japanese' : 'English'
}

export function estimateDuration(text: string): number {
  // ~15 chars/second natural speech — rough estimate for expression reset timing
  return Math.max(1.5, text.length / 15)
}
