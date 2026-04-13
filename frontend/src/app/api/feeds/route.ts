import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function GET(request: NextRequest) {
    const { searchParams } = new URL(request.url);
    const params = new URLSearchParams();

    const limitPerFeed = searchParams.get("limit_per_feed");
    const category = searchParams.get("category");
    const offset = searchParams.get("offset");

    if (limitPerFeed) params.set("limit_per_feed", limitPerFeed);
    if (category) params.set("category", category);
    if (offset) params.set("offset", offset);

    const backendEndpoint = `${BACKEND_URL}/api/feeds/rss${params.size > 0 ? `?${params}` : ""}`;

    try {
        const res = await fetch(backendEndpoint, {
            headers: { Accept: "application/json" },
            next: { revalidate: 0 }, // always fresh
        });

        if (!res.ok) {
            return NextResponse.json(
                { error: `Backend returned ${res.status}` },
                { status: res.status }
            );
        }

        const data = await res.json();
        return NextResponse.json(data);
    } catch (err) {
        return NextResponse.json(
            { error: `Failed to reach backend: ${String(err)}` },
            { status: 502 }
        );
    }
}
