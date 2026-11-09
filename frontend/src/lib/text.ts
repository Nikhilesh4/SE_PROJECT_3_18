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
