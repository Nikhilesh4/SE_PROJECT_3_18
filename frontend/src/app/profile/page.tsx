"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { AxiosError } from "axios";
import Link from "next/link";
import api from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import { invalidateProfileCache } from "@/lib/useProfile";
import ProfileDisplay from "./components/ProfileDisplay";
import ResumeUpload from "./components/ResumeUpload";
import { ProfileData } from "./components/types";

type ErrorResponse = { detail?: string };

function ProfilePageInner() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const isNewUser = searchParams.get("new") === "true";

    const { isAuthenticated, checking } = useAuth();

    const [profile, setProfile] = useState<ProfileData | null>(null);
    const [isUploading, setIsUploading] = useState(false);
    const [error, setError] = useState("");
    const [isLoading, setIsLoading] = useState(true);
    const [uploadDone, setUploadDone] = useState(false);

    useEffect(() => {
        if (checking || !isAuthenticated) return;

        const loadProfile = async () => {
            try {
                const { data } = await api.get<ProfileData>("/profile/me");
                setProfile(data);
            } catch (err) {
                const axiosErr = err as AxiosError<ErrorResponse>;
                if (axiosErr.response?.status !== 404) {
                    const detail =
                        axiosErr.response?.data?.detail || "Failed to load profile.";
                    setError(detail);
                }
            } finally {
                setIsLoading(false);
            }
        };

        loadProfile();
    }, [checking, isAuthenticated]);

    const handleUploadSuccess = (data: ProfileData) => {
        setProfile(data);
        setError("");
        setUploadDone(true);
        // Invalidate the shared module-level profile cache so useFeed
        // picks up the new skills on the next feed load.
        invalidateProfileCache(data);
    };

    // ── Auth guard — show spinner while checking ──────────────────────────────
    if (checking || !isAuthenticated) {
        return (
            <div className="min-h-screen bg-slate-50 flex items-center justify-center">
                <div className="flex flex-col items-center gap-4">
                    <div className="w-10 h-10 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                    <p className="text-slate-600 text-sm">Verifying access...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-50 relative overflow-hidden">
            {/* Ambient background */}
            <div className="pointer-events-none fixed inset-0">
                <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[700px] h-[400px] bg-gradient-to-b from-indigo-100 via-sky-50 to-transparent rounded-full blur-3xl" />
                <div className="absolute bottom-1/3 right-0 w-72 h-72 bg-indigo-100/60 rounded-full blur-3xl" />
            </div>

            <div className="relative max-w-5xl mx-auto px-4 sm:px-6 py-8 pt-24 space-y-6">
                {/* ── New-user welcome hero ───────────────────────────────── */}
                {isNewUser && !profile && !uploadDone && (
                    <div className="rounded-2xl border border-indigo-200 bg-gradient-to-br from-indigo-50 to-sky-50 p-8 text-center shadow-sm">
                        <div className="text-4xl mb-3">🎉</div>
                        <h2 className="text-2xl font-bold text-slate-900 mb-2">
                            Welcome to UniCompass!
                        </h2>
                        <p className="text-slate-600 max-w-md mx-auto mb-6">
                            Your account is ready. Upload your resume below so our AI can
                            extract your skills and show you the most relevant opportunities.
                        </p>
                        {/* Steps progress */}
                        <div className="flex items-center justify-center gap-3">
                            <div className="flex items-center gap-2">
                                <div className="w-7 h-7 rounded-full bg-emerald-500 flex items-center justify-center text-white text-xs">✓</div>
                                <span className="text-sm font-medium text-emerald-700">Registered</span>
                            </div>
                            <div className="h-px w-8 bg-indigo-300" />
                            <div className="flex items-center gap-2">
                                <div className="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center text-white text-xs font-bold animate-pulse">2</div>
                                <span className="text-sm font-medium text-indigo-700">Upload Resume</span>
                            </div>
                            <div className="h-px w-8 bg-slate-300" />
                            <div className="flex items-center gap-2">
                                <div className="w-7 h-7 rounded-full bg-slate-200 flex items-center justify-center text-slate-400 text-xs font-bold">3</div>
                                <span className="text-sm text-slate-400">Explore Feed</span>
                            </div>
                        </div>
                    </div>
                )}

                {/* ── Post-upload success CTA ─────────────────────────────── */}
                {uploadDone && (
                    <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-sm">
                        <div>
                            <p className="font-semibold text-emerald-800 text-lg">
                                ✅ Profile created successfully!
                            </p>
                            <p className="text-emerald-700 text-sm mt-1">
                                Your skills have been extracted. Your feed will now show
                                opportunities ranked by relevance to you.
                            </p>
                        </div>
                        <Link
                            href="/feed?sort=relevant"
                            className="shrink-0 inline-flex items-center gap-2 px-6 py-3 rounded-xl font-semibold text-white bg-emerald-600 hover:bg-emerald-500 transition-all shadow-sm"
                        >
                            Explore Your Feed →
                        </Link>
                    </div>
                )}

                <header className="mb-2">
                    <div className="flex items-center gap-3 mb-2">
                        <h1 className="text-3xl font-bold text-slate-900 tracking-tight">
                            Profile Builder
                        </h1>
                        {profile && (
                            <div
                                title={
                                    profile.from_cache
                                        ? "Served from Redis cache (fast path)"
                                        : "Freshly fetched from PostgreSQL (cache miss)"
                                }
                                className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full border text-xs font-semibold transition-all ${
                                    profile.from_cache
                                        ? "bg-amber-50 border-amber-300 text-amber-700"
                                        : "bg-emerald-50 border-emerald-300 text-emerald-700"
                                }`}
                            >
                                <span>{profile.from_cache ? "⚡ Redis Cache" : "🗄️ PostgreSQL DB"}</span>
                            </div>
                        )}
                    </div>
                    <p className="text-slate-600 text-sm">
                        Upload your resume PDF to generate a structured profile. Your
                        extracted skills are used to personalise your discovery feed.
                    </p>
                </header>

                {error && (
                    <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
                        {error}
                    </div>
                )}

                <ResumeUpload
                    isUploading={isUploading}
                    onUploadStart={() => setIsUploading(true)}
                    onUploadEnd={() => setIsUploading(false)}
                    onUploadSuccess={handleUploadSuccess}
                    onError={setError}
                />

                {isLoading ? (
                    <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500 text-center">
                        Loading profile...
                    </div>
                ) : profile ? (
                    <ProfileDisplay profile={profile} />
                ) : (
                    !uploadDone && (
                        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center">
                            <div className="text-4xl mb-3">📄</div>
                            <p className="text-slate-700 font-medium">No profile yet</p>
                            <p className="text-sm text-slate-500 mt-1">
                                Upload your resume above to generate a structured profile.
                            </p>
                        </div>
                    )
                )}
            </div>
        </div>
    );
}

export default function ProfilePage() {
    return (
        <Suspense
            fallback={
                <div className="min-h-screen bg-slate-50 flex items-center justify-center">
                    <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                </div>
            }
        >
            <ProfilePageInner />
        </Suspense>
    );
}
