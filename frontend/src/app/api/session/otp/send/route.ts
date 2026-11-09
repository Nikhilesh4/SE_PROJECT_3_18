import { NextRequest } from "next/server";
import { relayPublicJson } from "@/lib/server/backend";

export const dynamic = "force-dynamic";

/** POST /api/session/otp/send { email } → emails a verification code. */
export async function POST(request: NextRequest) {
    return relayPublicJson(request, "/auth/otp/send");
}
