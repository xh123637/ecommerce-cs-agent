"""RLHF closed-loop report: preference dataset export and adoption metrics.

Reads the RLHF feedback already collected in the repository (the same rows that
power /api/rlhf), converts them into a sharegpt-style preference dataset ready
for fine-tuning, and writes `rlhf_metrics.json` with adoption/correction KPI.
No LLM call is made here; the loop is about turning real human corrections into
a measurable, reusable training signal.
"""

import json
import os
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from app import repository  # noqa: E402

OUT_JSONL = Path(__file__).resolve().parent / "rlhf_preference_dataset.jsonl"
OUT_METRICS = Path(__file__).resolve().parent / "rlhf_metrics.json"


def build_preference_dataset(records: list[dict]) -> list[dict]:
    dataset = []
    for record in records:
        if record["label"] == "good":
            chosen = record["ai_reply"]
            rejected = ""
        elif record["label"] == "bad":
            chosen = record["human_reply"] or record["ai_reply"]
            rejected = record["ai_reply"]
        else:
            continue
        dataset.append(
            {
                "ticket_id": record["ticket_id"],
                "prompt": f"请处理电商客服工单 {record['ticket_id']}",
                "chosen": chosen,
                "rejected": rejected,
                "rating": record["rating"],
                "comment": record["comment"],
                "label": record["label"],
            }
        )
    return dataset


def main() -> int:
    records = repository.export_rlhf_feedback()
    dataset = build_preference_dataset(records)
    with open(OUT_JSONL, "w", encoding="utf-8") as fh:
        for item in dataset:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")

    stats = repository.rlhf_stats()
    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "stats": stats,
        "dataset_size": len(dataset),
        "positive_pairs": sum(1 for item in dataset if item["label"] == "good"),
        "correction_pairs": sum(1 for item in dataset if item["label"] == "bad"),
        "adoption_rate": stats.get("adoption_rate"),
        "closed_loop": (
            stats.get("correction_ready", 0) > 0
            or stats.get("preference_pairs", 0) > 0
        ),
        "training_ready": stats.get("preference_pairs", 0) >= 100,
    }
    OUT_METRICS.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
