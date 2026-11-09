import { NextRequest } from "next/server";
import { relayPublicJson } from "@/lib/server/backend";

export const dynamic = "force-dynamic";

/** POST /api/session/otp/verify { email, code } → { verification_token }. */
export async function POST(request: NextRequest) {
    return relayPublicJson(request, "/auth/otp/verify");
}
