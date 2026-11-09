"use client";

import { useState } from "react";
import PageShell, { ErrorNote, Spinner } from "@/app/components/PageShell";
import { errorMessage } from "@/lib/errors";
import { scoutResearch, type ScoutResult } from "@/lib/insights";

export default function ResearchPage() {
    const [topic, setTopic] = useState("");
    const [result, setResult] = useState<ScoutResult | null>(null);
    const [draft, setDraft] = useState<{ for: string; subject: string; body: string; note?: string } | null>(null);
    const [loading, setLoading] = useState(false);
    const [drafting, setDrafting] = useState<string | null>(null);
    const [copied, setCopied] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const search = async (e: React.FormEvent) => {
        e.preventDefault();
        if (topic.trim().length < 3) return;
        setLoading(true);
        setError(null);
        setDraft(null);
        try {
            setResult(await scoutResearch(topic.trim()));
        } catch (err) {
            setError(errorMessage(err, "The scout could not run. Please try again."));
        } finally {
            setLoading(false);
        }
    };

    const makeDraft = async (name: string) => {
        setDrafting(name);
        setError(null);
        try {
            const r = await scoutResearch(result?.topic ?? topic.trim(), name);
            if (r.draft) setDraft({ for: name, subject: r.draft.subject, body: r.draft.body, note: r.draft.review_note });
        } catch (err) {
            setError(errorMessage(err, "Could not draft the email."));
        } finally {
            setDrafting(null);
        }
    };

    const copy = async () => {
        if (!draft) return;
        try {
            await navigator.clipboard.writeText(`Subject: ${draft.subject}\n\n${draft.body}`);
            setCopied(true);
            setTimeout(() => setCopied(false), 1800);
        } catch {
            /* clipboard unavailable */
        }
    };

    return (
        <PageShell
            title="Research scout"
            subtitle="Find recent papers on a topic, see who is publishing them, and draft a first email to a lab. Drafts are for you to review and send yourself."
        >
            <form onSubmit={search} className="flex gap-2 mb-6">
                <input
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    aria-label="Research topic"
                    maxLength={120}
                    placeholder="e.g. efficient transformers, protein folding, federated learning"
                    className="flex-1 rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
                />
                <button disabled={loading || topic.trim().length < 3} className="px-5 py-2.5 rounded-xl bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-500 disabled:opacity-50 cursor-pointer">
                    {loading ? "Scouting…" : "Scout"}
                </button>
            </form>

            <ErrorNote message={error} />
            {loading && <Spinner label="Searching arXiv and Semantic Scholar..." />}

            {result && !loading && (
                <div className="space-y-6">
                    {result.errors.length > 0 && (
                        <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                            Some sources did not respond ({result.errors.map((e) => e.split(":")[0]).join(", ")}). Results may be incomplete.
                        </p>
                    )}

                    <section aria-labelledby="contacts-h">
                        <h2 id="contacts-h" className="font-semibold text-slate-900 mb-3">Suggested contacts</h2>
                        {result.contacts.length === 0 ? (
                            <p className="text-sm text-slate-500">No authors found for this topic.</p>
                        ) : (
                            <ul className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {result.contacts.map((c) => (
                                    <li key={c.name} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                                        <p className="font-semibold text-slate-900">{c.name}</p>
                                        {c.affiliations.length > 0 && <p className="text-xs text-slate-500">{c.affiliations.join(", ")}</p>}
                                        <ul className="mt-2 list-disc list-inside text-xs text-slate-600 space-y-0.5">
                                            {c.papers.map((p) => <li key={p} className="line-clamp-2">{p}</li>)}
                                        </ul>
                                        <div className="mt-3 flex items-center gap-3">
                                            <button onClick={() => makeDraft(c.name)} disabled={drafting === c.name} className="px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-semibold hover:bg-indigo-500 disabled:opacity-60 cursor-pointer">
                                                {drafting === c.name ? "Drafting…" : "Draft cold email"}
                                            </button>
                                            {c.homepage && <a href={c.homepage} target="_blank" rel="noopener noreferrer" className="text-xs text-indigo-600 hover:underline">Homepage ↗</a>}
                                        </div>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </section>

                    {draft && (
                        <section aria-label="Email draft" className="rounded-2xl border border-indigo-200 bg-indigo-50/40 p-5">
                            <div className="flex items-center justify-between gap-3 mb-2">
                                <h2 className="font-semibold text-slate-900">Draft for {draft.for}</h2>
                                <button onClick={copy} className="px-3 py-1.5 rounded-lg border border-slate-300 bg-white text-xs font-medium hover:bg-slate-100 cursor-pointer">
                                    {copied ? "Copied ✓" : "Copy"}
                                </button>
                            </div>
                            <p className="text-sm text-slate-700"><span className="font-medium">Subject:</span> {draft.subject}</p>
                            <pre className="mt-2 whitespace-pre-wrap font-[family-name:var(--font-inter)] text-sm text-slate-800">{draft.body}</pre>
                            <p className="mt-3 text-xs text-amber-700">{draft.note ?? "This is a draft. Check every claim, add personal details, and send it yourself."}</p>
                        </section>
                    )}

                    <section aria-labelledby="papers-h">
                        <h2 id="papers-h" className="font-semibold text-slate-900 mb-3">Recent papers</h2>
                        {result.papers.length === 0 ? (
                            <p className="text-sm text-slate-500">No papers found.</p>
                        ) : (
                            <ul className="space-y-3">
                                {result.papers.map((p) => (
                                    <li key={p.url || p.title} className="rounded-xl border border-slate-200 bg-white p-4">
                                        <a href={p.url} target="_blank" rel="noopener noreferrer" className="font-medium text-slate-900 hover:text-indigo-700">{p.title} ↗</a>
                                        <p className="text-xs text-slate-500 mt-0.5">
                                            {p.authors.slice(0, 4).join(", ")}{p.authors.length > 4 ? " et al." : ""} · {p.year ?? "n.d."} · {p.source === "arxiv" ? "arXiv" : "Semantic Scholar"}
                                        </p>
                                        {p.abstract && <p className="text-sm text-slate-600 mt-2 line-clamp-3">{p.abstract}</p>}
                                    </li>
                                ))}
                            </ul>
                        )}
                    </section>
                </div>
            )}
        </PageShell>
    );
}
