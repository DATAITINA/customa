// The stand's menu as rows: a food box and a price box (₦) per dish, so the menu is structured
// data ({ item, price }) that payments, Plate Ajo and the character's chat all read.
export type MenuRow = { item: string; price: string };

const blank = (): MenuRow => ({ item: '', price: '' });

// Older menus kept prices inside the food name ("Tomatoes ₦1,500–₦3,000"): split them out.
export function toRows(menu: { item: string; price: number }[]): MenuRow[] {
  const rows = menu.map((m) => {
    if (m.price) return { item: m.item, price: String(m.price) };
    const found = m.item.match(/^(.*?)[\s,:\-–₦]*?(\d[\d,]*)/);
    if (!found) return { item: m.item, price: '' };
    return { item: found[1].replace(/[\s,:\-–₦]+$/, '').trim() || m.item, price: found[2].replace(/,/g, '') };
  });
  return rows.length ? rows : [blank()];
}

export function fromRows(rows: MenuRow[]): { item: string; price: number }[] {
  return rows
    .filter((r) => r.item.trim())
    .map((r) => ({ item: r.item.trim(), price: Number(r.price.replace(/[^\d]/g, '')) || 0 }));
}

// A message when a named dish has no price, or null when the menu is ready.
export function menuProblem(rows: MenuRow[]): string | null {
  const named = rows.filter((r) => r.item.trim());
  if (!named.length) return 'Add at least one food and its price.';
  const noPrice = named.find((r) => !(Number(r.price.replace(/[^\d]/g, '')) > 0));
  return noPrice ? `Add a price for "${noPrice.item.trim()}".` : null;
}

export function MenuRows({ rows, onChange }: { rows: MenuRow[]; onChange: (rows: MenuRow[]) => void }) {
  const set = (i: number, patch: Partial<MenuRow>) => onChange(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  return (
    <div className="menu-rows">
      <div className="menu-row menu-row-head" aria-hidden="true"><span>Food</span><span>Price (₦)</span><span /></div>
      {rows.map((r, i) => (
        <div key={i} className="menu-row">
          <input className="input" aria-label={`Food ${i + 1}`} value={r.item} placeholder="Rice and stew with meat" maxLength={120}
            onChange={(e) => set(i, { item: e.target.value })} />
          <input className="input" aria-label={`Price of food ${i + 1} in naira`} inputMode="numeric" value={r.price} placeholder="10000"
            onChange={(e) => set(i, { price: e.target.value.replace(/[^\d]/g, '') })} />
          <button type="button" className="menu-row-x" aria-label={`Remove food ${i + 1}`} disabled={rows.length === 1}
            onClick={() => onChange(rows.filter((_, j) => j !== i))}>×</button>
        </div>
      ))}
      <button type="button" className="btn btn-outline" onClick={() => onChange([...rows, blank()])}>+ Add another food</button>
    </div>
  );
}
