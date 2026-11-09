const ENTITIES: Record<string, string> = {
    amp: "&",
    lt: "<",
    gt: ">",
    quot: '"',
    apos: "'",
    nbsp: " ",
};

/** Strip HTML tags and decode entities (named and numeric) into plain text. */
export function plainText(html: string | null | undefined): string {
    return (html ?? "")
        .replace(/<[^>]+>/g, " ")
        .replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (m, e: string) => {
            if (e[0] === "#") {
                const code = e[1].toLowerCase() === "x" ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10);
                return Number.isFinite(code) && code > 0 && code <= 0x10ffff ? String.fromCodePoint(code) : m;
            }
            return ENTITIES[e.toLowerCase()] ?? m;
        })
        .replace(/\s+/g, " ")
        .trim();
}

/**
 * Posting text comes from third parties (RSS feeds, job boards, scraped pages),
 * so it is never rendered as HTML. This turns whatever arrives (markup, entities
 * like &#160; or &amp;, or text that merely looks like a tag) into plain text.
 *
 * DOMParser builds an inert document: scripts do not run and nothing is loaded.
 * The result is only ever placed in the page as a text node.
 */
export function htmlToPlainText(raw: string | null | undefined): string {
    if (!raw) return "";
    const withBreaks = raw
        .replace(/<\s*br\s*\/?>/gi, "\n")
        .replace(/<\/\s*(p|div|li|h[1-6]|tr)\s*>/gi, "\n")
        .replace(/<\s*li[^>]*>/gi, "• ");
    let text: string;
    if (typeof DOMParser !== "undefined") {
        // Parse twice: feeds that double-escape (&amp;lt;p&amp;gt;) decode to markup on the first pass.
        const once = new DOMParser().parseFromString(withBreaks, "text/html").body.textContent ?? "";
        text = new DOMParser().parseFromString(once, "text/html").body.textContent ?? "";
    } else {
        text = withBreaks.replace(/<[^>]*>/g, " ");
    }
    return text
        .replace(/ /g, " ")
        .replace(/[ \t]+\n/g, "\n")
        .replace(/\n{3,}/g, "\n\n")
        .trim();
}
