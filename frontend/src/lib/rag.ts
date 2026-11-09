"use client";

/**
 * Posting Q&A — grounded answers about one opportunity, citing the
 * passages of the posting they come from.
 */

import axios from "axios";
import api from "@/lib/api";

export interface RagPassage {
    n: number;
    item_id: number;
    chunk_index: number;
    text: string;
    match: "keyword" | "semantic" | "both" | "context" | "metadata";
}

export interface PostingAnswer {
    answer: string;
    not_found: boolean;
    citations: number[];
    passages: RagPassage[];
}

export async function askPosting(itemId: number, question: string): Promise<PostingAnswer> {
    try {
        const { data } = await api.post<PostingAnswer>(`/api/rag/items/${itemId}/ask`, { question });
        return data;
    } catch (err) {
        if (axios.isAxiosError(err)) {
            const detail = err.response?.data?.detail;
            throw new Error(
                typeof detail === "string" ? detail : "Could not get an answer. Please try again."
            );
        }
        throw err;
    }
}
