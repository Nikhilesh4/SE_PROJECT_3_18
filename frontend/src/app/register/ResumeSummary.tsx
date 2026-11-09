"use client";

import type { ResumePreview } from "@/lib/authSession";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
    return (
        <div className="py-2.5 grid grid-cols-[6.5rem_1fr] gap-3 text-sm">
            <dt className="text-slate-500">{label}</dt>
            <dd className="text-slate-900 min-w-0 break-words">{children}</dd>
        </div>
    );
}

const NOT_FOUND = <span className="text-amber-700">Not found, please fill it in below</span>;
const NONE = <span className="text-slate-400">None found</span>;

/** Everything the resume reader pulled out, shown before the user commits to anything. */
export default function ResumeSummary({ preview, fileName }: { preview: ResumePreview; fileName: string }) {
    const skills = preview.skills.slice(0, 12);
    const extraSkills = preview.skills.length - skills.length;

    return (
        <section aria-label="Details found in your resume" className="rounded-xl border border-emerald-200 bg-emerald-50/50 p-4">
            <h2 className="text-sm font-semibold text-emerald-900">Found in your resume</h2>
            <p className="text-xs text-slate-500 mt-0.5 truncate">📎 {fileName}</p>

            <dl className="mt-2 divide-y divide-emerald-100">
                <Row label="Name">{preview.name || NOT_FOUND}</Row>
                <Row label="Email">{preview.email || NOT_FOUND}</Row>
                <Row label="Links">
                    {preview.socials.length === 0 ? (
                        NONE
                    ) : (
                        <ul className="space-y-0.5">
                            {preview.socials.map((s) => (
                                <li key={s.url}>
                                    <span className="font-medium">{s.label || "Link"}</span>{" "}
                                    <span className="text-slate-500">{s.url.replace(/^(https?:\/\/|mailto:)(www\.)?/i, "")}</span>
                                </li>
                            ))}
                        </ul>
                    )}
                </Row>
                <Row label="Education">
                    {preview.education.length === 0 ? (
                        NONE
                    ) : (
                        <ul className="space-y-0.5">
                            {preview.education.map((e, i) => (
                                <li key={i}>
                                    {[e.degree, e.institution].filter(Boolean).join(", ") || "Entry"}
                                    {e.year && <span className="text-slate-500"> ({e.year})</span>}
                                </li>
                            ))}
                        </ul>
                    )}
                </Row>
                <Row label="Experience">
                    {preview.experience.length === 0 ? (
                        NONE
                    ) : (
                        <ul className="space-y-0.5">
                            {preview.experience.map((x, i) => (
                                <li key={i}>
                                    {[x.role, x.company].filter(Boolean).join(" at ") || "Entry"}
                                    {x.duration && <span className="text-slate-500"> ({x.duration})</span>}
                                </li>
                            ))}
                        </ul>
                    )}
                </Row>
                <Row label="Skills">
                    {skills.length === 0 ? (
                        NONE
                    ) : (
                        <div className="flex flex-wrap gap-1.5">
                            {skills.map((s) => (
                                <span key={s} className="rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-xs text-indigo-700">
                                    {s}
                                </span>
                            ))}
                            {extraSkills > 0 && <span className="text-xs text-slate-500 self-center">+{extraSkills} more</span>}
                        </div>
                    )}
                </Row>
            </dl>
            <p className="mt-2 text-xs text-slate-500">
                Only your name and email are used to fill the form. The rest is saved to your profile after you verify your email.
            </p>
        </section>
    );
}
