"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

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
        const token = localStorage.getItem("token");
        if (!token) {
            router.replace("/login");
        } else {
            setIsAuthenticated(true);
        }
        setChecking(false);
    }, [router]);

    return { isAuthenticated, checking };
}
