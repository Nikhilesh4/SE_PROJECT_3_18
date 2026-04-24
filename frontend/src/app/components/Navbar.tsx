"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { clearToken, getToken } from "@/lib/authSession";
import { clearProfileCache } from "@/lib/useProfile";

export default function Navbar() {
    const router = useRouter();
    const [isLoggedIn, setIsLoggedIn] = useState<boolean | null>(null);

    useEffect(() => {
        const syncAuth = () => setIsLoggedIn(Boolean(getToken()));
        syncAuth();
        window.addEventListener("storage", syncAuth);
        window.addEventListener("auth-changed", syncAuth);
        return () => {
            window.removeEventListener("storage", syncAuth);
            window.removeEventListener("auth-changed", syncAuth);
        };
    }, []);

    const handleLogout = () => {
        clearProfileCache();   // wipe in-memory profile so next account starts fresh
        clearToken();          // removes JWT + localStorage feed cache
        setIsLoggedIn(false);
        router.push("/login");
    };

    if (isLoggedIn === null) {
        return null;
    }

    return (
        <nav className="fixed top-0 left-0 right-0 z-50 border-b border-slate-200 bg-white/90 backdrop-blur">
            <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
                {/* Logo */}
                <Link href="/" className="flex items-center gap-2 group">
                    <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold text-sm shadow-sm">
                        U
                    </div>
                    <span className="text-xl font-bold text-slate-900">
                        UniCompass
                    </span>
                </Link>

                {/* Navigation Links */}
                <div className="flex items-center gap-4">
                    {isLoggedIn ? (
                        <>
                            <Link
                                href="/feed"
                                className="text-slate-700 hover:text-slate-900 transition-colors text-sm font-medium"
                            >
                                Feed
                            </Link>
                            <Link
                                href="/bookmarks"
                                className="text-slate-700 hover:text-slate-900 transition-colors text-sm font-medium"
                            >
                                Bookmarks
                            </Link>
                            <Link
                                href="/profile"
                                className="text-slate-700 hover:text-slate-900 transition-colors text-sm font-medium"
                            >
                                Profile
                            </Link>
                            <button
                                onClick={handleLogout}
                                className="ml-2 px-4 py-2 rounded-lg text-sm font-medium border border-slate-300 text-slate-700 hover:bg-slate-100 transition-all cursor-pointer"
                            >
                                Logout
                            </button>
                        </>
                    ) : (
                        <>
                            <Link
                                href="/login"
                                className="text-slate-700 hover:text-slate-900 transition-colors text-sm font-medium"
                            >
                                Login
                            </Link>
                            <Link
                                href="/register"
                                className="px-4 py-2 rounded-lg text-sm font-medium bg-indigo-600 text-white hover:bg-indigo-500 transition-all"
                            >
                                Sign Up
                            </Link>
                        </>
                    )}
                </div>
            </div>
        </nav>
    );
}
