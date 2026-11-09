import { NextRequest } from "next/server";
import { relayResumePreview } from "@/lib/server/backend";

export const dynamic = "force-dynamic";

/** POST /api/session/resume-preview (multipart file) → { name, email, socials, skills }; nothing is saved. */
export async function POST(request: NextRequest) {
    return relayResumePreview(request);
}
