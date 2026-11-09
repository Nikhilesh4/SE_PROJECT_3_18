"use client";

import { FormEvent, Fragment, useState } from "react";
import { askPosting, PostingAnswer } from "@/lib/rag";

const SUGGESTIONS = ["Is it paid?", "Who can apply?", "What skills are needed?", "Is it remote?"];

/** Renders "[2]" markers in the answer as small citation chips. */
function AnswerText({ text, onCite }: { text: string; onCite: (n: number) => void }) {
    const parts = text.split(/(\[\d+\])/g);
    return (
        <p className="text-sm text-slate-800 leading-relaxed">
            {parts.map((part, i) => {
                const m = part.match(/^\[(\d+)\]$/);
                if (!m) return <Fragment key={i}>{part}</Fragment>;
                const n = Number(m[1]);
                return (
                    <button
                        key={i}
                        type="button"
                        onClick={() => onCite(n)}
                        className="mx-0.5 inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1 rounded bg-indigo-100 text-indigo-700 text-[11px] font-semibold align-text-top hover:bg-indigo-200"
                        aria-label={`Show source ${n}`}
                    >
                        {n}
                    </button>
                );
            })}
        </p>
    );
}

export default function AskPosting({ itemId }: { itemId: number }) {
    const [question, setQuestion] = useState("");
    const [asked, setAsked] = useState("");
    const [result, setResult] = useState<PostingAnswer | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [highlight, setHighlight] = useState<number | null>(null);

    async function ask(q: string) {
        const trimmed = q.trim();
        if (trimmed.length < 2 || loading) return;
        setLoading(true);
        setError(null);
        setResult(null);
        setHighlight(null);
        setAsked(trimmed);
        try {
            setResult(await askPosting(itemId, trimmed));
            setQuestion("");
        } catch (err) {
            setError(err instanceof Error ? err.message : "Could not get an answer.");
        } finally {
            setLoading(false);
        }
    }

    function onSubmit(e: FormEvent) {
        e.preventDefault();
        ask(question);
    }

    const cited = result ? result.passages.filter((p) => result.citations.includes(p.n)) : [];

    return (
        <div className="p-6 sm:p-8 border-t border-slate-200">
            <h2 className="text-lg font-semibold text-slate-900 mb-1 flex items-center gap-2">
                <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5 text-indigo-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" />
                    <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
                    <line x1="12" y1="17" x2="12.01" y2="17" />
                </svg>
                Ask about this posting
            </h2>
            <p className="text-xs text-slate-500 mb-4">
                Answers come only from this posting&apos;s text, with the passages they rely on.
            </p>

            <form onSubmit={onSubmit} className="flex gap-2">
                <input
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    maxLength={500}
                    placeholder="e.g. Can second-year students apply?"
                    className="flex-1 min-w-0 px-4 py-2.5 rounded-xl border border-slate-300 bg-white text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-400"
                />
                <button
                    type="submit"
                    disabled={loading || question.trim().length < 2}
                    className="px-5 py-2.5 rounded-xl text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                >
                    {loading ? "Asking…" : "Ask"}
                </button>
            </form>

            {!result && !loading && (
                <div className="flex flex-wrap gap-2 mt-3">
                    {SUGGESTIONS.map((s) => (
                        <button
                            key={s}
                            type="button"
                            onClick={() => ask(s)}
                            className="px-3 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200 hover:border-indigo-200 hover:text-indigo-700 transition-colors"
                        >
                            {s}
                        </button>
                    ))}
                </div>
            )}

            {loading && (
                <div className="mt-4 space-y-2 animate-pulse" aria-live="polite">
                    <div className="h-3 w-1/3 rounded bg-slate-200" />
                    <div className="h-3 w-full rounded bg-slate-100" />
                    <div className="h-3 w-2/3 rounded bg-slate-100" />
                </div>
            )}

            {error && (
                <p className="mt-4 text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-xl px-4 py-3">
                    {error}
                </p>
            )}

            {result && (
                <div className="mt-4 space-y-3" aria-live="polite">
                    <p className="text-xs font-medium text-slate-500">{asked}</p>
                    <div
                        className={`rounded-xl border px-4 py-3 ${
                            result.not_found ? "bg-slate-50 border-slate-200" : "bg-indigo-50/50 border-indigo-100"
                        }`}
                    >
                        <AnswerText text={result.answer} onCite={setHighlight} />
                    </div>

                    {cited.length > 0 && (
                        <div>
                            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Sources</p>
                            <ol className="space-y-2">
                                {cited.map((p) => (
                                    <li
                                        key={p.n}
                                        className={`flex gap-3 text-xs leading-relaxed rounded-lg border px-3 py-2 transition-colors ${
                                            highlight === p.n
                                                ? "border-indigo-300 bg-indigo-50 text-slate-800"
                                                : "border-slate-200 bg-white text-slate-600"
                                        }`}
                                    >
                                        <span className="shrink-0 font-semibold text-indigo-700">{p.n}</span>
                                        <span>{p.text}</span>
                                    </li>
                                ))}
                            </ol>
                        </div>
                    )}

                    <button
                        type="button"
                        onClick={() => {
                            setResult(null);
                            setAsked("");
                        }}
                        className="text-xs font-medium text-indigo-700 hover:text-indigo-600"
                    >
                        Ask another question
                    </button>
                </div>
            )}
        </div>
    );
}
