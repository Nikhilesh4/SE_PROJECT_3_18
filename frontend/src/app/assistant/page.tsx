"use client";

import { FormEvent, KeyboardEvent, useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/useAuth";
import {
    AgentEvent,
    ChatHttpError,
    ChatMessage,
    ConversationSummary,
    deleteConversation,
    listConversations,
    loadConversation,
    streamChat,
} from "@/lib/agent";
import MessageView from "./MessageView";

const STARTERS = [
    "What internships fit my profile best right now?",
    "Find research positions in computer vision",
    "Which of my bookmarks have deadlines in the next two weeks?",
    "Suggest hackathons I could join this month",
];

function applyEvent(message: ChatMessage, event: AgentEvent): ChatMessage {
    switch (event.type) {
        case "text":
            return { ...message, text: message.text + event.delta };
        case "tool_call":
            return {
                ...message,
                tools: [...message.tools, { id: event.id, name: event.name, arguments: event.arguments, status: "running" }],
            };
        case "tool_result":
            return {
                ...message,
                tools: message.tools.map((t) =>
                    t.id === event.id ? { ...t, status: event.ok ? "ok" : "error", preview: event.preview } : t
                ),
            };
        case "notice":
        case "error":
            return { ...message, notice: event.message };
        default:
            return message;
    }
}

export default function AssistantPage() {
    const { isAuthenticated, checking } = useAuth();
    const [conversations, setConversations] = useState<ConversationSummary[]>([]);
    const [activeId, setActiveId] = useState<number | null>(null);
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [input, setInput] = useState("");
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState("");
    const abortRef = useRef<AbortController | null>(null);
    const bottomRef = useRef<HTMLDivElement | null>(null);

    const refreshList = useCallback(async () => {
        try {
            setConversations(await listConversations());
        } catch {
            /* the list is a convenience; chat still works */
        }
    }, []);

    useEffect(() => {
        if (!checking && isAuthenticated) refreshList();
    }, [checking, isAuthenticated, refreshList]);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }, [messages]);

    useEffect(() => () => abortRef.current?.abort(), []);

    const openConversation = async (id: number) => {
        if (busy) return;
        setError("");
        setActiveId(id);
        try {
            setMessages(await loadConversation(id));
        } catch {
            setError("Couldn't load that chat.");
        }
    };

    const newChat = () => {
        if (busy) return;
        setActiveId(null);
        setMessages([]);
        setError("");
    };

    const removeConversation = async (id: number) => {
        if (busy || !window.confirm("Delete this chat?")) return;
        await deleteConversation(id).catch(() => undefined);
        if (id === activeId) newChat();
        refreshList();
    };

    const send = async (text: string) => {
        const message = text.trim();
        if (!message || busy) return;
        setInput("");
        setError("");
        setBusy(true);
        setMessages((prev) => [
            ...prev,
            { role: "user", text: message, tools: [] },
            { role: "assistant", text: "", tools: [] },
        ]);

        const controller = new AbortController();
        abortRef.current = controller;
        const updateLast = (fn: (m: ChatMessage) => ChatMessage) =>
            setMessages((prev) => [...prev.slice(0, -1), fn(prev[prev.length - 1])]);

        try {
            await streamChat(
                message,
                activeId,
                (event) => {
                    if (event.type === "conversation") setActiveId(event.id);
                    else updateLast((m) => applyEvent(m, event));
                },
                controller.signal
            );
        } catch (err) {
            if (!controller.signal.aborted) {
                const msg = err instanceof ChatHttpError ? err.message : "Connection lost. Please try again.";
                updateLast((m) => ({ ...m, notice: msg }));
            }
        } finally {
            setBusy(false);
            abortRef.current = null;
            refreshList();
        }
    };

    const onSubmit = (e: FormEvent) => {
        e.preventDefault();
        send(input);
    };

    const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            send(input);
        }
    };

    if (checking || !isAuthenticated) {
        return (
            <div className="min-h-screen bg-slate-50 flex items-center justify-center">
                <div className="w-10 h-10 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-50 pt-16">
            <div className="mx-auto flex h-[calc(100vh-4rem)] max-w-7xl gap-4 px-4 py-4 sm:px-6">
                {/* Conversation list */}
                <aside className="hidden w-64 shrink-0 flex-col rounded-2xl border border-slate-200 bg-white p-3 md:flex">
                    <button
                        onClick={newChat}
                        disabled={busy}
                        className="mb-3 rounded-xl bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
                    >
                        + New chat
                    </button>
                    <p className="px-2 pb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">Recent</p>
                    <ul className="flex-1 space-y-0.5 overflow-y-auto">
                        {conversations.length === 0 && <li className="px-2 py-1 text-sm text-slate-400">No chats yet</li>}
                        {conversations.map((c) => (
                            <li key={c.id} className="group flex items-center">
                                <button
                                    onClick={() => openConversation(c.id)}
                                    className={`flex-1 truncate rounded-lg px-2 py-1.5 text-left text-sm ${
                                        c.id === activeId ? "bg-indigo-50 font-medium text-indigo-700" : "text-slate-700 hover:bg-slate-100"
                                    }`}
                                    title={c.title}
                                >
                                    {c.title}
                                </button>
                                <button
                                    onClick={() => removeConversation(c.id)}
                                    aria-label={`Delete chat ${c.title}`}
                                    className="ml-1 hidden rounded px-1.5 text-slate-400 hover:text-red-600 group-hover:block"
                                >
                                    ×
                                </button>
                            </li>
                        ))}
                    </ul>
                </aside>

                {/* Chat */}
                <main className="flex min-w-0 flex-1 flex-col rounded-2xl border border-slate-200 bg-white">
                    <header className="flex items-center justify-between border-b border-slate-200 px-5 py-3">
                        <div>
                            <h1 className="text-lg font-semibold text-slate-900">Compass Assistant</h1>
                            <p className="text-xs text-slate-500">
                                Searches your feed, bookmarks and deadlines. It can save bookmarks and edit your skills when you ask.
                            </p>
                        </div>
                        <button onClick={newChat} disabled={busy} className="text-sm text-indigo-600 hover:text-indigo-500 md:hidden">
                            New chat
                        </button>
                    </header>

                    <div className="flex-1 space-y-5 overflow-y-auto px-5 py-5">
                        {messages.length === 0 ? (
                            <div className="mx-auto mt-10 max-w-xl text-center">
                                <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-600 text-xl font-bold text-white">
                                    C
                                </div>
                                <h2 className="text-xl font-semibold text-slate-900">How can I help with your search?</h2>
                                <p className="mt-1 text-sm text-slate-500">
                                    I rank opportunities against your profile, check deadlines and manage bookmarks.
                                </p>
                                <div className="mt-6 grid gap-2 sm:grid-cols-2">
                                    {STARTERS.map((s) => (
                                        <button
                                            key={s}
                                            onClick={() => send(s)}
                                            className="rounded-xl border border-slate-200 px-3 py-2.5 text-left text-sm text-slate-700 hover:border-indigo-300 hover:bg-indigo-50"
                                        >
                                            {s}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        ) : (
                            messages.map((m, i) => (
                                <MessageView key={i} message={m} streaming={busy && i === messages.length - 1} />
                            ))
                        )}
                        <div ref={bottomRef} />
                    </div>

                    {error && <p className="px-5 pb-2 text-sm text-red-600">{error}</p>}

                    <form onSubmit={onSubmit} className="flex items-end gap-2 border-t border-slate-200 p-3">
                        <textarea
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={onKeyDown}
                            rows={1}
                            maxLength={4000}
                            placeholder="Ask about internships, deadlines, your bookmarks…"
                            aria-label="Message the assistant"
                            className="max-h-40 min-h-[44px] flex-1 resize-none rounded-xl border border-slate-300 px-3 py-2.5 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none"
                        />
                        {busy ? (
                            <button
                                type="button"
                                onClick={() => abortRef.current?.abort()}
                                className="h-[44px] rounded-xl border border-slate-300 px-4 text-sm font-semibold text-slate-700 hover:bg-slate-100"
                            >
                                Stop
                            </button>
                        ) : (
                            <button
                                type="submit"
                                disabled={!input.trim()}
                                className="h-[44px] rounded-xl bg-indigo-600 px-4 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
                            >
                                Send
                            </button>
                        )}
                    </form>
                </main>
            </div>
        </div>
    );
}
