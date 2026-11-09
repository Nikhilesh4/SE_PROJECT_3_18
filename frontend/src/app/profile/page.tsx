"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { AxiosError } from "axios";
import Link from "next/link";
import api from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import { invalidateProfileCache } from "@/lib/useProfile";
import ProfileDisplay from "./components/ProfileDisplay";
import ProfileHeader from "./components/ProfileHeader";
import ApplicationsTab from "./components/ApplicationsTab";
import BookmarksTab from "./components/BookmarksTab";
import MissionsTab from "./components/MissionsTab";
import ResumeUpload from "./components/ResumeUpload";
import ProfileEditor from "./components/ProfileEditor";
import { ProfileData } from "./components/types";

type ErrorResponse = { detail?: string };

const TABS = [
    { id: "overview", label: "Overview" },
    { id: "applications", label: "Applications" },
    { id: "bookmarks", label: "Bookmarks" },
    { id: "missions", label: "Missions" },
] as const;
type TabId = (typeof TABS)[number]["id"];

function ProfilePageInner() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const isNewUser = searchParams.get("new") === "true";
    const tabParam = searchParams.get("tab");
    const tab: TabId = TABS.some((t) => t.id === tabParam) ? (tabParam as TabId) : "overview";

    const selectTab = (id: TabId) => {
        router.replace(id === "overview" ? "/profile" : `/profile?tab=${id}`, { scroll: false });
    };

    const { isAuthenticated, checking } = useAuth();

    const [profile, setProfile] = useState<ProfileData | null>(null);
    const [isUploading, setIsUploading] = useState(false);
    const [error, setError] = useState("");
    const [isLoading, setIsLoading] = useState(true);
    const [uploadDone, setUploadDone] = useState(false);
    const [updating, setUpdating] = useState(false);

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
        setUpdating(false);
        // Invalidate the shared module-level profile cache so useFeed
        // picks up the new skills on the next feed load.
        invalidateProfileCache(data);
    };

    const handleManualSaved = (data: ProfileData) => {
        setProfile(data);
        setError("");
        setUpdating(false);
        invalidateProfileCache(data);
    };

    const handleProfileChange = (data: ProfileData) => {
        setProfile(data);
        // Feed relevance ranking reads skills from this shared cache.
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

                {profile && <ProfileHeader profile={profile} />}

                <nav aria-label="Profile sections" className="flex gap-1 overflow-x-auto border-b border-slate-200">
                    {TABS.map((t) => (
                        <button
                            key={t.id}
                            type="button"
                            onClick={() => selectTab(t.id)}
                            aria-current={tab === t.id ? "page" : undefined}
                            className={`px-4 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 -mb-px cursor-pointer transition-colors ${
                                tab === t.id
                                    ? "border-indigo-600 text-indigo-700"
                                    : "border-transparent text-slate-600 hover:text-slate-900"
                            }`}
                        >
                            {t.label}
                        </button>
                    ))}
                </nav>

                {error && (
                    <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
                        {error}
                    </div>
                )}

                {tab === "applications" && <ApplicationsTab />}
                {tab === "bookmarks" && <BookmarksTab />}
                {tab === "missions" && <MissionsTab />}

                {tab === "overview" && (
                    <>
                {/* Update mode (or first-time setup): only the resume upload and the profile editor */}
                {updating || (!isLoading && !profile) ? (
                    <>
                        <ResumeUpload
                            isUploading={isUploading}
                            onUploadStart={() => setIsUploading(true)}
                            onUploadEnd={() => setIsUploading(false)}
                            onUploadSuccess={handleUploadSuccess}
                            onError={setError}
                        />
                        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                            <h2 className="text-xl font-semibold text-slate-900 tracking-tight">Edit your profile</h2>
                            <p className="mt-1 mb-5 text-sm text-slate-600">
                                Or enter and change your details by hand. Saving replaces what is shown on your profile.
                            </p>
                            <ProfileEditor
                                key={profile?.updated_at ?? "new"}
                                initial={profile}
                                submitLabel="Save profile"
                                onSaved={handleManualSaved}
                                onCancel={profile ? () => setUpdating(false) : undefined}
                            />
                        </section>
                        {profile && (
                            <button
                                type="button"
                                onClick={() => setUpdating(false)}
                                className="text-sm text-slate-500 hover:text-slate-700 cursor-pointer"
                            >
                                ← Back to profile
                            </button>
                        )}
                    </>
                ) : isLoading ? (
                    <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500 text-center">
                        Loading profile...
                    </div>
                ) : (
                    profile && (
                        <>
                            <div className="flex justify-end">
                                <button
                                    type="button"
                                    onClick={() => { setError(""); setUploadDone(false); setUpdating(true); }}
                                    className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 cursor-pointer"
                                >
                                    ✏️ Update profile
                                </button>
                            </div>
                            <ProfileDisplay profile={profile} onProfileChange={handleProfileChange} />
                        </>
                    )
                )}
                    </>
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
