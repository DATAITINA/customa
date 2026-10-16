import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { crewApi } from './crewApi';
import { PanelSkeleton } from '../../components/Loading';

// Lunch Crew, vendor side: turn it on, see crews and whose turn is next.
export function VendorCrewPanel({ slug }: { slug: string }) {
  const q = useQuery({ queryKey: ['lunchCrew', slug], queryFn: () => crewApi.vendor(slug), refetchInterval: 30000 });
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (q.isLoading) return <PanelSkeleton label="Lunch Crew" />;
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

  // Flip at once; the save runs in the background (its reply is the whole panel) and flips
  // back if it fails.
  const toggle = async () => {
    const next = !d.enabled;
    setBusy(true);
    setError(null);
    qc.setQueryData(['lunchCrew', slug], { ...d, enabled: next });
    try {
      qc.setQueryData(['lunchCrew', slug], await crewApi.setEnabled(slug, next));
    } catch {
      qc.setQueryData(['lunchCrew', slug], { ...d, enabled: !next });
      setError('Could not change Lunch Crew. Try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card-outline" style={{ gap: 12 }}>
      <div className="row" style={{ alignItems: 'center', flexWrap: 'wrap' }}>
        <span className="eyebrow">LUNCH CREW</span>
        <button type="button" role="switch" aria-checked={d.enabled} className="switch" disabled={busy} onClick={toggle}>
          <span className="switch-track" aria-hidden="true" />
          {d.enabled ? 'On' : 'Off'}
        </button>
      </div>
      <span className="note" style={{ fontSize: '0.875rem' }}>
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
                <span style={{ fontSize: '1.0625rem', fontWeight: 800 }}>{c.name}</span>
                <span style={{ fontSize: '0.8125rem', fontWeight: 700 }}>
                  Plate {c.plate_number}/{c.plates_for_jara}
                </span>
              </div>
              <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={c.plates_for_jara} aria-valuenow={c.plate_number}>
                <div style={{ width: `${(c.plate_number / c.plates_for_jara) * 100}%` }} />
              </div>
              <span style={{ fontSize: '0.875rem', fontWeight: 600 }}>{c.members.join(', ')}</span>
              {c.next_jara_to && <span style={{ fontSize: '0.875rem', fontWeight: 800 }}>Next jara: {c.next_jara_to}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
