"use client";

import { useEffect, useState } from "react";
import { errorMessage } from "@/lib/errors";
import { fetchItemInsights, fetchProjects, type ItemInsights } from "@/lib/insights";

function Chip({ children, tone }: { children: React.ReactNode; tone: "good" | "gap" | "neutral" }) {
    const cls = {
        good: "bg-emerald-50 text-emerald-700 border-emerald-200",
        gap: "bg-amber-50 text-amber-800 border-amber-200",
        neutral: "bg-slate-100 text-slate-700 border-slate-200",
    }[tone];
    return <span className={`px-2.5 py-0.5 rounded-lg text-xs font-medium border ${cls}`}>{children}</span>;
}

export default function InsightsPanel({ itemId }: { itemId: number }) {
    const [data, setData] = useState<ItemInsights | null>(null);
    const [projects, setProjects] = useState<{ skill: string; idea: string }[]>([]);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let alive = true;
        fetchItemInsights(itemId)
            .then((d) => {
                if (!alive) return;
                setData(d);
                if (d.skill_gap.missing.length > 0) {
                    fetchProjects(itemId).then((p) => alive && setProjects(p.projects)).catch(() => {});
                }
            })
            .catch((err) => alive && setError(errorMessage(err, "Could not load insights for this posting.")));
        return () => {
            alive = false;
        };
    }, [itemId]);

    if (error) return <section className="px-6 sm:px-8 pb-6"><p className="text-sm text-slate-500">{error}</p></section>;
    if (!data) {
        return (
            <section className="px-6 sm:px-8 pb-6">
                <div className="h-24 rounded-xl bg-slate-100 animate-pulse" aria-label="Loading insights" />
            </section>
        );
    }

    const { skill_gap: gap, scam, eligibility, provenance } = data;
    const hasEligibility = eligibility.years.length > 0 || eligibility.min_cgpa !== null || eligibility.branches.length > 0 || eligibility.notes.length > 0;

    return (
        <section aria-labelledby="insights-h" className="px-6 sm:px-8 pb-6 space-y-5">
            <h2 id="insights-h" className="text-lg font-semibold text-slate-900 flex items-center gap-2">💡 Insights for you</h2>

            {scam.score > 0 && (
                <div role="alert" className={`rounded-xl border p-4 text-sm ${scam.risky ? "border-red-300 bg-red-50 text-red-800" : "border-amber-200 bg-amber-50 text-amber-800"}`}>
                    <p className="font-semibold">{scam.risky ? "⚠ This posting shows signs of a scam" : "Worth double-checking"}</p>
                    <ul className="list-disc list-inside mt-1 space-y-0.5">
                        {scam.reasons.map((r) => <li key={r}>{r}</li>)}
                    </ul>
                    <p className="mt-2 text-xs opacity-80">Never pay to apply, and verify the company on its official site before sharing personal details.</p>
                </div>
            )}

            <div>
                <h3 className="text-sm font-semibold text-slate-700 mb-1.5">Why it ranks for you</h3>
                <ul className="list-disc list-inside text-sm text-slate-700 space-y-0.5">
                    {data.ranking.reasons.map((r) => <li key={r}>{r}</li>)}
                </ul>
                {!data.has_profile && <p className="mt-1 text-xs text-slate-500">Upload a resume on your profile for personalised matching.</p>}
            </div>

            {gap.required.length > 0 && (
                <div>
                    <div className="flex items-baseline justify-between mb-1.5">
                        <h3 className="text-sm font-semibold text-slate-700">Skill match</h3>
                        {gap.coverage !== null && <span className="text-sm font-semibold text-slate-900">{gap.coverage}%</span>}
                    </div>
                    {gap.coverage !== null && (
                        <div className="h-2 rounded-full bg-slate-100 overflow-hidden mb-2.5" role="img" aria-label={`${gap.coverage}% of required skills covered`}>
                            <div className="h-full rounded-full bg-emerald-500" style={{ width: `${gap.coverage}%` }} />
                        </div>
                    )}
                    <div className="flex flex-wrap gap-1.5">
                        {gap.matched.map((s) => <Chip key={s} tone="good">✓ {s}</Chip>)}
                        {gap.missing.map((s) => <Chip key={s} tone="gap">✗ {s}</Chip>)}
                    </div>
                </div>
            )}

            {projects.length > 0 && (
                <div>
                    <h3 className="text-sm font-semibold text-slate-700 mb-1.5">Projects that close the gap</h3>
                    <ul className="space-y-2">
                        {projects.map((p) => (
                            <li key={p.skill} className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                                <span className="font-semibold text-slate-900">{p.skill}:</span> {p.idea}
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            <div className="flex flex-wrap gap-1.5">
                {data.remote && <Chip tone="neutral">🏠 Remote</Chip>}
                {data.stipend && <Chip tone="good">💰 {data.stipend.raw} (≈ ₹{Math.round(data.stipend.amount).toLocaleString("en-IN")}/mo)</Chip>}
            </div>

            {hasEligibility && (
                <div>
                    <h3 className="text-sm font-semibold text-slate-700 mb-1.5">Eligibility mentioned</h3>
                    <ul className="list-disc list-inside text-sm text-slate-700 space-y-0.5">
                        {eligibility.years.length > 0 && <li>Graduating class of {eligibility.years.join(", ")}</li>}
                        {eligibility.min_cgpa !== null && <li>Minimum CGPA {eligibility.min_cgpa}</li>}
                        {eligibility.branches.length > 0 && <li>Branches: {eligibility.branches.join(", ").toUpperCase()}</li>}
                        {eligibility.notes.map((n) => <li key={n}>{n}</li>)}
                    </ul>
                    <p className="mt-1 text-xs text-slate-500">Read from the posting text; confirm on the original page.</p>
                </div>
            )}

            <p className="text-xs text-slate-500">
                Source: {provenance.discovered_by}
                {provenance.confidence !== null && <> · confidence {Math.round(provenance.confidence * 100)}%</>}
                {provenance.verified_at ? <> · verified {new Date(provenance.verified_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}</> : <> · not independently verified</>}
                {provenance.flags.length > 0 && <> · flags: {provenance.flags.join(", ")}</>}
            </p>
        </section>
    );
}
