"use client";

import { useEffect, useState } from "react";
import PageShell, { ErrorNote, Spinner } from "@/app/components/PageShell";
import { errorMessage } from "@/lib/errors";
import { fetchCompanies, fetchTrends, type CompanyMatch, type Trends } from "@/lib/insights";

function inr(n: number): string {
    return `₹${Math.round(n).toLocaleString("en-IN")}`;
}

export default function InsightsPage() {
    const [trends, setTrends] = useState<Trends | null>(null);
    const [companies, setCompanies] = useState<CompanyMatch[] | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let alive = true;
        fetchTrends()
            .then((t) => alive && setTrends(t))
            .catch((err) => alive && setError(errorMessage(err, "Could not load market trends.")));
        fetchCompanies()
            .then((c) => alive && setCompanies(c))
            .catch(() => alive && setCompanies([]));
        return () => {
            alive = false;
        };
    }, []);

    const maxSkill = Math.max(1, ...(trends?.top_skills.map((s) => s.postings) ?? [1]));
    const stipends = Object.entries(trends?.stipend_inr_month ?? {});
    const maxMedian = Math.max(1, ...stipends.map(([, v]) => v.median));

    return (
        <PageShell
            title="Market insights"
            subtitle={trends ? `Built from ${trends.postings.toLocaleString()} postings from the last ${trends.days} days.` : "What employers are asking for right now."}
        >
            <ErrorNote message={error} />
            {!trends && !error ? (
                <Spinner />
            ) : trends ? (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <section aria-labelledby="skills-h" className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                        <h2 id="skills-h" className="font-semibold text-slate-900 mb-4">Most requested skills</h2>
                        {trends.top_skills.length === 0 ? (
                            <p className="text-sm text-slate-500">Not enough postings yet.</p>
                        ) : (
                            <ul className="space-y-2">
                                {trends.top_skills.map((s) => (
                                    <li key={s.skill} className="grid grid-cols-[7rem_1fr_3rem] items-center gap-3 text-sm">
                                        <span className="truncate text-slate-700">{s.skill}</span>
                                        <span className="h-2.5 rounded-full bg-slate-100 overflow-hidden" role="img" aria-label={`${s.postings} postings`}>
                                            <span className="block h-full rounded-full bg-indigo-500" style={{ width: `${(s.postings / maxSkill) * 100}%` }} />
                                        </span>
                                        <span className="text-right text-xs text-slate-500 tabular-nums">{s.postings}</span>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </section>

                    <section aria-labelledby="stipend-h" className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                        <h2 id="stipend-h" className="font-semibold text-slate-900 mb-1">Stipend by category</h2>
                        <p className="text-xs text-slate-500 mb-4">Median of postings that state an amount, converted to ₹ per month.</p>
                        {stipends.length === 0 ? (
                            <p className="text-sm text-slate-500">No postings state a stipend yet.</p>
                        ) : (
                            <ul className="space-y-3">
                                {stipends.map(([cat, v]) => (
                                    <li key={cat}>
                                        <div className="flex items-baseline justify-between text-sm">
                                            <span className="capitalize text-slate-700">{cat}</span>
                                            <span className="font-semibold text-slate-900 tabular-nums">{inr(v.median)}</span>
                                        </div>
                                        <span className="mt-1 block h-2.5 rounded-full bg-slate-100 overflow-hidden">
                                            <span className="block h-full rounded-full bg-emerald-500" style={{ width: `${(v.median / maxMedian) * 100}%` }} />
                                        </span>
                                        <p className="text-[11px] text-slate-400 mt-0.5">
                                            {inr(v.min)} – {inr(v.max)} · {v.count} posting{v.count === 1 ? "" : "s"}
                                        </p>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </section>

                    <section aria-labelledby="cat-h" className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                        <h2 id="cat-h" className="font-semibold text-slate-900 mb-3">Postings by category</h2>
                        <ul className="flex flex-wrap gap-2">
                            {Object.entries(trends.by_category)
                                .sort((a, b) => b[1] - a[1])
                                .map(([c, n]) => (
                                    <li key={c} className="px-3 py-1.5 rounded-lg bg-slate-100 text-sm text-slate-700">
                                        <span className="capitalize">{c}</span> <span className="font-semibold">{n}</span>
                                    </li>
                                ))}
                        </ul>
                    </section>

                    <section aria-labelledby="co-h" className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                        <h2 id="co-h" className="font-semibold text-slate-900 mb-1">Companies closest to your profile</h2>
                        <p className="text-xs text-slate-500 mb-3">Ranked by the best semantic match among each company&apos;s postings.</p>
                        {companies === null ? (
                            <Spinner />
                        ) : companies.length === 0 ? (
                            <p className="text-sm text-slate-500">Upload a resume on your profile to see company matches.</p>
                        ) : (
                            <ol className="space-y-2">
                                {companies.map((c, i) => (
                                    <li key={c.company} className="flex items-center justify-between text-sm">
                                        <span className="text-slate-800"><span className="text-slate-400 mr-2 tabular-nums">{i + 1}.</span>{c.company}</span>
                                        <span className="text-xs text-slate-500">{c.postings} posting{c.postings === 1 ? "" : "s"} · <span className="font-semibold text-indigo-700">{Math.round(c.best_match * 100)}%</span></span>
                                    </li>
                                ))}
                            </ol>
                        )}
                    </section>
                </div>
            ) : null}
        </PageShell>
    );
}
