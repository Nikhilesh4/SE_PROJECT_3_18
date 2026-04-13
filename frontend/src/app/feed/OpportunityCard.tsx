"use client";

import Link from "next/link";
import { NormalizedRssItem } from "@/lib/useFeed";

const CATEGORY_STYLES: Record<string, { bg: string; text: string; dot: string }> = {
    internship: { bg: "bg-violet-500/15", text: "text-violet-300", dot: "bg-violet-400" },
    hackathon: { bg: "bg-pink-500/15", text: "text-pink-300", dot: "bg-pink-400" },
    research: { bg: "bg-sky-500/15", text: "text-sky-300", dot: "bg-sky-400" },
    course: { bg: "bg-emerald-500/15", text: "text-emerald-300", dot: "bg-emerald-400" },
    job: { bg: "bg-amber-500/15", text: "text-amber-300", dot: "bg-amber-400" },
    freelance: { bg: "bg-orange-500/15", text: "text-orange-300", dot: "bg-orange-400" },
};

const SOURCE_ICONS: Record<string, string> = {
    remoteok: "🌐",
    weworkremotely: "💼",
    arxiv: "📄",
    hackernews: "🔸",
    default: "📡",
};

function formatDate(iso: string | null): string {
    if (!iso) return "";
    try {
        return new Date(iso).toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
        });
    } catch {
        return "";
    }
}

interface Props {
    item: NormalizedRssItem;
}

export default function OpportunityCard({ item }: Props) {
    const cat = CATEGORY_STYLES[item.category] ?? {
        bg: "bg-slate-500/15", text: "text-slate-300", dot: "bg-slate-400",
    };
    const icon = SOURCE_ICONS[item.source_name.toLowerCase()] ?? SOURCE_ICONS.default;
    const displayedTags = item.tags.slice(0, 4);
    const dateStr = formatDate(item.published_at);

    // Create a URL-safe ID from guid or url
    const itemId = encodeURIComponent(item.guid || item.url);

    return (
        <article className="group flex flex-col gap-3 p-5 rounded-2xl bg-white/[0.04] border border-white/[0.08] hover:bg-white/[0.07] hover:border-violet-500/30 transition-all duration-200 shadow-sm hover:shadow-violet-500/10 hover:shadow-lg">
            {/* Header row */}
            <div className="flex items-start justify-between gap-3">
                {/* Category badge */}
                <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold ${cat.bg} ${cat.text}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${cat.dot}`} />
                    {item.category}
                </span>

                {/* External link */}
                <a
                    href={item.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    title="Open original"
                    onClick={(e) => e.stopPropagation()}
                    className="shrink-0 p-1.5 rounded-lg text-slate-500 hover:text-violet-300 hover:bg-violet-500/10 transition-colors"
                >
                    <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                        <polyline points="15 3 21 3 21 9" />
                        <line x1="10" y1="14" x2="21" y2="3" />
                    </svg>
                </a>
            </div>

            {/* Title — links to detail page */}
            <Link
                href={`/feed/${itemId}`}
                className="text-white font-semibold text-base leading-snug line-clamp-2 group-hover:text-violet-200 transition-colors"
            >
                {item.title}
            </Link>

            {/* Summary */}
            {item.summary && (
                <p className="text-slate-400 text-sm leading-relaxed line-clamp-3">
                    {item.summary.replace(/<[^>]+>/g, " ").slice(0, 200)}
                </p>
            )}

            {/* Tags */}
            {displayedTags.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                    {displayedTags.map((tag) => (
                        <span
                            key={tag}
                            className="px-2 py-0.5 rounded-md text-xs bg-slate-800 text-slate-400 border border-white/5"
                        >
                            {tag}
                        </span>
                    ))}
                    {item.tags.length > 4 && (
                        <span className="px-2 py-0.5 rounded-md text-xs bg-slate-800 text-slate-500 border border-white/5">
                            +{item.tags.length - 4}
                        </span>
                    )}
                </div>
            )}

            {/* Footer */}
            <div className="mt-auto pt-2 flex items-center justify-between border-t border-white/[0.06] text-xs text-slate-500">
                <span className="flex items-center gap-1.5">
                    {icon}
                    <span>{item.source_name}</span>
                </span>
                <div className="flex items-center gap-3">
                    {dateStr && <span>{dateStr}</span>}
                    <Link
                        href={`/feed/${itemId}`}
                        className="text-violet-400 hover:text-violet-300 font-medium transition-colors"
                    >
                        View Details →
                    </Link>
                </div>
            </div>
        </article>
    );
}
