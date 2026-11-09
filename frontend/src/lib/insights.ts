"use client";

/** Search, per-posting insights, trends, coaching and research helpers. */

import api from "@/lib/api";
import type { NormalizedRssItem } from "@/lib/useFeed";

// ── Search ──────────────────────────────────────────────────────────────────
export interface SearchParams {
    q?: string;
    category?: string;
    source?: string;
    remote?: boolean;
    min_stipend?: number;
    closing_within_days?: number;
    limit?: number;
    offset?: number;
}

export interface SearchResponse {
    total: number;
    facets: { categories: Record<string, number>; sources: Record<string, number>; remote: number };
    items: NormalizedRssItem[];
}

export async function searchOpportunities(params: SearchParams): Promise<SearchResponse> {
    const clean = Object.fromEntries(
        Object.entries(params).filter(([, v]) => v !== undefined && v !== "" && v !== false)
    );
    return (await api.get<SearchResponse>("/api/search", { params: clean })).data;
}

// ── Per-posting insights ────────────────────────────────────────────────────
export interface ItemInsights {
    item_id: number;
    has_profile: boolean;
    ranking: {
        reasons: string[];
        matched_in_title: string[];
        matched_in_description: string[];
        semantic_similarity: number | null;
    };
    skill_gap: { required: string[]; matched: string[]; missing: string[]; coverage: number | null };
    stipend: { amount: number; currency: string; period: string; raw: string } | null;
    remote: boolean;
    scam: { score: number; risky: boolean; reasons: string[] };
    eligibility: { years: number[]; min_cgpa: number | null; branches: string[]; notes: string[] };
    provenance: { discovered_by: string; confidence: number | null; verified_at: string | null; flags: string[] };
}

export async function fetchItemInsights(itemId: number): Promise<ItemInsights> {
    return (await api.get<ItemInsights>(`/api/insights/items/${itemId}`)).data;
}

export async function fetchProjects(itemId: number): Promise<{ missing: string[]; projects: { skill: string; idea: string }[] }> {
    return (await api.get("/api/insights/projects", { params: { item_id: itemId } })).data;
}

// ── Trends / companies ──────────────────────────────────────────────────────
export interface Trends {
    days: number;
    postings: number;
    by_category: Record<string, number>;
    top_skills: { skill: string; postings: number }[];
    stipend_inr_month: Record<string, PaySummary | null>;
}

/** Pay statistics in ₹ per month. */
export interface PaySummary {
    count: number;
    p25: number;
    median: number;
    p75: number;
    min: number;
    max: number;
}

export interface PayInsights {
    days: number;
    unit: string;
    postings: number;
    with_pay: number;
    coverage: number;
    overall: PaySummary | null;
    by_category: Record<string, PaySummary | null>;
    by_skill: (PaySummary & { skill: string })[];
    remote: Record<string, PaySummary | null>;
    left_out: { not_pay_category: number; out_of_range: number };
}

export async function fetchPayInsights(category?: string): Promise<PayInsights> {
    return (await api.get<PayInsights>("/api/insights/stipends", { params: category ? { category } : {} })).data;
}

export async function fetchTrends(): Promise<Trends> {
    return (await api.get<Trends>("/api/insights/trends")).data;
}

export interface CompanyMatch {
    company: string;
    postings: number;
    best_match: number;
}

export async function fetchCompanies(): Promise<CompanyMatch[]> {
    return (await api.get<{ companies: CompanyMatch[] }>("/api/insights/companies")).data.companies;
}

// ── Feedback ────────────────────────────────────────────────────────────────
export type FeedbackValue = "up" | "down" | "hide";

export async function fetchFeedback(): Promise<Record<string, FeedbackValue>> {
    return (await api.get<{ feedback: Record<string, FeedbackValue> }>("/api/feedback")).data.feedback;
}

export async function setFeedback(itemId: number, value: FeedbackValue): Promise<void> {
    await api.post(`/api/feedback/${itemId}`, { value });
}

export async function clearFeedback(itemId: number): Promise<void> {
    await api.delete(`/api/feedback/${itemId}`);
}

// ── Coaching ────────────────────────────────────────────────────────────────
export type OutreachKind = "cold_email" | "linkedin_note" | "referral_request" | "follow_up";

export interface OutreachDraft {
    kind: OutreachKind;
    subject: string;
    body: string;
    generated_by: string;
    review_note: string;
}

export async function draftOutreach(body: {
    kind: OutreachKind;
    item_id?: number;
    recipient?: string;
    note?: string;
}): Promise<OutreachDraft> {
    return (await api.post<OutreachDraft>("/api/outreach/draft", body)).data;
}

export interface InterviewQuestion {
    question: string;
    topic: string;
}

export async function interviewQuestions(itemId: number, count = 6): Promise<{ questions: InterviewQuestion[]; generated_by: string }> {
    return (await api.post("/api/interview/questions", { item_id: itemId, count })).data;
}

export interface InterviewFeedback {
    checks: Record<string, boolean>;
    tips: string[];
    critique?: string;
    words: number;
}

export async function interviewFeedback(question: string, answer: string): Promise<InterviewFeedback> {
    return (await api.post<InterviewFeedback>("/api/interview/feedback", { question, answer })).data;
}

// ── Research scout ──────────────────────────────────────────────────────────
export interface ScoutPaper {
    title: string;
    url: string;
    year: number | null;
    authors: string[];
    abstract: string;
    source: string;
}

export interface ScoutContact {
    name: string;
    papers: string[];
    affiliations: string[];
    homepage: string | null;
}

export interface ScoutResult {
    topic: string;
    papers: ScoutPaper[];
    contacts: ScoutContact[];
    errors: string[];
    draft?: { subject: string; body: string; review_note?: string };
}

export async function scoutResearch(topic: string, draftFor?: string): Promise<ScoutResult> {
    return (await api.post<ScoutResult>("/api/research/scout", { topic, draft_for: draftFor })).data;
}
