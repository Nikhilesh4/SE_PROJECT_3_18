"use client";

import { useState } from "react";
import { errorMessage } from "@/lib/errors";
import { draftOutreach, type OutreachDraft, type OutreachKind } from "@/lib/insights";

const KINDS: { value: OutreachKind; label: string }[] = [
    { value: "cold_email", label: "Cold email" },
    { value: "linkedin_note", label: "LinkedIn note" },
    { value: "referral_request", label: "Referral request" },
    { value: "follow_up", label: "Follow-up" },
];

export default function OutreachPanel({ itemId }: { itemId: number }) {
    const [kind, setKind] = useState<OutreachKind>("cold_email");
    const [recipient, setRecipient] = useState("");
    const [draft, setDraft] = useState<OutreachDraft | null>(null);
    const [loading, setLoading] = useState(false);
    const [copied, setCopied] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const generate = async () => {
        setLoading(true);
        setError(null);
        try {
            setDraft(await draftOutreach({ kind, item_id: itemId, recipient: recipient.trim() || undefined }));
        } catch (err) {
            setError(errorMessage(err, "Could not create a draft."));
        } finally {
            setLoading(false);
        }
    };

    const copy = async () => {
        if (!draft) return;
        try {
            await navigator.clipboard.writeText(draft.subject ? `Subject: ${draft.subject}\n\n${draft.body}` : draft.body);
            setCopied(true);
            setTimeout(() => setCopied(false), 1800);
        } catch {
            /* clipboard unavailable */
        }
    };

    return (
        <section aria-labelledby="outreach-h" className="px-6 sm:px-8 pb-6">
            <h2 id="outreach-h" className="text-lg font-semibold text-slate-900 mb-3">✉️ Draft outreach</h2>
            <div className="flex flex-wrap items-end gap-3">
                <label className="text-xs font-medium text-slate-600">
                    Type
                    <select value={kind} onChange={(e) => setKind(e.target.value as OutreachKind)} className="mt-1 block rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-sm text-slate-800">
                        {KINDS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
                    </select>
                </label>
                <label className="text-xs font-medium text-slate-600">
                    Recipient (optional)
                    <input value={recipient} onChange={(e) => setRecipient(e.target.value)} maxLength={100} placeholder="Priya" className="mt-1 block rounded-lg border border-slate-300 px-2.5 py-2 text-sm text-slate-800" />
                </label>
                <button onClick={generate} disabled={loading} className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-500 disabled:opacity-60 cursor-pointer">
                    {loading ? "Drafting…" : "Create draft"}
                </button>
            </div>
            {error && <p role="alert" className="mt-3 text-sm text-red-600">{error}</p>}
            {draft && (
                <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
                    <div className="flex items-center justify-between gap-3 mb-2">
                        <p className="text-xs text-slate-500">{draft.generated_by === "llm" ? "Written with AI from your profile" : "Template filled from your profile"}</p>
                        <button onClick={copy} className="px-3 py-1 rounded-lg border border-slate-300 bg-white text-xs font-medium hover:bg-slate-100 cursor-pointer">{copied ? "Copied ✓" : "Copy"}</button>
                    </div>
                    {draft.subject && <p className="text-sm text-slate-800"><span className="font-medium">Subject:</span> {draft.subject}</p>}
                    <pre className="mt-2 whitespace-pre-wrap font-[family-name:var(--font-inter)] text-sm text-slate-800">{draft.body}</pre>
                    <p className="mt-3 text-xs text-amber-700">{draft.review_note}</p>
                </div>
            )}
        </section>
    );
}
