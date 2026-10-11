import type { StandPublic } from '../../api';

// Pot Alert, customer side: "tell me when ___ is ready" on WhatsApp.
export function PotWatchCard(_props: { slug: string; stand: StandPublic }) {
  return null;
}

// Shown at the top of the stand page to everyone while a pot is ready.
export function PotReadyBanner(_props: { slug: string }) {
  return null;
}
