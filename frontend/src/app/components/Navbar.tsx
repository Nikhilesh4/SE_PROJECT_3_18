"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import NotificationBell from "./NotificationBell";
import { logout, useSession } from "@/lib/authSession";
import { clearProfileCache } from "@/lib/useProfile";

const LINK_CLASS = "text-slate-700 hover:text-slate-900 transition-colors text-sm font-medium";

const PRIMARY_LINKS = [
    { href: "/feed", label: "Feed" },
    { href: "/search", label: "Search" },
    { href: "/applications", label: "Applications" },
    { href: "/assistant", label: "Assistant" },
];

const MORE_LINKS = [
    { href: "/bookmarks", label: "Bookmarks" },
    { href: "/missions", label: "Missions" },
    { href: "/insights", label: "Market insights" },
    { href: "/research", label: "Research scout" },
];

export default function Navbar() {
    const router = useRouter();
    const isLoggedIn = useSession();
    const [moreOpen, setMoreOpen] = useState(false);
    const moreRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!moreOpen) return;
        const onDown = (e: MouseEvent) => {
            if (moreRef.current && !moreRef.current.contains(e.target as Node)) setMoreOpen(false);
        };
        const onKey = (e: KeyboardEvent) => e.key === "Escape" && setMoreOpen(false);
        document.addEventListener("mousedown", onDown);
        document.addEventListener("keydown", onKey);
        return () => {
            document.removeEventListener("mousedown", onDown);
            document.removeEventListener("keydown", onKey);
        };
    }, [moreOpen]);

    const handleLogout = async () => {
        clearProfileCache();   // wipe in-memory profile so next account starts fresh
        await logout();        // expires the session cookie + clears the cached feed
        router.push("/login");
    };

    if (isLoggedIn === null) {
        return null;
    }

    return (
        <nav className="fixed top-0 left-0 right-0 z-50 border-b border-slate-200 bg-white/90 backdrop-blur">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
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
                <div className="flex items-center gap-3 sm:gap-4">
                    {isLoggedIn ? (
                        <>
                            {PRIMARY_LINKS.map((l) => (
                                <Link key={l.href} href={l.href} className={`${LINK_CLASS} hidden md:inline`}>
                                    {l.label}
                                </Link>
                            ))}
                            <div ref={moreRef} className="relative">
                                <button
                                    onClick={() => setMoreOpen((o) => !o)}
                                    aria-expanded={moreOpen}
                                    aria-haspopup="menu"
                                    className={`${LINK_CLASS} inline-flex items-center gap-1 cursor-pointer`}
                                >
                                    More
                                    <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
                                        <polyline points="6 9 12 15 18 9" />
                                    </svg>
                                </button>
                                {moreOpen && (
                                    <div role="menu" className="absolute right-0 mt-2 w-48 rounded-xl border border-slate-200 bg-white py-1 shadow-xl">
                                        {PRIMARY_LINKS.map((l) => (
                                            <Link
                                                key={l.href}
                                                href={l.href}
                                                role="menuitem"
                                                onClick={() => setMoreOpen(false)}
                                                className="block md:hidden px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 hover:text-slate-900"
                                            >
                                                {l.label}
                                            </Link>
                                        ))}
                                        {MORE_LINKS.map((l) => (
                                            <Link
                                                key={l.href}
                                                href={l.href}
                                                role="menuitem"
                                                onClick={() => setMoreOpen(false)}
                                                className="block px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 hover:text-slate-900"
                                            >
                                                {l.label}
                                            </Link>
                                        ))}
                                    </div>
                                )}
                            </div>
                            <NotificationBell />
                            <Link href="/profile" className={LINK_CLASS}>
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
