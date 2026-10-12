import { useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type Delights } from '../../api';

// Customer delights, vendor side: today's special (the character announces it in the chat)
// and surprise jara (now and then a plate that is not the jara plate gets a free extra too).
export function VendorDelightsPanel({ slug }: { slug: string }) {
  const q = useQuery({ queryKey: ['delights', slug], queryFn: () => api.delights(slug) });
  const qc = useQueryClient();
  const [special, setSpecial] = useState('');
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { setSpecial(q.data?.special ?? ''); }, [q.data?.special]);

  if (q.isLoading) return <p className="note">Loading…</p>;
  if (q.isError || !q.data) {
    return (
      <div className="card-outline">
        <span className="eyebrow">TODAY'S SPECIAL &amp; SURPRISE JARA</span>
        <p className="error" style={{ margin: 0 }}>Could not load these settings.</p>
        <button className="link-btn" style={{ alignSelf: 'flex-start' }} onClick={() => q.refetch()}>Try again</button>
      </div>
    );
  }
  const d = q.data;

  // Flip at once; save in the background and flip back if it fails.
  const toggleSurprise = async () => {
    const next = !d.surprise_enabled;
    setBusy(true);
    setError(null);
    qc.setQueryData<Delights>(['delights', slug], { ...d, surprise_enabled: next });
    try {
      qc.setQueryData(['delights', slug], await api.setSurprise(slug, next));
    } catch {
      qc.setQueryData<Delights>(['delights', slug], { ...d, surprise_enabled: !next });
      setError('Could not change surprise jara. Try again.');
    } finally {
      setBusy(false);
    }
  };

  const saveSpecial = async (text: string) => {
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      qc.setQueryData(['delights', slug], await api.setSpecial(slug, text));
      setSaved(true);
    } catch {
      setError("Could not save today's special. Try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card-outline" style={{ gap: 12 }}>
      <span className="eyebrow">TODAY'S SPECIAL</span>
      <form
        className="special-form"
        onSubmit={(e) => { e.preventDefault(); saveSpecial(special); }}
      >
        <label htmlFor="special-input" style={{ position: 'absolute', left: -9999 }}>Today's special</label>
        <input id="special-input" className="input" value={special} maxLength={80} placeholder="e.g. Peppered snail" onChange={(e) => { setSpecial(e.target.value); setSaved(false); }} />
        <button className="btn" type="submit" disabled={busy || special.trim() === (d.special ?? '')}>Save</button>
      </form>
      <span className="note" style={{ fontSize: 14 }}>
        {d.special ? `Your character tells customers about "${d.special}" today. It ends at midnight.` : 'Your character tells customers about it in the chat, until midnight.'}
        {d.special && <> <button type="button" className="link-btn" onClick={() => { setSpecial(''); saveSpecial(''); }}>Remove</button></>}
      </span>
      {saved && <span style={{ fontSize: 14, fontWeight: 700 }}>Saved ✓</span>}

      <div className="row" style={{ alignItems: 'center', flexWrap: 'wrap', marginTop: 4 }}>
        <span className="eyebrow">SURPRISE JARA</span>
        <button type="button" role="switch" aria-checked={d.surprise_enabled} className="switch" disabled={busy} onClick={toggleSurprise}>
          <span className="switch-track" aria-hidden="true" />
          {d.surprise_enabled ? 'On' : 'Off'}
        </button>
      </div>
      <span className="note" style={{ fontSize: 14 }}>
        About 1 plate in {d.surprise_one_in} also gets a jara, when the customer least expects it. Surprises make
        customers smile and talk about your food. It costs you about one extra jara per {d.surprise_one_in} plates.
      </span>
      {error && <span className="error">{error}</span>}
    </div>
  );
}
