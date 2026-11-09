from eval.rag_eval import Case, evaluate, load_cases, score_case
from tests.conftest import make_item


def test_metrics_on_known_rankings():
    passages = [{"item_id": 1, "text": "Apply by Friday"}, {"item_id": 1, "text": "Stipend is 30,000 per month"}, {"item_id": 1, "text": "Stipend: 30,000"}]
    case = Case("stipend?", item_id=1, expected=["30,000"])
    hit, rr, precision = score_case(case, passages)
    assert hit and rr == 0.5 and round(precision, 2) == 0.67
    assert score_case(Case("x", item_id=1, expected=["nothing"]), passages) == (False, 0.0, 0.0)
    assert score_case(Case("find", expected_item_id=2), [{"item_id": 1, "text": ""}, {"item_id": 2, "text": ""}]) == (True, 0.5, 0.0)


def test_evaluate_aggregates_and_skips_not_stated():
    cases = [Case("a", item_id=1, expected=["yes"]), Case("b", item_id=1, expected=["zzz"]), Case("c", item_id=1, expect_not_stated=True)]
    report = evaluate(cases, lambda c: [{"item_id": 1, "text": "yes indeed"}])
    assert report.n == 3 and report.hit_at_k == 0.5 and report.failures == ["b"]


def test_example_dataset_parses(tmp_path):
    from pathlib import Path
    cases = load_cases(Path(__file__).parent.parent / "eval" / "rag_eval_set.example.jsonl")
    assert len(cases) == 5 and cases[3].expect_not_stated


def test_db_retriever_on_real_index(db, seed_items):
    """End to end: the labelled question finds its passage in the real retrieval stack."""
    from app.services.matching.semantic import embed_pending_items
    from eval.rag_eval import db_retriever
    (item,) = seed_items(make_item(summary="This is a paid internship. The stipend is 30,000 INR per month. Remote work is allowed."))
    embed_pending_items()
    report = evaluate([Case("What is the stipend?", item_id=item.id, expected=["30,000"])], db_retriever)
    assert report.hit_at_k == 1.0 and report.mrr > 0
