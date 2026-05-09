from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Any, Literal

StdoutMode = Literal["wrapped", "final"]

# Fill input here if you don't want to pass --input
EMBEDDED_INPUT: dict[str, Any] = {
    "user_input": {
        "description": "Please arrange a basic bedroom that is neat, practical, and easy to use. I want the bed to be the main focal point, with nightstands and bedside lamps on both sides, or just on one side if needed. The wardrobe should be placed in a convenient spot without making the area around the bed feel cramped. If there is enough space, add a small side table near the window. The room should also have curtains and a ceiling light. Overall, the layout should feel tidy, comfortable, and easy to move around in.",
        "room_type": "bedroom",
        "floor_area_m2": 20.0,
        "height": 2400.0,
        "shape_points": [
            {"x": 0.0, "y": 0.0},
            {"x": 2400, "y": 0.0},
            {"x": 2400, "y": 3500},
            {"x": 0.0, "y": 3500},
        ],
        "windows": 1,
        "window_direction": "SE",
        "style": "minimal",
    }
}

# Fill user id here if you don't want to pass --user
EMBEDDED_USER_ID = "demo_user"


def main() -> int:
    _configure_logging()
    parser = argparse.ArgumentParser(
        description="Run the multi-agent backend pipeline (no UI) and emit JSON output."
    )
    parser.add_argument(
        "--input",
        default="",
        help="Path to UI input JSON (same schema as the frontend).",
    )
    parser.add_argument(
        "--user", default=EMBEDDED_USER_ID, help="user_id (default: EMBEDDED_USER_ID)"
    )
    parser.add_argument("--description", default="", help="Optional user description")
    parser.add_argument("--notes", default="", help="Optional special notes")
    parser.add_argument(
        "--cases-root",
        default="cases",
        help="Root folder for writing per-case artifacts",
    )
    parser.add_argument(
        "--case-id",
        default="",
        help="Optional explicit case_id (default: auto-generated)",
    )
    parser.add_argument(
        "--stdout",
        choices=("wrapped", "final"),
        default="wrapped",
        help="JSON to print to stdout: 'wrapped' (run_case return) or 'final' (stylist output only).",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Optional path to write the same JSON that is printed to stdout.",
    )
    parser.add_argument(
        "--ablation",
        default="",
        help="TKNT ablation mode: full, no_style_policy, no_capacity_control, or single_concept.",
    )
    args = parser.parse_args()

    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            raise SystemExit(f"Input file not found: {input_path}")
        input_payload: Any = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(input_payload, dict):
            raise SystemExit("--input must be a JSON object at the top level.")
    else:
        input_payload = EMBEDDED_INPUT

    try:
        from clients.gemini_client import GeminiClient
        from clients.openai_client import OpenAIClient
        from pipeline.orchestrator import run_case
    except ModuleNotFoundError as e:
        raise SystemExit(
            "Missing dependency while importing the pipeline. "
            "Activate your venv and install requirements (e.g. `pip install -r requirements.txt`). "
            f"Original error: {e}"
        ) from e

    GeminiClient.reset_usage_totals()
    OpenAIClient.reset_usage_totals()
    exit_code = 0
    try:
        result = run_case(
            input_payload=input_payload,
            user_id=str(args.user),
            description=(args.description or None),
            special_notes=(args.notes or None),
            cases_root=str(args.cases_root),
            case_id=(args.case_id or None),
            ablation_mode=(args.ablation or None),
        )
    except Exception as exc:
        logging.getLogger(__name__).exception("run_case failed")
        result = {
            "error": f"{type(exc).__name__}: {exc}",
            "final_output": None,
            "case_dir": None,
        }
        exit_code = 2
    llm_usage = _combine_llm_usage(
        gemini_usage=GeminiClient.usage_totals(),
        openai_usage=OpenAIClient.usage_totals(),
    )
    if int(llm_usage.get("request_count") or 0) > 0 or llm_usage.get("retry_events"):
        result["llm_usage"] = llm_usage
        result["input_tokens"] = llm_usage.get("input_tokens")
        result["output_tokens"] = llm_usage.get("output_tokens")

    stdout_mode: StdoutMode = args.stdout
    payload: Any
    if stdout_mode == "final":
        payload = result.get("final_output")
        if payload is None:
            payload = {
                "error": result.get("error"),
                "final_output": None,
                "case_dir": result.get("case_dir"),
            }
    else:
        payload = result

    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)

    if exit_code:
        return exit_code
    return 0 if not result.get("error") else 2


def _combine_llm_usage(
    *,
    gemini_usage: dict[str, object],
    openai_usage: dict[str, object],
) -> dict[str, object]:
    by_provider = {
        "gemini": gemini_usage,
        "openai": openai_usage,
    }
    retry_events = gemini_usage.get("retry_events")
    retry_summary = gemini_usage.get("retry_summary")
    return {
        "request_count": _usage_total(by_provider, "request_count"),
        "input_tokens": _usage_total(by_provider, "input_tokens"),
        "output_tokens": _usage_total(by_provider, "output_tokens"),
        "total_tokens": _usage_total(by_provider, "total_tokens"),
        "by_provider": by_provider,
        "retry_events": list(retry_events) if isinstance(retry_events, list) else [],
        "retry_summary": dict(retry_summary) if isinstance(retry_summary, dict) else {},
    }


def _usage_total(
    by_provider: dict[str, dict[str, object]],
    key: str,
) -> int:
    return sum(int(usage.get(key) or 0) for usage in by_provider.values())


def _configure_logging() -> None:
    level_name = os.getenv("TKNT_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


if __name__ == "__main__":
    raise SystemExit(main())
