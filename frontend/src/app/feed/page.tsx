"use client";

import { useMemo, useState } from "react";
import { useFeed } from "@/lib/useFeed";
import { useAuth } from "@/lib/useAuth";
import OpportunityCard from "./OpportunityCard";
import SourceStatusPanel from "./SourceStatusPanel";

const ALL_CATEGORIES = [
    { value: "", label: "All", icon: "✨" },
    { value: "internship", label: "Internship", icon: "🎓" },
    { value: "job", label: "Job", icon: "💼" },
    { value: "hackathon", label: "Hackathon", icon: "⚡" },
    { value: "research", label: "Research", icon: "🔬" },
    { value: "freelance", label: "Freelance", icon: "🌐" },
    { value: "course", label: "Course", icon: "📚" },
];

const ITEMS_PER_PAGE = 50;

function SkeletonCard() {
    return (
        <div className="flex flex-col gap-3 p-5 rounded-2xl bg-white border border-slate-200 animate-pulse">
            <div className="flex items-center justify-between">
                <div className="h-5 w-20 rounded-full bg-slate-200" />
                <div className="h-6 w-6 rounded-lg bg-slate-200" />
            </div>
            <div className="space-y-2">
                <div className="h-4 rounded bg-slate-200 w-full" />
                <div className="h-4 rounded bg-slate-200 w-4/5" />
            </div>
            <div className="space-y-1.5">
                <div className="h-3 rounded bg-slate-100 w-full" />
                <div className="h-3 rounded bg-slate-100 w-full" />
                <div className="h-3 rounded bg-slate-100 w-3/4" />
            </div>
            <div className="flex gap-1.5">
                {[1, 2, 3].map((i) => (
                    <div key={i} className="h-5 w-14 rounded-md bg-slate-200" />
                ))}
            </div>
            <div className="pt-2 border-t border-slate-200 flex justify-between">
                <div className="h-3 w-20 rounded bg-slate-200" />
                <div className="h-3 w-16 rounded bg-slate-200" />
            </div>
        </div>
    );
}

export default function FeedPage() {
    const { isAuthenticated, checking } = useAuth();
    const [selectedCategory, setSelectedCategory] = useState("");
    const [search, setSearch] = useState("");
    const [page, setPage] = useState(1);

    const offset = (page - 1) * ITEMS_PER_PAGE;

    const { data, loading, error, refetch } = useFeed({
        category: selectedCategory || undefined,
        limitPerFeed: ITEMS_PER_PAGE,
        offset,
    });

    // Client-side search filter on top of category filter
    const filtered = useMemo(() => {
        if (!data) return [];
        const q = search.trim().toLowerCase();
        if (!q) return data.items;
        return data.items.filter(
            (item) =>
                item.title.toLowerCase().includes(q) ||
                item.summary.toLowerCase().includes(q) ||
                item.source_name.toLowerCase().includes(q) ||
                item.tags.some((t) => t.toLowerCase().includes(q))
        );
    }, [data, search]);

    const totalPages = data ? Math.max(1, Math.ceil(data.total_items / ITEMS_PER_PAGE)) : 1;

    const handleCategoryChange = (value: string) => {
        setSelectedCategory(value);
        setSearch("");
        setPage(1);
    };

    // Auth guard — show spinner while checking
    if (checking || !isAuthenticated) {
        return (
            <div className="min-h-screen bg-slate-50 flex items-center justify-center">
                <div className="flex flex-col items-center gap-4">
                    <div className="w-10 h-10 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                    <p className="text-slate-600 text-sm">Verifying access...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-50 relative overflow-hidden">
            {/* Ambient background */}
            <div className="pointer-events-none fixed inset-0">
                <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[700px] h-[400px] bg-gradient-to-b from-indigo-100 via-sky-50 to-transparent rounded-full blur-3xl" />
                <div className="absolute bottom-1/3 right-0 w-72 h-72 bg-indigo-100/60 rounded-full blur-3xl" />
            </div>

            <div className="relative max-w-7xl mx-auto px-4 sm:px-6 py-8 pt-24">
                {/* Page header */}
                <div className="mb-8">
                    {/* Data-source indicator — tells TA/dev where this response came from */}
                    <div className="flex items-center gap-2 mb-4 flex-wrap">
                        {/* Always-on badge */}
                        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50 border border-indigo-200 text-indigo-700 text-xs font-medium">
                            <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-pulse" />
                            Live RSS Aggregation
                        </div>

                        {/* Dynamic cache-origin badge — only shown once data arrives */}
                        {data && (
                            <div
                                title={data.from_cache
                                    ? "Response served from Redis cache (fast path — no DB query)"
                                    : "Response fetched fresh from PostgreSQL (cache miss)"}
                                className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full border text-xs font-semibold transition-all ${data.from_cache
                                        ? "bg-amber-50 border-amber-300 text-amber-700"
                                        : "bg-emerald-50 border-emerald-300 text-emerald-700"
                                    }`}
                            >
                                <span>{data.from_cache ? "⚡" : "🗄️"}</span>
                                <span>{data.from_cache ? "Redis Cache" : "PostgreSQL DB"}</span>
                            </div>
                        )}
                    </div>
                    <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
                        <div>
                            <h1 className="text-3xl font-bold text-slate-900 tracking-tight">
                                Discovery Feed
                            </h1>
                            <p className="mt-1 text-slate-600 text-sm">
                                {data
                                    ? `${data.total_items.toLocaleString()} opportunities from ${data.sources.length} sources · refreshed ${new Date(data.fetched_at).toLocaleTimeString()}`
                                    : "Fetching live opportunities…"}
                            </p>
                        </div>

                        {/* Refresh button */}
                        <button
                            onClick={refetch}
                            disabled={loading}
                            className="shrink-0 inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                        >
                            <svg
                                xmlns="http://www.w3.org/2000/svg"
                                className={`w-4 h-4 ${loading ? "animate-spin" : ""}`}
                                viewBox="0 0 24 24" fill="none" stroke="currentColor"
                                strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                            >
                                <path d="M21.5 2v6h-6" />
                                <path d="M2.5 12A10 10 0 0 1 18.5 4.3L21.5 8" />
                                <path d="M2.5 22v-6h6" />
                                <path d="M21.5 12A10 10 0 0 1 5.5 19.7L2.5 16" />
                            </svg>
                            {loading ? "Fetching…" : "Refresh"}
                        </button>
                    </div>
                </div>

                {/* Search bar */}
                <div className="relative mb-6">
                    <svg
                        xmlns="http://www.w3.org/2000/svg"
                        className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400"
                        viewBox="0 0 24 24" fill="none" stroke="currentColor"
                        strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                    >
                        <circle cx="11" cy="11" r="8" />
                        <line x1="21" y1="21" x2="16.65" y2="16.65" />
                    </svg>
                    <input
                        type="text"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        placeholder="Search by title, source, or tags…"
                        className="w-full pl-10 pr-4 py-3 rounded-xl bg-white border border-slate-300 text-slate-900 placeholder:text-slate-400 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-500 transition-all"
                    />
                    {search && (
                        <button
                            onClick={() => setSearch("")}
                            className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                            </svg>
                        </button>
                    )}
                </div>

                <div className="flex flex-col lg:flex-row gap-6">
                    {/* ── Sidebar ── */}
                    <aside className="lg:w-56 shrink-0 flex flex-col gap-4">
                        {/* Category filter */}
                        <div className="rounded-xl border border-slate-200 bg-white p-3 flex flex-col gap-1">
                            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider px-2 mb-1">
                                Category
                            </p>
                            {ALL_CATEGORIES.map((cat) => {
                                const isActive = selectedCategory === cat.value;
                                return (
                                    <button
                                        key={cat.value}
                                        onClick={() => handleCategoryChange(cat.value)}
                                        className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-all text-left ${isActive
                                            ? "bg-indigo-50 text-indigo-700 border border-indigo-200"
                                            : "text-slate-700 hover:text-slate-900 hover:bg-slate-100 border border-transparent"
                                            }`}
                                    >
                                        <span className="text-base">{cat.icon}</span>
                                        {cat.label}
                                    </button>
                                );
                            })}
                        </div>

                        {/* Source status panel */}
                        {data && <SourceStatusPanel sources={data.sources} />}
                    </aside>

                    {/* ── Main content ── */}
                    <main className="flex-1 min-w-0">
                        {/* Error state */}
                        {error && !loading && (
                            <div className="flex flex-col items-center justify-center py-20 text-center gap-4">
                                <div className="w-12 h-12 rounded-full bg-red-500/10 flex items-center justify-center text-2xl">🚫</div>
                                <div>
                                    <p className="text-slate-900 font-semibold">Failed to load feed</p>
                                    <p className="text-slate-600 text-sm mt-1">{error}</p>
                                </div>
                                <button
                                    onClick={refetch}
                                    className="px-4 py-2 rounded-lg text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-500 transition-colors"
                                >
                                    Try again
                                </button>
                            </div>
                        )}

                        {/* Loading skeletons */}
                        {loading && (
                            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                                {Array.from({ length: 9 }).map((_, i) => (
                                    <SkeletonCard key={i} />
                                ))}
                            </div>
                        )}

                        {/* Results */}
                        {!loading && !error && (
                            <>
                                {/* Results count */}
                                {data && (
                                    <p className="text-xs text-slate-500 mb-4">
                                        Showing <span className="text-slate-800 font-medium">{filtered.length}</span>
                                        {data.total_items !== filtered.length && (
                                            <> of {data.total_items.toLocaleString()}</>
                                        )}{" "}
                                        results{selectedCategory && <> · <span className="text-indigo-700">{selectedCategory}</span></>}
                                        {search && <> matching <span className="text-indigo-700">&ldquo;{search}&rdquo;</span></>}
                                        {totalPages > 1 && <> · Page <span className="text-slate-800 font-medium">{page}</span> of {totalPages}</>}
                                    </p>
                                )}

                                {/* Grid */}
                                {filtered.length > 0 ? (
                                    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                                        {filtered.map((item, idx) => (
                                            <OpportunityCard key={item.guid ?? item.url ?? idx} item={item} />
                                        ))}
                                    </div>
                                ) : (
                                    // Empty state
                                    <div className="flex flex-col items-center justify-center py-24 text-center gap-4">
                                        <div className="w-14 h-14 rounded-full bg-violet-500/10 flex items-center justify-center text-3xl">🔍</div>
                                        <div>
                                            <p className="text-slate-900 font-semibold text-lg">No results found</p>
                                            <p className="text-slate-600 text-sm mt-1">
                                                {search
                                                    ? `No opportunities match "${search}"`
                                                    : `No ${selectedCategory || "opportunity"} listings available right now.`}
                                            </p>
                                        </div>
                                        <button
                                            onClick={() => { setSelectedCategory(""); setSearch(""); setPage(1); }}
                                            className="px-4 py-2 rounded-lg text-sm font-medium text-slate-700 bg-white border border-slate-300 hover:bg-slate-100 transition-colors"
                                        >
                                            Clear filters
                                        </button>
                                    </div>
                                )}

                                {/* ── Pagination controls ── */}
                                {totalPages > 1 && (
                                    <div className="mt-8 flex items-center justify-center gap-3">
                                        <button
                                            onClick={() => setPage((p) => Math.max(1, p - 1))}
                                            disabled={page <= 1}
                                            className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-sm font-semibold border transition-all disabled:opacity-40 disabled:cursor-not-allowed bg-white border-slate-300 text-slate-700 hover:bg-slate-100"
                                        >
                                            <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                                <polyline points="15 18 9 12 15 6" />
                                            </svg>
                                            Previous
                                        </button>

                                        <div className="flex items-center gap-1">
                                            {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
                                                let pageNum: number;
                                                if (totalPages <= 7) {
                                                    pageNum = i + 1;
                                                } else if (page <= 4) {
                                                    pageNum = i + 1;
                                                } else if (page >= totalPages - 3) {
                                                    pageNum = totalPages - 6 + i;
                                                } else {
                                                    pageNum = page - 3 + i;
                                                }
                                                return (
                                                    <button
                                                        key={pageNum}
                                                        onClick={() => setPage(pageNum)}
                                                        className={`w-10 h-10 rounded-lg text-sm font-medium transition-all ${pageNum === page
                                                            ? "bg-indigo-600 text-white shadow-sm"
                                                            : "text-slate-700 hover:bg-slate-100 border border-transparent hover:border-slate-200"
                                                            }`}
                                                    >
                                                        {pageNum}
                                                    </button>
                                                );
                                            })}
                                        </div>

                                        <button
                                            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                                            disabled={page >= totalPages}
                                            className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-sm font-semibold border transition-all disabled:opacity-40 disabled:cursor-not-allowed bg-white border-slate-300 text-slate-700 hover:bg-slate-100"
                                        >
                                            Next
                                            <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                                <polyline points="9 18 15 12 9 6" />
                                            </svg>
                                        </button>
                                    </div>
                                )}
                            </>
                        )}
                    </main>
                </div>
            </div>
        </div>
    );
}
