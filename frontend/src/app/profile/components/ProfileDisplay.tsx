"use client";

import { ProfileData } from "./types";

type ProfileDisplayProps = {
    profile: ProfileData;
};

export default function ProfileDisplay({ profile }: ProfileDisplayProps) {
    return (
        <div className="space-y-6">
            <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <h2 className="text-lg font-semibold text-slate-900 tracking-tight">Skills</h2>
                <div className="mt-4 flex flex-wrap gap-2">
                    {profile.skills.length === 0 ? (
                        <p className="text-sm text-slate-500">No skills parsed yet.</p>
                    ) : (
                        profile.skills.map((skill, index) => (
                            <span
                                key={`${skill}-${index}`}
                                className="rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-sm font-medium text-indigo-700"
                            >
                                {skill}
                            </span>
                        ))
                    )}
                </div>
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <h2 className="text-lg font-semibold text-slate-900 tracking-tight">Interests</h2>
                <div className="mt-4 flex flex-wrap gap-2">
                    {profile.interests.length === 0 ? (
                        <p className="text-sm text-slate-500">No interests parsed yet.</p>
                    ) : (
                        profile.interests.map((interest, index) => (
                            <span
                                key={`${interest}-${index}`}
                                className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-sm font-medium text-emerald-700"
                            >
                                {interest}
                            </span>
                        ))
                    )}
                </div>
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <h2 className="text-lg font-semibold text-slate-900 tracking-tight">Education</h2>
                <div className="mt-4 space-y-3">
                    {profile.education.length === 0 ? (
                        <p className="text-sm text-slate-500">No education entries parsed yet.</p>
                    ) : (
                        profile.education.map((item, index) => (
                            <article
                                key={`${item.degree}-${item.institution}-${index}`}
                                className="rounded-xl border border-slate-200 bg-slate-50 p-4"
                            >
                                <h3 className="font-semibold text-slate-900">{item.degree || "Degree not specified"}</h3>
                                <p className="text-sm text-slate-600 mt-1">
                                    {item.institution || "Institution not specified"}
                                </p>
                                {item.year && <p className="text-xs font-medium text-slate-500 mt-2">{item.year}</p>}
                            </article>
                        ))
                    )}
                </div>
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <h2 className="text-lg font-semibold text-slate-900 tracking-tight">Experience</h2>
                <div className="mt-4 space-y-3">
                    {profile.experience.length === 0 ? (
                        <p className="text-sm text-slate-500">No experience entries parsed yet.</p>
                    ) : (
                        profile.experience.map((item, index) => (
                            <article
                                key={`${item.role}-${item.company}-${index}`}
                                className="rounded-xl border border-slate-200 bg-slate-50 p-4"
                            >
                                <h3 className="font-semibold text-slate-900">{item.role || "Role not specified"}</h3>
                                <p className="text-sm text-slate-600 mt-1">
                                    {item.company || "Company not specified"}
                                    {item.duration ? ` • ${item.duration}` : ""}
                                </p>
                                {item.summary && (
                                    <p className="mt-3 text-sm leading-relaxed text-slate-600">
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
