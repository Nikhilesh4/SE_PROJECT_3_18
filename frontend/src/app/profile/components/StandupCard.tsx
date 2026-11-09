"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { errorMessage } from "@/lib/errors";
import { fetchStandup, type Standup } from "@/lib/tracker";

const KIND_ICON: Record<string, string> = {
    profile: "📄",
    deadline: "⏰",
    interview: "🎤",
    follow_up: "✉️",
    skill_gap: "🧩",
    match: "🎯",
    apply: "🚀",
    mission: "🛰️",
    save: "🔖",
};

/** This week's three next actions, computed from the student's own tracker data. */
export default function StandupCard() {
    const [standup, setStandup] = useState<Standup | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        fetchStandup()
            .then((s) => !cancelled && setStandup(s))
            .catch((err) => !cancelled && setError(errorMessage(err, "Could not load your standup.")));
        return () => {
            cancelled = true;
        };
    }, []);

    if (error) return null; // the board below has its own error note; this card is a bonus
    if (!standup) return null;
    const { facts, actions } = standup;

    return (
        <section aria-label="This week" className="mb-6 rounded-2xl border border-indigo-200 bg-indigo-50/60 p-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2 mb-2">
                <h2 className="text-sm font-semibold text-indigo-900">🧭 Your week</h2>
                <p className="text-xs text-indigo-800">
                    {facts.saved} saved · {facts.applied} applied · {facts.interview} interviewing · {facts.offer} offers
                </p>
            </div>
            {actions.length === 0 ? (
                <p className="text-sm text-slate-700">You&apos;re all caught up. Nothing urgent this week.</p>
            ) : (
                <ol className="space-y-1.5">
                    {actions.map((a, i) => (
                        <li key={`${a.kind}-${i}`} className="flex gap-2 text-sm text-slate-800">
                            <span aria-hidden>{KIND_ICON[a.kind] ?? "•"}</span>
                            {a.kind === "profile" ? (
                                <Link href="/profile" className="underline decoration-indigo-300 hover:decoration-indigo-600">
                                    {a.text}
                                </Link>
                            ) : (
                                <span>{a.text}</span>
                            )}
                        </li>
                    ))}
                </ol>
            )}
        </section>
    );
}
