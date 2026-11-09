"use client";

/** Application tracker (Kanban board over bookmarks) and deadlines. */

import api from "@/lib/api";
import type { NormalizedRssItem } from "@/lib/useFeed";

export type ApplicationStatus = "saved" | "applied" | "interview" | "offer" | "rejected";

export interface ApplicationCard {
    item: NormalizedRssItem;
    status: ApplicationStatus;
    notes: string;
    applied_at: string | null;
    saved_at: string | null;
    updated_at: string | null;
}

export interface ApplicationBoard {
    statuses: ApplicationStatus[];
    columns: Record<string, ApplicationCard[]>;
    total: number;
}

export interface DeadlineItem extends NormalizedRssItem {
    days_left: number;
}

export async function fetchBoard(): Promise<ApplicationBoard> {
    const { data } = await api.get<ApplicationBoard>("/api/applications");
    return data;
}

export async function updateApplication(
    itemId: number,
    patch: { status?: ApplicationStatus; notes?: string }
): Promise<ApplicationCard> {
    const { data } = await api.patch<ApplicationCard>(`/api/applications/${itemId}`, patch);
    return data;
}

export async function fetchDeadlines(days = 14, scope: "saved" | "all" = "saved"): Promise<DeadlineItem[]> {
    const { data } = await api.get<{ items: DeadlineItem[] }>("/api/deadlines", { params: { days, scope } });
    return data.items;
}

/** Download the .ics file (the browser sends the session cookie, so a plain link works). */
export const CALENDAR_URL = "/api/backend/api/bookmarks/calendar.ics";
