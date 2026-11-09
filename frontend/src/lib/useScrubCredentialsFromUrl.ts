"use client";

import { useEffect } from "react";

const SENSITIVE_PARAMS = ["password", "confirmPassword", "pass", "pwd", "code", "token"];

/**
 * If a credential ever ends up in the address bar (e.g. a form submitted natively
 * before the page finished loading), remove it from the URL and history right away
 * so it is not kept in browser history or sent along in a Referer header.
 */
export function useScrubCredentialsFromUrl(): void {
    useEffect(() => {
        const url = new URL(window.location.href);
        const hits = SENSITIVE_PARAMS.filter((key) => url.searchParams.has(key));
        if (hits.length === 0 && !url.searchParams.has("email") && !url.searchParams.has("username")) return;
        ["email", "username", ...SENSITIVE_PARAMS].forEach((key) => url.searchParams.delete(key));
        window.history.replaceState(null, "", url.pathname + url.search + url.hash);
    }, []);
}
