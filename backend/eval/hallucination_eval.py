"""Hallucination-rate evaluation for grounded customer-service replies.

Runs the same isolated-data setup as run_eval.py. For every retrieval query it
(1) pulls RAG evidence, (2) generates a grounded reply with the LLM, then
(3) has an LLM judge decide whether the reply contains facts not supported by
the evidence. Results are written beside run_eval's results.json and printed.
LLM-dependent sections report status=pending when the endpoint is not reachable
so a value is never silently fabricated.
"""

import json
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="ecs_halluc_"))
os.environ["DATA_DIR"] = str(_TMP / "data")
os.environ["TICKET_DB_PATH"] = str(_TMP / "data" / "tickets.db")
os.environ["CHROMA_DIR"] = str(_TMP / "data" / ".chroma")

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from app.database import init_db  # noqa: E402
from app.llm import chat_text  # noqa: E402
from app.rag import vector_search  # noqa: E402
from app.seed import seed_if_empty  # noqa: E402

DATASETS = Path(__file__).resolve().parent / "datasets"
RESULTS = Path(__file__).resolve().parent / "hallucination_results.json"
RETRY_ATTEMPTS = 4
RETRY_SLEEP = 4.0


def _chat_retry(system: str, user: str) -> str:
    """Call chat_text with backoff on transient service-busy errors."""
    last_exc: Exception | None = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            return str(chat_text(system, user)).strip()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            retryable = (
                "503" in str(exc)
                or "SERVICE_BUSY" in str(exc)
                or "504" in str(exc)
                or "Gateway Time" in str(exc)
            )
            if not retryable:
                raise
            time.sleep(RETRY_SLEEP * (attempt + 1))
    raise RuntimeError(f"重试 {RETRY_ATTEMPTS} 次仍失败: {last_exc}")


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def parse_judge(text: str) -> dict:
    """Parse the judge's raw output into an explicit hallucination verdict."""
    data = _extract_json(text)
    if "hallucinated" in data:
        verdict = data["hallucinated"]
        if isinstance(verdict, str):
            verdict = verdict.strip().lower() in {"true", "yes", "是", "有", "1"}
        return {
            "hallucinated": bool(verdict),
            "reason": str(data.get("reason", "") or "").strip(),
        }
    lowered = text.strip().lower()
    return {
        "hallucinated": lowered.startswith(("true", "yes", "是", "有", "1")),
        "reason": text.strip(),
    }


def _evidence_text(query: str, category: str, top_k: int = 3) -> str:
    results = vector_search(query, category=category, top_k=top_k, rerank=True)
    if not results:
        return "无可用证据"
    lines = []
    for item in results:
        content = item.get("content") or item.get("resolution") or ""
        lines.append(
            f"- [{item['id']}] ({item['source']}, score={item['score']}) "
            f"{item['title']}: {content}"
        )
    return "\n".join(lines)


def generate_grounded_reply(query: str, evidence: str, language: str = "zh") -> str:
    system = (
        "你是电商客服回复助手。根据提供的知识库/工单证据回答客户问题。"
        "只能使用证据中明确存在的信息，不得编造证据中不存在的事实、数字、期限、金额、政策或承诺。"
        "请给出简短、直接、面向客户的中文答复正文，不要输出 JSON 或任何解释。"
    )
    user = f"客户问题：{query}\n\n可参考证据：\n{evidence}"
    return _chat_retry(system, user)


def judge_reply(query: str, evidence: str, reply: str) -> dict:
    system = (
        "你是幻觉检测器。判断 AI 回复是否包含证据不支持的事实（幻觉）。"
        "幻觉包括：编造证据中没有的具体数据/期限/金额/政策/承诺；"
        "把推测当成既定事实陈述；回答内容与证据相冲突。"
        "仅当回复包含明显不被证据支持或与之矛盾的内容时才判为幻觉；"
        "措辞层面略作润色不算幻觉。"
        '只输出 JSON：{"hallucinated": true 或 false, "reason": "简要说明"}。'
    )
    user = f"客户问题：{query}\n\n证据：\n{evidence}\n\nAI回复：\n{reply}"
    raw = _chat_retry(system, user)
    return parse_judge(raw)


def run_hallucination_eval() -> dict:
    with open(DATASETS / "retrieval.json", encoding="utf-8") as fh:
        queries = json.load(fh)

    details = []
    hallucinated = 0
    measured = 0
    pending = 0
    for item in queries:
        evidence = _evidence_text(
            item["query"], item.get("category", ""), top_k=3
        )
        reply = ""
        started = time.perf_counter()
        try:
            reply = generate_grounded_reply(item["query"], evidence)
            verdict = judge_reply(item["query"], evidence, reply)
        except Exception as exc:  # noqa: BLE001
            pending += 1
            verdict = {"hallucinated": None, "reason": f"LLM 调用失败: {exc}"}
        if verdict.get("hallucinated") is not None:
            measured += 1
            hallucinated += int(verdict["hallucinated"])
        details.append(
            {
                "query": item["query"],
                "category": item.get("category", ""),
                "evidence_ids": [
                    line.split("]")[0].lstrip("[")
                    for line in evidence.splitlines()
                    if line.startswith("- [")
                ],
                "reply": reply,
                "hallucinated": verdict.get("hallucinated"),
                "reason": verdict.get("reason", ""),
                "latency_ms": int((time.perf_counter() - started) * 1000),
            }
        )

    total = len(details)
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "data_dir": str(_TMP),
        "queries": total,
        "measured": measured,
        "pending": pending,
        "status": "pending" if pending == total else "done",
        "hallucination_rate": (
            round(hallucinated / measured, 4) if measured else None
        ),
        "hallucinated": hallucinated,
        "details": details,
    }


def main() -> int:
    os.makedirs(_TMP / "data", exist_ok=True)
    init_db()
    seed_if_empty()
    from app import repository

    repository.reindex_rag()
    started = time.perf_counter()
    report = run_hallucination_eval()
    report["elapsed_seconds"] = round(time.perf_counter() - started, 2)
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
