"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useNotifications, type AppNotification } from "@/lib/notifications";

const KIND_ICON: Record<string, string> = {
    new_match: "🎯",
    deadline: "⏰",
    mission: "🧭",
    digest: "🗞️",
};

function timeAgo(iso: string | null): string {
    if (!iso) return "";
    const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
    if (seconds < 60) return "just now";
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
}

function hrefFor(n: AppNotification): string {
    if (n.kind === "mission") return "/missions";
    if (n.kind === "digest") return "/applications";
    return n.rss_item_id != null ? `/feed/${encodeURIComponent(String(n.rss_item_id))}?by=id` : "/feed";
}

/** Toast that dismisses itself. */
function Toast({ n, onClose }: { n: AppNotification; onClose: () => void }) {
    useEffect(() => {
        const t = setTimeout(onClose, 7000);
        return () => clearTimeout(t);
    }, [onClose]);
    return (
        <div role="status" className="pointer-events-auto w-80 max-w-[calc(100vw-2rem)] rounded-xl border border-indigo-200 bg-white p-3 shadow-lg">
            <div className="flex items-start gap-2">
                <span aria-hidden className="text-lg">{KIND_ICON[n.kind] ?? "🔔"}</span>
                <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-slate-900 line-clamp-2">{n.title}</p>
                    {n.body && <p className="mt-0.5 text-xs text-slate-600 line-clamp-2">{n.body}</p>}
                </div>
                <button onClick={onClose} aria-label="Dismiss notification" className="text-slate-400 hover:text-slate-700 cursor-pointer">✕</button>
            </div>
        </div>
    );
}

export default function NotificationBell() {
    const { items, unread, toasts, markAllRead, markRead, dismissToast } = useNotifications();
    const [open, setOpen] = useState(false);
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

    return (
        <>
            <div ref={rootRef} className="relative">
                <button
                    onClick={() => setOpen((o) => !o)}
                    aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}
                    aria-expanded={open}
                    className="relative p-2 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors cursor-pointer"
                >
                    <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                        <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
                        <path d="M13.73 21a2 2 0 0 1-3.46 0" />
                    </svg>
                    {unread > 0 && (
                        <span className="absolute -top-0.5 -right-0.5 min-w-4 h-4 px-1 rounded-full bg-rose-500 text-white text-[10px] font-bold leading-4 text-center">
                            {unread > 9 ? "9+" : unread}
                        </span>
                    )}
                </button>

                {open && (
                    <div className="absolute right-0 mt-2 w-96 max-w-[calc(100vw-2rem)] rounded-xl border border-slate-200 bg-white shadow-xl overflow-hidden">
                        <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-200">
                            <p className="text-sm font-semibold text-slate-900">Notifications</p>
                            <button
                                onClick={markAllRead}
                                disabled={unread === 0}
                                className="text-xs font-medium text-indigo-600 hover:text-indigo-500 disabled:text-slate-400 cursor-pointer disabled:cursor-default"
                            >
                                Mark all read
                            </button>
                        </div>
                        <ul className="max-h-96 overflow-y-auto divide-y divide-slate-100">
                            {items.length === 0 && (
                                <li className="px-4 py-8 text-center text-sm text-slate-500">
                                    Nothing yet. New matches and closing deadlines will show up here.
                                </li>
                            )}
                            {items.map((n) => (
                                <li key={n.id}>
                                    <Link
                                        href={hrefFor(n)}
                                        onClick={() => {
                                            void markRead(n.id);
                                            setOpen(false);
                                        }}
                                        className={`flex gap-3 px-4 py-3 hover:bg-slate-50 ${n.read ? "" : "bg-indigo-50/50"}`}
                                    >
                                        <span aria-hidden className="text-lg">{KIND_ICON[n.kind] ?? "🔔"}</span>
                                        <span className="min-w-0 flex-1">
                                            <span className={`block text-sm text-slate-900 line-clamp-2 ${n.read ? "" : "font-semibold"}`}>{n.title}</span>
                                            {n.body && <span className="block text-xs text-slate-600 line-clamp-2 mt-0.5">{n.body}</span>}
                                            <span className="block text-[11px] text-slate-400 mt-1">{timeAgo(n.created_at)}</span>
                                        </span>
                                        {!n.read && <span aria-label="Unread" className="mt-1.5 w-2 h-2 rounded-full bg-indigo-500 shrink-0" />}
                                    </Link>
                                </li>
                            ))}
                        </ul>
                    </div>
                )}
            </div>

            {/* Toasts */}
            <div aria-live="polite" className="pointer-events-none fixed top-20 right-4 z-[60] flex flex-col gap-2">
                {toasts.map((t) => (
                    <Toast key={t.id} n={t} onClose={() => dismissToast(t.id)} />
                ))}
            </div>
        </>
    );
}
