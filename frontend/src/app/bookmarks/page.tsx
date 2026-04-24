"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/useAuth";
import { useBookmarks } from "@/lib/useBookmarks";
import { NormalizedRssItem } from "@/lib/useFeed";
import OpportunityCard from "@/app/feed/OpportunityCard";
import api from "@/lib/api";

export default function BookmarksPage() {
    const { isAuthenticated, checking } = useAuth();
    const { isBookmarked, toggleBookmark } = useBookmarks();
    const [items, setItems] = useState<NormalizedRssItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchBookmarks = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await api.get("/api/bookmarks");
            setItems(res.data ?? []);
        } catch (err) {
            setError(String(err));
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (!checking && isAuthenticated) {
            fetchBookmarks();
        }
    }, [checking, isAuthenticated]);

    const handleToggle = async (itemId: number) => {
        await toggleBookmark(itemId);
        // Re-fetch to update the list (item removed)
        fetchBookmarks();
    };

    // Auth spinner
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
                <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[700px] h-[400px] bg-gradient-to-b from-rose-100 via-pink-50 to-transparent rounded-full blur-3xl" />
                <div className="absolute bottom-1/3 right-0 w-72 h-72 bg-rose-100/60 rounded-full blur-3xl" />
            </div>

            <div className="relative max-w-7xl mx-auto px-4 sm:px-6 py-8 pt-24">
                {/* Page header */}
                <div className="mb-8">
                    <div className="flex items-center gap-2 mb-4">
                        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-rose-50 border border-rose-200 text-rose-700 text-xs font-medium">
                            <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
                            </svg>
                            Saved Opportunities
                        </div>
                    </div>

                    <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
                        <div>
                            <h1 className="text-3xl font-bold text-slate-900 tracking-tight">
                                Your Bookmarks
                            </h1>
                            <p className="mt-1 text-slate-600 text-sm">
                                {loading
                                    ? "Loading saved opportunities…"
                                    : `${items.length} bookmarked ${items.length === 1 ? "opportunity" : "opportunities"}`}
                            </p>
                        </div>

                        <Link
                            href="/feed"
                            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-500 transition-all"
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <line x1="19" y1="12" x2="5" y2="12" />
                                <polyline points="12 19 5 12 12 5" />
                            </svg>
                            Back to Feed
                        </Link>
                    </div>
                </div>

                {/* Error state */}
                {error && !loading && (
                    <div className="flex flex-col items-center justify-center py-20 text-center gap-4">
                        <div className="w-12 h-12 rounded-full bg-red-500/10 flex items-center justify-center text-2xl">🚫</div>
                        <div>
                            <p className="text-slate-900 font-semibold">Failed to load bookmarks</p>
                            <p className="text-slate-600 text-sm mt-1">{error}</p>
                        </div>
                        <button
                            onClick={fetchBookmarks}
                            className="px-4 py-2 rounded-lg text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-500 transition-colors"
                        >
                            Try again
                        </button>
                    </div>
                )}

                {/* Loading skeletons */}
                {loading && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                        {Array.from({ length: 6 }).map((_, i) => (
                            <div key={i} className="flex flex-col gap-3 p-5 rounded-2xl bg-white border border-slate-200 animate-pulse">
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
                                    <div className="h-3 rounded bg-slate-100 w-3/4" />
                                </div>
                            </div>
                        ))}
                    </div>
                )}

                {/* Results */}
                {!loading && !error && (
                    <>
                        {items.length > 0 ? (
                            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                                {items.map((item, idx) => (
                                    <OpportunityCard
                                        key={item.guid ?? item.url ?? idx}
                                        item={item}
                                        isBookmarked={item.id != null ? isBookmarked(item.id) : true}
                                        onToggleBookmark={handleToggle}
                                    />
                                ))}
                            </div>
                        ) : (
                            <div className="flex flex-col items-center justify-center py-24 text-center gap-4">
                                <div className="w-16 h-16 rounded-full bg-rose-500/10 flex items-center justify-center text-4xl">
                                    💝
                                </div>
                                <div>
                                    <p className="text-slate-900 font-semibold text-lg">
                                        No bookmarks yet
                                    </p>
                                    <p className="text-slate-600 text-sm mt-1">
                                        Browse the Discovery Feed and save opportunities you&apos;re interested in.
                                    </p>
                                </div>
                                <Link
                                    href="/feed"
                                    className="px-6 py-2.5 rounded-xl text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-500 transition-all"
                                >
                                    Explore Opportunities
                                </Link>
                            </div>
                        )}
                    </>
                )}
            </div>
        </div>
    );
}
