"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/useAuth";
import { NormalizedRssItem, RssAggregationResponse } from "@/lib/useFeed";

const CATEGORY_STYLES: Record<string, { bg: string; text: string; border: string; icon: string }> = {
    internship: { bg: "bg-indigo-50", text: "text-indigo-700", border: "border-indigo-200", icon: "🎓" },
    hackathon: { bg: "bg-pink-50", text: "text-pink-700", border: "border-pink-200", icon: "⚡" },
    research: { bg: "bg-sky-50", text: "text-sky-700", border: "border-sky-200", icon: "🔬" },
    job: { bg: "bg-amber-50", text: "text-amber-700", border: "border-amber-200", icon: "💼" },
    freelance: { bg: "bg-orange-50", text: "text-orange-700", border: "border-orange-200", icon: "🌐" },
};

function formatDate(iso: string | null): string {
    if (!iso) return "Not specified";
    try {
        return new Date(iso).toLocaleDateString("en-US", {
            weekday: "long",
            month: "long",
            day: "numeric",
            year: "numeric",
        });
    } catch {
        return "Not specified";
    }
}

function formatTime(iso: string | null): string {
    if (!iso) return "";
    try {
        return new Date(iso).toLocaleTimeString("en-US", {
            hour: "2-digit",
            minute: "2-digit",
        });
    } catch {
        return "";
    }
}

export default function OpportunityDetailPage() {
    const { isAuthenticated, checking: authChecking } = useAuth();
    const params = useParams();
    const router = useRouter();
    const [item, setItem] = useState<NormalizedRssItem | null>(null);
    const [loading, setLoading] = useState(true);
    const [notFound, setNotFound] = useState(false);

    const itemId = typeof params.id === "string" ? decodeURIComponent(params.id) : "";

    useEffect(() => {
        if (!itemId || authChecking || !isAuthenticated) return;

        // First try localStorage cache
        try {
            const raw = localStorage.getItem("unicompass_feed_cache_v2");
            if (raw) {
                const cached = JSON.parse(raw);
                const data: RssAggregationResponse = cached.data;
                const found = data.items.find(
                    (i) => (i.guid || i.url) === itemId
                );
                if (found) {
                    setItem(found);
                    setLoading(false);
                    return;
                }
            }
        } catch { /* ignore */ }

        // Fallback: fetch from API and search
        (async () => {
            try {
                const res = await fetch(`/api/feeds?limit_per_feed=500`);
                if (res.ok) {
                    const data: RssAggregationResponse = await res.json();
                    const found = data.items.find(
                        (i) => (i.guid || i.url) === itemId
                    );
                    if (found) {
                        setItem(found);
                    } else {
                        setNotFound(true);
                    }
                } else {
                    setNotFound(true);
                }
            } catch {
                setNotFound(true);
            } finally {
                setLoading(false);
            }
        })();
    }, [itemId, authChecking, isAuthenticated]);

    // Auth spinner
    if (authChecking || !isAuthenticated) {
        return (
            <div className="min-h-screen bg-slate-50 flex items-center justify-center">
                <div className="flex flex-col items-center gap-4">
                    <div className="w-10 h-10 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                    <p className="text-slate-600 text-sm">Verifying access...</p>
                </div>
            </div>
        );
    }

    // Loading state
    if (loading) {
        return (
            <div className="min-h-screen bg-slate-50 relative overflow-hidden">
                <div className="pointer-events-none fixed inset-0">
                    <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[700px] h-[400px] bg-gradient-to-b from-indigo-100 via-sky-50 to-transparent rounded-full blur-3xl" />
                </div>
                <div className="relative max-w-4xl mx-auto px-4 sm:px-6 py-8 pt-24">
                    <div className="animate-pulse space-y-6">
                        <div className="h-4 w-24 rounded bg-slate-200" />
                        <div className="h-8 w-3/4 rounded bg-slate-200" />
                        <div className="h-4 w-full rounded bg-slate-100" />
                        <div className="h-4 w-full rounded bg-slate-100" />
                        <div className="h-4 w-2/3 rounded bg-slate-100" />
                    </div>
                </div>
            </div>
        );
    }

    // Not found
    if (notFound || !item) {
        return (
            <div className="min-h-screen bg-slate-50 flex items-center justify-center">
                <div className="text-center space-y-4">
                    <div className="w-16 h-16 mx-auto rounded-full bg-red-500/10 flex items-center justify-center text-3xl">🔍</div>
                    <h2 className="text-xl font-bold text-slate-900">Opportunity Not Found</h2>
                    <p className="text-slate-600 text-sm">This item may have been removed or the link is invalid.</p>
                    <button
                        onClick={() => router.push("/feed")}
                        className="px-6 py-2.5 rounded-xl text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-500 transition-all"
                    >
                        ← Back to Feed
                    </button>
                </div>
            </div>
        );
    }

    const cat = CATEGORY_STYLES[item.category] ?? {
        bg: "bg-slate-100", text: "text-slate-700", border: "border-slate-200", icon: "📌",
    };

    return (
        <div className="min-h-screen bg-slate-50 relative overflow-hidden">
            {/* Ambient background */}
            <div className="pointer-events-none fixed inset-0">
                <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[700px] h-[400px] bg-gradient-to-b from-indigo-100 via-sky-50 to-transparent rounded-full blur-3xl" />
                <div className="absolute bottom-1/3 right-0 w-72 h-72 bg-indigo-100/60 rounded-full blur-3xl" />
            </div>

            <div className="relative max-w-4xl mx-auto px-4 sm:px-6 py-8 pt-24">
                {/* Back link */}
                <Link
                    href="/feed"
                    className="inline-flex items-center gap-2 text-sm text-slate-600 hover:text-indigo-700 transition-colors mb-6 group"
                >
                    <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="19" y1="12" x2="5" y2="12" />
                        <polyline points="12 19 5 12 12 5" />
                    </svg>
                    Back to Discovery Feed
                </Link>

                {/* Main card */}
                <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
                    {/* Header */}
                    <div className="p-6 sm:p-8 border-b border-slate-200">
                        <div className="flex flex-wrap items-center gap-3 mb-4">
                            <span className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm font-semibold ${cat.bg} ${cat.text} border ${cat.border}`}>
                                <span className="text-base">{cat.icon}</span>
                                {item.category.charAt(0).toUpperCase() + item.category.slice(1)}
                            </span>
                            <span className="text-xs text-slate-500">📡 {item.source_name}</span>
                        </div>

                        <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 leading-tight mb-3">
                            {item.title}
                        </h1>

                        {item.author && (
                            <p className="text-slate-600 text-sm flex items-center gap-2">
                                <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                                    <circle cx="12" cy="7" r="4" />
                                </svg>
                                {item.author}
                            </p>
                        )}
                    </div>

                    {/* Meta info */}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-px bg-slate-200">
                        <div className="p-4 sm:p-5 bg-white">
                            <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">Published</p>
                            <p className="text-sm text-slate-900 font-medium">{formatDate(item.published_at)}</p>
                            {item.published_at && (
                                <p className="text-xs text-slate-500">{formatTime(item.published_at)}</p>
                            )}
                        </div>
                        <div className="p-4 sm:p-5 bg-white">
                            <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">Source</p>
                            <p className="text-sm text-slate-900 font-medium">{item.source_name}</p>
                            <p className="text-xs text-slate-500 truncate">{item.feed_url}</p>
                        </div>
                        <div className="p-4 sm:p-5 bg-white">
                            <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">Category</p>
                            <p className={`text-sm font-medium ${cat.text}`}>
                                {cat.icon} {item.category.charAt(0).toUpperCase() + item.category.slice(1)}
                            </p>
                        </div>
                    </div>

                    {/* Description / Summary */}
                    <div className="p-6 sm:p-8">
                        <h2 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
                            <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5 text-indigo-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                                <polyline points="14 2 14 8 20 8" />
                                <line x1="16" y1="13" x2="8" y2="13" />
                                <line x1="16" y1="17" x2="8" y2="17" />
                                <polyline points="10 9 9 9 8 9" />
                            </svg>
                            Description
                        </h2>
                        {item.summary ? (
                            <div
                                className="text-slate-700 text-sm leading-relaxed space-y-3 prose prose-slate prose-sm max-w-none"
                                dangerouslySetInnerHTML={{ __html: item.summary }}
                            />
                        ) : (
                            <p className="text-slate-500 text-sm italic">No description available for this opportunity.</p>
                        )}
                    </div>

                    {/* Tags */}
                    {item.tags.length > 0 && (
                        <div className="px-6 sm:px-8 pb-6">
                            <h3 className="text-sm font-semibold text-slate-400 mb-3 flex items-center gap-2">
                                <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z" />
                                    <line x1="7" y1="7" x2="7.01" y2="7" />
                                </svg>
                                Tags
                            </h3>
                            <div className="flex flex-wrap gap-2">
                                {item.tags.map((tag) => (
                                    <span
                                        key={tag}
                                        className="px-3 py-1 rounded-lg text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200 hover:border-indigo-200 hover:text-indigo-700 transition-colors"
                                    >
                                        {tag}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Action buttons */}
                    <div className="p-6 sm:p-8 border-t border-slate-200 bg-slate-50">
                        <div className="flex flex-col sm:flex-row gap-3">
                            <a
                                href={item.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex-1 inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl font-semibold text-white bg-indigo-600 hover:bg-indigo-500 transition-all text-sm"
                            >
                                <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                                    <polyline points="15 3 21 3 21 9" />
                                    <line x1="10" y1="14" x2="21" y2="3" />
                                </svg>
                                Visit Original Source
                            </a>
                            <button
                                onClick={() => {
                                    navigator.clipboard.writeText(item.url);
                                }}
                                className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl font-semibold text-slate-700 bg-white border border-slate-300 hover:bg-slate-100 transition-all text-sm"
                            >
                                <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                                </svg>
                                Copy Link
                            </button>
                        </div>
                    </div>
                </div>

                {/* GUID info */}
                {item.guid && (
                    <p className="mt-4 text-center text-xs text-slate-600">
                        ID: {item.guid}
                    </p>
                )}
            </div>
        </div>
    );
}
