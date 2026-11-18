"""
export_openapi.py – write an OpenAPI file that watsonx Orchestrate can import.

Orchestrate only imports OpenAPI 3.0 specs with exactly one server URL.
FastAPI produces OpenAPI 3.1 with no server, so this script:
- keeps only the /tools/* operations (the agent's tools),
- sets "openapi": "3.0.3" and a single server URL,
- turns 3.1-style nullable fields (anyOf with {"type": "null"}) into
  3.0-style "nullable": true,
- drops the 422 validation-error responses the agent does not need.

Usage (from the repo root):
    python agent/export_openapi.py --server-url https://example.trycloudflare.com
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = REPO_ROOT / "agent" / "disputedesk_tools_openapi.json"
EXPECTED_TOOLS = {
    "get_dispute",
    "get_transaction",
    "get_customer_history",
    "get_merchant_info",
    "check_deadline",
    "recommend_outcome",
    "record_letter_draft",
}
NULL = {"type": "null"}


def _fix_nullable(node):
    """Recursively convert 3.1 nullable unions into 3.0 'nullable: true'."""
    if isinstance(node, list):
        return [_fix_nullable(item) for item in node]
    if not isinstance(node, dict):
        return node

    node = {key: _fix_nullable(value) for key, value in node.items()}
    for key in ("anyOf", "oneOf"):
        options = node.get(key)
        if isinstance(options, list) and NULL in options:
            others = [opt for opt in options if opt != NULL]
            rest = {k: v for k, v in node.items() if k != key}
            if len(others) == 1:
                only = others[0]
                # A $ref ignores sibling keys in 3.0, so wrap it in allOf.
                base = {"allOf": [only]} if "$ref" in only else dict(only)
            else:
                base = {key: others}
            base.update(rest)
            base["nullable"] = True
            node = base
    return node


def build_spec(server_url: str) -> dict:
    sys.path.insert(0, str(REPO_ROOT))
    from backend.app.main import app  # imported here so the repo root is on the path

    spec = copy.deepcopy(app.openapi())

    paths = {path: ops for path, ops in spec["paths"].items() if path.startswith("/tools/")}
    for path, ops in paths.items():
        for method, op in ops.items():
            if not op.get("operationId"):
                raise SystemExit(f"Missing operationId on {method.upper()} {path}")
            if not op.get("description"):
                raise SystemExit(f"Missing description on {method.upper()} {path}")
            op.get("responses", {}).pop("422", None)

    schemas = spec.get("components", {}).get("schemas", {})
    for unused in ("HTTPValidationError", "ValidationError"):
        schemas.pop(unused, None)

    spec = {
        "openapi": "3.0.3",
        "info": spec["info"],
        "servers": [{"url": server_url.rstrip("/")}],
        "paths": paths,
        "components": {"schemas": schemas},
    }
    spec = _fix_nullable(spec)

    found = {op["operationId"] for ops in spec["paths"].values() for op in ops.values()}
    if found != EXPECTED_TOOLS:
        raise SystemExit(f"Expected tools {sorted(EXPECTED_TOOLS)}, found {sorted(found)}")
    return spec


def validate(spec: dict) -> bool:
    """Validate with openapi-spec-validator when it is installed."""
    try:
        from openapi_spec_validator import validate as _validate
    except ImportError:
        print("Note: openapi-spec-validator is not installed, skipping validation.")
        return False
    _validate(spec)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the DisputeDesk tools for watsonx Orchestrate.")
    parser.add_argument("--server-url", required=True, help="Public HTTPS address of the running API.")
    parser.add_argument("--output", default=str(OUTPUT), help="Where to write the JSON file.")
    args = parser.parse_args()

    if not args.server_url.startswith("https://"):
        raise SystemExit("The server URL must start with https:// (Orchestrate needs a public HTTPS address).")

    spec = build_spec(args.server_url)
    checked = validate(spec)
    Path(args.output).write_text(json.dumps(spec, indent=2), encoding="utf-8")
    print(f"Wrote {args.output} with {len(spec['paths'])} tools" + (" (validated as OpenAPI 3.0)." if checked else "."))


if __name__ == "__main__":
    main()
