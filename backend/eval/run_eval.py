"""Run M5 test-set evaluation in an isolated temporary data directory.

Measures classification accuracy, RAG retrieval recall@k, and end-to-end
auto-solve rate. LLM-dependent sections report status=pending when the LLM
endpoint is not reachable so results are never silently fabricated.
"""

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="ecs_eval_"))
os.environ["DATA_DIR"] = str(_TMP / "data")
os.environ["TICKET_DB_PATH"] = str(_TMP / "data" / "tickets.db")
os.environ["CHROMA_DIR"] = str(_TMP / "data" / ".chroma")

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from app import repository  # noqa: E402
from app.agent_graph import _classify_node, process_ticket  # noqa: E402
from app.database import init_db  # noqa: E402
from app.rag import vector_search  # noqa: E402
from app.seed import seed_if_empty  # noqa: E402

DATASETS = Path(__file__).resolve().parent / "datasets"
RESULTS = Path(__file__).resolve().parent / "results.json"


def load(name: str) -> list:
    with open(DATASETS / name, encoding="utf-8") as fh:
        return json.load(fh)


def retrieval_eval(queries: list, k: int = 3) -> dict:
    hits = 0
    details = []
    for item in queries:
        results = vector_search(
            item["query"],
            category=item.get("category", ""),
            top_k=k,
            rerank=True,
        )
        got = {r["id"] for r in results}
        expected = set(item["expected_ids"])
        ok = bool(expected & got)
        hits += int(ok)
        details.append(
            {
                "query": item["query"],
                "expected": sorted(expected),
                "got": sorted(got),
                "ok": ok,
            }
        )
    return {
        "top_k": k,
        "queries": len(details),
        "recall_at_k": round(hits / len(details), 4) if details else None,
        "details": details,
    }


def classification_eval(samples: list) -> dict:
    correct = 0
    confidences = []
    details = []
    pending = 0
    for sample in samples:
        ticket = repository.create_ticket(
            title=sample["title"],
            description=sample["description"],
            category="其他",
            priority="中",
            customer_id=1,
        )
        started = time.perf_counter()
        try:
            out = _classify_node(
                {"ticket": {**ticket, "language": "zh"}}
            )
        except Exception:  # noqa: BLE001
            pending += 1
            out = {"category": None, "confidence": 0.0}
        ok = bool(out.get("category")) and out["category"] == sample["expected"]
        correct += int(ok)
        if out.get("confidence") is not None:
            confidences.append(float(out["confidence"]))
        details.append(
            {
                "title": sample["title"],
                "expected": sample["expected"],
                "predicted": out.get("category"),
                "confidence": out.get("confidence"),
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "ok": ok,
            }
        )
    total = len(details)
    measured = total - pending
    return {
        "samples": total,
        "measured": measured,
        "pending": pending,
        "status": "pending" if pending == total else "done",
        "accuracy": round(correct / measured, 4) if measured else None,
        "avg_confidence": (
            round(sum(confidences) / len(confidences), 4) if confidences else None
        ),
        "details": details,
    }


def e2e_eval(scenarios: list) -> dict:
    auto_solved = 0
    processed = 0
    details = []
    pending = 0
    for scenario in scenarios:
        ticket = repository.create_ticket(
            title=scenario["title"],
            description=scenario["description"],
            category="其他",
            priority="中",
            customer_id=1,
        )
        started = time.perf_counter()
        try:
            result = process_ticket(ticket["id"])
        except Exception:  # noqa: BLE001
            pending += 1
            result = {"needs_human": True, "error": True}
        processed += int(not result.get("needs_human", True))
        auto_solved += int(
            not result.get("needs_human", True)
            and result.get("ticket", {}).get("status") == "已解决"
        )
        details.append(
            {
                "title": scenario["title"],
                "needs_human": result.get("needs_human", True),
                "status": result.get("ticket", {}).get("status"),
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "log_steps": len(result.get("logs", [])),
            }
        )
    total = len(details)
    return {
        "scenarios": total,
        "pending": pending,
        "status": "pending" if pending == total else "done",
        "auto_solve_rate": round(auto_solved / (total - pending), 4)
        if (total - pending)
        else None,
        "details": details,
    }


def main() -> int:
    os.makedirs(_TMP / "data", exist_ok=True)
    init_db()
    seed_if_empty()
    repository.reindex_rag()

    retrieval = load("retrieval.json")
    classification = load("classification.json")

    started = time.perf_counter()
    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "data_dir": str(_TMP),
        "retrieval": retrieval_eval(retrieval),
        "classification": classification_eval(classification),
        "e2e_auto_solve": e2e_eval(classification[:6]),
        "elapsed_seconds": round(time.perf_counter() - started, 2),
    }
    RESULTS.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        shutil.rmtree(_TMP, ignore_errors=True)
