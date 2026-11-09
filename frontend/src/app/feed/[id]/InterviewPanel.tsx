"use client";

import { useState } from "react";
import { errorMessage } from "@/lib/errors";
import { interviewFeedback, interviewQuestions, type InterviewFeedback, type InterviewQuestion } from "@/lib/insights";

const CHECK_LABEL: Record<string, string> = {
    gives_example: "Uses a concrete example",
    states_result: "States the outcome",
    right_length: "Good length",
};

export default function InterviewPanel({ itemId }: { itemId: number }) {
    const [questions, setQuestions] = useState<InterviewQuestion[] | null>(null);
    const [active, setActive] = useState(0);
    const [answer, setAnswer] = useState("");
    const [feedback, setFeedback] = useState<InterviewFeedback | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const start = async () => {
        setLoading(true);
        setError(null);
        try {
            const r = await interviewQuestions(itemId);
            setQuestions(r.questions);
            setActive(0);
            setAnswer("");
            setFeedback(null);
        } catch (err) {
            setError(errorMessage(err, "Could not load practice questions."));
        } finally {
            setLoading(false);
        }
    };

    const submit = async () => {
        if (!questions || !answer.trim()) return;
        setLoading(true);
        setError(null);
        try {
            setFeedback(await interviewFeedback(questions[active].question, answer.trim()));
        } catch (err) {
            setError(errorMessage(err, "Could not get feedback."));
        } finally {
            setLoading(false);
        }
    };

    const go = (index: number) => {
        setActive(index);
        setAnswer("");
        setFeedback(null);
    };

    return (
        <section aria-labelledby="interview-h" className="px-6 sm:px-8 pb-6">
            <div className="flex items-center justify-between gap-3 mb-3">
                <h2 id="interview-h" className="text-lg font-semibold text-slate-900">🎤 Practice interview</h2>
                {!questions && (
                    <button onClick={start} disabled={loading} className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-500 disabled:opacity-60 cursor-pointer">
                        {loading ? "Loading…" : "Start"}
                    </button>
                )}
            </div>
            {error && <p role="alert" className="text-sm text-red-600">{error}</p>}

            {questions && (
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-3">
                    <div className="flex items-center justify-between text-xs text-slate-500">
                        <span>Question {active + 1} of {questions.length} · {questions[active].topic}</span>
                        <div className="flex gap-1.5">
                            <button disabled={active === 0} onClick={() => go(active - 1)} className="px-2 py-1 rounded border border-slate-300 bg-white disabled:opacity-40 cursor-pointer">←</button>
                            <button disabled={active + 1 >= questions.length} onClick={() => go(active + 1)} className="px-2 py-1 rounded border border-slate-300 bg-white disabled:opacity-40 cursor-pointer">→</button>
                        </div>
                    </div>
                    <p className="text-sm font-medium text-slate-900">{questions[active].question}</p>
                    <textarea
                        value={answer}
                        onChange={(e) => setAnswer(e.target.value)}
                        rows={5}
                        maxLength={4000}
                        aria-label="Your answer"
                        placeholder="Type your answer as you would say it. Aim for 40–250 words."
                        className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
                    />
                    <button onClick={submit} disabled={loading || !answer.trim()} className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-500 disabled:opacity-50 cursor-pointer">
                        {loading ? "Checking…" : "Get feedback"}
                    </button>

                    {feedback && (
                        <div className="rounded-lg bg-white border border-slate-200 p-3 space-y-2 text-sm">
                            <ul className="flex flex-wrap gap-2">
                                {Object.entries(feedback.checks).map(([k, ok]) => (
                                    <li key={k} className={`px-2 py-0.5 rounded-md text-xs font-medium ${ok ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-800"}`}>
                                        {ok ? "✓" : "✗"} {CHECK_LABEL[k] ?? k}
                                    </li>
                                ))}
                                <li className="px-2 py-0.5 rounded-md text-xs bg-slate-100 text-slate-600">{feedback.words} words</li>
                            </ul>
                            <ul className="list-disc list-inside text-slate-700 space-y-0.5">
                                {feedback.tips.map((t) => <li key={t}>{t}</li>)}
                            </ul>
                            {feedback.critique && <p className="text-slate-700 border-t border-slate-100 pt-2">{feedback.critique}</p>}
                        </div>
                    )}
                </div>
            )}
        </section>
    );
}
