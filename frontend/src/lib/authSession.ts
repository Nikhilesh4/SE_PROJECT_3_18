"use client";

const TOKEN_KEY = "token";
const COOKIE_KEY = "auth_token";
const COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 7; // 7 days

export function getToken(): string | null {
    if (typeof window === "undefined") return null;
    const local = localStorage.getItem(TOKEN_KEY);
    if (local) return local;

    const cookie = document.cookie
        .split("; ")
        .find((part) => part.startsWith(`${COOKIE_KEY}=`));
    if (!cookie) return null;
    return decodeURIComponent(cookie.split("=")[1] ?? "");
}

export function persistToken(token: string): void {
    if (typeof window === "undefined") return;
    localStorage.setItem(TOKEN_KEY, token);
    document.cookie = `${COOKIE_KEY}=${encodeURIComponent(token)}; Path=/; Max-Age=${COOKIE_MAX_AGE_SECONDS}; SameSite=Lax`;
    window.dispatchEvent(new Event("auth-changed"));
}

export function clearToken(): void {
    if (typeof window === "undefined") return;
    localStorage.removeItem(TOKEN_KEY);
    document.cookie = `${COOKIE_KEY}=; Path=/; Max-Age=0; SameSite=Lax`;
    window.dispatchEvent(new Event("auth-changed"));
}

