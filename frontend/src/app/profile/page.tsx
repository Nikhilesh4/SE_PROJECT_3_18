"use client";

import { useEffect, useState } from "react";
import { AxiosError } from "axios";
import api from "@/lib/api";
import ProfileDisplay from "./components/ProfileDisplay";
import ResumeUpload from "./components/ResumeUpload";
import { ProfileData } from "./components/types";

type ErrorResponse = {
    detail?: string;
};

export default function ProfilePage() {
    const [profile, setProfile] = useState<ProfileData | null>(null);
    const [isUploading, setIsUploading] = useState(false);
    const [error, setError] = useState("");
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
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
    }, []);

    return (
        <div className="min-h-screen bg-slate-950 pt-24 px-6 pb-10">
            <div className="max-w-5xl mx-auto space-y-6">
                <header>
                    <h1 className="text-3xl font-bold text-white">Profile Builder</h1>
                    <p className="mt-2 text-slate-300">
                        Upload your resume PDF to generate a structured profile with skills, education, and experience.
                    </p>
                </header>

                {error && (
                    <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
                        {error}
                    </div>
                )}

                <ResumeUpload
                    isUploading={isUploading}
                    onUploadStart={() => setIsUploading(true)}
                    onUploadEnd={() => setIsUploading(false)}
                    onUploadSuccess={(data) => {
                        setProfile(data);
                        setError("");
                    }}
                    onError={setError}
                />

                {isLoading ? (
                    <div className="rounded-xl border border-slate-700 bg-slate-900/70 px-4 py-6 text-sm text-slate-300">
                        Loading profile...
                    </div>
                ) : profile ? (
                    <ProfileDisplay profile={profile} />
                ) : (
                    <div className="rounded-xl border border-slate-700 bg-slate-900/70 px-4 py-6 text-sm text-slate-300">
                        No profile found yet. Upload your resume to generate one.
                    </div>
                )}
            </div>
        </div>
    );
}
