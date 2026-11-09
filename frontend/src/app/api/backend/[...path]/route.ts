import { NextRequest, NextResponse } from "next/server";
import {
    authHeaders,
    BACKEND_URL,
    clearSession,
    clientHeaders,
    forbidden,
    isCrossSite,
    SESSION_COOKIE,
} from "@/lib/server/backend";

export const dynamic = "force-dynamic";

/**
 * Authenticated proxy to the FastAPI backend: /api/backend/<path> → <backend>/<path>.
 *
 * The browser sends only its httpOnly session cookie; this handler turns it
 * into the Authorization header. Responses are streamed through untouched, so
 * the assistant's Server-Sent Events keep arriving token by token.
 *
 * Login and registration are deliberately not reachable here: they go through
 * /api/session/*, which is what sets the cookie.
 */

const PREFIX = "/api/backend/";
const ALLOWED = ["profile/", "agent/", "api/", "auth/me"];
const MAX_BODY_BYTES = 10 * 1024 * 1024; // the backend caps resumes at 5 MB
const PASS_THROUGH = ["content-type", "cache-control", "retry-after", "x-accel-buffering", "content-disposition"];

async function proxy(request: NextRequest): Promise<NextResponse> {
    const pathname = request.nextUrl.pathname;
    const target = pathname.startsWith(PREFIX) ? pathname.slice(PREFIX.length) : "";
    const segments = target.split("/").map((s) => {
        try {
            return decodeURIComponent(s);
        } catch {
            return s;
        }
    });
    if (
        !ALLOWED.some((p) => target === p || target.startsWith(p)) ||
        segments.some((s) => s === ".." || s === ".")
    ) {
        return NextResponse.json({ detail: "Not found." }, { status: 404 });
    }

    const method = request.method;
    const hasBody = method !== "GET" && method !== "HEAD";
    if (hasBody && isCrossSite(request)) return forbidden();

    const headers: Record<string, string> = {
        Accept: request.headers.get("accept") ?? "application/json",
        ...clientHeaders(request),
        ...authHeaders(request),
    };
    let body: ArrayBuffer | undefined;
    if (hasBody) {
        const declared = Number(request.headers.get("content-length") ?? 0);
        if (declared > MAX_BODY_BYTES) {
            return NextResponse.json({ detail: "Request body too large." }, { status: 413 });
        }
        body = await request.arrayBuffer();
        if (body.byteLength > MAX_BODY_BYTES) {
            return NextResponse.json({ detail: "Request body too large." }, { status: 413 });
        }
        const contentType = request.headers.get("content-type");
        if (contentType) headers["Content-Type"] = contentType;
    }

    let upstream: Response;
    try {
        upstream = await fetch(`${BACKEND_URL}/${target}${request.nextUrl.search}`, {
            method,
            headers,
            body,
            cache: "no-store",
            signal: request.signal, // the Stop button / closed tab cancels the backend work too
        });
    } catch (err) {
        if (request.signal.aborted) return new NextResponse(null, { status: 499 });
        console.error("[proxy] backend unreachable:", err instanceof Error ? err.message : err);
        return NextResponse.json({ detail: "Could not reach the server." }, { status: 502 });
    }

    const out = new Headers();
    for (const name of PASS_THROUGH) {
        const value = upstream.headers.get(name);
        if (value) out.set(name, value);
    }
    if (out.get("content-type")?.startsWith("text/event-stream")) {
        // no-transform stops Next from compressing (and so buffering) the stream
        out.set("Cache-Control", "no-cache, no-transform");
    }

    const response = new NextResponse(upstream.body, { status: upstream.status, headers: out });
    if (upstream.status === 401 && request.cookies.has(SESSION_COOKIE)) clearSession(response);
    return response;
}

export const GET = (request: NextRequest) => proxy(request);
export const POST = (request: NextRequest) => proxy(request);
export const PUT = (request: NextRequest) => proxy(request);
export const PATCH = (request: NextRequest) => proxy(request);
export const DELETE = (request: NextRequest) => proxy(request);
