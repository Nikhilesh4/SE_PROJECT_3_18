/**
 * Server-side helpers for talking to the FastAPI backend on behalf of the
 * signed-in user. Only import this from route handlers.
 *
 * The JWT lives in an httpOnly cookie, so page scripts (and anything injected
 * into the page) can never read it. The browser only ever talks to Next.js;
 * these helpers attach the token when forwarding to FastAPI.
 */

import { NextRequest, NextResponse } from "next/server";

export const BACKEND_URL =
    process.env.BACKEND_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * In production the `__Host-` prefix makes browsers accept the cookie only when it is
 * Secure, set for the exact host (no Domain) and Path=/, so a sibling subdomain can't overwrite it.
 */
export const SESSION_COOKIE = process.env.NODE_ENV === "production" ? "__Host-uc_session" : "uc_session";

/** Matches the backend's ACCESS_TOKEN_EXPIRE_MINUTES when the token has no readable `exp`. */
const DEFAULT_MAX_AGE_SECONDS = 60 * 60 * 24;

/** Seconds since epoch at which the JWT expires, read without verifying it. */
function tokenExpiry(token: string): number | null {
    try {
        const payload = JSON.parse(Buffer.from(token.split(".")[1] ?? "", "base64url").toString());
        return typeof payload.exp === "number" ? payload.exp : null;
    } catch {
        return null;
    }
}

/** The session token from the request cookie, or null if absent or already expired. */
export function sessionToken(request: NextRequest): string | null {
    const token = request.cookies.get(SESSION_COOKIE)?.value;
    if (!token) return null;
    const exp = tokenExpiry(token);
    return exp !== null && exp * 1000 <= Date.now() ? null : token;
}

/** Headers that authenticate a forwarded request as the signed-in user. */
export function authHeaders(request: NextRequest): Record<string, string> {
    const token = sessionToken(request);
    return token ? { Authorization: `Bearer ${token}` } : {};
}

export function setSession(response: NextResponse, token: string): void {
    const exp = tokenExpiry(token);
    const maxAge = exp === null ? DEFAULT_MAX_AGE_SECONDS : Math.max(exp - Math.floor(Date.now() / 1000), 0);
    response.cookies.set({
        name: SESSION_COOKIE,
        value: token,
        httpOnly: true,
        sameSite: "lax",
        secure: process.env.NODE_ENV === "production",
        path: "/",
        maxAge,
    });
}

export function clearSession(response: NextResponse): void {
    response.cookies.set({
        name: SESSION_COOKIE,
        value: "",
        httpOnly: true,
        sameSite: "lax",
        secure: process.env.NODE_ENV === "production",
        path: "/",
        maxAge: 0,
    });
}

/**
 * CSRF guard for state-changing requests. SameSite=Lax already keeps the
 * cookie off cross-site POSTs; this also rejects them outright when the
 * browser says the request came from another site or origin.
 */
export function isCrossSite(request: NextRequest): boolean {
    const fetchSite = request.headers.get("sec-fetch-site");
    if (fetchSite && fetchSite !== "same-origin" && fetchSite !== "none") return true;
    const origin = request.headers.get("origin");
    if (!origin) return false;
    const host = request.headers.get("x-forwarded-host") ?? request.headers.get("host");
    try {
        return new URL(origin).host !== host;
    } catch {
        return true;
    }
}

export function forbidden(): NextResponse {
    return NextResponse.json({ detail: "Cross-site request blocked." }, { status: 403 });
}

/** Headers worth passing on so the backend sees the real client (rate limits are per IP). */
export function clientHeaders(request: NextRequest): Record<string, string> {
    const forwarded = request.headers.get("x-forwarded-for");
    return forwarded ? { "X-Forwarded-For": forwarded } : {};
}

/**
 * POST credentials to a backend auth endpoint (/auth/login or /auth/register).
 * On success the returned JWT goes into the httpOnly cookie and is never sent
 * to the browser; errors (including 429 rate limits) are relayed as-is.
 */
export async function startSession(request: NextRequest, backendPath: string): Promise<NextResponse> {
    if (isCrossSite(request)) return forbidden();

    let body: unknown;
    try {
        body = await request.json();
    } catch {
        return NextResponse.json({ detail: "Invalid request body." }, { status: 400 });
    }

    let upstream: Response;
    try {
        upstream = await fetch(`${BACKEND_URL}${backendPath}`, {
            method: "POST",
            headers: { "Content-Type": "application/json", Accept: "application/json", ...clientHeaders(request) },
            body: JSON.stringify(body),
            cache: "no-store",
        });
    } catch {
        return NextResponse.json({ detail: "Could not reach the server." }, { status: 502 });
    }

    const data = await upstream.json().catch(() => ({}));
    if (!upstream.ok || typeof data.access_token !== "string") {
        const headers: Record<string, string> = {};
        const retryAfter = upstream.headers.get("retry-after");
        if (retryAfter) headers["Retry-After"] = retryAfter;
        return NextResponse.json(
            { detail: data.detail ?? "Request failed." },
            { status: upstream.ok ? 502 : upstream.status, headers }
        );
    }

    const response = NextResponse.json({ ok: true });
    setSession(response, data.access_token);
    return response;
}

/** Forward an unauthenticated JSON POST (signup helpers such as email codes) and relay the answer. */
export async function relayPublicJson(request: NextRequest, backendPath: string): Promise<NextResponse> {
    if (isCrossSite(request)) return forbidden();

    let body: unknown;
    try {
        body = await request.json();
    } catch {
        return NextResponse.json({ detail: "Invalid request body." }, { status: 400 });
    }

    let upstream: Response;
    try {
        upstream = await fetch(`${BACKEND_URL}${backendPath}`, {
            method: "POST",
            headers: { "Content-Type": "application/json", Accept: "application/json", ...clientHeaders(request) },
            body: JSON.stringify(body),
            cache: "no-store",
        });
    } catch {
        return NextResponse.json({ detail: "Could not reach the server." }, { status: 502 });
    }
    return relayJson(upstream);
}

/** Forward a resume PDF to the signup pre-fill endpoint; nothing is stored. */
export async function relayResumePreview(request: NextRequest): Promise<NextResponse> {
    if (isCrossSite(request)) return forbidden();

    let incoming: FormData;
    try {
        incoming = await request.formData();
    } catch {
        return NextResponse.json({ detail: "Invalid upload." }, { status: 400 });
    }
    const file = incoming.get("file");
    if (!(file instanceof File)) return NextResponse.json({ detail: "Choose a PDF file." }, { status: 400 });
    if (file.size > 5 * 1024 * 1024) return NextResponse.json({ detail: "File size must be under 5MB" }, { status: 413 });

    const outgoing = new FormData();
    outgoing.append("file", file, file.name);

    let upstream: Response;
    try {
        upstream = await fetch(`${BACKEND_URL}/auth/resume-preview`, {
            method: "POST",
            headers: { Accept: "application/json", ...clientHeaders(request) },
            body: outgoing,
            cache: "no-store",
        });
    } catch {
        return NextResponse.json({ detail: "Could not reach the server." }, { status: 502 });
    }
    return relayJson(upstream);
}

async function relayJson(upstream: Response): Promise<NextResponse> {
    const data = await upstream.json().catch(() => ({ detail: "Request failed." }));
    const headers: Record<string, string> = { "Cache-Control": "no-store" };
    const retryAfter = upstream.headers.get("retry-after");
    if (retryAfter) headers["Retry-After"] = retryAfter;
    return NextResponse.json(data, { status: upstream.status, headers });
}
