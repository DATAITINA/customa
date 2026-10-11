import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { crewApi } from './crewApi';

// Lunch Crew, vendor side: turn it on, see crews and whose turn is next.
export function VendorCrewPanel({ slug }: { slug: string }) {
  const q = useQuery({ queryKey: ['lunchCrew', slug], queryFn: () => crewApi.vendor(slug), refetchInterval: 15000 });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (q.isLoading) return <p className="note">Loading Lunch Crew…</p>;
  if (q.isError || !q.data) {
    return (
      <div className="card-outline">
        <span className="eyebrow">LUNCH CREW</span>
        <p className="error" style={{ margin: 0 }}>Could not load Lunch Crew.</p>
        <button className="link-btn" style={{ alignSelf: 'flex-start' }} onClick={() => q.refetch()}>Try again</button>
      </div>
    );
  }
  const d = q.data;

  const toggle = async () => {
    setBusy(true);
    setError(null);
    try {
      await crewApi.setEnabled(slug, !d.enabled);
      await q.refetch();
    } catch {
      setError('Could not change Lunch Crew. Try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card-outline" style={{ gap: 12 }}>
      <div className="row" style={{ alignItems: 'center', flexWrap: 'wrap' }}>
        <span className="eyebrow">LUNCH CREW</span>
        <label className="check" style={{ alignItems: 'center', fontSize: 15, fontWeight: 800 }}>
          <input type="checkbox" checked={d.enabled} disabled={busy} onChange={toggle} />
          <span>{d.enabled ? 'On' : 'Off'}</span>
        </label>
      </div>
      <span className="note" style={{ fontSize: 14 }}>
        Friends (up to {d.max_members}) share one card. Every {d.plates_for_jara}th crew plate, one jara goes to the next
        member in turn, like ajo. Same cost to you: one jara per {d.plates_for_jara} plates.
      </span>
      {error && <span className="error">{error}</span>}
      {d.crews.length === 0 ? (
        <span className="note">
          {d.enabled ? 'No crews yet. Customers can start one on their stand page.' : 'Turn it on to let customers start crews.'}
        </span>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 12 }}>
          {d.crews.map((c, i) => (
            <div key={`${c.name}-${i}`} className="card" style={{ gap: 8 }}>
              <div className="row">
                <span style={{ fontSize: 17, fontWeight: 800 }}>{c.name}</span>
                <span style={{ fontSize: 13, fontWeight: 700 }}>
                  Plate {c.plate_number}/{c.plates_for_jara}
                </span>
              </div>
              <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={c.plates_for_jara} aria-valuenow={c.plate_number}>
                <div style={{ width: `${(c.plate_number / c.plates_for_jara) * 100}%` }} />
              </div>
              <span style={{ fontSize: 14, fontWeight: 600 }}>{c.members.join(', ')}</span>
              {c.next_jara_to && <span style={{ fontSize: 14, fontWeight: 800 }}>Next jara: {c.next_jara_to}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
