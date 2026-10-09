import { useEffect, useRef, useState } from 'react';
import { Logo } from '../components/Logo';
import { api, type StandPublic } from '../api';
import { Character } from '../components/Character';
import { Link } from '../App';

type Msg = { role: 'user' | 'assistant'; content: string };

export function ChatPage({ slug }: { slug: string }) {
  const [stand, setStand] = useState<StandPublic | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState('');
  const [thinking, setThinking] = useState(false);
  const [slow, setSlow] = useState(false);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.stand(slug).then((s) => {
      setStand(s);
      const name = s.customer?.first_name;
      setMsgs([{ role: 'assistant', content: `${name ? name + '! ' : ''}${s.character?.greeting ?? 'Welcome!'} Ask me anything about the food.` }]);
    });
  }, [slug]);

  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth' }); }, [msgs, thinking]);

  const send = async (message: string) => {
    if (!message.trim() || thinking) return;
    const history = msgs;
    setMsgs([...history, { role: 'user', content: message }]);
    setText('');
    setThinking(true);
    // After 3 seconds of waiting, offer quick answers (the slow-AI screen).
    const slowTimer = setTimeout(() => setSlow(true), 3000);
    try {
      const r = await api.chat(slug, message, history);
      setMsgs((m) => [...m, { role: 'assistant', content: r.reply }]);
    } catch {
      setMsgs((m) => [...m, { role: 'assistant', content: 'Network no gree. Try again small, or ask the vendor!' }]);
    } finally {
      clearTimeout(slowTimer);
      setThinking(false);
      setSlow(false);
    }
  };

  const ch = stand?.character;
  const first = ch?.name.split(' ')[0] ?? 'Bisi';
  const quick = [
    'How much is the food?',
    ch?.menu?.[0] ? `How much is ${ch.menu[0].item.toLowerCase()}?` : 'What do you sell?',
    'How do I get jara?',
  ];

  return (
    <main className="phone" style={{ display: 'flex', flexDirection: 'column' }}>
      <header className="topbar">
        <Link to={`/s/${slug}`} className="link-btn">Back</Link>
        <span style={{ fontWeight: 800 }}>Talk to {first}</span>
        <Logo size={22} />
      </header>
      <div style={{ display: 'flex', justifyContent: 'center', background: 'var(--blush)', margin: '0 12px', borderRadius: 28 }}>
        <Character body={ch?.body} color={ch?.color} accessory={ch?.accessory} expression={thinking ? 'proud' : 'happy'} pose={thinking ? 'idle' : 'wave'} size={110} />
      </div>
      <div className="chat-log" aria-live="polite" style={{ flexGrow: 1 }}>
        {msgs.map((m, i) => (
          <div key={i} className={`msg ${m.role === 'user' ? 'msg-me' : 'msg-bisi'}`}>{m.content}</div>
        ))}
        {thinking && <div className="msg msg-bisi" aria-label={`${first} is typing`}>…</div>}
        {slow && <p className="note" style={{ margin: 0 }}>{first} is a bit slow right now. Tap a quick question:</p>}
        <div ref={end} />
      </div>
      <div className="quick">
        {quick.map((q) => <button key={q} onClick={() => send(q)} disabled={thinking}>{q}</button>)}
      </div>
      <form className="chat-form" onSubmit={(e) => { e.preventDefault(); send(text); }}>
        <label htmlFor="chat-input" style={{ position: 'absolute', left: -9999 }}>Message</label>
        <input id="chat-input" className="input" value={text} onChange={(e) => setText(e.target.value)} placeholder={`Message ${first}`} maxLength={500} />
        <button className="btn" style={{ width: 100 }} type="submit" disabled={thinking || !text.trim()}>Send</button>
      </form>
    </main>
  );
}
