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
        <div className="min-h-screen bg-slate-50 relative overflow-hidden">
            {/* Ambient background */}
            <div className="pointer-events-none fixed inset-0">
                <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[700px] h-[400px] bg-gradient-to-b from-indigo-100 via-sky-50 to-transparent rounded-full blur-3xl" />
                <div className="absolute bottom-1/3 right-0 w-72 h-72 bg-indigo-100/60 rounded-full blur-3xl" />
            </div>

            <div className="relative max-w-5xl mx-auto px-4 sm:px-6 py-8 pt-24 space-y-6">
                <header className="mb-8">
                    <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Profile Builder</h1>
                    <p className="mt-1 text-slate-600 text-sm">
                        Upload your resume PDF to generate a structured profile with skills, education, and experience.
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
                    onUploadSuccess={(data) => {
                        setProfile(data);
                        setError("");
                    }}
                    onError={setError}
                />

                {isLoading ? (
                    <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500 text-center">
                        Loading profile...
                    </div>
                ) : profile ? (
                    <ProfileDisplay profile={profile} />
                ) : (
                    <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500 text-center">
                        No profile found yet. Upload your resume to generate one.
                    </div>
                )}
            </div>
        </div>
    );
}
