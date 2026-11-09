"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "@/lib/authSession";

/**
 * Auth guard hook.
 * Asks /api/session whether someone is signed in; if not, redirects to /login.
 * Returns { isAuthenticated, checking } once checked.
 */
export function useAuth() {
    const router = useRouter();
    const session = useSession();

    useEffect(() => {
        if (session === false) router.replace("/login");
    }, [session, router]);

    return { isAuthenticated: session === true, checking: session === null };
}
