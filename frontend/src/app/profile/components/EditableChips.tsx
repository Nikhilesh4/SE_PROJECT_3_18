"use client";

import { FormEvent, useState } from "react";
import { AxiosError } from "axios";
import api from "@/lib/api";
import { ProfileData } from "./types";

type EditableChipsProps = {
    title: string;
    field: "skills" | "interests";
    values: string[];
    emptyText: string;
    chipClassName: string;
    onProfileChange: (profile: ProfileData) => void;
};

/**
 * Chip list with add/remove, saved via PATCH /profile/me.
 * Each change is saved immediately; the backend trims and de-duplicates.
 */
export default function EditableChips({
    title,
    field,
    values,
    emptyText,
    chipClassName,
    onProfileChange,
}: EditableChipsProps) {
    const [draft, setDraft] = useState("");
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState("");

    const save = async (next: string[]) => {
        setSaving(true);
        setError("");
        try {
            const { data } = await api.patch<ProfileData>("/profile/me", { [field]: next });
            onProfileChange(data);
            return true;
        } catch (err) {
            const axiosErr = err as AxiosError<{ detail?: string }>;
            setError(axiosErr.response?.data?.detail || `Failed to save ${title.toLowerCase()}.`);
            return false;
        } finally {
            setSaving(false);
        }
    };

    const handleAdd = async (e: FormEvent) => {
        e.preventDefault();
        const value = draft.trim();
        if (!value) return;
        if (values.some((v) => v.toLowerCase() === value.toLowerCase())) {
            setDraft("");
            return;
        }
        if (await save([...values, value])) setDraft("");
    };

    return (
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-900 tracking-tight">{title}</h2>
            <div className="mt-4 flex flex-wrap gap-2">
                {values.length === 0 ? (
                    <p className="text-sm text-slate-500">{emptyText}</p>
                ) : (
                    values.map((value, index) => (
                        <span
                            key={`${value}-${index}`}
                            className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm font-medium ${chipClassName}`}
                        >
                            {value}
                            <button
                                type="button"
                                onClick={() => save(values.filter((_, i) => i !== index))}
                                disabled={saving}
                                aria-label={`Remove ${value}`}
                                className="-mr-1 rounded-full px-1 leading-none opacity-60 hover:opacity-100 disabled:cursor-not-allowed"
                            >
                                ×
                            </button>
                        </span>
                    ))
                )}
            </div>

            <form onSubmit={handleAdd} className="mt-4 flex gap-2">
                <input
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    maxLength={60}
                    placeholder={`Add ${field === "skills" ? "a skill" : "an interest"}`}
                    aria-label={`Add to ${title}`}
                    className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none"
                />
                <button
                    type="submit"
                    disabled={saving || !draft.trim()}
                    className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
                >
                    {saving ? "Saving…" : "Add"}
                </button>
            </form>

            {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
        </section>
    );
}
