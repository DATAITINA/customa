import { useEffect, useState } from 'react';
import { api, type StandPublic } from '../../api';
import { Link } from '../../App';
import { Logo } from '../../components/Logo';
import { CharacterLoader } from '../../components/Loading';
import { CatchJara } from './CatchJara';
import { MenuQuiz } from './MenuQuiz';
import './games.css';

type Game = 'catch' | 'quiz';

// Mini-games at /s/{slug}/play. Everything runs on the phone: no plates, no server writes.
export function PlayPage({ slug }: { slug: string }) {
  const [stand, setStand] = useState<StandPublic | null>(null);
  const [failed, setFailed] = useState(false);
  const [game, setGame] = useState<Game>('catch');

  useEffect(() => {
    let alive = true;
    setFailed(false);
    api
      .stand(slug)
      .then((s) => alive && setStand(s))
      .catch(() => alive && setFailed(true));
    return () => {
      alive = false;
    };
  }, [slug]);

  const ch = stand?.character ?? null;
  const first = ch?.name.split(' ')[0] ?? stand?.stand.name ?? '';

  return (
    <main className="phone page-in">
      <header className="topbar">
        <Link to={`/s/${slug}`} className="back-btn" aria-label="Back to my card"><span aria-hidden="true">←</span> My card</Link>
        <span className="games-title">{first ? `Play with ${first}` : 'Play'}</span>
        <Logo size={22} />
      </header>

      {failed ? (
        <div className="games-body">
          <div className="card">
            <span className="display games-h">Wahala!</span>
            <p className="note" style={{ margin: 0 }}>We no fit load this stand. Check your network and try again.</p>
          </div>
        </div>
      ) : !stand ? (
        <CharacterLoader kind="game" />
      ) : (
        <div className="games-body">
          <div className="games-picker" role="group" aria-label="Pick a game">
            <button type="button" className="games-pick" aria-pressed={game === 'catch'} onClick={() => setGame('catch')}>
              <span className="games-pick-emoji" aria-hidden="true">🍗</span>
              <span className="games-pick-name">Catch the jara</span>
              <span className="games-pick-sub">20 seconds. Dodge the pepper!</span>
            </button>
            <button type="button" className="games-pick" aria-pressed={game === 'quiz'} onClick={() => setGame('quiz')}>
              <span className="games-pick-emoji" aria-hidden="true">₦</span>
              <span className="games-pick-name">Which one cost pass?</span>
              <span className="games-pick-sub">5 rounds from the real menu</span>
            </button>
          </div>
          {/* key remounts the game on switch so its loop and timers are torn down */}
          {game === 'catch' ? <CatchJara key="catch" slug={slug} character={ch} /> : <MenuQuiz key="quiz" slug={slug} character={ch} />}
        </div>
      )}
    </main>
  );
}
