"""Evaluate RAG quality on a labelled question set.

    python -m eval.rag_eval eval/rag_eval_set.example.jsonl            # retrieval metrics (no LLM needed)
    python -m eval.rag_eval my_set.jsonl --faithfulness                # + LLM-judged answer faithfulness (needs a key)

Each JSONL line:
    {"question": "What is the stipend?", "item_id": 42, "expected": ["30,000", "per month"]}
`expected` lists strings (any one is enough) that a correct supporting passage must contain;
omit `item_id` to evaluate cross-posting search (then `expected_item_id` is the posting that should rank).
Use `"expect_not_stated": true` for questions the posting does NOT answer.

Metrics: hit@k, MRR, and context precision (share of the retrieved passages that contain an expected string).
Faithfulness asks the configured model whether each generated answer is fully supported by its cited
passages, scored 0/1 and averaged. It needs AGENT_PROVIDER credentials; without one it is skipped.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from app.services.rag import retrieval


@dataclass
class Case:
    question: str
    item_id: int | None = None
    expected: list[str] = field(default_factory=list)
    expected_item_id: int | None = None
    expect_not_stated: bool = False


@dataclass
class Report:
    n: int
    hit_at_k: float
    mrr: float
    context_precision: float
    faithfulness: float | None = None
    not_stated_accuracy: float | None = None
    failures: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in self.__dict__.items()}


def load_cases(path: Path) -> list[Case]:
    return [Case(**json.loads(line)) for line in path.read_text().splitlines() if line.strip() and not line.startswith("#")]


def _contains(text: str, expected: list[str]) -> bool:
    low = text.lower()
    return any(e.lower() in low for e in expected)


def score_case(case: Case, passages: list[dict]) -> tuple[bool, float, float]:
    """(hit, reciprocal_rank, context_precision) for one case."""
    if case.item_id is None and case.expected_item_id is not None:
        rank = next((i for i, p in enumerate(passages, 1) if p["item_id"] == case.expected_item_id), None)
        return rank is not None, (1 / rank if rank else 0.0), 0.0
    flags = [_contains(p["text"], case.expected) for p in passages]
    rank = next((i for i, ok in enumerate(flags, 1) if ok), None)
    precision = sum(flags) / len(flags) if flags else 0.0
    return rank is not None, (1 / rank if rank else 0.0), precision


def evaluate(cases: list[Case], retrieve: Callable[[Case], list[dict]], *, k: int = 4) -> Report:
    hits = rr = prec = 0.0
    scored = 0
    failures: list[str] = []
    for case in cases:
        if case.expect_not_stated:
            continue
        passages = retrieve(case)[:k]
        hit, r, p = score_case(case, passages)
        scored += 1
        hits += hit
        rr += r
        prec += p
        if not hit:
            failures.append(case.question)
    n = max(scored, 1)
    return Report(len(cases), hits / n, rr / n, prec / n, failures=failures)


def db_retriever(case: Case) -> list[dict]:
    if case.item_id is not None:
        found = retrieval.posting_passages(case.item_id, case.question, limit=8) or []
    else:
        found = retrieval.search_passages(case.question, limit=8)
    return [p.as_dict() for p in found]


async def judge_faithfulness(cases: list[Case]) -> tuple[float | None, float | None]:
    """(faithfulness, not_stated_accuracy) using the configured provider; (None, None) when unavailable."""
    from app.services.agent.providers import ProviderError, get_provider
    from app.services.rag.answer import answer_question
    try:
        provider = get_provider()
    except ProviderError:
        return None, None
    judged = supported = ns_total = ns_ok = 0
    for case in cases:
        if case.item_id is None:
            continue
        try:
            ans = await answer_question(provider, case.item_id, case.question)
        except ProviderError as exc:
            print(f"LLM unavailable ({exc}); skipping faithfulness", file=sys.stderr)
            return None, None
        if ans is None:
            continue
        if case.expect_not_stated:
            ns_total += 1
            ns_ok += ans.not_found
            continue
        if ans.not_found:
            continue
        judged += 1
        cited = " ".join(p["text"] for p in ans.passages if p["n"] in ans.citations)
        supported += bool(ans.citations) and (_contains(cited, case.expected) if case.expected else True)
    return (supported / judged if judged else None), (ns_ok / ns_total if ns_total else None)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dataset", type=Path)
    ap.add_argument("-k", type=int, default=4)
    ap.add_argument("--faithfulness", action="store_true")
    args = ap.parse_args()
    cases = load_cases(args.dataset)
    report = evaluate(cases, db_retriever, k=args.k)
    if args.faithfulness:
        report.faithfulness, report.not_stated_accuracy = asyncio.run(judge_faithfulness(cases))
    print(json.dumps(report.as_dict(), indent=2))


if __name__ == "__main__":
    main()
