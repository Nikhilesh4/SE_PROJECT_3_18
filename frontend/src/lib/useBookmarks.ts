"use client";

/**
 * useBookmarks — Hook for managing user bookmark state.
 *
 * Loads bookmarked RSS item IDs on mount, provides toggle function,
 * and exposes a Set for O(1) lookup in the UI.
 *
 * All requests go through the Next.js API proxy which forwards
 * the JWT Authorization header to the FastAPI backend.
 */

import { useCallback, useEffect, useState } from "react";
import api from "@/lib/api";

interface UseBookmarksReturn {
    /** Set of bookmarked rss_item IDs for O(1) lookup */
    bookmarkedIds: Set<number>;
    /** Whether we're still loading the initial bookmark list */
    loading: boolean;
    /** Toggle bookmark for a given item ID — returns the action taken */
    toggleBookmark: (itemId: number) => Promise<"added" | "removed" | null>;
    /** Check if a specific item is bookmarked */
    isBookmarked: (itemId: number) => boolean;
    /** Reload bookmarks from server */
    refetch: () => Promise<void>;
}

export function useBookmarks(): UseBookmarksReturn {
    const [bookmarkedIds, setBookmarkedIds] = useState<Set<number>>(new Set());
    const [loading, setLoading] = useState(true);

    const fetchIds = useCallback(async () => {
        try {
            const res = await api.get("/api/bookmarks/ids");
            const ids: number[] = res.data?.ids ?? [];
            setBookmarkedIds(new Set(ids));
        } catch {
            // Silently ignore — user may not be logged in yet
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchIds();
    }, [fetchIds]);

    const toggleBookmark = useCallback(
        async (itemId: number): Promise<"added" | "removed" | null> => {
            try {
                const res = await api.post(`/api/bookmarks/${itemId}`);
                const action: "added" | "removed" = res.data?.action;

                setBookmarkedIds((prev) => {
                    const next = new Set(prev);
                    if (action === "added") {
                        next.add(itemId);
                    } else {
                        next.delete(itemId);
                    }
                    return next;
                });

                return action;
            } catch {
                return null;
            }
        },
        []
    );

    const isBookmarked = useCallback(
        (itemId: number) => bookmarkedIds.has(itemId),
        [bookmarkedIds]
    );

    return {
        bookmarkedIds,
        loading,
        toggleBookmark,
        isBookmarked,
        refetch: fetchIds,
    };
}
