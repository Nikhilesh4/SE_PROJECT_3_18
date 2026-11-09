import { NextRequest } from "next/server";
import { startSession } from "@/lib/server/backend";

export const dynamic = "force-dynamic";

/** POST /api/session/login { email, password } → sets the httpOnly session cookie. */
export async function POST(request: NextRequest) {
    return startSession(request, "/auth/login");
}
