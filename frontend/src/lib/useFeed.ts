"use client";

/**
 * useFeed — Data-fetching hook for the RSS opportunity feed.
 *
 * Design Patterns:
 *   - Hook Pattern: Encapsulates all fetching, caching, and error state.
 *   - Cache-Aside (client-side): Persists the last fetch to localStorage so
 *     the page renders instantly on revisit (stale-while-revalidate feel).
 *
 * Skill-based Relevance:
 *   When `skills` is provided the hook appends them as a query param.
 *   The backend re-ranks results by tag/title overlap with the skill set
 *   and caches the personalised slice separately (skills_hash in cache key).
 */

import { useCallback, useEffect, useState } from "react";

export interface NormalizedRssItem {
    title: string;
    url: string;
    summary: string;
    published_at: string | null;
    application_deadline?: string | null;
    category: string;
    source_name: string;
    feed_url: string;
    tags: string[];
    author: string | null;
    guid: string | null;
}

export interface FeedSourceStatus {
    feed_url: string;
    category: string;
    source_name: string;
    ok: boolean;
    http_status: number | null;
    error: string | null;
    entries_fetched: number;
    items_normalized: number;
}

export interface RssAggregationResponse {
    items: NormalizedRssItem[];
    sources: FeedSourceStatus[];
    total_items: number;
    fetched_at: string;
    from_cache: boolean;
}

interface UseFeedOptions {
    category?: string;
    limitPerFeed?: number;
    offset?: number;
    /** User skills extracted from resume — triggers relevance-based ranking */
    skills?: string[];
}

const CACHE_KEY = "unicompass_feed_cache";
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

interface CachedFeed {
    data: RssAggregationResponse;
    category: string;
    offset: number;
    skillsKey: string;
    timestamp: number;
}

function skillsKey(skills: string[] | undefined): string {
    if (!skills || skills.length === 0) return "";
    return [...skills].sort().join(",").toLowerCase();
}

function getCachedFeed(
    category: string,
    offset: number,
    sk: string
): RssAggregationResponse | null {
    try {
        const raw = localStorage.getItem(CACHE_KEY);
        if (!raw) return null;
        const cached: CachedFeed = JSON.parse(raw);
        if (cached.category !== category) return null;
        if (cached.offset !== offset) return null;
        if (cached.skillsKey !== sk) return null;
        if (Date.now() - cached.timestamp > CACHE_TTL_MS) return null;
        return cached.data;
    } catch {
        return null;
    }
}

function setCachedFeed(
    category: string,
    offset: number,
    sk: string,
    data: RssAggregationResponse
): void {
    try {
        const entry: CachedFeed = { data, category, offset, skillsKey: sk, timestamp: Date.now() };
        localStorage.setItem(CACHE_KEY, JSON.stringify(entry));
    } catch {
        // localStorage might be full — silently ignore
    }
}

export function useFeed({
    category,
    limitPerFeed = 50,
    offset = 0,
    skills,
}: UseFeedOptions = {}) {
    const cat = category ?? "";
    const sk = skillsKey(skills);

    const [data, setData] = useState<RssAggregationResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // On mount / parameter change — load from localStorage first (instant)
    useEffect(() => {
        const cached = getCachedFeed(cat, offset, sk);
        if (cached) {
            setData(cached);
        }
    }, [cat, offset, sk]);

    const fetch_ = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const params = new URLSearchParams({ limit_per_feed: String(limitPerFeed) });
            if (category) params.set("category", category);
            if (offset > 0) params.set("offset", String(offset));
            if (sk) params.set("skills", sk); // comma-separated skills string

            const res = await fetch(`/api/feeds?${params}`);
            if (!res.ok) {
                const body = await res.json().catch(() => ({}));
                throw new Error(body.error ?? `HTTP ${res.status}`);
            }
            const json: RssAggregationResponse = await res.json();
            setData(json);
            setCachedFeed(cat, offset, sk, json); // persist to localStorage
        } catch (err) {
            setError(String(err));
        } finally {
            setLoading(false);
        }
    }, [category, limitPerFeed, cat, offset, sk]);

    useEffect(() => {
        fetch_();
    }, [fetch_]);

    return { data, loading, error, refetch: fetch_ };
}
