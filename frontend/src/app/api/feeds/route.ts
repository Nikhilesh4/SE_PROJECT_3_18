import { NextRequest, NextResponse } from "next/server";

/**
 * Next.js API proxy for the feeds endpoint.
 *
 * Forwards to the FastAPI backend and relays:
 *   - Pagination params (limit_per_feed, offset, category)
 *   - Skills param — enables backend relevance ranking
 *   - Authorization header — allows future authenticated endpoints
 *
 * Architecture — Facade Pattern:
 *   The frontend never calls the FastAPI backend directly; all traffic is
 *   proxied through this Next.js route, keeping the backend URL internal.
 */

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function GET(request: NextRequest) {
    const { searchParams } = new URL(request.url);
    const params = new URLSearchParams();

    // ── Relay recognised query parameters ────────────────────────────────────
    const limitPerFeed = searchParams.get("limit_per_feed");
    const category     = searchParams.get("category");
    const offset       = searchParams.get("offset");
    const skills       = searchParams.get("skills");       // ← NEW
    const activeOnly   = searchParams.get("active_only");  // ← optional

    if (limitPerFeed) params.set("limit_per_feed", limitPerFeed);
    if (category)     params.set("category",       category);
    if (offset)       params.set("offset",         offset);
    if (skills)       params.set("skills",         skills);   // ← forward skills
    if (activeOnly)   params.set("active_only",    activeOnly);

    const backendEndpoint = `${BACKEND_URL}/api/feeds/rss${params.size > 0 ? `?${params}` : ""}`;

    // ── Forward Authorization header if present ───────────────────────────────
    // Required so the backend can (optionally) verify the user in the future.
    const headers: Record<string, string> = { Accept: "application/json" };
    const authHeader = request.headers.get("Authorization");
    if (authHeader) headers["Authorization"] = authHeader;

    try {
        console.log(`[Frontend API] Fetching: ${backendEndpoint}`);
        const res = await fetch(backendEndpoint, {
            headers,
            next: { revalidate: 0 }, // always fresh — caching is handled by Redis
        });

        if (!res.ok) {
            console.error(`[Frontend API] Backend error: ${res.status} ${res.statusText}`);
            return NextResponse.json(
                { error: `Backend returned ${res.status}` },
                { status: res.status }
            );
        }

        const data = await res.json();
        return NextResponse.json(data);
    } catch (err: unknown) {
        const message = err instanceof Error ? err.message : String(err);
        console.error(`[Frontend API] Request failed:`, { endpoint: backendEndpoint, error: message });
        return NextResponse.json(
            { error: `Failed to reach backend: ${message}` },
            { status: 502 }
        );
    }
}
