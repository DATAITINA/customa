// Shrink a phone photo before upload: at most 1280 px on the long side, JPEG. A 4 MB camera
// photo becomes about 150-300 KB, quick to send on mobile data and quick for customers to load.
const MAX_EDGE = 1280;
const MAX_BYTES = 850 * 1024;

async function decode(file: File): Promise<ImageBitmap | HTMLImageElement> {
  if ('createImageBitmap' in window) {
    try {
      return await createImageBitmap(file, { imageOrientation: 'from-image' });
    } catch {
      // Older browsers: fall back to an <img>.
    }
  }
  const url = URL.createObjectURL(file);
  try {
    const img = new Image();
    img.decoding = 'async';
    img.src = url;
    await img.decode();
    return img;
  } finally {
    URL.revokeObjectURL(url);
  }
}

export async function shrinkPhoto(file: File, opts: { maxEdge?: number; maxBytes?: number } = {}): Promise<string> {
  const maxEdge = opts.maxEdge ?? MAX_EDGE;
  const maxBytes = opts.maxBytes ?? MAX_BYTES;
  const img = await decode(file);
  const w = 'naturalWidth' in img ? img.naturalWidth : img.width;
  const h = 'naturalHeight' in img ? img.naturalHeight : img.height;
  for (const [edge, quality] of [[maxEdge, 0.82], [Math.min(maxEdge, 1024), 0.72], [Math.min(maxEdge, 800), 0.65], [Math.min(maxEdge, 600), 0.6]] as const) {
    const scale = Math.min(1, edge / Math.max(w, h));
    const canvas = document.createElement('canvas');
    canvas.width = Math.round(w * scale);
    canvas.height = Math.round(h * scale);
    canvas.getContext('2d')!.drawImage(img, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL('image/jpeg', quality);
    if (dataUrl.length * 0.75 <= maxBytes) return dataUrl;
  }
  throw new Error('This photo is too big. Try another one.');
}
