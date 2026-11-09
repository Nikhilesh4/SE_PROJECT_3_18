"use client";

/**
 * Client-side view of the session.
 *
 * The JWT lives in an httpOnly cookie that scripts cannot read, so there is no
 * token here. Signing in and out goes through the /api/session routes, and the
 * UI asks GET /api/session whether someone is signed in.
 */

import { useEffect, useState } from "react";

export const AUTH_EVENT = "auth-changed";
const CROSS_TAB_KEY = "unicompass_auth_event";
const FEED_CACHE_KEY = "unicompass_feed_cache";

/** Remove credentials stored by earlier versions (a JWT in localStorage and a script-readable cookie). */
function purgeLegacyCredentials(): void {
    try {
        localStorage.removeItem("token");
    } catch {
        /* storage unavailable */
    }
    document.cookie = "auth_token=; Path=/; Max-Age=0; SameSite=Lax";
}

/** Tell this tab's components, and other tabs, that the session changed. */
function notifyAuthChanged(): void {
    try {
        localStorage.setItem(CROSS_TAB_KEY, String(Date.now()));
    } catch {
        /* storage unavailable */
    }
    window.dispatchEvent(new Event(AUTH_EVENT));
}

/** Drop locally cached data so the next account never sees this one's ranked results. */
export function clearClientCaches(): void {
    try {
        localStorage.removeItem(FEED_CACHE_KEY);
    } catch {
        /* storage unavailable */
    }
}

export async function fetchSession(): Promise<boolean> {
    purgeLegacyCredentials();
    try {
        const res = await fetch("/api/session", { cache: "no-store" });
        if (!res.ok) return false;
        return Boolean((await res.json()).authenticated);
    } catch {
        return false;
    }
}

/** Authenticated flag for the UI: null until the first check finishes. */
export function useSession(): boolean | null {
    const [authenticated, setAuthenticated] = useState<boolean | null>(null);

    useEffect(() => {
        let alive = true;
        const sync = () => {
            fetchSession().then((value) => {
                if (alive) setAuthenticated(value);
            });
        };
        sync();
        window.addEventListener("storage", sync); // other tabs
        window.addEventListener(AUTH_EVENT, sync);
        return () => {
            alive = false;
            window.removeEventListener("storage", sync);
            window.removeEventListener(AUTH_EVENT, sync);
        };
    }, []);

    return authenticated;
}

export class AuthRequestError extends Error {}

async function postCredentials(path: string, payload: Record<string, string>, failure: string): Promise<void> {
    let res: Response;
    try {
        res = await fetch(path, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
    } catch {
        throw new AuthRequestError(`${failure}. Please try again.`);
    }
    if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new AuthRequestError(typeof body.detail === "string" ? body.detail : failure);
    }
    clearClientCaches();
    notifyAuthChanged();
}

export function login(email: string, password: string): Promise<void> {
    return postCredentials("/api/session/login", { email, password }, "Login failed");
}

export function register(name: string, email: string, password: string): Promise<void> {
    return postCredentials("/api/session/register", { name, email, password }, "Registration failed");
}

export async function logout(): Promise<void> {
    clearClientCaches();
    try {
        await fetch("/api/session/logout", { method: "POST" });
    } finally {
        notifyAuthChanged();
    }
}
