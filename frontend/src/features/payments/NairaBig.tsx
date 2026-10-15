// A bold ₦ for the big display numbers: the display font has no ₦, so the browser borrowed a
// thin one from another font. Drawn here to match the heavy digits.
export function NairaBig({ amount }: { amount: number }) {
  return (
    <span aria-label={`₦${amount.toLocaleString('en-NG')}`}>
      <svg aria-hidden="true" viewBox="0 0 22 24" style={{ height: '0.74em', width: 'auto', marginRight: '0.06em', verticalAlign: 'baseline' }} fill="currentColor">
        <path d="M3 0h5l6 13V0h5v24h-5L8 11v13H3z" />
        <rect x="0" y="7" width="22" height="3" />
        <rect x="0" y="13" width="22" height="3" />
      </svg>
      <span aria-hidden="true">{amount.toLocaleString('en-NG')}</span>
    </span>
  );
}
