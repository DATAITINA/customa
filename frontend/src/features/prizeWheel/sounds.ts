// Small sounds for the wheel, made on the phone (no sound files): a tick as each slice passes
// the pointer and a happy jingle for the win. Off with the speaker button; the choice is kept.
const KEY = 'customa:wheel-sound';
let ctx: AudioContext | null = null;

export function soundOn(): boolean {
  try { return localStorage.getItem(KEY) !== 'off'; } catch { return true; }
}
export function setSoundOn(on: boolean) {
  try { localStorage.setItem(KEY, on ? 'on' : 'off'); } catch { /* not kept */ }
}

function audio(): AudioContext | null {
  if (!soundOn()) return null;
  try {
    const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctor) return null;
    ctx ??= new Ctor();
    if (ctx.state === 'suspended') void ctx.resume();
    return ctx;
  } catch {
    return null;
  }
}

/** Call from the tap that starts the spin, so phones allow sound. */
export function unlockSound() { audio(); }

function blip(freq: number, at: number, length: number, volume: number, type: OscillatorType = 'square') {
  const a = audio();
  if (!a) return;
  const osc = a.createOscillator();
  const gain = a.createGain();
  osc.type = type;
  osc.frequency.value = freq;
  const t = a.currentTime + at;
  gain.gain.setValueAtTime(volume, t);
  gain.gain.exponentialRampToValueAtTime(0.0001, t + length);
  osc.connect(gain).connect(a.destination);
  osc.start(t);
  osc.stop(t + length + 0.02);
}

export function tick() { blip(1500, 0, 0.03, 0.05); }

export function winJingle() {
  [523, 659, 784, 1047].forEach((f, i) => blip(f, i * 0.11, 0.28, 0.09, 'triangle'));
}
