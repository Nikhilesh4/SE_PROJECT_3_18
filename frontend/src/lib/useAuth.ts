"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getToken } from "@/lib/authSession";

/**
 * Auth guard hook.
 * Checks for JWT token in localStorage. If missing, redirects to /login.
 * Returns { isAuthenticated, token } once checked.
 */
export function useAuth() {
    const router = useRouter();
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [checking, setChecking] = useState(true);

    useEffect(() => {
        const applyAuthState = () => {
            const token = getToken();
            const authenticated = Boolean(token);
            setIsAuthenticated(authenticated);
            if (!authenticated) router.replace("/login");
            setChecking(false);
        };

        applyAuthState();
        window.addEventListener("storage", applyAuthState);
        window.addEventListener("auth-changed", applyAuthState);
        return () => {
            window.removeEventListener("storage", applyAuthState);
            window.removeEventListener("auth-changed", applyAuthState);
        };
    }, [router]);

    return { isAuthenticated, checking };
}
