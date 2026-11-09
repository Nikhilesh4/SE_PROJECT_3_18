"use client";

/**
 * Compass Agent client — streaming chat + conversation history.
 *
 * Chat uses fetch + a stream reader because the response is Server-Sent
 * Events (axios cannot stream in the browser). History calls use the shared
 * axios instance like the other hooks.
 */

import api, { API_BASE_URL } from "@/lib/api";
import { getToken } from "@/lib/authSession";

export interface ResultPreview {
    id?: number;
    title?: string;
    url?: string;
    category?: string;
}

export type AgentEvent =
    | { type: "conversation"; id: number; title: string }
    | { type: "text"; delta: string }
    | { type: "tool_call"; id: string; name: string; arguments: Record<string, unknown> | null }
    | { type: "tool_result"; id: string; name: string; ok: boolean; preview: ResultPreview[] | string }
    | { type: "notice" | "error"; message: string }
    | { type: "done"; stop: string };

export interface ToolActivity {
    id: string;
    name: string;
    arguments: Record<string, unknown> | null;
    status: "running" | "ok" | "error";
    preview?: ResultPreview[] | string;
}

export interface ChatMessage {
    role: "user" | "assistant";
    text: string;
    tools: ToolActivity[];
    notice?: string;
}

export interface ConversationSummary {
    id: number;
    title: string;
    provider: string;
    updated_at: string;
}

export const TOOL_LABELS: Record<string, string> = {
    search_opportunities: "Searching opportunities",
    get_opportunity: "Reading the posting",
    upcoming_deadlines: "Checking deadlines",
    list_bookmarks: "Looking at your bookmarks",
    bookmark_opportunity: "Saving a bookmark",
    remove_bookmark: "Removing a bookmark",
    get_profile: "Reading your profile",
    update_profile: "Updating your profile",
    search_posting_text: "Searching posting text",
    find_in_posting: "Reading the posting",
    compare_opportunities: "Comparing postings",
    match_resume_to_opportunity: "Matching your resume",
};

export class ChatHttpError extends Error {
    constructor(public status: number, message: string) {
        super(message);
    }
}

/** POST /agent/chat and invoke `onEvent` for each SSE event until the stream ends. */
export async function streamChat(
    message: string,
    conversationId: number | null,
    onEvent: (event: AgentEvent) => void,
    signal?: AbortSignal
): Promise<void> {
    const res = await fetch(`${API_BASE_URL}/agent/chat`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${getToken() ?? ""}`,
        },
        body: JSON.stringify(
            conversationId == null ? { message } : { message, conversation_id: conversationId }
        ),
        signal,
    });
    if (!res.ok || !res.body) {
        const body = await res.json().catch(() => ({}));
        throw new ChatHttpError(res.status, body.detail ?? `Request failed (${res.status})`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let boundary;
        while ((boundary = buffer.indexOf("\n\n")) !== -1) {
            const chunk = buffer.slice(0, boundary);
            buffer = buffer.slice(boundary + 2);
            if (chunk.startsWith("data: ")) onEvent(JSON.parse(chunk.slice(6)) as AgentEvent);
        }
    }
}

export async function listConversations(): Promise<ConversationSummary[]> {
    return (await api.get<ConversationSummary[]>("/agent/conversations")).data;
}

interface StoredMessage {
    role: "user" | "assistant";
    text: string;
    tool_calls: { name: string; arguments: Record<string, unknown> | null }[];
}

export async function loadConversation(id: number): Promise<ChatMessage[]> {
    const { data } = await api.get<{ messages: StoredMessage[] }>(`/agent/conversations/${id}`);
    return data.messages.map((m) => ({
        role: m.role,
        text: m.text,
        tools: m.tool_calls.map((t, i) => ({
            id: `${id}-${i}`,
            name: t.name,
            arguments: t.arguments,
            status: "ok" as const,
        })),
    }));
}

export async function deleteConversation(id: number): Promise<void> {
    await api.delete(`/agent/conversations/${id}`);
}
