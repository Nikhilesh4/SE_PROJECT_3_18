"use client";

import { ProfileData } from "./types";

function initials(name: string): string {
    return name
        .split(/\s+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((w) => w[0]?.toUpperCase())
        .join("");
}

function safeHref(url: string): string | null {
    return /^(https?:|mailto:)/i.test(url) ? url : null;
}

function prettyUrl(url: string): string {
    return url.replace(/^(https?:\/\/|mailto:)(www\.)?/i, "").replace(/\/$/, "");
}

export default function ProfileHeader({ profile }: { profile: ProfileData }) {
    const name = profile.name?.trim() || "";
    const socials = (profile.socials ?? []).filter((s) => safeHref(s.url));

    return (
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm flex flex-col sm:flex-row sm:items-center gap-5">
            <div className="w-16 h-16 shrink-0 rounded-full bg-gradient-to-br from-indigo-500 to-sky-500 text-white text-xl font-bold flex items-center justify-center">
                {name ? initials(name) : "?"}
            </div>
            <div className="min-w-0">
                <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight truncate">
                    {name || "Your profile"}
                </h1>
                {socials.length > 0 ? (
                    <ul className="mt-2 flex flex-wrap gap-2">
                        {socials.map((s) => (
                            <li key={s.url}>
                                <a
                                    href={safeHref(s.url)!}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    title={s.url}
                                    className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700 hover:border-indigo-300 hover:text-indigo-700"
                                >
                                    <span className="font-semibold">{s.label || "Link"}</span>
                                    <span className="text-slate-400 max-w-40 truncate">{prettyUrl(s.url)}</span>
                                </a>
                            </li>
                        ))}
                    </ul>
                ) : (
                    <p className="mt-1 text-sm text-slate-500">
                        {name ? "No social links found in your resume." : "Upload your resume to fill in your name and links."}
                    </p>
                )}
            </div>
        </section>
    );
}
