import { NextRequest, NextResponse } from "next/server";
import { authHeaders, BACKEND_URL } from "@/lib/server/backend";

/**
 * Next.js API proxy for a single opportunity.
 * GET /api/feeds/:id → FastAPI GET /api/feeds/rss/:id
 *
 * `id` is the item's GUID, or its URL when the source has no GUID, so it may
 * contain slashes and must be re-encoded before forwarding.
 */

function safeDecode(value: string): string {
    try {
        return decodeURIComponent(value);
    } catch {
        return value; // already decoded and contains a literal "%"
    }
}

export async function GET(
    request: NextRequest,
    { params }: { params: Promise<{ id: string }> }
) {
    const { id } = await params;
    const endpoint = `${BACKEND_URL}/api/feeds/rss/${encodeURIComponent(safeDecode(id))}`;

    const headers: Record<string, string> = { Accept: "application/json", ...authHeaders(request) };

    try {
        const res = await fetch(endpoint, {
            headers,
            next: { revalidate: 0 }, // caching is handled by Redis
        });
        if (!res.ok) {
            const body = await res.json().catch(() => ({}));
            return NextResponse.json(
                { error: body.detail ?? `Backend returned ${res.status}` },
                { status: res.status }
            );
        }
        return NextResponse.json(await res.json());
    } catch (err: unknown) {
        const message = err instanceof Error ? err.message : String(err);
        return NextResponse.json(
            { error: `Failed to reach backend: ${message}` },
            { status: 502 }
        );
    }
}
