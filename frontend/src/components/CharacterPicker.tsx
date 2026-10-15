// Pick the stand's character: picture tiles for the body, colour swatches and accessories.
import { BODY_CHOICES, Character, PRESETS } from './Character';

export type CharacterLook = { body?: string; color?: string; accessory?: string };

const ACCESSORIES = [
  { key: 'chef', label: 'Chef hat' },
  { key: 'headwrap', label: 'Headwrap' },
  { key: 'sunglasses', label: 'Shades' },
  { key: 'bowtie', label: 'Bow tie' },
  { key: 'none', label: 'None' },
];

export function CharacterPicker({ value, onChange }: { value: CharacterLook; onChange: (next: CharacterLook) => void }) {
  return (
    <>
      <span className="eyebrow">CHARACTER</span>
      <div className="char-grid" role="radiogroup" aria-label="Character">
        {BODY_CHOICES.map((c) => (
          <button
            type="button"
            key={c.body}
            role="radio"
            aria-checked={value.body === c.body}
            className="char-tile"
            // Picking an animal also picks its best colour; the vendor can change it after.
            onClick={() => onChange({ ...value, body: c.body, color: value.body === c.body ? value.color : c.color })}
          >
            <Character body={c.body} color={value.body === c.body ? value.color : c.color} accessory="none" expression="happy" pose="idle" size={52} />
            <span>{c.label}</span>
          </button>
        ))}
      </div>
      <span className="eyebrow">COLOUR</span>
      <div className="swatches">
        {Object.entries(PRESETS).map(([k, v]) => (
          <button type="button" key={k} className="swatch" aria-label={k} aria-pressed={value.color === k} style={{ background: v.fill }} onClick={() => onChange({ ...value, color: k })} />
        ))}
      </div>
      <span className="eyebrow">ACCESSORY</span>
      <div className="seg">
        {ACCESSORIES.map((a) => (
          <button type="button" key={a.key} aria-pressed={value.accessory === a.key} onClick={() => onChange({ ...value, accessory: a.key })}>{a.label}</button>
        ))}
      </div>
    </>
  );
}
