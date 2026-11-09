"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import api from "@/lib/api";
import { AuthRequestError, register, sendEmailCode, verifyEmailCode } from "@/lib/authSession";
import { clearProfileCache, invalidateProfileCache } from "@/lib/useProfile";
import { useScrubCredentialsFromUrl } from "@/lib/useScrubCredentialsFromUrl";
import ProfileEditor from "../profile/components/ProfileEditor";

type Step = "account" | "verify" | "details";

const MAX_FILE_BYTES = 5 * 1024 * 1024;
const RESEND_SECONDS = 60;
const INPUT_CLASS =
    "w-full px-4 py-3 rounded-lg bg-white border border-slate-300 text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-500 transition-all";
const PRIMARY_BTN =
    "w-full py-3 px-4 rounded-lg font-semibold text-white bg-indigo-600 hover:bg-indigo-500 transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer";

const STEPS: { id: Step; label: string }[] = [
    { id: "account", label: "Account" },
    { id: "verify", label: "Verify email" },
    { id: "details", label: "Your details" },
];

export default function RegisterPage() {
    const router = useRouter();
    const fileRef = useRef<HTMLInputElement>(null);

    const [step, setStep] = useState<Step>("account");
    const [formData, setFormData] = useState({ username: "", email: "", password: "", confirmPassword: "" });
    const [code, setCode] = useState("");
    const [error, setError] = useState("");
    const [notice, setNotice] = useState("");
    const [loading, setLoading] = useState(false);
    const [cooldown, setCooldown] = useState(0);
    const [manual, setManual] = useState(false);
    const [ready, setReady] = useState(false); // see login page: no native submit before hydration
    useEffect(() => setReady(true), []);
    useScrubCredentialsFromUrl();

    useEffect(() => {
        if (cooldown <= 0) return;
        const t = setTimeout(() => setCooldown((c) => c - 1), 1000);
        return () => clearTimeout(t);
    }, [cooldown]);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setFormData({ ...formData, [e.target.name]: e.target.value });
    };

    const fail = (err: unknown, fallback: string) =>
        setError(err instanceof AuthRequestError ? err.message : fallback);

    // ── Step 1: account details → send code ──────────────────────────────────
    const requestCode = async (e?: React.FormEvent) => {
        e?.preventDefault();
        setError("");
        setNotice("");
        if (formData.password !== formData.confirmPassword) {
            setError("The two passwords do not match.");
            return;
        }
        setLoading(true);
        try {
            const { delivered } = await sendEmailCode(formData.email.trim());
            setCooldown(RESEND_SECONDS);
            setCode("");
            setStep("verify");
            setNotice(
                delivered
                    ? `We sent a 6-digit code to ${formData.email.trim()}. Check your spam folder if it does not arrive.`
                    : "Email delivery is not set up on this server. In development the code is printed in the backend console."
            );
        } catch (err) {
            fail(err, "Could not send the code. Please try again.");
        } finally {
            setLoading(false);
        }
    };

    // ── Step 2: verify code → create the account ─────────────────────────────
    const verifyAndRegister = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");
        setNotice("");
        setLoading(true);
        try {
            const token = await verifyEmailCode(formData.email.trim(), code.trim());
            clearProfileCache(); // wipe any previous account's profile first
            await register(formData.username.trim(), formData.email.trim(), formData.password, token);
            setStep("details");
        } catch (err) {
            fail(err, "Verification failed. Please try again.");
        } finally {
            setLoading(false);
        }
    };

    // ── Step 3: profile details (resume) — the account already exists ────────
    const handleResume = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        e.target.value = "";
        if (!file) return;
        if (file.type !== "application/pdf") return setError("Only PDF files are accepted.");
        if (file.size > MAX_FILE_BYTES) return setError("File size must be under 5MB.");

        setError("");
        setLoading(true);
        try {
            const form = new FormData();
            form.append("file", file);
            await api.post("/profile/upload-resume", form, { headers: { "Content-Type": "multipart/form-data" } });
            router.push("/profile");
        } catch {
            setError("Could not read that resume. Try another PDF, or skip and add it later from your profile.");
            setLoading(false);
        }
    };

    const stepIndex = STEPS.findIndex((s) => s.id === step);

    return (
        <div className="min-h-screen bg-slate-50 flex items-center justify-center px-4 py-12">
            <div className="fixed inset-0 overflow-hidden pointer-events-none">
                <div className="absolute top-1/4 -left-1/4 w-96 h-96 bg-indigo-100 rounded-full blur-3xl" />
                <div className="absolute bottom-1/4 -right-1/4 w-96 h-96 bg-sky-100 rounded-full blur-3xl" />
            </div>

            <div className={`relative w-full ${step === "details" && manual ? "max-w-2xl" : "max-w-md"}`}>
                <div className="text-center mb-8">
                    <Link href="/" className="inline-flex items-center gap-2 mb-6">
                        <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center text-white font-bold text-lg shadow-sm">
                            U
                        </div>
                        <span className="text-2xl font-bold text-slate-900">UniCompass</span>
                    </Link>
                    <h1 className="text-3xl font-bold text-slate-900 mb-2">Create Account</h1>
                    <p className="text-slate-600">Join UniCompass to discover opportunities</p>
                </div>

                <ol className="flex items-center justify-center gap-3 mb-8" aria-label="Signup progress">
                    {STEPS.map((s, i) => (
                        <li key={s.id} className="flex items-center gap-3">
                            {i > 0 && <div className="h-px w-6 bg-slate-300" />}
                            <div className="flex items-center gap-2">
                                <div
                                    className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                                        i <= stepIndex ? "bg-indigo-600 text-white" : "bg-slate-200 text-slate-400"
                                    }`}
                                >
                                    {i < stepIndex ? "✓" : i + 1}
                                </div>
                                <span className={`text-sm ${i === stepIndex ? "font-medium text-indigo-700" : "text-slate-400"}`}>
                                    {s.label}
                                </span>
                            </div>
                        </li>
                    ))}
                </ol>

                <div className="bg-white border border-slate-200 rounded-2xl p-8 shadow-sm">
                    {error && (
                        <div role="alert" className="mb-6 p-4 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
                            {error}
                        </div>
                    )}
                    {notice && (
                        <div className="mb-6 p-4 rounded-lg bg-sky-50 border border-sky-200 text-sky-800 text-sm">{notice}</div>
                    )}

                    {step === "account" && (
                        <form method="post" action="/register" onSubmit={requestCode} className="space-y-5">
                            <div>
                                <label htmlFor="username" className="block text-sm font-medium text-slate-700 mb-1.5">Username</label>
                                <input id="username" name="username" type="text" required minLength={2} autoComplete="username" value={formData.username} onChange={handleChange} className={INPUT_CLASS} placeholder="johndoe" />
                            </div>
                            <div>
                                <label htmlFor="email" className="block text-sm font-medium text-slate-700 mb-1.5">Gmail</label>
                                <input id="email" name="email" type="email" required autoComplete="email" value={formData.email} onChange={handleChange} className={INPUT_CLASS} placeholder="you@gmail.com" />
                                <p className="mt-1.5 text-xs text-slate-500">We will email a verification code to this address.</p>
                            </div>
                            <div>
                                <label htmlFor="password" className="block text-sm font-medium text-slate-700 mb-1.5">Password</label>
                                <input id="password" name="password" type="password" required minLength={8} maxLength={72} autoComplete="new-password" value={formData.password} onChange={handleChange} className={INPUT_CLASS} placeholder="••••••••" />
                            </div>
                            <div>
                                <label htmlFor="confirmPassword" className="block text-sm font-medium text-slate-700 mb-1.5">Confirm Password</label>
                                <input
                                    id="confirmPassword"
                                    name="confirmPassword"
                                    type="password"
                                    required
                                    minLength={8}
                                    maxLength={72}
                                    autoComplete="new-password"
                                    value={formData.confirmPassword}
                                    onChange={handleChange}
                                    aria-invalid={formData.confirmPassword !== "" && formData.confirmPassword !== formData.password}
                                    className={INPUT_CLASS}
                                    placeholder="••••••••"
                                />
                                {formData.confirmPassword !== "" && formData.confirmPassword !== formData.password && (
                                    <p className="mt-1.5 text-xs text-red-600">Passwords do not match.</p>
                                )}
                            </div>
                            <button type="submit" disabled={loading || !ready} className={PRIMARY_BTN}>
                                {loading ? "Sending code…" : "Send verification code →"}
                            </button>
                        </form>
                    )}

                    {step === "verify" && (
                        <form method="post" action="/register" onSubmit={verifyAndRegister} className="space-y-5">
                            <div>
                                <label htmlFor="code" className="block text-sm font-medium text-slate-700 mb-1.5">
                                    Verification code
                                </label>
                                <input
                                    id="code"
                                    inputMode="numeric"
                                    autoComplete="one-time-code"
                                    pattern="[0-9]{6}"
                                    maxLength={6}
                                    required
                                    value={code}
                                    onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                                    className={`${INPUT_CLASS} text-center text-2xl tracking-[0.5em] font-mono`}
                                    placeholder="••••••"
                                />
                            </div>
                            <button type="submit" disabled={loading || code.length !== 6} className={PRIMARY_BTN}>
                                {loading ? "Verifying…" : "Verify email →"}
                            </button>
                            <div className="flex items-center justify-between text-sm">
                                <button
                                    type="button"
                                    onClick={() => { setError(""); setNotice(""); setStep("account"); }}
                                    className="text-slate-500 hover:text-slate-700 cursor-pointer"
                                >
                                    ← Change email
                                </button>
                                <button
                                    type="button"
                                    disabled={cooldown > 0 || loading}
                                    onClick={() => void requestCode()}
                                    className="text-indigo-600 hover:text-indigo-500 disabled:text-slate-400 cursor-pointer disabled:cursor-not-allowed"
                                >
                                    {cooldown > 0 ? `Resend in ${cooldown}s` : "Resend code"}
                                </button>
                            </div>
                        </form>
                    )}

                    {step === "details" && !manual && (
                        <div className="space-y-4">
                            <p className="text-sm text-slate-600">
                                Email verified and your account is ready. Now tell us about yourself so we can rank
                                opportunities for you.
                            </p>
                            <input ref={fileRef} type="file" accept="application/pdf" className="hidden" onChange={handleResume} />
                            <button
                                type="button"
                                disabled={loading}
                                onClick={() => fileRef.current?.click()}
                                className="w-full text-left rounded-xl border border-indigo-200 bg-indigo-50/60 p-4 hover:border-indigo-400 transition-colors disabled:opacity-60 cursor-pointer"
                            >
                                <span className="block font-semibold text-slate-900">
                                    {loading ? "Reading your resume…" : "📄 Upload my resume"}
                                </span>
                                <span className="block text-sm text-slate-600 mt-1">
                                    We extract your skills, education and experience from a PDF. Max 5MB.
                                </span>
                            </button>
                            <button
                                type="button"
                                disabled={loading}
                                onClick={() => { setError(""); setManual(true); }}
                                className="w-full text-left rounded-xl border border-slate-200 bg-white p-4 hover:border-slate-400 transition-colors cursor-pointer"
                            >
                                <span className="block font-semibold text-slate-900">✍️ Add info manually</span>
                                <span className="block text-sm text-slate-600 mt-1">
                                    Type in your skills, education and experience yourself.
                                </span>
                            </button>
                            <button
                                type="button"
                                disabled={loading}
                                onClick={() => router.push("/profile?new=true")}
                                className="w-full text-sm text-slate-500 hover:text-slate-700 cursor-pointer"
                            >
                                Skip for now
                            </button>
                        </div>
                    )}

                    {step === "details" && manual && (
                        <ProfileEditor
                            initial={{ name: formData.username, skills: [], interests: [], education: [], experience: [], from_cache: false }}
                            submitLabel="Save & continue →"
                            onCancel={() => setManual(false)}
                            onSaved={(profile) => {
                                invalidateProfileCache(profile);
                                router.push("/profile");
                            }}
                        />
                    )}

                    <p className="mt-6 text-center text-sm text-slate-600">
                        Already have an account?{" "}
                        <Link href="/login" className="text-indigo-600 hover:text-indigo-500 font-medium transition-colors">
                            Sign in
                        </Link>
                    </p>
                </div>
            </div>
        </div>
    );
}
