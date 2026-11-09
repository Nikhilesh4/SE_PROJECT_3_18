"use client";

import { FormEvent, useState } from "react";
import { AxiosError } from "axios";
import api from "@/lib/api";
import { EducationItem, ExperienceItem, ProfileData, SocialLink } from "./types";

type ProfileEditorProps = {
    /** Existing profile to edit; omit to start from a blank form. */
    initial?: ProfileData | null;
    submitLabel?: string;
    onSaved: (profile: ProfileData) => void;
    onCancel?: () => void;
};

const INPUT =
    "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200";
const LABEL = "block text-sm font-medium text-slate-700 mb-1.5";
const GHOST_BTN =
    "rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 cursor-pointer";

const blankEducation = (): EducationItem => ({ degree: "", institution: "", year: "" });
const blankExperience = (): ExperienceItem => ({ role: "", company: "", duration: "", summary: "" });
const blankSocial = (): SocialLink => ({ label: "", url: "" });

const splitList = (text: string) =>
    text
        .split(/[,\n]/)
        .map((v) => v.trim())
        .filter(Boolean);

/**
 * Form for entering or editing a profile by hand (saved with PUT /profile/me).
 * Used at the end of signup and from the profile page's "Update profile" mode.
 */
export default function ProfileEditor({ initial, submitLabel = "Save profile", onSaved, onCancel }: ProfileEditorProps) {
    const [name, setName] = useState(initial?.name ?? "");
    const [skills, setSkills] = useState((initial?.skills ?? []).join(", "));
    const [interests, setInterests] = useState((initial?.interests ?? []).join(", "));
    const [education, setEducation] = useState<EducationItem[]>(
        initial?.education?.length ? initial.education : [blankEducation()]
    );
    const [experience, setExperience] = useState<ExperienceItem[]>(
        initial?.experience?.length ? initial.experience : [blankExperience()]
    );
    const [socials, setSocials] = useState<SocialLink[]>(initial?.socials?.length ? initial.socials : [blankSocial()]);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState("");

    const change = <T,>(list: T[], set: (next: T[]) => void, index: number, patch: Partial<T>) =>
        set(list.map((item, i) => (i === index ? { ...item, ...patch } : item)));
    const remove = <T,>(list: T[], set: (next: T[]) => void, index: number) =>
        set(list.filter((_, i) => i !== index));

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault();
        setSaving(true);
        setError("");
        try {
            const { data } = await api.put<ProfileData>("/profile/me", {
                name,
                skills: splitList(skills),
                interests: splitList(interests),
                education,
                experience,
                socials,
            });
            onSaved(data);
        } catch (err) {
            const axiosErr = err as AxiosError<{ detail?: unknown }>;
            const detail = axiosErr.response?.data?.detail;
            setError(typeof detail === "string" ? detail : "Could not save your profile. Check the fields and try again.");
        } finally {
            setSaving(false);
        }
    };

    return (
        <form onSubmit={handleSubmit} className="space-y-6">
            <div>
                <label htmlFor="pe-name" className={LABEL}>Full name</label>
                <input id="pe-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} className={INPUT} placeholder="Your name" />
            </div>

            <div>
                <label htmlFor="pe-skills" className={LABEL}>Skills</label>
                <textarea id="pe-skills" rows={2} value={skills} onChange={(e) => setSkills(e.target.value)} className={INPUT} placeholder="Python, React, Machine Learning" />
                <p className="mt-1 text-xs text-slate-500">Separate with commas. Your feed is ranked using these.</p>
            </div>

            <div>
                <label htmlFor="pe-interests" className={LABEL}>Interests</label>
                <textarea id="pe-interests" rows={2} value={interests} onChange={(e) => setInterests(e.target.value)} className={INPUT} placeholder="Open source, Research, Startups" />
            </div>

            <fieldset className="space-y-3">
                <legend className={LABEL}>Education</legend>
                {education.map((item, i) => (
                    <div key={i} className="rounded-xl border border-slate-200 bg-slate-50 p-3 space-y-2">
                        <input aria-label="Degree" value={item.degree} onChange={(e) => change(education, setEducation, i, { degree: e.target.value })} className={INPUT} placeholder="Degree (e.g. B.Tech Computer Science)" />
                        <div className="flex gap-2">
                            <input aria-label="Institution" value={item.institution} onChange={(e) => change(education, setEducation, i, { institution: e.target.value })} className={INPUT} placeholder="Institution" />
                            <input aria-label="Year" value={item.year} onChange={(e) => change(education, setEducation, i, { year: e.target.value })} className={`${INPUT} max-w-28`} placeholder="Year" />
                        </div>
                        <button type="button" onClick={() => remove(education, setEducation, i)} className="text-xs text-red-600 hover:underline cursor-pointer">Remove</button>
                    </div>
                ))}
                <button type="button" onClick={() => setEducation([...education, blankEducation()])} className={GHOST_BTN}>+ Add education</button>
            </fieldset>

            <fieldset className="space-y-3">
                <legend className={LABEL}>Experience</legend>
                {experience.map((item, i) => (
                    <div key={i} className="rounded-xl border border-slate-200 bg-slate-50 p-3 space-y-2">
                        <div className="flex gap-2">
                            <input aria-label="Role" value={item.role} onChange={(e) => change(experience, setExperience, i, { role: e.target.value })} className={INPUT} placeholder="Role" />
                            <input aria-label="Company" value={item.company} onChange={(e) => change(experience, setExperience, i, { company: e.target.value })} className={INPUT} placeholder="Company" />
                        </div>
                        <input aria-label="Duration" value={item.duration} onChange={(e) => change(experience, setExperience, i, { duration: e.target.value })} className={INPUT} placeholder="Duration (e.g. Jun 2025 – Aug 2025)" />
                        <textarea aria-label="Summary" rows={2} value={item.summary} onChange={(e) => change(experience, setExperience, i, { summary: e.target.value })} className={INPUT} placeholder="What did you work on?" />
                        <button type="button" onClick={() => remove(experience, setExperience, i)} className="text-xs text-red-600 hover:underline cursor-pointer">Remove</button>
                    </div>
                ))}
                <button type="button" onClick={() => setExperience([...experience, blankExperience()])} className={GHOST_BTN}>+ Add experience</button>
            </fieldset>

            <fieldset className="space-y-3">
                <legend className={LABEL}>Links</legend>
                {socials.map((item, i) => (
                    <div key={i} className="flex gap-2">
                        <input aria-label="Link label" value={item.label} onChange={(e) => change(socials, setSocials, i, { label: e.target.value })} className={`${INPUT} max-w-32`} placeholder="GitHub" />
                        <input aria-label="Link URL" type="url" value={item.url} onChange={(e) => change(socials, setSocials, i, { url: e.target.value })} className={INPUT} placeholder="https://github.com/you" />
                        <button type="button" onClick={() => remove(socials, setSocials, i)} aria-label="Remove link" className="px-2 text-slate-400 hover:text-red-600 cursor-pointer">×</button>
                    </div>
                ))}
                <button type="button" onClick={() => setSocials([...socials, blankSocial()])} className={GHOST_BTN}>+ Add link</button>
            </fieldset>

            {error && (
                <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">{error}</div>
            )}

            <div className="flex items-center gap-3">
                <button
                    type="submit"
                    disabled={saving}
                    className="rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer"
                >
                    {saving ? "Saving…" : submitLabel}
                </button>
                {onCancel && (
                    <button type="button" onClick={onCancel} className="text-sm text-slate-500 hover:text-slate-700 cursor-pointer">
                        Cancel
                    </button>
                )}
            </div>
        </form>
    );
}
