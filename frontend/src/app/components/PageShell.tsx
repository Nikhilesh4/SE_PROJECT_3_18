"use client";

import type { ReactNode } from "react";
import { useAuth } from "@/lib/useAuth";

interface Props {
    title: string;
    subtitle?: string;
    /** Page content is rendered only once the session is confirmed. */
    children: ReactNode;
    actions?: ReactNode;
    wide?: boolean;
}

/** Shared page frame: auth guard, ambient background, heading. */
export default function PageShell({ title, subtitle, actions, wide = false, children }: Props) {
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
        <div className="min-h-screen bg-slate-50 relative overflow-hidden">
            <div className="pointer-events-none fixed inset-0">
                <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[700px] h-[400px] bg-gradient-to-b from-indigo-100 via-sky-50 to-transparent rounded-full blur-3xl" />
            </div>
            <main className={`relative ${wide ? "max-w-7xl" : "max-w-5xl"} mx-auto px-4 sm:px-6 pt-24 pb-12`}>
                <div className="flex flex-wrap items-end justify-between gap-3 mb-6">
                    <div>
                        <h1 className="text-2xl sm:text-3xl font-bold text-slate-900">{title}</h1>
                        {subtitle && <p className="mt-1 text-sm text-slate-600 max-w-2xl">{subtitle}</p>}
                    </div>
                    {actions}
                </div>
                {children}
            </main>
        </div>
    );
}

export function ErrorNote({ message }: { message: string | null }) {
    if (!message) return null;
    return (
        <p role="alert" className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {message}
        </p>
    );
}

export function Spinner({ label = "Loading..." }: { label?: string }) {
    return (
        <div className="flex items-center gap-3 py-10 justify-center text-sm text-slate-500">
            <div className="w-5 h-5 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
            {label}
        </div>
    );
}
