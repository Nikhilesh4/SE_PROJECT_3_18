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
    { value: "course", label: "Course", icon: "📚" },
    { value: "freelance", label: "Freelance", icon: "🌐" },
];

function SkeletonCard() {
    return (
        <div className="flex flex-col gap-3 p-5 rounded-2xl bg-white/[0.04] border border-white/[0.06] animate-pulse">
            <div className="flex items-center justify-between">
                <div className="h-5 w-20 rounded-full bg-white/10" />
                <div className="h-6 w-6 rounded-lg bg-white/10" />
            </div>
            <div className="space-y-2">
                <div className="h-4 rounded bg-white/10 w-full" />
                <div className="h-4 rounded bg-white/10 w-4/5" />
            </div>
            <div className="space-y-1.5">
                <div className="h-3 rounded bg-white/[0.07] w-full" />
                <div className="h-3 rounded bg-white/[0.07] w-full" />
                <div className="h-3 rounded bg-white/[0.07] w-3/4" />
            </div>
            <div className="flex gap-1.5">
                {[1, 2, 3].map((i) => (
                    <div key={i} className="h-5 w-14 rounded-md bg-white/10" />
                ))}
            </div>
            <div className="pt-2 border-t border-white/[0.06] flex justify-between">
                <div className="h-3 w-20 rounded bg-white/10" />
                <div className="h-3 w-16 rounded bg-white/10" />
            </div>
        </div>
    );
}

export default function FeedPage() {
    const { isAuthenticated, checking } = useAuth();
    const [selectedCategory, setSelectedCategory] = useState("");
    const [search, setSearch] = useState("");

    const { data, loading, error, refetch } = useFeed({
        category: selectedCategory || undefined,
        limitPerFeed: 50,
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

    // Auth guard — show spinner while checking
    if (checking || !isAuthenticated) {
        return (
            <div className="min-h-screen bg-slate-950 flex items-center justify-center">
                <div className="flex flex-col items-center gap-4">
                    <div className="w-10 h-10 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
                    <p className="text-slate-400 text-sm">Verifying access…</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-950 relative overflow-hidden">
            {/* Ambient background */}
            <div className="pointer-events-none fixed inset-0">
                <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[700px] h-[400px] bg-gradient-to-b from-violet-600/15 via-indigo-600/8 to-transparent rounded-full blur-3xl" />
                <div className="absolute bottom-1/3 right-0 w-72 h-72 bg-indigo-600/8 rounded-full blur-3xl" />
            </div>

            <div className="relative max-w-7xl mx-auto px-4 sm:px-6 py-8 pt-24">
                {/* Page header */}
                <div className="mb-8">
                    <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-violet-500/10 border border-violet-500/20 text-violet-300 text-xs font-medium mb-4">
                        <span className="w-1.5 h-1.5 bg-violet-400 rounded-full animate-pulse" />
                        Live RSS Aggregation
                    </div>
                    <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
                        <div>
                            <h1 className="text-3xl font-bold text-white tracking-tight">
                                Discovery Feed
                            </h1>
                            <p className="mt-1 text-slate-400 text-sm">
                                {data
                                    ? `${data.total_items.toLocaleString()} opportunities from ${data.sources.length} sources · refreshed ${new Date(data.fetched_at).toLocaleTimeString()}`
                                    : "Fetching live opportunities…"}
                            </p>
                        </div>

                        {/* Refresh button */}
                        <button
                            onClick={refetch}
                            disabled={loading}
                            className="shrink-0 inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-white bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-violet-500/20 transition-all"
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
                        className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500"
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
                        className="w-full pl-10 pr-4 py-3 rounded-xl bg-white/[0.05] border border-white/[0.08] text-white placeholder:text-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500/50 transition-all"
                    />
                    {search && (
                        <button
                            onClick={() => setSearch("")}
                            className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
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
                        <div className="rounded-xl border border-white/[0.08] bg-white/[0.03] p-3 flex flex-col gap-1">
                            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider px-2 mb-1">
                                Category
                            </p>
                            {ALL_CATEGORIES.map((cat) => {
                                const isActive = selectedCategory === cat.value;
                                return (
                                    <button
                                        key={cat.value}
                                        onClick={() => { setSelectedCategory(cat.value); setSearch(""); }}
                                        className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-all text-left ${isActive
                                            ? "bg-violet-500/20 text-violet-200 border border-violet-500/30"
                                            : "text-slate-400 hover:text-slate-200 hover:bg-white/[0.05] border border-transparent"
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
                                    <p className="text-white font-semibold">Failed to load feed</p>
                                    <p className="text-slate-400 text-sm mt-1">{error}</p>
                                </div>
                                <button
                                    onClick={refetch}
                                    className="px-4 py-2 rounded-lg text-sm font-semibold text-white bg-violet-600 hover:bg-violet-500 transition-colors"
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
                                        Showing <span className="text-slate-300 font-medium">{filtered.length}</span>
                                        {data.total_items !== filtered.length && (
                                            <> of {data.total_items.toLocaleString()}</>
                                        )}{" "}
                                        results{selectedCategory && <> · <span className="text-violet-300">{selectedCategory}</span></>}
                                        {search && <> matching <span className="text-violet-300">&ldquo;{search}&rdquo;</span></>}
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
                                            <p className="text-white font-semibold text-lg">No results found</p>
                                            <p className="text-slate-400 text-sm mt-1">
                                                {search
                                                    ? `No opportunities match "${search}"`
                                                    : `No ${selectedCategory || "opportunity"} listings available right now.`}
                                            </p>
                                        </div>
                                        <button
                                            onClick={() => { setSelectedCategory(""); setSearch(""); }}
                                            className="px-4 py-2 rounded-lg text-sm font-medium text-slate-300 bg-white/5 border border-white/10 hover:bg-white/10 transition-colors"
                                        >
                                            Clear filters
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
