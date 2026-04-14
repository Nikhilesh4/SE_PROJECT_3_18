"use client";

import { useAuth } from "@/lib/useAuth";

export default function ProfilePage() {
    const { isAuthenticated, checking } = useAuth();

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
        <div className="min-h-screen bg-slate-50 pt-24 px-6">
            <div className="max-w-4xl mx-auto">
                <h1 className="text-3xl font-bold text-slate-900 mb-4">Profile</h1>
                <p className="text-slate-600">
                    Upload your resume and view your profile here.
                </p>
            </div>
        </div>
    );
}
