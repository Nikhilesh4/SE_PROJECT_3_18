"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import PageShell, { ErrorNote, Spinner } from "@/app/components/PageShell";
import { errorMessage } from "@/lib/errors";
import {
    createMission,
    deleteMission,
    listMissions,
    missionMatches,
    patchMission,
    runMission,
    type Mission,
    type MissionMatch,
} from "@/lib/missions";

function formatWhen(iso: string | null): string {
    if (!iso) return "never";
    try {
        return new Date(iso).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
    } catch {
        return "never";
    }
}

function MissionCard({ mission, onChanged }: { mission: Mission; onChanged: () => void }) {
    const [matches, setMatches] = useState<MissionMatch[] | null>(null);
    const [open, setOpen] = useState(false);
    const [busy, setBusy] = useState(false);
    const [note, setNote] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    const loadMatches = async () => {
        try {
            setMatches(await missionMatches(mission.id));
        } catch (err) {
            setError(errorMessage(err, "Could not load matches."));
        }
    };

    const toggleOpen = async () => {
        const next = !open;
        setOpen(next);
        if (next && matches === null) await loadMatches();
    };

    const run = async () => {
        setBusy(true);
        setError(null);
        try {
            const fresh = await runMission(mission.id);
            setNote(fresh.length ? `${fresh.length} new match${fresh.length === 1 ? "" : "es"} found.` : "No new matches since the last run.");
            await loadMatches();
            setOpen(true);
            onChanged();
        } catch (err) {
            setError(errorMessage(err, "The run failed."));
        } finally {
            setBusy(false);
        }
    };

    const toggleActive = async () => {
        try {
            await patchMission(mission.id, { active: !mission.active });
            onChanged();
        } catch (err) {
            setError(errorMessage(err, "Could not update the mission."));
        }
    };

    const remove = async () => {
        if (!window.confirm(`Delete mission “${mission.name}”?`)) return;
        try {
            await deleteMission(mission.id);
            onChanged();
        } catch (err) {
            setError(errorMessage(err, "Could not delete the mission."));
        }
    };

    const constraints = [
        mission.category,
        mission.remote_only ? "remote" : null,
        mission.min_stipend ? `≥ ₹${mission.min_stipend.toLocaleString("en-IN")}/mo` : null,
        mission.deadline_after ? `deadline after ${new Date(mission.deadline_after).toLocaleDateString("en-US", { month: "short", year: "numeric" })}` : null,
    ].filter(Boolean) as string[];

    return (
        <li className={`rounded-2xl border bg-white p-4 shadow-sm ${mission.active ? "border-slate-200" : "border-slate-200 opacity-70"}`}>
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                    <h3 className="font-semibold text-slate-900">{mission.name}</h3>
                    <p className="text-sm text-slate-600 mt-0.5">“{mission.query}”</p>
                    {constraints.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 mt-2">
                            {constraints.map((c) => (
                                <span key={c} className="px-2 py-0.5 rounded-md bg-indigo-50 text-indigo-700 text-xs font-medium">{c}</span>
                            ))}
                        </div>
                    )}
                    <p className="text-xs text-slate-500 mt-2">Last run: {formatWhen(mission.last_run_at)} · runs daily when active</p>
                </div>
                <div className="flex items-center gap-2">
                    <button onClick={run} disabled={busy} className="px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-semibold hover:bg-indigo-500 disabled:opacity-60 cursor-pointer">
                        {busy ? "Running…" : "Run now"}
                    </button>
                    <button
                        onClick={toggleActive}
                        role="switch"
                        aria-checked={mission.active}
                        aria-label={`${mission.name} active`}
                        className={`relative w-10 h-6 rounded-full transition-colors cursor-pointer ${mission.active ? "bg-emerald-500" : "bg-slate-300"}`}
                    >
                        <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${mission.active ? "translate-x-4" : ""}`} />
                    </button>
                    <button onClick={remove} className="px-2.5 py-1.5 rounded-lg text-xs text-rose-600 hover:bg-rose-50 cursor-pointer">Delete</button>
                </div>
            </div>

            {note && <p className="mt-3 text-sm text-emerald-700">{note}</p>}
            <ErrorNote message={error} />

            <button onClick={toggleOpen} className="mt-3 text-xs font-medium text-indigo-600 hover:text-indigo-500 cursor-pointer" aria-expanded={open}>
                {open ? "Hide matches" : "Show matches"}
            </button>
            {open && (
                <ul className="mt-2 divide-y divide-slate-100 border-t border-slate-100">
                    {matches === null && <li className="py-3"><Spinner /></li>}
                    {matches?.length === 0 && <li className="py-3 text-sm text-slate-500">No matches yet. Run the mission to look now.</li>}
                    {matches?.map((m) => (
                        <li key={m.id} className="py-2.5 flex items-center justify-between gap-3">
                            <div className="min-w-0">
                                <Link href={`/feed/${encodeURIComponent(String(m.id))}?by=id`} className="text-sm font-medium text-slate-900 hover:text-indigo-700 line-clamp-1">
                                    {m.title}
                                </Link>
                                <p className="text-xs text-slate-500">{m.category} · {m.source_name}{m.found_at ? ` · found ${formatWhen(m.found_at)}` : ""}</p>
                            </div>
                            <a href={m.url} target="_blank" rel="noopener noreferrer" className="shrink-0 text-xs text-indigo-600 hover:underline">Open ↗</a>
                        </li>
                    ))}
                </ul>
            )}
        </li>
    );
}

export default function MissionsPage() {
    const [missions, setMissions] = useState<Mission[] | null>(null);
    const [name, setName] = useState("");
    const [query, setQuery] = useState("");
    const [creating, setCreating] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const load = useCallback(async () => {
        try {
            setMissions(await listMissions());
        } catch (err) {
            setError(errorMessage(err, "Could not load missions."));
        }
    }, []);

    useEffect(() => {
        const t = setTimeout(() => void load(), 0);
        return () => clearTimeout(t);
    }, [load]);

    const submit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!name.trim() || query.trim().length < 3) return;
        setCreating(true);
        setError(null);
        try {
            await createMission(name.trim(), query.trim());
            setName("");
            setQuery("");
            await load();
        } catch (err) {
            setError(errorMessage(err, "Could not create the mission."));
        } finally {
            setCreating(false);
        }
    };

    return (
        <PageShell
            title="Missions"
            subtitle="Describe what you want once. UniCompass re-checks daily and tells you only about new, verified matches."
        >
            <form onSubmit={submit} className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-5 shadow-sm space-y-3 mb-6">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <label className="block">
                        <span className="text-xs font-medium text-slate-600">Name</span>
                        <input
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            maxLength={80}
                            placeholder="Remote ML internships"
                            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
                        />
                    </label>
                    <label className="block sm:col-span-2">
                        <span className="text-xs font-medium text-slate-600">What are you looking for?</span>
                        <input
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            maxLength={500}
                            placeholder="remote paid ML internships, at least ₹20k/month, deadline after Dec"
                            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
                        />
                    </label>
                </div>
                <div className="flex items-center justify-between gap-3">
                    <p className="text-xs text-slate-500">
                        Category, remote, minimum stipend and deadline are read from your sentence. Up to 10 missions.
                    </p>
                    <button
                        type="submit"
                        disabled={creating || !name.trim() || query.trim().length < 3}
                        className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-500 disabled:opacity-50 cursor-pointer"
                    >
                        {creating ? "Creating…" : "Create mission"}
                    </button>
                </div>
            </form>

            <ErrorNote message={error} />
            {missions === null ? (
                <Spinner />
            ) : missions.length === 0 ? (
                <p className="text-center text-sm text-slate-500 py-10">No missions yet. Create your first one above.</p>
            ) : (
                <ul className="space-y-4">
                    {missions.map((m) => (
                        <MissionCard key={m.id} mission={m} onChanged={load} />
                    ))}
                </ul>
            )}
        </PageShell>
    );
}
