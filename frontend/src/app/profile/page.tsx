"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import api from "@/lib/api";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface Profile {
    id: number;
    user_id: number;
    parsed_skills: string[];
    parsed_education: string | null;
    parsed_experience: string | null;
    created_at: string | null;
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function ProfilePage() {
    const router = useRouter();

    const [profile, setProfile] = useState<Profile | null>(null);
    const [loading, setLoading] = useState(true);
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState("");
    const [success, setSuccess] = useState("");
    const [dragOver, setDragOver] = useState(false);
    const [fileName, setFileName] = useState("");

    /* ---------- Fetch existing profile on mount ---------- */
    const fetchProfile = useCallback(async () => {
        try {
            setLoading(true);
            const res = await api.get("/profile/me");
            setProfile(res.data);
            setError("");
        } catch (err: unknown) {
            const axiosErr = err as { response?: { status?: number } };
            if (axiosErr.response?.status === 404) {
                setProfile(null); // no profile yet
            } else if (axiosErr.response?.status === 401) {
                router.push("/login");
            } else {
                setError("Failed to load profile.");
            }
        } finally {
            setLoading(false);
        }
    }, [router]);

    useEffect(() => {
        fetchProfile();
    }, [fetchProfile]);

    /* ---------- Upload handler ---------- */
    const handleUpload = async (file: File) => {
        if (file.type !== "application/pdf") {
            setError("Only PDF files are accepted.");
            return;
        }
        if (file.size > 10 * 1024 * 1024) {
            setError("File too large. Maximum 10 MB.");
            return;
        }

        setUploading(true);
        setError("");
        setSuccess("");
        setFileName(file.name);

        const formData = new FormData();
        formData.append("file", file);

        try {
            const res = await api.post("/profile/upload-resume", formData, {
                headers: { "Content-Type": "multipart/form-data" },
            });
            setProfile(res.data.profile);
            setSuccess(res.data.message || "Resume parsed successfully!");
        } catch (err: unknown) {
            const axiosErr = err as { response?: { data?: { detail?: string } } };
            setError(
                axiosErr.response?.data?.detail ||
                "Upload failed. Please try again."
            );
        } finally {
            setUploading(false);
        }
    };

    /* ---------- Drag & Drop ---------- */
    const onDrop = (e: React.DragEvent) => {
        e.preventDefault();
        setDragOver(false);
        const file = e.dataTransfer.files[0];
        if (file) handleUpload(file);
    };

    const onFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) handleUpload(file);
    };

    /* ---------- Render helpers ---------- */
    const formatDate = (iso: string | null) => {
        if (!iso) return "—";
        return new Date(iso).toLocaleDateString("en-IN", {
            year: "numeric",
            month: "long",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
        });
    };

    /* ================================================================ */
    /*  JSX                                                              */
    /* ================================================================ */
    return (
        <div className="min-h-screen bg-slate-950 pt-24 pb-16 px-6 relative overflow-hidden">
            {/* Background glow */}
            <div className="absolute inset-0 pointer-events-none">
                <div className="absolute top-0 right-1/3 w-[600px] h-[400px] bg-gradient-to-b from-violet-600/15 via-indigo-600/8 to-transparent rounded-full blur-3xl" />
                <div className="absolute bottom-0 left-1/4 w-80 h-80 bg-indigo-600/10 rounded-full blur-3xl" />
            </div>

            <div className="relative max-w-4xl mx-auto">
                {/* Page header */}
                <div className="mb-10">
                    <h1 className="text-3xl sm:text-4xl font-bold text-white mb-2">
                        Your Profile
                    </h1>
                    <p className="text-slate-400 text-base">
                        Upload your resume and let AI build your profile automatically.
                    </p>
                </div>

                {/* ───────── Upload Card ───────── */}
                <div className="mb-10">
                    <div
                        id="upload-dropzone"
                        onDragOver={(e) => {
                            e.preventDefault();
                            setDragOver(true);
                        }}
                        onDragLeave={() => setDragOver(false)}
                        onDrop={onDrop}
                        className={`
                            relative rounded-2xl border-2 border-dashed p-10 text-center transition-all duration-300 cursor-pointer
                            ${dragOver
                                ? "border-violet-400 bg-violet-500/10 scale-[1.01]"
                                : "border-white/15 bg-white/[0.03] hover:border-white/25 hover:bg-white/[0.05]"
                            }
                        `}
                    >
                        {uploading ? (
                            /* Uploading spinner */
                            <div className="flex flex-col items-center gap-4 py-4">
                                <div className="w-12 h-12 rounded-full border-4 border-violet-500/30 border-t-violet-500 animate-spin" />
                                <p className="text-white font-medium">
                                    Parsing your resume with AI…
                                </p>
                                {fileName && (
                                    <p className="text-sm text-slate-400">{fileName}</p>
                                )}
                            </div>
                        ) : (
                            /* Upload prompt */
                            <label
                                htmlFor="resume-input"
                                className="flex flex-col items-center gap-4 py-4 cursor-pointer"
                            >
                                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-500/20 to-indigo-600/20 border border-white/10 flex items-center justify-center">
                                    <svg
                                        className="w-8 h-8 text-violet-400"
                                        fill="none"
                                        viewBox="0 0 24 24"
                                        stroke="currentColor"
                                        strokeWidth={1.5}
                                    >
                                        <path
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                            d="M12 16.5V9.75m0 0 3 3m-3-3-3 3M6.75 19.5a4.5 4.5 0 0 1-1.41-8.775 5.25 5.25 0 0 1 10.233-2.33 3 3 0 0 1 3.758 3.848A3.752 3.752 0 0 1 18 19.5H6.75Z"
                                        />
                                    </svg>
                                </div>
                                <div>
                                    <p className="text-white font-semibold text-lg">
                                        {profile
                                            ? "Upload a new resume"
                                            : "Drop your resume here"}
                                    </p>
                                    <p className="text-sm text-slate-400 mt-1">
                                        PDF only · Max 10 MB
                                    </p>
                                </div>
                                <div className="mt-2 px-6 py-2.5 rounded-xl text-sm font-medium bg-gradient-to-r from-violet-600 to-indigo-600 text-white hover:from-violet-500 hover:to-indigo-500 shadow-lg shadow-violet-500/25 hover:shadow-violet-500/40 transition-all">
                                    Browse Files
                                </div>
                            </label>
                        )}
                        <input
                            id="resume-input"
                            type="file"
                            accept="application/pdf"
                            className="hidden"
                            onChange={onFileSelect}
                        />
                    </div>
                </div>

                {/* ───────── Alerts ───────── */}
                {error && (
                    <div className="mb-6 px-5 py-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 text-sm flex items-center gap-3">
                        <svg className="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z" />
                        </svg>
                        {error}
                    </div>
                )}
                {success && (
                    <div className="mb-6 px-5 py-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-sm flex items-center gap-3">
                        <svg className="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
                        </svg>
                        {success}
                    </div>
                )}

                {/* ───────── Profile Data ───────── */}
                {loading ? (
                    <div className="flex items-center justify-center py-20">
                        <div className="w-10 h-10 rounded-full border-4 border-violet-500/30 border-t-violet-500 animate-spin" />
                    </div>
                ) : profile ? (
                    <div className="space-y-6">
                        {/* ── Skills ── */}
                        <div className="rounded-2xl bg-white/[0.04] border border-white/10 p-6 hover:bg-white/[0.06] transition-colors">
                            <div className="flex items-center gap-2 mb-4">
                                <span className="text-xl">🛠️</span>
                                <h2 className="text-lg font-semibold text-white">
                                    Skills
                                </h2>
                            </div>
                            <div className="flex flex-wrap gap-2">
                                {profile.parsed_skills.length > 0 ? (
                                    profile.parsed_skills.map((skill, i) => (
                                        <span
                                            key={i}
                                            className="px-3 py-1.5 rounded-lg bg-violet-500/15 border border-violet-500/20 text-violet-300 text-sm font-medium hover:bg-violet-500/25 transition-colors"
                                        >
                                            {skill}
                                        </span>
                                    ))
                                ) : (
                                    <p className="text-slate-500 text-sm">
                                        No skills extracted.
                                    </p>
                                )}
                            </div>
                        </div>

                        {/* ── Education ── */}
                        <div className="rounded-2xl bg-white/[0.04] border border-white/10 p-6 hover:bg-white/[0.06] transition-colors">
                            <div className="flex items-center gap-2 mb-4">
                                <span className="text-xl">🎓</span>
                                <h2 className="text-lg font-semibold text-white">
                                    Education
                                </h2>
                            </div>
                            <p className="text-slate-300 text-sm leading-relaxed whitespace-pre-line">
                                {profile.parsed_education || "No education data extracted."}
                            </p>
                        </div>

                        {/* ── Experience ── */}
                        <div className="rounded-2xl bg-white/[0.04] border border-white/10 p-6 hover:bg-white/[0.06] transition-colors">
                            <div className="flex items-center gap-2 mb-4">
                                <span className="text-xl">💼</span>
                                <h2 className="text-lg font-semibold text-white">
                                    Experience
                                </h2>
                            </div>
                            <p className="text-slate-300 text-sm leading-relaxed whitespace-pre-line">
                                {profile.parsed_experience || "No experience data extracted."}
                            </p>
                        </div>

                        {/* ── Metadata ── */}
                        <div className="text-center">
                            <p className="text-xs text-slate-500">
                                Profile last updated: {formatDate(profile.created_at)}
                            </p>
                        </div>
                    </div>
                ) : (
                    /* No profile yet */
                    <div className="text-center py-16">
                        <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center">
                            <span className="text-4xl">📄</span>
                        </div>
                        <h2 className="text-xl font-semibold text-white mb-2">
                            No profile yet
                        </h2>
                        <p className="text-slate-400 text-sm max-w-md mx-auto">
                            Upload your resume above and our AI will automatically
                            extract your skills, education, and experience to build
                            your profile.
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
}
