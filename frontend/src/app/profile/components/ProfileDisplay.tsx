"use client";

import { ProfileData } from "./types";

type ProfileDisplayProps = {
    profile: ProfileData;
};

export default function ProfileDisplay({ profile }: ProfileDisplayProps) {
    return (
        <div className="space-y-6">
            <section className="rounded-2xl border border-slate-700 bg-slate-900/70 p-6">
                <h2 className="text-xl font-semibold text-white">Skills</h2>
                <div className="mt-4 flex flex-wrap gap-2">
                    {profile.skills.length === 0 ? (
                        <p className="text-sm text-slate-300">No skills parsed yet.</p>
                    ) : (
                        profile.skills.map((skill, index) => (
                            <span
                                key={`${skill}-${index}`}
                                className="rounded-full border border-cyan-400/40 bg-cyan-400/10 px-3 py-1 text-sm text-cyan-200"
                            >
                                {skill}
                            </span>
                        ))
                    )}
                </div>
            </section>

            <section className="rounded-2xl border border-slate-700 bg-slate-900/70 p-6">
                <h2 className="text-xl font-semibold text-white">Interests</h2>
                <div className="mt-4 flex flex-wrap gap-2">
                    {profile.interests.length === 0 ? (
                        <p className="text-sm text-slate-300">No interests parsed yet.</p>
                    ) : (
                        profile.interests.map((interest, index) => (
                            <span
                                key={`${interest}-${index}`}
                                className="rounded-full border border-emerald-400/40 bg-emerald-400/10 px-3 py-1 text-sm text-emerald-200"
                            >
                                {interest}
                            </span>
                        ))
                    )}
                </div>
            </section>

            <section className="rounded-2xl border border-slate-700 bg-slate-900/70 p-6">
                <h2 className="text-xl font-semibold text-white">Education</h2>
                <div className="mt-4 space-y-3">
                    {profile.education.length === 0 ? (
                        <p className="text-sm text-slate-300">No education entries parsed yet.</p>
                    ) : (
                        profile.education.map((item, index) => (
                            <article
                                key={`${item.degree}-${item.institution}-${index}`}
                                className="rounded-lg border border-slate-700 bg-slate-950 p-4"
                            >
                                <h3 className="font-medium text-slate-100">{item.degree || "Degree not specified"}</h3>
                                <p className="text-sm text-slate-300">
                                    {item.institution || "Institution not specified"}
                                </p>
                                {item.year && <p className="text-xs text-slate-400">{item.year}</p>}
                            </article>
                        ))
                    )}
                </div>
            </section>

            <section className="rounded-2xl border border-slate-700 bg-slate-900/70 p-6">
                <h2 className="text-xl font-semibold text-white">Experience</h2>
                <div className="mt-4 space-y-3">
                    {profile.experience.length === 0 ? (
                        <p className="text-sm text-slate-300">No experience entries parsed yet.</p>
                    ) : (
                        profile.experience.map((item, index) => (
                            <article
                                key={`${item.role}-${item.company}-${index}`}
                                className="rounded-lg border border-slate-700 bg-slate-950 p-4"
                            >
                                <h3 className="font-medium text-slate-100">{item.role || "Role not specified"}</h3>
                                <p className="text-sm text-slate-300">
                                    {item.company || "Company not specified"}
                                    {item.duration ? ` • ${item.duration}` : ""}
                                </p>
                                {item.summary && (
                                    <p className="mt-2 text-sm leading-relaxed text-slate-300">
                                        {item.summary}
                                    </p>
                                )}
                            </article>
                        ))
                    )}
                </div>
            </section>
        </div>
    );
}
