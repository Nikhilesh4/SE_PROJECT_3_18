import { NextRequest, NextResponse } from "next/server";

/**
 * Next.js API proxy for bookmark list endpoints.
 * GET /api/bookmarks      → FastAPI GET /api/bookmarks
 * GET /api/bookmarks?ids  → FastAPI GET /api/bookmarks/ids  (if 'ids' param present)
 */

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function GET(request: NextRequest) {
    const { searchParams } = new URL(request.url);
    const headers: Record<string, string> = { Accept: "application/json" };

    // Forward Authorization header
    const authHeader = request.headers.get("Authorization");
    if (authHeader) headers["Authorization"] = authHeader;

    // Check if this is a request for bookmark IDs
    const wantIds = searchParams.has("ids");
    const backendPath = wantIds ? "/api/bookmarks/ids" : "/api/bookmarks";

    // Forward pagination params for list endpoint
    const params = new URLSearchParams();
    const limit = searchParams.get("limit");
    const offset = searchParams.get("offset");
    const category = searchParams.get("category");
    if (limit) params.set("limit", limit);
    if (offset) params.set("offset", offset);
    if (category) params.set("category", category);

    const endpoint = `${BACKEND_URL}${backendPath}${params.size > 0 ? `?${params}` : ""}`;

    try {
        const res = await fetch(endpoint, { headers, next: { revalidate: 0 } });
        if (!res.ok) {
            const body = await res.json().catch(() => ({}));
            return NextResponse.json(
                { error: body.detail ?? `Backend returned ${res.status}` },
                { status: res.status }
            );
        }
        const data = await res.json();
        return NextResponse.json(data);
    } catch (err: unknown) {
        const message = err instanceof Error ? err.message : String(err);
        return NextResponse.json(
            { error: `Failed to reach backend: ${message}` },
            { status: 502 }
        );
    }
}
