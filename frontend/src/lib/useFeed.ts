"use client";

import { useCallback, useEffect, useState } from "react";

export interface NormalizedRssItem {
    title: string;
    url: string;
    summary: string;
    published_at: string | null;
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
}

interface UseFeedOptions {
    category?: string;
    limitPerFeed?: number;
}

const CACHE_KEY = "unicompass_feed_cache";
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

interface CachedFeed {
    data: RssAggregationResponse;
    category: string;
    timestamp: number;
}

function getCachedFeed(category: string): RssAggregationResponse | null {
    try {
        const raw = localStorage.getItem(CACHE_KEY);
        if (!raw) return null;
        const cached: CachedFeed = JSON.parse(raw);
        if (cached.category !== category) return null;
        if (Date.now() - cached.timestamp > CACHE_TTL_MS) return null;
        return cached.data;
    } catch {
        return null;
    }
}

function setCachedFeed(category: string, data: RssAggregationResponse): void {
    try {
        const entry: CachedFeed = { data, category, timestamp: Date.now() };
        localStorage.setItem(CACHE_KEY, JSON.stringify(entry));
    } catch {
        // localStorage might be full — silently ignore
    }
}

export function useFeed({ category, limitPerFeed = 50 }: UseFeedOptions = {}) {
    const cat = category ?? "";
    const [data, setData] = useState<RssAggregationResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // On mount / category change — load from localStorage first (instant)
    useEffect(() => {
        const cached = getCachedFeed(cat);
        if (cached) {
            setData(cached);
        }
    }, [cat]);

    const fetch_ = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const params = new URLSearchParams({ limit_per_feed: String(limitPerFeed) });
            if (category) params.set("category", category);

            const res = await fetch(`/api/feeds?${params}`);
            if (!res.ok) {
                const body = await res.json().catch(() => ({}));
                throw new Error(body.error ?? `HTTP ${res.status}`);
            }
            const json: RssAggregationResponse = await res.json();
            setData(json);
            setCachedFeed(cat, json); // persist to localStorage
        } catch (err) {
            setError(String(err));
        } finally {
            setLoading(false);
        }
    }, [category, limitPerFeed, cat]);

    useEffect(() => {
        fetch_();
    }, [fetch_]);

    return { data, loading, error, refetch: fetch_ };
}
