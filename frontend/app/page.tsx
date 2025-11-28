'use client';

import { useState, useEffect, useRef } from 'react';
import HeaderNav from '@/components/HeaderNav';

interface Citation {
  source: string;
  text: string;
  number: number;
}

interface Output {
  query: string;
  response: string;
  citations: Citation[];
}

export default function Page() {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState<Output | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const responseRef = useRef<HTMLDivElement | null>(null);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError('');
    setResult(null);

    try {
      const res = await fetch(`http://localhost:80/query?q=${encodeURIComponent(query)}`);
      if (!res.ok) {
        throw new Error('Failed to fetch response');
      }
      const data: Output = await res.json();
      setResult(data);
    } catch (err) {
      setError('An error occurred while fetching the answer. Please try again.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const renderResponseHtml = (text: string) => {
    const escapeHtml = (str: string) =>
      str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');

    return escapeHtml(text).replace(/\[(\d+)\]/g, (_m, num) =>
      `<a href="#source-${num}" class="citation-link" data-citation="${num}">[${num}]</a>`
    );
  };

  useEffect(() => {
    if (!result) return;
    const container = responseRef.current;
    if (!container) return;

    const links = Array.from(container.querySelectorAll<HTMLElement>('a.citation-link'));
    const cards = Array.from(document.querySelectorAll<HTMLElement>('.citation-card[data-citation]'));

    const cardFor = (n: string | null) =>
      cards.find((c) => c.dataset.citation === n) ?? null;

    const linksFor = (n: string | null) =>
      links.filter((l) => l.dataset.citation === n);

    const onLinkEnter = (e: Event) => {
      const t = e.currentTarget as HTMLElement;
      const n = t.dataset.citation ?? null;
      const card = cardFor(n);
      if (card) card.classList.add('highlight');
      t.classList.add('highlight');
    };
    const onLinkLeave = (e: Event) => {
      const t = e.currentTarget as HTMLElement;
      const n = t.dataset.citation ?? null;
      const card = cardFor(n);
      if (card) card.classList.remove('highlight');
      t.classList.remove('highlight');
    };
    const onLinkClick = (e: Event) => {
      e.preventDefault();
      const t = e.currentTarget as HTMLElement;
      const n = t.dataset.citation ?? null;
      const card = cardFor(n);
      if (card) {
        card.scrollIntoView({ behavior: 'smooth', block: 'center' });
        card.classList.add('highlight');
        setTimeout(() => card.classList.remove('highlight'), 1200);
      }
    };

    const onCardEnter = (e: Event) => {
      const c = e.currentTarget as HTMLElement;
      const n = c.dataset.citation ?? null;
      const ls = linksFor(n);
      c.classList.add('highlight');
      ls.forEach((l) => l.classList.add('highlight'));
    };
    const onCardLeave = (e: Event) => {
      const c = e.currentTarget as HTMLElement;
      const n = c.dataset.citation ?? null;
      const ls = linksFor(n);
      c.classList.remove('highlight');
      ls.forEach((l) => l.classList.remove('highlight'));
    };

    links.forEach((l) => {
      l.addEventListener('mouseenter', onLinkEnter);
      l.addEventListener('mouseleave', onLinkLeave);
      l.addEventListener('click', onLinkClick);
    });
    cards.forEach((c) => {
      c.addEventListener('mouseenter', onCardEnter);
      c.addEventListener('mouseleave', onCardLeave);
    });

    return () => {
      links.forEach((l) => {
        l.removeEventListener('mouseenter', onLinkEnter);
        l.removeEventListener('mouseleave', onLinkLeave);
        l.removeEventListener('click', onLinkClick);
      });
      cards.forEach((c) => {
        c.removeEventListener('mouseenter', onCardEnter);
        c.removeEventListener('mouseleave', onCardLeave);
      });
    };
  }, [result]);

  return (
    <div className="min-h-screen flex flex-col">
      <HeaderNav signOut={() => { }} />

      <main className="flex-grow container mx-auto px-4 py-12 max-w-4xl">
        <div className="text-center mb-12">
          <h1 className="text-5xl font-serif font-bold text-slate-900 mb-4 tracking-tight">
            Westeros Legal Assistant
          </h1>
          <p className="text-lg text-slate-600 font-light">
            Your AI-powered guide to the laws of The Seven Kingdoms.
          </p>
        </div>

        <form onSubmit={handleSearch} className="mb-12">
          <div className="relative flex items-center">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g., What happens if I steal?"
              className="w-full p-4 pl-6 pr-32 text-lg rounded-full border-2 border-slate-200 shadow-sm focus:border-slate-800 focus:ring-0 transition-colors outline-none bg-white placeholder:text-slate-400"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className="absolute right-2 top-2 bottom-2 px-6 bg-slate-900 text-white rounded-full font-medium hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? 'Asking...' : 'Ask'}
            </button>
          </div>
          {error && <p className="mt-4 text-red-600 text-center">{error}</p>}
        </form>

        {result && (
          <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="bg-white rounded-2xl p-8 shadow-lg border border-slate-100">
              <h2 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-4">
                Answer
              </h2>
              <div
                ref={responseRef}
                className="prose prose-lg text-slate-800 leading-relaxed"
                dangerouslySetInnerHTML={{ __html: renderResponseHtml(result.response) }}
              />
            </div>

            {result.citations && result.citations.length > 0 && (
              <div className="bg-slate-50 rounded-2xl p-8 border border-slate-200">
                <h2 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-6">
                  Sources & Citations
                </h2>
                <div className="grid gap-6">
                  {result.citations.map((citation, idx) => (
                    <div
                      key={idx}
                      id={`source-${citation.number}`}
                      data-citation={String(citation.number)}
                      className="citation-card bg-white p-6 rounded-xl border border-slate-200 shadow-sm"
                    >
                      <div className="flex items-center gap-2 mb-3">
                        <span className="bg-slate-100 text-slate-600 text-xs font-bold px-2 py-1 rounded">
                          {`Source ${citation.number}`}
                        </span>
                        <span className="font-serif font-medium text-slate-900 ml-3">
                          {citation.source}
                        </span>
                      </div>
                      <p className="text-slate-600 text-sm italic border-l-2 border-slate-300 pl-4">
                        {citation.text}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </main>

      <style>{`
        .citation-link {
          text-decoration: underline;
          text-underline-offset: 2px;
          cursor: pointer;
          color: rgba(17,24,39,0.9); /* slate-900-ish */
          padding: 0 2px;
          border-radius: 4px;
          transition: background-color 120ms, color 120ms;
        }
        .citation-link:hover, .citation-link.highlight {
          background: rgba(99,102,241,0.10); /* indigo-ish highlight */
          color: rgb(67,56,202);
        }
        /* Ensure the card has an explicit baseline transform and is prepared for animation */
        .citation-card {
          transform: translateY(0);
          will-change: transform, box-shadow;
          transition: transform 180ms cubic-bezier(.2,.9,.2,1), box-shadow 180ms cubic-bezier(.2,.9,.2,1);
        }
        /* Use box-shadow (not outline) for the visual emphasis so there is no layout shift */
        .citation-card.highlight {
          transform: translateY(-3px);
          box-shadow:
            0 6px 18px rgba(2,6,23,0.06),
            0 18px 40px rgba(2,6,23,0.08),
            0 0 0 6px rgba(99,102,241,0.06); /* subtle halo instead of outline */
        }
      `}</style>
    </div>
  );
}
