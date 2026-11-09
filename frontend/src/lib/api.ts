import axios from "axios";
import { clearClientCaches, AUTH_EVENT } from "@/lib/authSession";

/**
 * Every request goes to the Next.js proxy, which adds the user's token from
 * the httpOnly session cookie and forwards to FastAPI. The browser never sees
 * the backend URL or the token.
 */
export const API_BASE_URL = "/api/backend";

const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        "Content-Type": "application/json",
    },
});

// Response interceptor — a 401 means the session is gone (the proxy has already
// expired the cookie), so reset local state and send the user to sign in.
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401 && typeof window !== "undefined") {
            clearClientCaches();
            window.dispatchEvent(new Event(AUTH_EVENT));
            window.location.href = "/login";
        }
        return Promise.reject(error);
    }
);

export default api;
