"use client";

import { Fragment, ReactNode } from "react";
import { ChatMessage, TOOL_LABELS, ToolActivity } from "@/lib/agent";

/**
 * Minimal Markdown → React (no innerHTML): paragraphs, "-"/"1." lists,
 * ### headings, **bold**, `code`, [links](https://…) and bare URLs.
 * Model output is untrusted, so only http(s) links are rendered as links.
 */
const INLINE = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\(https?:\/\/[^\s)]+\)|https?:\/\/[^\s)]+)/g;

function inline(text: string): ReactNode[] {
    return text.split(INLINE).map((part, i) => {
        if (!part) return null;
        if (part.startsWith("**") && part.endsWith("**")) return <strong key={i}>{part.slice(2, -2)}</strong>;
        if (part.startsWith("`") && part.endsWith("`"))
            return <code key={i} className="rounded bg-slate-100 px-1 py-0.5 text-[0.85em]">{part.slice(1, -1)}</code>;
        const md = part.match(/^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/);
        const href = md ? md[2] : /^https?:\/\//.test(part) ? part : null;
        if (href)
            return (
                <a key={i} href={href} target="_blank" rel="noopener noreferrer"
                   className="text-indigo-600 underline decoration-indigo-300 underline-offset-2 hover:text-indigo-500 break-words">
                    {md ? md[1] : part}
                </a>
            );
        return <Fragment key={i}>{part}</Fragment>;
    });
}

function Markdown({ text }: { text: string }) {
    const blocks: ReactNode[] = [];
    let list: { ordered: boolean; items: string[] } | null = null;
    const flush = () => {
        if (!list) return;
        const items = list.items.map((it, i) => <li key={i}>{inline(it)}</li>);
        blocks.push(list.ordered
            ? <ol key={blocks.length} className="list-decimal pl-5 space-y-1">{items}</ol>
            : <ul key={blocks.length} className="list-disc pl-5 space-y-1">{items}</ul>);
        list = null;
    };
    for (const raw of text.split("\n")) {
        const line = raw.trimEnd();
        const bullet = line.match(/^\s*[-*]\s+(.*)$/);
        const numbered = line.match(/^\s*\d+[.)]\s+(.*)$/);
        if (bullet || numbered) {
            const ordered = Boolean(numbered);
            if (list && list.ordered !== ordered) flush();
            list ??= { ordered, items: [] };
            list.items.push((bullet ?? numbered)![1]);
            continue;
        }
        flush();
        if (!line.trim()) continue;
        const heading = line.match(/^#{1,4}\s+(.*)$/);
        blocks.push(heading
            ? <p key={blocks.length} className="font-semibold text-slate-900">{inline(heading[1])}</p>
            : <p key={blocks.length}>{inline(line)}</p>);
    }
    flush();
    return <div className="space-y-2 leading-relaxed">{blocks}</div>;
}

function describeArgs(tool: ToolActivity): string {
    const a = tool.arguments ?? {};
    if (typeof a.query === "string") return `“${a.query}”`;
    if (typeof a.category === "string") return a.category;
    if (typeof a.days === "number") return `next ${a.days} days`;
    return "";
}

function ToolChip({ tool }: { tool: ToolActivity }) {
    const label = TOOL_LABELS[tool.name] ?? tool.name;
    const results = Array.isArray(tool.preview) ? tool.preview : [];
    return (
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
            <div className="flex items-center gap-2">
                {tool.status === "running" ? (
                    <span className="h-3 w-3 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin" />
                ) : (
                    <span className={tool.status === "ok" ? "text-emerald-600" : "text-amber-600"}>
                        {tool.status === "ok" ? "✓" : "!"}
                    </span>
                )}
                <span className="font-medium text-slate-700">{label}</span>
                <span className="truncate">{describeArgs(tool)}</span>
                {results.length > 0 && <span className="ml-auto shrink-0">{results.length} found</span>}
            </div>
            {tool.status === "error" && typeof tool.preview === "string" && (
                <p className="mt-1 text-amber-700">{tool.preview}</p>
            )}
            {results.length > 0 && (
                <ul className="mt-1.5 space-y-0.5 pl-5">
                    {results.map((r, i) => (
                        <li key={r.id ?? i} className="truncate">
                            {r.url ? (
                                <a href={r.url} target="_blank" rel="noopener noreferrer" className="hover:text-indigo-600">
                                    {r.title}
                                </a>
                            ) : r.title}
                            {r.category && <span className="text-slate-400"> · {r.category}</span>}
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
}

export default function MessageView({ message, streaming }: { message: ChatMessage; streaming?: boolean }) {
    if (message.role === "user") {
        return (
            <div className="flex justify-end">
                <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-indigo-600 px-4 py-2.5 text-sm text-white shadow-sm">
                    {message.text}
                </div>
            </div>
        );
    }
    return (
        <div className="flex gap-3">
            <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-indigo-600 text-xs font-bold text-white">
                C
            </div>
            <div className="min-w-0 flex-1 space-y-2 text-sm text-slate-800">
                {message.tools.map((t) => <ToolChip key={t.id} tool={t} />)}
                {message.text && <Markdown text={message.text} />}
                {streaming && !message.text && message.tools.every((t) => t.status !== "running") && (
                    <p className="text-slate-400 animate-pulse">Thinking…</p>
                )}
                {message.notice && (
                    <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                        {message.notice}
                    </p>
                )}
            </div>
        </div>
    );
}
