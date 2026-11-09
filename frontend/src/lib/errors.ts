import axios from "axios";

/** A readable message from a failed API call (FastAPI puts it in `detail`). */
export function errorMessage(err: unknown, fallback: string): string {
    if (axios.isAxiosError(err)) {
        const detail = err.response?.data?.detail;
        if (typeof detail === "string") return detail;
        if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg);
        if (err.response?.status === 429) return "Too many requests. Please wait a moment.";
    }
    return fallback;
}
