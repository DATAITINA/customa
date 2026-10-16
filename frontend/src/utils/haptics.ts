// Gentle haptics where the phone supports them (most Android phones; iPhone ignores it).
// Short patterns only: a tap of feedback, never a buzz that startles.
export const HAPTIC = {
  tap: 10,
  stamp: [18, 40, 26],
  jara: [30, 50, 30, 50, 80],
} as const;

export function buzz(pattern: number | readonly number[]) {
  try {
    navigator.vibrate?.(pattern as number | number[]);
  } catch {
    // Not supported: nothing to do.
  }
}
