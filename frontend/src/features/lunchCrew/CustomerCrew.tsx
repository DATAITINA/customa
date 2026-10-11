import { useEffect, useState } from 'react';
import { getCustomerKey, type ApiError, type StandPublic } from '../../api';
import { crewApi, dropInviteFromUrl, inviteCodeFromUrl, type CrewPublic, type CrewView } from './crewApi';

// Lunch Crew, customer side: create or join a crew, see the shared card and whose turn is next.
// Hidden when the vendor has not turned it on, before the customer's first plate, or on error.
// The crew card's plate count is shown by the page's plate card, not repeated here.
// refreshKey: bump it whenever the page learns of a new plate, so whose turn is next stays current.
// ownPlate: plates on the customer's own card (it pauses while they are in a crew).
export function CrewCard({
  slug, stand, onChange, refreshKey, ownPlate,
}: { slug: string; stand: StandPublic; onChange?: () => void; refreshKey?: number; ownPlate?: number | null }) {
  const [data, setData] = useState<CrewPublic | null>(null);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [code, setCode] = useState(inviteCodeFromUrl);
  const hasKey = !!getCustomerKey(slug);

  useEffect(() => {
    if (!hasKey) return;
    let live = true;
    crewApi
      .get(slug, code)
      .then((d) => live && setData(d))
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
    };
  }, [slug, code, hasKey, refreshKey]);

  if (!hasKey || failed || !data || !data.enabled) return null;

  const run = async (call: () => Promise<CrewPublic>) => {
    setBusy(true);
    setError(null);
    try {
      const d = await call();
      setData(d);
      onChange?.();
      return true;
    } catch (err) {
      setError((err as ApiError).message || 'Something went wrong. Try again.');
      return false;
    } finally {
      setBusy(false);
    }
  };

  const total = data.plates_for_jara || stand.plates_for_jara;
  const pauseNote =
    ownPlate == null
      ? null
      : `Your own card (plate ${ownPlate} of ${total}) pauses while you're in a crew. It continues if you leave.`;

  if (data.crew) {
    return (
      <CrewInfo
        slug={slug}
        crew={data.crew}
        ownPlate={ownPlate}
        busy={busy}
        error={error}
        onLeave={() => run(() => crewApi.leave(slug))}
      />
    );
  }

  if (data.invite) {
    const inv = data.invite;
    return (
      <div className="card-outline">
        <span className="eyebrow">LUNCH CREW INVITE</span>
        <span style={{ fontSize: 20, fontWeight: 800, lineHeight: 1.25 }}>Join {inv.name}</span>
        <span className="note">
          {inv.members_count} of {inv.max_members} members. You share one card: every {total}th plate, the jara goes to the next person in line.
        </span>
        {pauseNote && <span className="note">{pauseNote}</span>}
        {error && <span className="error">{error}</span>}
        {inv.full ? (
          <span style={{ fontWeight: 700 }}>This crew is full.</span>
        ) : (
          <button
            className="btn"
            disabled={busy}
            onClick={async () => {
              if (await run(() => crewApi.join(slug, inv.code))) dropInviteFromUrl();
            }}
          >
            {busy ? 'Joining…' : `Join ${inv.name}`}
          </button>
        )}
        <div className="links">
          <button
            className="link-btn"
            onClick={() => {
              dropInviteFromUrl();
              setCode(null);
            }}
          >
            No thanks
          </button>
        </div>
      </div>
    );
  }

  const trimmed = name.trim();
  return (
    <form
      className="card-outline"
      onSubmit={async (e) => {
        e.preventDefault();
        if (trimmed.length < 2) return;
        if (await run(() => crewApi.create(slug, trimmed))) setName('');
      }}
    >
      <span className="eyebrow">LUNCH CREW</span>
      <span style={{ fontSize: 15, lineHeight: 1.45, fontWeight: 600 }}>
        Eat here with friends? Share one card. Every {total}th plate, the jara goes to the next person — like ajo.
      </span>
      <label className="field">
        Crew name
        <input
          className="input"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Office Crew"
          minLength={2}
          maxLength={30}
        />
      </label>
      {pauseNote && <span className="note">{pauseNote}</span>}
      {error && <span className="error">{error}</span>}
      <button className="btn btn-outline" type="submit" disabled={busy || trimmed.length < 2}>
        {busy ? 'Creating…' : 'Create a crew'}
      </button>
    </form>
  );
}

function CrewInfo({
  slug, crew, ownPlate, busy, error, onLeave,
}: { slug: string; crew: CrewView; ownPlate?: number | null; busy: boolean; error: string | null; onLeave: () => Promise<boolean> }) {
  const [confirmLeave, setConfirmLeave] = useState(false);
  const [copied, setCopied] = useState(false);
  const link = `${window.location.origin}/s/${slug}?crew=${crew.code}`;
  const text = `Join my lunch crew "${crew.name}". We share one card and take turns getting the jara: ${link}`;
  const total = crew.plates_for_jara;
  const turnText =
    crew.my_turn_position === 1
      ? 'The next crew jara is yours!'
      : crew.my_turn_position
        ? `Your turn: after ${crew.my_turn_position - 1} more jara${crew.my_turn_position > 2 ? 's' : ''}.`
        : '';

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      window.prompt('Copy this link', link);
    }
  };

  return (
    <div className="card">
      <div className="row">
        <span className="eyebrow">LUNCH CREW</span>
        <span style={{ fontSize: 13, fontWeight: 700 }}>
          {crew.members.length}/{crew.max_members} members
        </span>
      </div>
      <span style={{ fontSize: 22, fontWeight: 800, lineHeight: 1.2 }}>{crew.name}</span>
      {crew.next_jara_to && (
        <span style={{ fontSize: 15, fontWeight: 800 }}>Next jara: {crew.next_jara_to}</span>
      )}
      <ol style={{ margin: 0, paddingLeft: 22, display: 'flex', flexDirection: 'column', gap: 4 }}>
        {crew.members.map((m, i) => (
          <li key={i} style={{ fontSize: 15, fontWeight: m.is_next ? 800 : 600 }}>
            {m.name}
            {m.is_me ? ' (you)' : ''}
            {m.is_next && (
              <span className="badge" style={{ marginLeft: 8, background: 'var(--pepper)' }}>NEXT JARA</span>
            )}
          </li>
        ))}
      </ol>
      {turnText && <span className="note">{turnText} Turns go in join order, one jara every {total} crew plates.</span>}
      {ownPlate != null && <span className="note">Your own card is paused at plate {ownPlate} of {total}.</span>}
      {error && <span className="error">{error}</span>}
      <a
        className="btn"
        href={`https://wa.me/?text=${encodeURIComponent(text)}`}
        target="_blank"
        rel="noopener noreferrer"
      >
        Invite friends on WhatsApp
      </a>
      <button className="btn btn-outline" type="button" onClick={copy}>
        {copied ? 'Link copied' : 'Copy invite link'}
      </button>
      {confirmLeave ? (
        <div className="card-outline" style={{ background: 'var(--paper)' }}>
          <span style={{ fontWeight: 800 }}>
            Leave {crew.name}? Plates already counted stay with the crew. Your next plates go on your own card
            {ownPlate != null ? ` (from plate ${ownPlate} of ${total})` : ''}.
          </span>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              className="btn"
              disabled={busy}
              onClick={async () => {
                if (await onLeave()) setConfirmLeave(false);
              }}
            >
              Yes, leave
            </button>
            <button className="btn btn-outline" onClick={() => setConfirmLeave(false)}>Stay</button>
          </div>
        </div>
      ) : (
        <div className="links">
          <button className="link-btn" onClick={() => setConfirmLeave(true)}>Leave crew</button>
        </div>
      )}
    </div>
  );
}
