import { NextRequest, NextResponse } from "next/server";
import { clearSession, forbidden, isCrossSite } from "@/lib/server/backend";

export const dynamic = "force-dynamic";

/** POST /api/session/logout → expires the session cookie. */
export async function POST(request: NextRequest) {
    if (isCrossSite(request)) return forbidden();
    const response = NextResponse.json({ ok: true });
    clearSession(response);
    return response;
}
