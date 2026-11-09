"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { fetchItemInsights, type ItemInsights } from "@/lib/insights";
import type { NormalizedRssItem } from "@/lib/useFeed";
import { useFeedback } from "@/lib/useFeedback";

// ── Provenance ──────────────────────────────────────────────────────────────

const PROVENANCE_LABEL: [prefix: string, label: string][] = [
    ["ats", "ATS"],
    ["hn", "HN"],
    ["web", "Web"],
    ["devpost", "Devpost"],
    ["programs", "Program"],
];

/** Short label for non-RSS discovery channels, or null for plain feeds. */
export function provenanceLabel(discoveredBy?: string): string | null {
    if (!discoveredBy || discoveredBy === "rss") return null;
    return PROVENANCE_LABEL.find(([p]) => discoveredBy.startsWith(p))?.[1] ?? discoveredBy;
}

export function isScamRisk(item: Pick<NormalizedRssItem, "flags" | "scam_risk">): boolean {
    return (item.flags ?? []).includes("scam-risk") || (item.scam_risk ?? 0) >= 40;
}

function formatStipend(inrPerMonth: number): string {
    return inrPerMonth >= 100_000 ? `₹${(inrPerMonth / 1000).toFixed(0)}k/mo` : `₹${Math.round(inrPerMonth).toLocaleString("en-IN")}/mo`;
}

/** Chips shown under the title: scam warning, remote, stipend, discovery channel. */
export function SignalChips({ item }: { item: NormalizedRssItem }) {
    const channel = provenanceLabel(item.discovered_by);
    const scam = isScamRisk(item);
    if (!scam && !item.remote && !item.stipend_inr_month && !channel) return null;
    return (
        <div className="flex flex-wrap gap-1.5 text-xs">
            {scam && (
                <span title="This posting shows signs of a scam (fees, chat-only contact, …). Check it carefully." className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-red-50 border border-red-200 text-red-700 font-semibold">
                    ⚠ Possible scam
                </span>
            )}
            {item.remote && <span className="px-2 py-0.5 rounded-md bg-teal-50 border border-teal-200 text-teal-700">🏠 Remote</span>}
            {item.stipend_inr_month ? (
                <span className="px-2 py-0.5 rounded-md bg-emerald-50 border border-emerald-200 text-emerald-700">💰 {formatStipend(item.stipend_inr_month)}</span>
            ) : null}
            {channel && (
                <span title={`Found via ${item.discovered_by}`} className="px-2 py-0.5 rounded-md bg-slate-100 border border-slate-200 text-slate-600">
                    via {channel}
                </span>
            )}
        </div>
    );
}

// ── Feedback ────────────────────────────────────────────────────────────────

const iconProps = { className: "w-4 h-4", viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": true } as const;

export function FeedbackButtons({ itemId }: { itemId: number }) {
    const { feedback, choose } = useFeedback();
    const value = feedback[String(itemId)];
    const base = "p-1.5 rounded-lg transition-colors cursor-pointer";
    return (
        <div className="flex items-center" role="group" aria-label="Rate this opportunity">
            <button
                onClick={() => void choose(itemId, "up")}
                aria-pressed={value === "up"}
                title="Relevant to me"
                className={`${base} ${value === "up" ? "text-emerald-600 bg-emerald-50" : "text-slate-400 hover:text-emerald-600 hover:bg-emerald-50"}`}
            >
                <svg {...iconProps} fill={value === "up" ? "currentColor" : "none"}><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3" /></svg>
                <span className="sr-only">Thumbs up</span>
            </button>
            <button
                onClick={() => void choose(itemId, "down")}
                aria-pressed={value === "down"}
                title="Not relevant: show me fewer like this"
                className={`${base} ${value === "down" ? "text-amber-600 bg-amber-50" : "text-slate-400 hover:text-amber-600 hover:bg-amber-50"}`}
            >
                <svg {...iconProps} fill={value === "down" ? "currentColor" : "none"}><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17" /></svg>
                <span className="sr-only">Thumbs down</span>
            </button>
            <button
                onClick={() => void choose(itemId, "hide")}
                title="Hide this opportunity"
                className={`${base} text-slate-400 hover:text-rose-600 hover:bg-rose-50`}
            >
                <svg {...iconProps}><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" /><line x1="1" y1="1" x2="23" y2="23" /></svg>
                <span className="sr-only">Hide</span>
            </button>
        </div>
    );
}

/** Placeholder shown in place of a card the user just hid or thumbed down. */
export function DismissedCard({ itemId, title }: { itemId: number; title: string }) {
    const { choose, feedback } = useFeedback();
    const value = feedback[String(itemId)];
    return (
        <article className="flex items-center justify-between gap-3 p-4 rounded-2xl border border-dashed border-slate-300 bg-slate-50 text-sm text-slate-500">
            <span className="line-clamp-1">{value === "hide" ? "Hidden" : "Marked not relevant"}: {title}</span>
            <button onClick={() => void choose(itemId, value ?? "hide")} className="shrink-0 font-medium text-indigo-600 hover:underline cursor-pointer">
                Undo
            </button>
        </article>
    );
}

// ── Why this? ───────────────────────────────────────────────────────────────

export function WhyThis({ itemId, detailHref }: { itemId: number; detailHref: string }) {
    const [open, setOpen] = useState(false);
    const [data, setData] = useState<ItemInsights | null>(null);
    const [failed, setFailed] = useState(false);
    const rootRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!open) return;
        const onDown = (e: MouseEvent) => {
            if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
        };
        const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
        document.addEventListener("mousedown", onDown);
        document.addEventListener("keydown", onKey);
        return () => {
            document.removeEventListener("mousedown", onDown);
            document.removeEventListener("keydown", onKey);
        };
    }, [open]);

    const toggle = () => {
        const next = !open;
        setOpen(next);
        if (next && !data && !failed) {
            fetchItemInsights(itemId).then(setData).catch(() => setFailed(true));
        }
    };

    return (
        <div ref={rootRef} className="relative">
            <button onClick={toggle} aria-expanded={open} className="text-xs font-medium text-slate-500 hover:text-indigo-700 cursor-pointer">
                Why this?
            </button>
            {open && (
                <div role="dialog" aria-label="Why this opportunity" className="absolute bottom-full left-0 mb-2 w-72 max-w-[80vw] rounded-xl border border-slate-200 bg-white p-3 text-xs shadow-xl z-20 space-y-2">
                    {!data && !failed && <p className="text-slate-500">Checking…</p>}
                    {failed && <p className="text-slate-500">Could not load the explanation.</p>}
                    {data && (
                        <>
                            <ul className="list-disc list-inside space-y-1 text-slate-700">
                                {data.ranking.reasons.map((r) => <li key={r}>{r}</li>)}
                            </ul>
                            {data.skill_gap.coverage !== null && (
                                <p className="text-slate-600">
                                    You cover <span className="font-semibold">{data.skill_gap.coverage}%</span> of the skills it names
                                    {data.skill_gap.missing.length > 0 && <> (missing {data.skill_gap.missing.slice(0, 3).join(", ")})</>}.
                                </p>
                            )}
                            <Link href={detailHref} className="inline-block font-medium text-indigo-600 hover:underline">Full breakdown →</Link>
                        </>
                    )}
                </div>
            )}
        </div>
    );
}
