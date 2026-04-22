"use client";

/**
 * useProfile — Shared hook for fetching the current user's parsed resume profile.
 *
 * Design Patterns:
 *   - Hook Pattern: Encapsulates data-fetching logic, keeps components lean.
 *   - Cache: Profile is stored in a module-level variable so multiple components
 *     on the same page share a single fetch (no redundant API calls).
 *
 * The profile data (skills, interests) is also exposed for downstream use —
 * e.g., the feed page reads skills to request relevance-ranked results.
 */

import { useCallback, useEffect, useState } from "react";
import api from "@/lib/api";
import { AxiosError } from "axios";

export interface ProfileData {
    skills: string[];
    interests: string[];
    education: { degree: string; institution: string; year: string }[];
    experience: { role: string; company: string; duration: string; summary: string }[];
    updated_at?: string | null;
    from_cache: boolean;
}

// ── Module-level in-memory cache (session lifetime) ───────────────────────────
// Avoids redundant fetches when multiple components mount in the same session.
let _cachedProfile: ProfileData | null = null;
let _fetchPromise: Promise<ProfileData | null> | null = null;

async function fetchProfileOnce(): Promise<ProfileData | null> {
    if (_cachedProfile) return _cachedProfile;
    if (_fetchPromise) return _fetchPromise;

    _fetchPromise = api
        .get<ProfileData>("/profile/me")
        .then((res) => {
            _cachedProfile = res.data;
            return res.data;
        })
        .catch((err: AxiosError) => {
            // 404 means no resume uploaded yet — not an error
            if (err.response?.status === 404) return null;
            return null;
        })
        .finally(() => {
            _fetchPromise = null;
        });

    return _fetchPromise;
}

/** Call this after a successful resume upload to clear the module-level cache
 *  so the next `useProfile` mount fetches fresh data. */
export function invalidateProfileCache(freshProfile?: ProfileData) {
    _cachedProfile = freshProfile ?? null;
    _fetchPromise = null;
}

/**
 * Call this on LOGOUT or LOGIN (account switch) to ensure the next user
 * never inherits the previous user's in-memory profile.
 *
 * This is critical: _cachedProfile is a module-level singleton that survives
 * React re-renders and page navigations. Without clearing it, account B would
 * see account A's skills when clicking "Sort by Relevance".
 */
export function clearProfileCache() {
    _cachedProfile = null;
    _fetchPromise = null;
}

export function useProfile() {
    const [profile, setProfile] = useState<ProfileData | null>(_cachedProfile);
    const [loading, setLoading] = useState(!_cachedProfile);
    const [hasProfile, setHasProfile] = useState(Boolean(_cachedProfile));

    const load = useCallback(async () => {
        setLoading(true);
        const data = await fetchProfileOnce();
        setProfile(data);
        setHasProfile(Boolean(data));
        setLoading(false);
    }, []);

    useEffect(() => {
        if (!_cachedProfile) {
            load();
        }
    }, [load]);

    const refresh = useCallback(async () => {
        _cachedProfile = null;
        await load();
    }, [load]);

    return { profile, loading, hasProfile, refresh };
}
