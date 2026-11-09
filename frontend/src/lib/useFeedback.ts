"use client";

/**
 * useFeedback: the user's thumbs up / thumbs down / hide choices, shared by
 * every card through one module-level store. Updates are optimistic and roll
 * back if the request fails.
 */

import { useCallback, useEffect, useSyncExternalStore } from "react";
import { AUTH_EVENT } from "@/lib/authSession";
import { clearFeedback, fetchFeedback, setFeedback, type FeedbackValue } from "@/lib/insights";

type FeedbackMap = Record<string, FeedbackValue>;

let state: FeedbackMap = {};
let loaded = false;
let loading = false;
const listeners = new Set<() => void>();

function emit(next: FeedbackMap) {
    state = next;
    listeners.forEach((l) => l());
}

function subscribe(listener: () => void) {
    listeners.add(listener);
    return () => listeners.delete(listener);
}

async function load() {
    if (loaded || loading) return;
    loading = true;
    try {
        const data = await fetchFeedback();
        loaded = true;
        emit(data);
    } catch {
        /* signed out or offline: stay empty, retry on next mount */
    } finally {
        loading = false;
    }
}

if (typeof window !== "undefined") {
    // A different account must never see the previous one's choices.
    window.addEventListener(AUTH_EVENT, () => {
        loaded = false;
        emit({});
    });
}

export function useFeedback() {
    const feedback = useSyncExternalStore(subscribe, () => state, () => state);

    // Cards only render for signed-in users; the first one to mount loads the map.
    useEffect(() => {
        void load();
    }, []);

    /** Click the active value again to undo it. Returns the resulting value (or null). */
    const choose = useCallback(async (itemId: number, value: FeedbackValue): Promise<FeedbackValue | null> => {
        const key = String(itemId);
        const previous = state[key];
        const next: FeedbackMap = { ...state };
        let result: FeedbackValue | null = value;
        if (previous === value) {
            delete next[key];
            result = null;
        } else {
            next[key] = value;
        }
        emit(next);
        try {
            if (result === null) await clearFeedback(itemId);
            else await setFeedback(itemId, value);
        } catch {
            const rollback = { ...state };
            if (previous) rollback[key] = previous;
            else delete rollback[key];
            emit(rollback);
            return previous ?? null;
        }
        return result;
    }, []);

    return { feedback, choose };
}
