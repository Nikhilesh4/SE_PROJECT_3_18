"use client";

import { useEffect, useState } from "react";
import { errorMessage } from "@/lib/errors";
import { fetchPayInsights, type PayInsights, type PaySummary } from "@/lib/insights";

const INR_PER_USD = 83; // the backend converts at the same rate

const inr = (n: number) => `₹${Math.round(n).toLocaleString("en-IN")}`;
const usdYear = (inrMonth: number) => `$${Math.round((inrMonth * 12) / INR_PER_USD / 1000).toLocaleString("en-US")}k/yr`;

function Money({ value }: { value: number }) {
    return (
        <span className="tabular-nums">
            {inr(value)} <span className="text-slate-400 text-xs">≈ {usdYear(value)}</span>
        </span>
    );
}

function Range({ v, max }: { v: PaySummary; max: number }) {
    const pct = (n: number) => `${Math.min(100, (n / max) * 100)}%`;
    return (
        <span className="relative mt-1 block h-2.5 rounded-full bg-slate-100">
            <span
                className="absolute inset-y-0 rounded-full bg-emerald-200"
                style={{ left: pct(v.p25), width: `${Math.max(1, (Math.min(v.p75, max) - v.p25) / max * 100)}%` }}
                title={`Middle half of postings: ${inr(v.p25)} – ${inr(v.p75)}`}
            />
            <span className="absolute -top-0.5 h-3.5 w-1 rounded bg-emerald-600" style={{ left: pct(v.median) }} title={`Median ${inr(v.median)}`} />
        </span>
    );
}

/** What postings pay, from the pay stated in their text. Quartiles, with the sample size beside each number. */
export default function PaySection() {
    const [category, setCategory] = useState<string>("");
    const [data, setData] = useState<PayInsights | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let alive = true;
        fetchPayInsights(category || undefined)
            .then((d) => alive && (setData(d), setError(null)))
            .catch((err) => alive && setError(errorMessage(err, "Could not load pay insights.")));
        return () => {
            alive = false;
        };
    }, [category]);

    const cats = Object.entries(data?.by_category ?? {}).filter((e): e is [string, PaySummary] => e[1] !== null);
    const max = Math.max(1, ...cats.map(([, v]) => v.p75));
    const remote = data?.remote ?? {};

    return (
        <section aria-labelledby="pay-h" className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-2">
            <div className="flex flex-wrap items-baseline justify-between gap-2 mb-1">
                <h2 id="pay-h" className="font-semibold text-slate-900">What postings pay</h2>
                <label className="text-xs text-slate-500">
                    Category{" "}
                    <select
                        value={category}
                        onChange={(e) => setCategory(e.target.value)}
                        className="ml-1 rounded-md border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700"
                    >
                        <option value="">All paid</option>
                        {["internship", "job", "freelance", "research"].map((c) => (
                            <option key={c} value={c}>
                                {c}
                            </option>
                        ))}
                    </select>
                </label>
            </div>
            {error && <p className="text-sm text-rose-600">{error}</p>}
            {!data && !error && <p className="text-sm text-slate-500">Loading…</p>}
            {data && (
                <>
                    <p className="text-xs text-slate-500 mb-4">
                        Median and middle half, ₹ per month. Based on the {data.with_pay.toLocaleString()} of{" "}
                        {data.postings.toLocaleString()} postings ({Math.round(data.coverage * 100)}%) that state an amount in the last{" "}
                        {data.days} days. Prize pools and course fees are left out
                        {data.left_out.out_of_range > 0 ? `, and ${data.left_out.out_of_range} implausible amounts` : ""}.
                    </p>
                    {cats.length === 0 ? (
                        <p className="text-sm text-slate-500">Not enough postings state pay yet.</p>
                    ) : (
                        <div className="grid gap-6 md:grid-cols-2">
                            <ul className="space-y-3">
                                {cats.map(([cat, v]) => (
                                    <li key={cat}>
                                        <div className="flex items-baseline justify-between text-sm">
                                            <span className="capitalize text-slate-700">{cat}</span>
                                            <span className="font-semibold text-slate-900">
                                                <Money value={v.median} />
                                            </span>
                                        </div>
                                        <Range v={v} max={max} />
                                        <p className="text-[11px] text-slate-400 mt-0.5">
                                            middle half {inr(v.p25)} – {inr(v.p75)} · {v.count} posting{v.count === 1 ? "" : "s"}
                                            {v.count < 5 ? " · small sample" : ""}
                                        </p>
                                    </li>
                                ))}
                                {(remote.remote || remote.onsite) && (
                                    <li className="pt-2 border-t border-slate-100 text-xs text-slate-600">
                                        {remote.remote && <span>Remote median <b><Money value={remote.remote.median} /></b> ({remote.remote.count}) </span>}
                                        {remote.onsite && <span className="ml-2">On-site median <b><Money value={remote.onsite.median} /></b> ({remote.onsite.count})</span>}
                                    </li>
                                )}
                            </ul>
                            <div>
                                <h3 className="text-sm font-medium text-slate-700 mb-2">Skills that appear in higher-paid postings</h3>
                                {data.by_skill.length === 0 ? (
                                    <p className="text-sm text-slate-500">Not enough postings per skill.</p>
                                ) : (
                                    <table className="w-full text-sm">
                                        <thead>
                                            <tr className="text-left text-[11px] uppercase text-slate-400">
                                                <th className="font-medium pb-1">Skill</th>
                                                <th className="font-medium pb-1 text-right">Median</th>
                                                <th className="font-medium pb-1 text-right">n</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {data.by_skill.slice(0, 8).map((s) => (
                                                <tr key={s.skill} className="border-t border-slate-100">
                                                    <td className="py-1 text-slate-700">{s.skill}</td>
                                                    <td className="py-1 text-right"><Money value={s.median} /></td>
                                                    <td className="py-1 text-right text-slate-400 tabular-nums">{s.count}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                )}
                                <p className="text-[11px] text-slate-400 mt-2">Association, not cause: mostly senior and US-remote roles name these skills.</p>
                            </div>
                        </div>
                    )}
                </>
            )}
        </section>
    );
}
