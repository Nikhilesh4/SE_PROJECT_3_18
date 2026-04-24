import { NextRequest, NextResponse } from "next/server";

/**
 * Next.js API proxy for individual bookmark operations.
 * POST   /api/bookmarks/:id → FastAPI POST   /api/bookmarks/:id (toggle)
 * DELETE /api/bookmarks/:id → FastAPI DELETE /api/bookmarks/:id (remove)
 */

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

async function proxyRequest(
    request: NextRequest,
    method: string,
    id: string
) {
    const headers: Record<string, string> = {
        Accept: "application/json",
        "Content-Type": "application/json",
    };
    const authHeader = request.headers.get("Authorization");
    if (authHeader) headers["Authorization"] = authHeader;

    const endpoint = `${BACKEND_URL}/api/bookmarks/${id}`;

    try {
        const res = await fetch(endpoint, {
            method,
            headers,
            next: { revalidate: 0 },
        });
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

export async function POST(
    request: NextRequest,
    { params }: { params: Promise<{ id: string }> }
) {
    const { id } = await params;
    return proxyRequest(request, "POST", id);
}

export async function DELETE(
    request: NextRequest,
    { params }: { params: Promise<{ id: string }> }
) {
    const { id } = await params;
    return proxyRequest(request, "DELETE", id);
}
