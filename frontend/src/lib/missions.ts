"use client";

/** Missions: saved natural-language searches that report only new matches. */

import api from "@/lib/api";

export interface Mission {
    id: number;
    name: string;
    query: string;
    category: string | null;
    remote_only: boolean;
    min_stipend: number | null;
    deadline_after: string | null;
    active: boolean;
    last_run_at: string | null;
    created_at: string | null;
}

export interface MissionMatch {
    id: number;
    title: string;
    url: string;
    category: string;
    source_name: string;
    score: number;
    found_at?: string;
}

export async function listMissions(): Promise<Mission[]> {
    return (await api.get<{ missions: Mission[] }>("/api/missions")).data.missions;
}

export async function createMission(name: string, query: string): Promise<Mission> {
    return (await api.post<Mission>("/api/missions", { name, query })).data;
}

export async function patchMission(id: number, patch: { active?: boolean; name?: string }): Promise<Mission> {
    return (await api.patch<Mission>(`/api/missions/${id}`, patch)).data;
}

export async function deleteMission(id: number): Promise<void> {
    await api.delete(`/api/missions/${id}`);
}

export async function runMission(id: number): Promise<MissionMatch[]> {
    return (await api.post<{ new_matches: MissionMatch[] }>(`/api/missions/${id}/run`)).data.new_matches;
}

export async function missionMatches(id: number): Promise<MissionMatch[]> {
    return (await api.get<{ matches: MissionMatch[] }>(`/api/missions/${id}/matches`)).data.matches;
}
