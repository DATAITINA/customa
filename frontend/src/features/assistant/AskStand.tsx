import { useState } from 'react';
import { apiClient, type ApiError, type Character as CharacterT } from '../../api';
import { Character } from '../../components/Character';
import './assistant.css';

// "Ask about your stand": the vendor's AI helper (MSFLib ai-api agent with read-only tools over
// this stand's own numbers). Answers come from real data; it never sees phone numbers.
const SUGGESTIONS = ['How did this week go?', 'When am I busiest?', 'Who are my regulars?', 'Which food sells best for me?'];

export function AskStand({ slug, character }: { slug: string; character?: CharacterT | null }) {
  const [question, setQuestion] = useState('');
  const [asked, setAsked] = useState<string | null>(null);
  const [answer, setAnswer] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ask = async (q: string) => {
    const text = q.trim();
    if (!text || busy) return;
    setBusy(true);
    setError(null);
    setAsked(text);
    setAnswer(null);
    try {
      const r = await apiClient<{ content: string }>('POST', `/stands/${slug}/assistant/ask?protocol=langchain`, { question: text });
      setAnswer(r.content || 'I could not find an answer this time. Try asking another way.');
      setQuestion('');
    } catch (err) {
      const e = err as ApiError;
      setError(e.status === 503 ? 'Your helper is resting right now. Try again in a minute.' : e.message || 'Could not get an answer. Try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card-outline ask-stand" aria-label="Ask about your stand">
      <div className="ask-head">
        <Character body={character?.body} color={character?.color} accessory={character?.accessory} expression="happy" pose={busy ? 'hop' : 'wave'} size={52} />
        <div>
          <span className="eyebrow">ASK ABOUT YOUR STAND</span>
          <p className="ask-sub">Your helper reads your own plates, customers and payments, and answers in plain words.</p>
        </div>
      </div>
      <div className="ask-chips">
        {SUGGESTIONS.map((s) => (
          <button key={s} type="button" className="link-btn" disabled={busy} onClick={() => ask(s)}>{s}</button>
        ))}
      </div>
      <form className="ask-form" onSubmit={(e) => { e.preventDefault(); ask(question); }}>
        <input className="input" value={question} maxLength={300} placeholder="Ask anything about your stand…" onChange={(e) => setQuestion(e.target.value)} aria-label="Your question" />
        <button type="submit" className="btn ask-send" disabled={busy || !question.trim()}>{busy ? '…' : 'Ask'}</button>
      </form>
      {asked && (
        <div className="ask-thread" aria-live="polite">
          <div className="ask-q">{asked}</div>
          <div className="ask-a">{busy ? 'Checking your numbers…' : error ? <span className="error">{error}</span> : answer}</div>
        </div>
      )}
    </section>
  );
}
