"use client";

import { useState } from "react";
import { FeedSourceStatus } from "@/lib/useFeed";

interface Props {
    sources: FeedSourceStatus[];
}

export default function SourceStatusPanel({ sources }: Props) {
    const [open, setOpen] = useState(false);
    const okCount = sources.filter((s) => s.ok).length;
    const failCount = sources.length - okCount;

    return (
        <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
            {/* Toggle header */}
            <button
                onClick={() => setOpen((v) => !v)}
                className="w-full flex items-center justify-between p-4 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
            >
                <span className="font-medium flex items-center gap-2">
                    <span className="text-base">📡</span> Feed Sources
                </span>
                <span className="flex items-center gap-2">
                    <span className="px-1.5 py-0.5 rounded-md text-xs bg-emerald-100 text-emerald-700">
                        {okCount} ✓
                    </span>
                    {failCount > 0 && (
                        <span className="px-1.5 py-0.5 rounded-md text-xs bg-red-100 text-red-700">
                            {failCount} ✗
                        </span>
                    )}
                    <svg
                        xmlns="http://www.w3.org/2000/svg"
                        className={`w-4 h-4 text-slate-500 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
                        viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                        strokeLinecap="round" strokeLinejoin="round"
                    >
                        <polyline points="6 9 12 15 18 9" />
                    </svg>
                </span>
            </button>

            {/* Sources list */}
            {open && (
                <ul className="border-t border-slate-200 divide-y divide-slate-100">
                    {sources.map((src) => (
                        <li
                            key={src.feed_url}
                            className="px-4 py-2.5 flex items-center justify-between gap-3"
                        >
                            <span className="min-w-0 flex-1">
                                <p className="text-xs font-medium text-slate-800 truncate">{src.source_name}</p>
                                <p className="text-[10px] text-slate-600 truncate">{src.category}</p>
                            </span>
                            <span className="shrink-0 flex items-center gap-1.5 text-xs">
                                {src.ok ? (
                                    <span className="text-emerald-700">✓ {src.items_normalized}</span>
                                ) : (
                                    <span className="text-red-700 truncate max-w-[80px]" title={src.error ?? ""}>
                                        ✗ {src.http_status ?? "err"}
                                    </span>
                                )}
                            </span>
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
}
