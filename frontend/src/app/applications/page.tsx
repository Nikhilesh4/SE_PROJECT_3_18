"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import PageShell, { ErrorNote, Spinner } from "@/app/components/PageShell";
import { errorMessage } from "@/lib/errors";
import {
    CALENDAR_URL,
    fetchBoard,
    fetchDeadlines,
    updateApplication,
    type ApplicationBoard,
    type ApplicationCard,
    type ApplicationStatus,
    type DeadlineItem,
} from "@/lib/tracker";

const COLUMN_STYLE: Record<ApplicationStatus, { label: string; bar: string; chip: string }> = {
    saved: { label: "Saved", bar: "bg-slate-400", chip: "bg-slate-100 text-slate-700" },
    applied: { label: "Applied", bar: "bg-indigo-500", chip: "bg-indigo-50 text-indigo-700" },
    interview: { label: "Interview", bar: "bg-amber-500", chip: "bg-amber-50 text-amber-700" },
    offer: { label: "Offer", bar: "bg-emerald-500", chip: "bg-emerald-50 text-emerald-700" },
    rejected: { label: "Rejected", bar: "bg-rose-400", chip: "bg-rose-50 text-rose-700" },
};

function daysUntil(iso?: string | null): number | null {
    if (!iso) return null;
    const ms = new Date(iso).getTime() - Date.now();
    return Number.isNaN(ms) ? null : Math.ceil(ms / 86_400_000);
}

function Card({
    card,
    statuses,
    onMove,
    onSaveNotes,
}: {
    card: ApplicationCard;
    statuses: ApplicationStatus[];
    onMove: (id: number, status: ApplicationStatus) => void;
    onSaveNotes: (id: number, notes: string) => Promise<void>;
}) {
    const { item } = card;
    const id = item.id!;
    const [notes, setNotes] = useState(card.notes);
    const [editing, setEditing] = useState(false);
    const [saving, setSaving] = useState(false);
    const left = daysUntil(item.application_deadline);

    const save = async () => {
        if (notes === card.notes) {
            setEditing(false);
            return;
        }
        setSaving(true);
        await onSaveNotes(id, notes);
        setSaving(false);
        setEditing(false);
    };

    return (
        <li className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm space-y-2">
            <Link
                href={`/feed/${encodeURIComponent(item.guid || item.url)}`}
                className="block text-sm font-semibold text-slate-900 hover:text-indigo-700 line-clamp-2"
            >
                {item.title}
            </Link>
            <p className="text-xs text-slate-500">{item.source_name}</p>
            {left !== null && card.status === "saved" && (
                <span className={`inline-block px-2 py-0.5 rounded-md text-[11px] font-medium ${left <= 3 ? "bg-rose-50 text-rose-700" : "bg-amber-50 text-amber-700"}`}>
                    {left < 0 ? "Deadline passed" : left === 0 ? "Closes today" : `Closes in ${left}d`}
                </span>
            )}

            <label className="block">
                <span className="sr-only">Move {item.title} to</span>
                <select
                    value={card.status}
                    onChange={(e) => onMove(id, e.target.value as ApplicationStatus)}
                    className="w-full rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-300"
                >
                    {statuses.map((s) => (
                        <option key={s} value={s}>
                            {COLUMN_STYLE[s]?.label ?? s}
                        </option>
                    ))}
                </select>
            </label>

            {editing ? (
                <div className="space-y-1.5">
                    <textarea
                        value={notes}
                        onChange={(e) => setNotes(e.target.value)}
                        rows={3}
                        maxLength={5000}
                        autoFocus
                        aria-label={`Notes for ${item.title}`}
                        placeholder="Recruiter name, interview rounds, next step…"
                        className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-300"
                    />
                    <div className="flex gap-2">
                        <button onClick={save} disabled={saving} className="px-2.5 py-1 rounded-md bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-500 disabled:opacity-60 cursor-pointer">
                            {saving ? "Saving…" : "Save"}
                        </button>
                        <button onClick={() => { setNotes(card.notes); setEditing(false); }} className="px-2.5 py-1 rounded-md text-xs text-slate-600 hover:bg-slate-100 cursor-pointer">
                            Cancel
                        </button>
                    </div>
                </div>
            ) : (
                <button
                    onClick={() => setEditing(true)}
                    className="w-full text-left text-xs rounded-lg px-2 py-1.5 bg-slate-50 hover:bg-slate-100 text-slate-600 cursor-pointer"
                >
                    {card.notes ? <span className="line-clamp-3 whitespace-pre-wrap">{card.notes}</span> : <span className="text-slate-400">+ Add notes</span>}
                </button>
            )}
        </li>
    );
}

export default function ApplicationsPage() {
    const [board, setBoard] = useState<ApplicationBoard | null>(null);
    const [deadlines, setDeadlines] = useState<DeadlineItem[]>([]);
    const [error, setError] = useState<string | null>(null);

    const load = useCallback(async () => {
        try {
            const [b, d] = await Promise.all([fetchBoard(), fetchDeadlines(14, "saved")]);
            setBoard(b);
            setDeadlines(d);
            setError(null);
        } catch (err) {
            setError(errorMessage(err, "Could not load your applications."));
        }
    }, []);

    useEffect(() => {
        const t = setTimeout(() => void load(), 0);
        return () => clearTimeout(t);
    }, [load]);

    const move = async (id: number, status: ApplicationStatus) => {
        try {
            await updateApplication(id, { status });
            await load();
        } catch (err) {
            setError(errorMessage(err, "Could not move that card."));
        }
    };

    const saveNotes = async (id: number, notes: string) => {
        try {
            await updateApplication(id, { notes });
            await load();
        } catch (err) {
            setError(errorMessage(err, "Could not save notes."));
        }
    };

    return (
        <PageShell
            wide
            title="Applications"
            subtitle="Track every saved opportunity from first look to offer. Bookmark a posting to add it here."
            actions={
                <a
                    href={CALENDAR_URL}
                    download="unicompass-deadlines.ics"
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border border-slate-300 bg-white text-slate-700 hover:bg-slate-100"
                >
                    📅 Export calendar (.ics)
                </a>
            }
        >
            <ErrorNote message={error} />

            {deadlines.length > 0 && (
                <section aria-label="Closing soon" className="mb-6 rounded-2xl border border-amber-200 bg-amber-50/70 p-4">
                    <h2 className="text-sm font-semibold text-amber-900 mb-2">⏰ Closing within 14 days</h2>
                    <ul className="flex flex-wrap gap-2">
                        {deadlines.map((d) => (
                            <li key={d.id}>
                                <Link
                                    href={`/feed/${encodeURIComponent(d.guid || d.url)}`}
                                    className="inline-flex items-center gap-2 rounded-lg bg-white border border-amber-200 px-3 py-1.5 text-xs text-slate-800 hover:border-amber-400"
                                >
                                    <span className="font-medium line-clamp-1 max-w-56">{d.title}</span>
                                    <span className={`font-semibold ${d.days_left <= 3 ? "text-rose-600" : "text-amber-700"}`}>
                                        {d.days_left === 0 ? "today" : `${d.days_left}d`}
                                    </span>
                                </Link>
                            </li>
                        ))}
                    </ul>
                </section>
            )}

            {!board ? (
                <Spinner />
            ) : board.total === 0 ? (
                <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center">
                    <p className="text-slate-700 font-medium">No saved opportunities yet</p>
                    <p className="text-sm text-slate-500 mt-1">
                        Bookmark postings from the <Link href="/feed" className="text-indigo-600 underline">feed</Link> and they will appear here.
                    </p>
                </div>
            ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 items-start">
                    {board.statuses.map((status) => {
                        const cards = board.columns[status] ?? [];
                        const style = COLUMN_STYLE[status];
                        return (
                            <section key={status} aria-label={style.label} className="rounded-2xl bg-slate-100/70 p-3">
                                <div className="flex items-center justify-between mb-3">
                                    <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-800">
                                        <span className={`w-2 h-2 rounded-full ${style.bar}`} />
                                        {style.label}
                                    </h2>
                                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${style.chip}`}>{cards.length}</span>
                                </div>
                                <ul className="space-y-3">
                                    {cards.map((c) => (
                                        <Card key={`${c.item.id}-${c.updated_at}`} card={c} statuses={board.statuses} onMove={move} onSaveNotes={saveNotes} />
                                    ))}
                                    {cards.length === 0 && <li className="text-xs text-slate-400 text-center py-4">Empty</li>}
                                </ul>
                            </section>
                        );
                    })}
                </div>
            )}
        </PageShell>
    );
}
