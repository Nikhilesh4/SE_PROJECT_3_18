"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/useAuth";
import { useBookmarks } from "@/lib/useBookmarks";
import { NormalizedRssItem } from "@/lib/useFeed";
import OpportunityCard from "@/app/feed/OpportunityCard";
import api from "@/lib/api";

export default function BookmarksTab() {
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

    if (checking || !isAuthenticated) return null;

    return (
        <div>
            <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
                <p className="text-sm text-slate-600">
                    {loading
                        ? "Loading saved opportunities…"
                        : `${items.length} bookmarked ${items.length === 1 ? "opportunity" : "opportunities"}`}
                </p>
                <Link
                    href="/feed"
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-500 transition-all"
                >
                    Browse feed
                </Link>
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
    );
}
