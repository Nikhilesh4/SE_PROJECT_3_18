"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import PageShell, { ErrorNote, Spinner } from "@/app/components/PageShell";
import OpportunityCard from "@/app/feed/OpportunityCard";
import { errorMessage } from "@/lib/errors";
import { searchOpportunities, type SearchResponse } from "@/lib/insights";
import { useBookmarks } from "@/lib/useBookmarks";

const PAGE_SIZE = 24;
const CLOSING_OPTIONS = [
    { value: "", label: "Any time" },
    { value: "3", label: "Within 3 days" },
    { value: "7", label: "Within a week" },
    { value: "30", label: "Within a month" },
];

export default function SearchPage() {
    const { isBookmarked, toggleBookmark } = useBookmarks();
    const [q, setQ] = useState("");
    const [category, setCategory] = useState("");
    const [source, setSource] = useState("");
    const [remote, setRemote] = useState(false);
    const [minStipend, setMinStipend] = useState("");
    const [closing, setClosing] = useState("");
    const [page, setPage] = useState(0);
    const [result, setResult] = useState<SearchResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const submitted = useRef({ q: "" });

    const run = useCallback(
        async (nextPage: number, text: string) => {
            setLoading(true);
            setError(null);
            try {
                const data = await searchOpportunities({
                    q: text,
                    category,
                    source,
                    remote,
                    min_stipend: minStipend ? Number(minStipend) : undefined,
                    closing_within_days: closing ? Number(closing) : undefined,
                    limit: PAGE_SIZE,
                    offset: nextPage * PAGE_SIZE,
                });
                setResult(data);
                setPage(nextPage);
            } catch (err) {
                setError(errorMessage(err, "Search failed. Please try again."));
            } finally {
                setLoading(false);
            }
        },
        [category, source, remote, minStipend, closing]
    );

    // Facet changes re-run the search using the last submitted text.
    useEffect(() => {
        const t = setTimeout(() => void run(0, submitted.current.q), 0);
        return () => clearTimeout(t);
    }, [run]);

    const onSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        submitted.current = { q };
        void run(0, q);
    };

    const totalPages = result ? Math.ceil(result.total / PAGE_SIZE) : 0;
    const select = "mt-1 w-full rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-300";

    return (
        <PageShell
            wide
            title="Search"
            subtitle={'Full-text search across every posting. Use quotes for exact phrases, OR for alternatives, and -word to exclude.'}
        >
            <form onSubmit={onSubmit} role="search" className="flex gap-2 mb-5">
                <input
                    value={q}
                    onChange={(e) => setQ(e.target.value)}
                    aria-label="Search opportunities"
                    placeholder='e.g. "machine learning" intern -senior'
                    className="flex-1 rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
                />
                <button type="submit" className="px-5 py-2.5 rounded-xl bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-500 cursor-pointer">
                    Search
                </button>
            </form>

            <div className="grid grid-cols-1 lg:grid-cols-[16rem_1fr] gap-6 items-start">
                <aside aria-label="Filters" className="rounded-2xl border border-slate-200 bg-white p-4 space-y-4 shadow-sm">
                    <label className="block text-xs font-medium text-slate-600">
                        Category
                        <select value={category} onChange={(e) => setCategory(e.target.value)} className={select}>
                            <option value="">All categories</option>
                            {Object.entries(result?.facets.categories ?? {}).map(([c, n]) => (
                                <option key={c} value={c}>{c} ({n})</option>
                            ))}
                            {category && !(category in (result?.facets.categories ?? {})) && <option value={category}>{category}</option>}
                        </select>
                    </label>
                    <label className="block text-xs font-medium text-slate-600">
                        Source
                        <select value={source} onChange={(e) => setSource(e.target.value)} className={select}>
                            <option value="">All sources</option>
                            {Object.entries(result?.facets.sources ?? {}).map(([s, n]) => (
                                <option key={s} value={s}>{s} ({n})</option>
                            ))}
                            {source && !(source in (result?.facets.sources ?? {})) && <option value={source}>{source}</option>}
                        </select>
                    </label>
                    <label className="flex items-center gap-2 text-sm text-slate-700">
                        <input type="checkbox" checked={remote} onChange={(e) => setRemote(e.target.checked)} className="rounded border-slate-300 text-indigo-600" />
                        Remote only{result ? <span className="text-xs text-slate-400">({result.facets.remote})</span> : null}
                    </label>
                    <label className="block text-xs font-medium text-slate-600">
                        Minimum stipend (₹/month)
                        <input
                            type="number"
                            min={0}
                            step={5000}
                            value={minStipend}
                            onChange={(e) => setMinStipend(e.target.value)}
                            placeholder="e.g. 20000"
                            className={select}
                        />
                    </label>
                    <label className="block text-xs font-medium text-slate-600">
                        Deadline
                        <select value={closing} onChange={(e) => setClosing(e.target.value)} className={select}>
                            {CLOSING_OPTIONS.map((o) => (
                                <option key={o.value} value={o.value}>{o.label}</option>
                            ))}
                        </select>
                    </label>
                    <button
                        type="button"
                        onClick={() => { setCategory(""); setSource(""); setRemote(false); setMinStipend(""); setClosing(""); }}
                        className="text-xs text-indigo-600 hover:underline cursor-pointer"
                    >
                        Reset filters
                    </button>
                </aside>

                <section aria-live="polite">
                    <ErrorNote message={error} />
                    {loading && !result ? (
                        <Spinner label="Searching..." />
                    ) : result && result.items.length === 0 ? (
                        <p className="text-center text-sm text-slate-500 py-16">No postings match. Try fewer filters or different words.</p>
                    ) : result ? (
                        <>
                            <p className="text-sm text-slate-600 mb-3">
                                {result.total} result{result.total === 1 ? "" : "s"}
                                {loading && <span className="ml-2 text-slate-400">updating…</span>}
                            </p>
                            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                                {result.items.map((item) => (
                                    <OpportunityCard
                                        key={item.guid ?? item.url}
                                        item={item}
                                        isBookmarked={item.id != null ? isBookmarked(item.id) : false}
                                        onToggleBookmark={toggleBookmark}
                                    />
                                ))}
                            </div>
                            {totalPages > 1 && (
                                <nav className="flex items-center justify-center gap-3 mt-6" aria-label="Pagination">
                                    <button disabled={page === 0 || loading} onClick={() => void run(page - 1, submitted.current.q)} className="px-3 py-1.5 rounded-lg border border-slate-300 bg-white text-sm disabled:opacity-40 cursor-pointer">← Previous</button>
                                    <span className="text-sm text-slate-600">Page {page + 1} of {totalPages}</span>
                                    <button disabled={page + 1 >= totalPages || loading} onClick={() => void run(page + 1, submitted.current.q)} className="px-3 py-1.5 rounded-lg border border-slate-300 bg-white text-sm disabled:opacity-40 cursor-pointer">Next →</button>
                                </nav>
                            )}
                        </>
                    ) : null}
                </section>
            </div>
        </PageShell>
    );
}
