"""
scripts/evaluation_report.py – fetch /api/evaluation from the running local
API and write docs/evaluation_results.md.

Usage (with the API running on port 8000):
    python scripts/evaluation_report.py [--url http://localhost:8000]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = REPO_ROOT / "docs" / "evaluation_results.md"


def fetch_evaluation(base_url: str) -> dict:
    url = base_url.rstrip("/") + "/api/evaluation"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as exc:
        sys.exit(f"ERROR: could not reach {url}\n{exc}\n\nMake sure the API is running: uvicorn backend.app.main:app --port 8000")


def write_report(data: dict, output: Path) -> None:
    total = data["total_cases"]
    investigated = data["investigated"]
    correct = data["correct"]
    accuracy = data["accuracy"]
    matches = data["matches"]

    pct = f"{accuracy * 100:.1f}%" if investigated > 0 else "N/A"
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "# DisputeDesk – Evaluation Results",
        "",
        f"Generated: {ts}",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Total cases in answer key | {total} |",
        f"| Cases investigated (recommend_outcome called) | {investigated} |",
        f"| Correct recommendations | {correct} |",
        f"| Accuracy (investigated cases) | {pct} |",
        "",
    ]

    if investigated == 0:
        lines += [
            "> **No cases have been investigated yet.**",
            "> Run all 30 disputes through the DisputeDesk supervisor in Orchestrate (see `docs/evaluation.md`).",
            "> Each `recommend_outcome` call is saved automatically.",
        ]
    else:
        lines += [
            "## Per-case breakdown",
            "",
            "| Dispute | Expected | Actual | Match |",
            "|---|---|---|---|",
        ]
        for m in sorted(matches, key=lambda x: x["dispute_id"]):
            icon = "✅" if m["correct"] else "❌"
            lines.append(f"| {m['dispute_id']} | {m['expected']} | {m['actual']} | {icon} |")

        wrong = [m for m in matches if not m["correct"]]
        if wrong:
            lines += [
                "",
                "## Wrong cases",
                "",
                "| Dispute | Expected | Actual |",
                "|---|---|---|",
            ]
            for m in sorted(wrong, key=lambda x: x["dispute_id"]):
                lines.append(f"| {m['dispute_id']} | {m['expected']} | {m['actual']} |")
        else:
            lines += ["", "> All investigated cases match the answer key."]

    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {output}  ({investigated}/{total} investigated, accuracy {pct})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch /api/evaluation and write docs/evaluation_results.md.")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of the running API.")
    args = parser.parse_args()

    data = fetch_evaluation(args.url)
    write_report(data, OUTPUT)


if __name__ == "__main__":
    main()
