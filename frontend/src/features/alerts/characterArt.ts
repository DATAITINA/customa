// The stand character's picture for alerts: drawn on the phone from the same SVG character
// the app shows, then kept in IndexedDB for the service worker (public/sw.js).
import { createElement } from 'react';
import { createRoot } from 'react-dom/client';
import { flushSync } from 'react-dom';
import { Character } from '../../components/Character';
import type { Character as CharacterData } from '../../api';

export type AlertArt = { icon: string; image: string };

const INK = '#141414';
const BLUSH = '#FDE6E2';
const PEPPER = '#F04E30';

// The character as a still SVG string (animations removed), with room for the hat.
function characterSvg(ch: CharacterData | null): string {
  const host = document.createElement('div');
  const root = createRoot(host);
  flushSync(() => {
    root.render(createElement(Character, { body: ch?.body, color: ch?.color, accessory: ch?.accessory, expression: 'excited', pose: 'wave', size: 200 }));
  });
  const svg = host.querySelector('svg');
  let out = '';
  if (svg) {
    svg.querySelectorAll('animate, animateTransform').forEach((a) => a.remove());
    svg.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    svg.setAttribute('viewBox', '-30 -40 260 300');
    svg.setAttribute('width', '260');
    svg.setAttribute('height', '300');
    svg.removeAttribute('style');
    out = new XMLSerializer().serializeToString(svg);
  }
  root.unmount();
  return out;
}

function loadImage(svg: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
  });
}

export async function drawAlertArt(ch: CharacterData | null, standName: string): Promise<AlertArt> {
  const img = await loadImage(characterSvg(ch));
  try { await document.fonts?.load('400 64px "Lilita One"'); } catch { /* falls back to a system font */ }

  // Icon: the character on a round blush badge with an ink ring.
  const icon = document.createElement('canvas');
  icon.width = icon.height = 192;
  const c = icon.getContext('2d')!;
  c.fillStyle = BLUSH;
  c.beginPath(); c.arc(96, 96, 92, 0, Math.PI * 2); c.fill();
  c.lineWidth = 6; c.strokeStyle = INK; c.stroke();
  c.save(); c.beginPath(); c.arc(96, 96, 89, 0, Math.PI * 2); c.clip();
  c.drawImage(img, 16, 6, 160, 185);
  c.restore();

  // Banner (2:1, Android's expanded alert): "LAST PLATES TONIGHT!" with the character.
  const banner = document.createElement('canvas');
  banner.width = 720; banner.height = 360;
  const b = banner.getContext('2d')!;
  b.fillStyle = BLUSH; b.fillRect(0, 0, 720, 360);
  b.fillStyle = PEPPER; b.beginPath(); b.arc(560, 210, 150, 0, Math.PI * 2); b.fill();
  b.drawImage(img, 440, 30, 250, 288);
  b.fillStyle = INK;
  b.font = '400 76px "Lilita One", "Arial Black", sans-serif';
  b.fillText('LAST', 40, 120);
  b.fillText('PLATES', 40, 196);
  b.fillStyle = PEPPER;
  b.fillText('TONIGHT!', 40, 272);
  b.fillStyle = INK;
  b.font = '800 24px Figtree, Arial, sans-serif';
  b.fillText(standName.length > 30 ? `${standName.slice(0, 29)}…` : standName, 42, 318);

  return { icon: icon.toDataURL('image/png'), image: banner.toDataURL('image/png') };
}

// Shared with public/sw.js: database "customa", store "art", key = stand slug.
export function saveAlertArt(slug: string, art: AlertArt): Promise<void> {
  return new Promise((resolve) => {
    if (!('indexedDB' in window)) return resolve();
    const open = indexedDB.open('customa', 1);
    open.onupgradeneeded = () => open.result.createObjectStore('art');
    open.onerror = () => resolve();
    open.onsuccess = () => {
      try {
        const tx = open.result.transaction('art', 'readwrite');
        tx.objectStore('art').put(art, slug);
        tx.oncomplete = () => resolve();
        tx.onerror = () => resolve();
      } catch {
        resolve();
      }
    };
  });
}
