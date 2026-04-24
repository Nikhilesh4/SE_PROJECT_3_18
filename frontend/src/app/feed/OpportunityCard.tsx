"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { NormalizedRssItem } from "@/lib/useFeed";

const CATEGORY_STYLES: Record<string, { bg: string; text: string; dot: string }> = {
    internship: { bg: "bg-indigo-50",  text: "text-indigo-700",  dot: "bg-indigo-500"  },
    hackathon:  { bg: "bg-pink-50",    text: "text-pink-700",    dot: "bg-pink-500"    },
    research:   { bg: "bg-sky-50",     text: "text-sky-700",     dot: "bg-sky-500"     },
    job:        { bg: "bg-amber-50",   text: "text-amber-700",   dot: "bg-amber-500"   },
    freelance:  { bg: "bg-orange-50",  text: "text-orange-700",  dot: "bg-orange-500"  },
    course:     { bg: "bg-emerald-50", text: "text-emerald-700", dot: "bg-emerald-500" },
};

const SOURCE_ICONS: Record<string, string> = {
    remoteok:       "🌐",
    weworkremotely: "💼",
    arxiv:          "📄",
    hackernews:     "🔸",
    default:        "📡",
};

function formatDate(iso: string | null): string {
    if (!iso) return "";
    try {
        return new Date(iso).toLocaleDateString("en-US", {
            month: "short", day: "numeric", year: "numeric",
        });
    } catch {
        return "";
    }
}

interface MatchResult {
    hasMatch: boolean;
    /** Skills found in tags */
    tagMatches: string[];
    /** Skills found in title words */
    titleMatches: string[];
    /** Skills found in summary text */
    summaryMatches: string[];
}

/** Compute where the user's skills appear in this opportunity. */
function computeMatch(item: NormalizedRssItem, skillSet: Set<string>): MatchResult {
    if (skillSet.size === 0) {
        return { hasMatch: false, tagMatches: [], titleMatches: [], summaryMatches: [] };
    }

    // Tag matches — exact token comparison
    const tagMatches = item.tags
        .filter((t) => skillSet.has(t.trim().toLowerCase()))
        .slice(0, 3);  // cap display to 3

    // Title word matches — split on non-alpha boundaries
    const titleWords = new Set(
        item.title.toLowerCase().split(/[\s\-\/,().]+/).filter(Boolean)
    );
    const titleMatches = [...skillSet]
        .filter((s) => titleWords.has(s))
        .slice(0, 3);

    // Summary substring matches (skills ≥ 3 chars to avoid noise)
    const summaryLower = item.summary.toLowerCase();
    const summaryMatches = [...skillSet]
        .filter((s) => s.length >= 3 && summaryLower.includes(s))
        .slice(0, 3);

    const hasMatch =
        tagMatches.length > 0 ||
        titleMatches.length > 0 ||
        summaryMatches.length > 0;

    return { hasMatch, tagMatches, titleMatches, summaryMatches };
}

interface Props {
    item: NormalizedRssItem;
    /** When provided, skills are matched against tags, title, and summary */
    highlightSkills?: string[];
    /** Whether this item is bookmarked by the current user */
    isBookmarked?: boolean;
    /** Callback to toggle bookmark state */
    onToggleBookmark?: (itemId: number) => void;
}

export default function OpportunityCard({ item, highlightSkills = [], isBookmarked = false, onToggleBookmark }: Props) {
    const [animating, setAnimating] = useState(false);
    const cat = CATEGORY_STYLES[item.category] ?? {
        bg: "bg-slate-100", text: "text-slate-700", dot: "bg-slate-500",
    };
    const icon    = SOURCE_ICONS[item.source_name.toLowerCase()] ?? SOURCE_ICONS.default;
    const dateStr = formatDate(item.published_at);
    const itemId  = encodeURIComponent(item.guid || item.url);

    const skillSet = useMemo(
        () => new Set(highlightSkills.map((s) => s.trim().toLowerCase())),
        [highlightSkills]
    );

    const match = useMemo(
        () => computeMatch(item, skillSet),
        [item, skillSet]
    );

    // Tags shown in the card — matched ones shown first
    const displayedTags = useMemo(() => {
        const matched = item.tags.filter((t) =>
            skillSet.has(t.trim().toLowerCase())
        );
        const unmatched = item.tags.filter(
            (t) => !skillSet.has(t.trim().toLowerCase())
        );
        return [...matched, ...unmatched].slice(0, 5);
    }, [item.tags, skillSet]);

    return (
        <article
            className={`group flex flex-col gap-3 p-5 rounded-2xl bg-white border transition-all duration-200 shadow-sm hover:shadow-md ${
                match.hasMatch
                    ? "border-violet-300 hover:border-violet-400 ring-1 ring-violet-100"
                    : "border-slate-200 hover:border-indigo-200"
            }`}
        >
            {/* ── Header row ───────────────────────────────────────── */}
            <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2 flex-wrap">
                    {/* Category badge */}
                    <span
                        className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold ${cat.bg} ${cat.text}`}
                    >
                        <span className={`w-1.5 h-1.5 rounded-full ${cat.dot}`} />
                        {item.category}
                    </span>

                    {/* 🎯 Match badge — shown for ANY match (tag, title, or summary) */}
                    {match.hasMatch && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-violet-100 text-violet-700 border border-violet-300">
                            🎯 Match
                        </span>
                    )}
                </div>

                <div className="flex items-center gap-1">
                    {/* Bookmark button */}
                    {item.id != null && onToggleBookmark && (
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                setAnimating(true);
                                onToggleBookmark(item.id!);
                                setTimeout(() => setAnimating(false), 400);
                            }}
                            title={isBookmarked ? "Remove bookmark" : "Bookmark this opportunity"}
                            className={`shrink-0 p-1.5 rounded-lg transition-all duration-200 ${
                                isBookmarked
                                    ? "text-rose-500 hover:text-rose-600 hover:bg-rose-50"
                                    : "text-slate-400 hover:text-rose-500 hover:bg-rose-50"
                            } ${animating ? "scale-125" : "scale-100"}`}
                        >
                            <svg
                                xmlns="http://www.w3.org/2000/svg"
                                className="w-4 h-4"
                                viewBox="0 0 24 24"
                                fill={isBookmarked ? "currentColor" : "none"}
                                stroke="currentColor"
                                strokeWidth="2"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                            >
                                <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
                            </svg>
                        </button>
                    )}

                    {/* External link */}
                    <a
                        href={item.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        title="Open original"
                        onClick={(e) => e.stopPropagation()}
                        className="shrink-0 p-1.5 rounded-lg text-slate-500 hover:text-indigo-700 hover:bg-indigo-50 transition-colors"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                            <polyline points="15 3 21 3 21 9" />
                            <line x1="10" y1="14" x2="21" y2="3" />
                        </svg>
                    </a>
                </div>
            </div>

            {/* ── Title ────────────────────────────────────────────── */}
            <Link
                href={`/feed/${itemId}`}
                className="text-slate-900 font-semibold text-base leading-snug line-clamp-2 group-hover:text-indigo-700 transition-colors"
            >
                {item.title}
            </Link>

            {/* ── Match reason row ─────────────────────────────────── */}
            {/* Shows how the item was matched so the user understands relevance */}
            {match.hasMatch && (
                <div className="flex flex-wrap gap-1.5 text-xs">
                    {match.tagMatches.length > 0 && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-violet-50 border border-violet-200 text-violet-700">
                            <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
                            </svg>
                            tag: {match.tagMatches.join(", ")}
                        </span>
                    )}
                    {match.titleMatches.length > 0 && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-50 border border-blue-200 text-blue-700">
                            <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h8m-8 6h16" />
                            </svg>
                            title: {match.titleMatches.join(", ")}
                        </span>
                    )}
                    {match.summaryMatches.length > 0 && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-sky-50 border border-sky-200 text-sky-700">
                            <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                            description: {match.summaryMatches.join(", ")}
                        </span>
                    )}
                </div>
            )}

            {/* ── Summary ──────────────────────────────────────────── */}
            {item.summary && (
                <p className="text-slate-600 text-sm leading-relaxed line-clamp-3">
                    {item.summary.replace(/<[^>]+>/g, " ").slice(0, 200)}
                </p>
            )}

            {/* ── Tags — matched ones shown first with highlight ───── */}
            {displayedTags.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                    {displayedTags.map((tag) => {
                        const isMatched = skillSet.has(tag.trim().toLowerCase());
                        return (
                            <span
                                key={tag}
                                className={`px-2 py-0.5 rounded-md text-xs border transition-colors ${
                                    isMatched
                                        ? "bg-violet-100 text-violet-700 border-violet-200 font-medium"
                                        : "bg-slate-100 text-slate-600 border-slate-200"
                                }`}
                            >
                                {isMatched && <span className="mr-0.5">✓</span>}
                                {tag}
                            </span>
                        );
                    })}
                    {item.tags.length > 5 && (
                        <span className="px-2 py-0.5 rounded-md text-xs bg-slate-100 text-slate-500 border border-slate-200">
                            +{item.tags.length - 5}
                        </span>
                    )}
                </div>
            )}

            {/* ── Footer ───────────────────────────────────────────── */}
            <div className="mt-auto pt-2 flex items-center justify-between border-t border-slate-200 text-xs text-slate-500">
                <span className="flex items-center gap-1.5">
                    {icon}
                    <span>{item.source_name}</span>
                </span>
                <div className="flex items-center gap-3">
                    {dateStr && <span>{dateStr}</span>}
                    <Link
                        href={`/feed/${itemId}`}
                        className="text-indigo-600 hover:text-indigo-500 font-medium transition-colors"
                    >
                        View Details →
                    </Link>
                </div>
            </div>
        </article>
    );
}
