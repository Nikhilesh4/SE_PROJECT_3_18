import { NextRequest, NextResponse } from "next/server";
import { clearSession, sessionToken, SESSION_COOKIE } from "@/lib/server/backend";

export const dynamic = "force-dynamic";

/**
 * GET /api/session → { authenticated }
 *
 * The browser can't read the httpOnly cookie, so this is how the UI learns
 * whether someone is signed in. It checks only that a session cookie exists
 * and hasn't expired; the backend remains the authority on every real request.
 */
export async function GET(request: NextRequest) {
    const authenticated = sessionToken(request) !== null;
    const response = NextResponse.json({ authenticated }, { headers: { "Cache-Control": "no-store" } });
    if (!authenticated && request.cookies.has(SESSION_COOKIE)) clearSession(response); // expired
    return response;
}
