import { NextRequest } from "next/server";
import { startSession } from "@/lib/server/backend";

export const dynamic = "force-dynamic";

/** POST /api/session/register { name, email, password } → creates the account and signs in. */
export async function POST(request: NextRequest) {
    return startSession(request, "/auth/register");
}
