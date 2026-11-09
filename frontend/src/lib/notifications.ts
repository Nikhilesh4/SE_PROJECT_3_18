"use client";

/**
 * Notifications: initial list over REST, live updates over Server-Sent Events.
 * The stream goes through the same cookie proxy as everything else, so no
 * token ever touches the page.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import api from "@/lib/api";
import { useSession } from "@/lib/authSession";

export interface AppNotification {
    id: number;
    kind: "new_match" | "deadline" | "mission" | "digest" | string;
    title: string;
    body: string;
    rss_item_id: number | null;
    read: boolean;
    created_at: string | null;
}

const STREAM_URL = "/api/backend/api/notifications/stream";
const MAX_BACKOFF_MS = 30_000;

export async function fetchNotifications(): Promise<{ unread: number; notifications: AppNotification[] }> {
    return (await api.get("/api/notifications", { params: { limit: 30 } })).data;
}

export async function markNotificationsRead(ids?: number[]): Promise<void> {
    await api.post("/api/notifications/read", ids ? { ids } : {});
}

export function useNotifications() {
    const session = useSession();
    const [items, setItems] = useState<AppNotification[]>([]);
    const [unread, setUnread] = useState(0);
    const [toasts, setToasts] = useState<AppNotification[]>([]);
    const seen = useRef<Set<number>>(new Set());

    // Reset everything when signed out so the next account starts clean.
    useEffect(() => {
        if (session === true) return;
        seen.current = new Set();
        const reset = setTimeout(() => {
            setItems([]);
            setUnread(0);
            setToasts([]);
        }, 0);
        return () => clearTimeout(reset);
    }, [session]);

    useEffect(() => {
        if (session !== true) return;
        let cancelled = false;
        let source: EventSource | null = null;
        let retry: ReturnType<typeof setTimeout> | undefined;
        let backoff = 2000;

        const accept = (n: AppNotification) => {
            if (seen.current.has(n.id)) return;
            seen.current.add(n.id);
            setItems((prev) => [n, ...prev].slice(0, 50));
            setUnread((u) => u + 1);
            setToasts((prev) => [...prev, n].slice(-3));
        };

        const connect = () => {
            if (cancelled) return;
            source = new EventSource(STREAM_URL);
            source.addEventListener("open", () => {
                backoff = 2000;
            });
            source.addEventListener("notification", (event) => {
                try {
                    accept(JSON.parse((event as MessageEvent).data) as AppNotification);
                } catch {
                    /* ignore malformed event */
                }
            });
            source.addEventListener("error", () => {
                // EventSource retries by itself unless the server closed the stream
                // (e.g. a 401): then reconnect manually with backoff.
                if (source && source.readyState === EventSource.CLOSED && !cancelled) {
                    source.close();
                    retry = setTimeout(connect, backoff);
                    backoff = Math.min(backoff * 2, MAX_BACKOFF_MS);
                }
            });
        };

        fetchNotifications()
            .then((data) => {
                if (cancelled) return;
                data.notifications.forEach((n) => seen.current.add(n.id));
                setItems(data.notifications);
                setUnread(data.unread);
            })
            .catch(() => {})
            .finally(connect);

        return () => {
            cancelled = true;
            if (retry) clearTimeout(retry);
            source?.close();
        };
    }, [session]);

    const markAllRead = useCallback(async () => {
        setItems((prev) => prev.map((n) => ({ ...n, read: true })));
        setUnread(0);
        try {
            await markNotificationsRead();
        } catch {
            /* the next refresh corrects it */
        }
    }, []);

    const markRead = useCallback(async (id: number) => {
        let wasUnread = false;
        setItems((prev) =>
            prev.map((n) => {
                if (n.id === id && !n.read) wasUnread = true;
                return n.id === id ? { ...n, read: true } : n;
            })
        );
        if (wasUnread) setUnread((u) => Math.max(0, u - 1));
        try {
            await markNotificationsRead([id]);
        } catch {
            /* ignore */
        }
    }, []);

    const dismissToast = useCallback((id: number) => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
    }, []);

    return { items, unread, toasts, markAllRead, markRead, dismissToast };
}
