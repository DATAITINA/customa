import { useEffect, useRef, useState } from 'react';
import { Logo } from '../components/Logo';
import { api, type ApiError, type ChatState, type StandPublic } from '../api';
import { Character } from '../components/Character';
import { CharacterLoader } from '../components/Loading';
import { Link } from '../App';

type Msg = { role: 'user' | 'assistant'; content: string };

// This visit's messages stay on the phone, so a reload keeps the chat. One key per visit:
// older visits' chats are dropped when a new one starts.
const chatKey = (slug: string, visitId: number | null) => `customa:chat:${slug}:${visitId ?? 0}`;
function loadMsgs(slug: string, visitId: number | null): Msg[] | null {
  try {
    const raw = localStorage.getItem(chatKey(slug, visitId));
    return raw ? (JSON.parse(raw) as Msg[]) : null;
  } catch {
    return null;
  }
}
function saveMsgs(slug: string, visitId: number | null, msgs: Msg[]) {
  try {
    const prefix = `customa:chat:${slug}:`;
    for (let i = localStorage.length - 1; i >= 0; i--) {
      const k = localStorage.key(i);
      if (k && k.startsWith(prefix) && k !== chatKey(slug, visitId)) localStorage.removeItem(k);
    }
    localStorage.setItem(chatKey(slug, visitId), JSON.stringify(msgs));
  } catch {
    // Private mode or storage full: the chat still works, it just won't survive a reload.
  }
}

const waitText = (s: number) => {
  if (s <= 0) return 'Scan again for your next plate';
  const minutes = Math.ceil(s / 60);
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `Your next plate can count in ${h > 0 ? `${h}h${m ? ` ${m}m` : ''}` : `${m} min`}`;
};

export function ChatPage({ slug }: { slug: string }) {
  const [stand, setStand] = useState<StandPublic | null>(null);
  const [chat, setChat] = useState<ChatState | null>(null);
  const [noPlate, setNoPlate] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState('');
  const [thinking, setThinking] = useState(false);
  const [slow, setSlow] = useState(false);
  const [showMemory, setShowMemory] = useState(false);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.stand(slug).then(setStand).catch(() => setLoadError(true));
    api
      .chatState(slug)
      .then((c) => {
        setChat(c);
        setMsgs(loadMsgs(slug, c.visit_id) ?? (c.opener ? [{ role: 'assistant', content: c.opener }] : []));
      })
      .catch((err: ApiError) => (err.status === 403 ? setNoPlate(true) : setLoadError(true)));
  }, [slug]);

  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth' }); }, [msgs, thinking, chat?.open]);

  const send = async (message: string) => {
    if (!message.trim() || thinking || !chat?.open) return;
    const history = msgs;
    const withMine: Msg[] = [...history, { role: 'user', content: message }];
    setMsgs(withMine);
    setText('');
    setThinking(true);
    // After 3 seconds of waiting, offer quick answers (the slow-AI screen).
    const slowTimer = setTimeout(() => setSlow(true), 3000);
    try {
      const r = await api.chat(slug, message, history);
      const next: Msg[] = r.reply ? [...withMine, { role: 'assistant', content: r.reply }] : withMine;
      setMsgs(next);
      saveMsgs(slug, r.chat.visit_id, next);
      setChat(r.chat);
    } catch {
      setMsgs((m) => [...m, { role: 'assistant', content: 'Network no gree. Try again small, or ask the vendor!' }]);
    } finally {
      clearTimeout(slowTimer);
      setThinking(false);
      setSlow(false);
    }
  };

  const forget = async () => {
    try {
      const r = await api.forgetChatMemory(slug);
      setChat((c) => (c ? { ...c, memory: r.memory } : c));
    } catch {
      // Leave it as it is; the customer can try again.
    }
  };

  const ch = stand?.character;
  const first = ch?.name.split(' ')[0] ?? 'Bisi';
  const standName = stand?.stand.name ?? 'The vendor';
  const quick = ['What should I eat today?', 'Any special today?', 'Tell me a joke 😄', 'How do I get jara?'];
  const mem = chat?.memory;
  const remembered = mem
    ? ([
        mem.favourite_item && `Your favourite: ${mem.favourite_item}`,
        mem.last_item && mem.last_item !== mem.favourite_item && `Last dish you talked about: ${mem.last_item}`,
        mem.follow_up && `To ask you next time: “${mem.follow_up}”`,
      ].filter(Boolean) as string[])
    : [];
  const closed = chat !== null && !chat.open;

  return (
    <main className="phone page-in" style={{ display: 'flex', flexDirection: 'column' }}>
      <header className="topbar">
        <Link to={`/s/${slug}`} className="link-btn">Back</Link>
        <span style={{ fontWeight: 800 }}>Talk to {first}</span>
        <Logo size={22} />
      </header>
      {/* The character glows softly while it thinks, like a voice assistant's orb. */}
      <div className={`chat-stage${thinking ? ' thinking' : ''}`}>
        <span className="chat-orb" aria-hidden="true" />
        <Character body={ch?.body} color={ch?.color} accessory={ch?.accessory} expression={closed ? 'wink' : thinking ? 'proud' : 'happy'} pose={closed || !thinking ? 'wave' : 'idle'} size={110} react follow />
      </div>
      <p className="chat-private">
        <LockIcon /> Private chat. {standName} only sees questions about the food.
      </p>

      {!chat && !noPlate && !loadError ? (
        <CharacterLoader kind="chat" character={ch} size={70} />
      ) : noPlate ? (
        <div className="stack">
          <div className="card-outline">
            <span style={{ fontSize: '1.0625rem', fontWeight: 800 }}>Count a plate first, then we can talk! 🍛</span>
            <span className="note">Scan the QR code at the stand to count your plate. Your chat opens with each plate.</span>
          </div>
          <Link to={`/s/${slug}`} className="btn">Go to my card</Link>
        </div>
      ) : loadError ? (
        <div className="stack"><p className="error">Could not load the chat. Check your network and try again.</p></div>
      ) : (
        <>
          <div className="chat-log" aria-live="polite" style={{ flexGrow: 1 }}>
            {msgs.map((m, i) => (
              <div key={i} className={`msg ${m.role === 'user' ? 'msg-me' : 'msg-bisi'}`}>{m.content}</div>
            ))}
            {thinking && (
              <div className="msg msg-bisi typing" role="status" aria-label={`${first} is typing`}>
                <i /><i /><i />
              </div>
            )}
            {slow && <p className="note" style={{ margin: 0 }}>{first} is a bit slow right now. Tap a quick question:</p>}
            <div ref={end} />
          </div>

          {chat && (
            <div style={{ padding: '0 12px 8px' }}>
              <button type="button" className="link-btn" aria-expanded={showMemory} onClick={() => setShowMemory(!showMemory)}>
                {showMemory ? `Hide what ${first} remembers` : `What ${first} remembers about you`}
              </button>
              {showMemory && (
                <div className="card-outline" style={{ marginTop: 8, gap: 6 }}>
                  {remembered.length === 0 ? (
                    <span className="note">Nothing yet. Tell {first} your favourite dish!</span>
                  ) : (
                    <>
                      {remembered.map((line) => <span key={line} style={{ fontSize: '0.9375rem', fontWeight: 600 }}>{line}</span>)}
                      <button type="button" className="link-btn" style={{ alignSelf: 'flex-start' }} onClick={forget}>Forget all of this</button>
                    </>
                  )}
                </div>
              )}
            </div>
          )}

          {closed ? (
            <div className="chat-closed" role="status">
              <span style={{ fontSize: '1.0625rem', fontWeight: 800 }}>{first} don go back to the pot 🍲</span>
              <span style={{ fontSize: '0.9375rem', fontWeight: 600 }}>Your chat opens again with your next plate, right where you stopped.</span>
              <span className="note">{waitText(chat.seconds_left)}</span>
              <Link to={`/s/${slug}`} className="btn">Back to my card</Link>
            </div>
          ) : (
            <>
              <div className="quick">
                {quick.map((q) => <button key={q} onClick={() => send(q)} disabled={thinking || !chat}>{q}</button>)}
              </div>
              <form className="chat-form" onSubmit={(e) => { e.preventDefault(); send(text); }}>
                <label htmlFor="chat-input" style={{ position: 'absolute', left: -9999 }}>Message</label>
                <input id="chat-input" className="input" value={text} onChange={(e) => setText(e.target.value)} placeholder={`Message ${first}`} maxLength={500} />
                <button className="btn" style={{ width: 100 }} type="submit" disabled={thinking || !text.trim() || !chat}>Send</button>
              </form>
            </>
          )}
        </>
      )}
    </main>
  );
}

const LockIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <rect x="4" y="11" width="16" height="10" rx="2" />
    <path d="M8 11V7a4 4 0 0 1 8 0v4" />
  </svg>
);
