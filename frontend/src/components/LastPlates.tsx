import type { LastPlates } from '../api';

const untilText = (iso: string) =>
  new Date(iso + 'Z').toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });

// "Only 12 plates left tonight": the vendor's announcement to sell leftover food.
export function LastPlatesBanner({ lp, big }: { lp: LastPlates; big?: boolean }) {
  if (!lp) return null;
  return (
    <div className={big ? 'last-plates last-plates-big' : 'last-plates'} role="status">
      <span className="lp-dot" aria-hidden="true" />
      <span>
        <strong>Only {lp.left} plate{lp.left === 1 ? '' : 's'} left tonight!</strong> Come before {untilText(lp.until)}.
      </span>
    </div>
  );
}
