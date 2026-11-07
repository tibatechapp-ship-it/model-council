"""MODEL-COUNCIL command line interface.

Commands
--------
``model-council --version``                      print version
``model-council providers``                      list providers + availability
``model-council ask "question"``                 quick multi-model consult
``model-council deliberate "question"``          full four-phase deliberation
``model-council demo``                           offline demo (no API keys)
``model-council serve --port 8000``              run the REST API

Exit codes: 0 completed, 3 partial (some members failed), 4 failed,
2 usage error.
"""

from __future__ import annotations

import argparse
import json
import sys

from model_council import __version__
from model_council.cli.render import render_providers, render_summary
from model_council.domain.models import CouncilStatus
from model_council.engine import Council, DeliberationConfig
from model_council.engine.results import DeliberationResult

_DEMO_QUESTION = (
    "Should a small engineering team adopt a weekly model-council review "
    "for high-stakes architectural decisions?"
)

_EXIT_CODES = {
    CouncilStatus.COMPLETED: 0,
    CouncilStatus.PARTIAL: 3,
    CouncilStatus.FAILED: 4,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="model-council",
        description=(
            "Structured multi-model deliberation: independent positions, "
            "pseudonymised cross-critique, revision, weighted vote."
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"MODEL-COUNCIL {__version__}"
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("providers", help="list providers and availability")

    def _add_council_options(p: argparse.ArgumentParser) -> None:
        p.add_argument("question", help="the question put to the council")
        p.add_argument(
            "--members",
            default=None,
            help=(
                "comma-separated member specs like "
                "'echo:optimist,openai:gpt-4o-mini' "
                "(default: offline demo council)"
            ),
        )
        p.add_argument("--rounds", type=int, default=1, choices=range(0, 6))
        p.add_argument("--timeout", type=float, default=60.0)
        p.add_argument("--temperature", type=float, default=0.4)
        p.add_argument("--max-tokens", type=int, default=2048)
        p.add_argument("--workers", type=int, default=4)
        p.add_argument("--json", action="store_true", help="JSON output")
        p.add_argument(
            "--export",
            default=None,
            help="write result to PATH (.md transcript or .json full result)",
        )
        p.add_argument(
            "--show-transcript",
            action="store_true",
            help="print the full verbatim transcript",
        )

    ask = sub.add_parser(
        "ask", help="quick consult: positions + vote, no debate rounds"
    )
    _add_council_options(ask)

    deliberate = sub.add_parser(
        "deliberate", help="full deliberation: critique + revision rounds"
    )
    _add_council_options(deliberate)

    demo = sub.add_parser(
        "demo", help="offline demo council - no API keys needed"
    )
    demo.add_argument("--json", action="store_true")
    demo.add_argument("--export", default=None)

    serve = sub.add_parser("serve", help="run the REST API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 2

    if args.command == "providers":
        from model_council.providers import available_providers

        print(render_providers(available_providers()))
        return 0

    if args.command == "serve":
        return _serve(args)

    if args.command == "demo":
        args.question = _DEMO_QUESTION
        args.members = None
        args.rounds = 1
        args.timeout = 60.0
        args.temperature = 0.4
        args.max_tokens = 2048
        args.workers = 4
        args.json = getattr(args, "json", False)
        args.show_transcript = False

    result, error = _run_council(args)
    if error is not None:
        print(f"error: {error}", file=sys.stderr)
        return 2

    assert result is not None
    _emit(args, result)
    return _EXIT_CODES.get(result.status, 4)


# --------------------------------------------------------------------------
# internals
# --------------------------------------------------------------------------
def _run_council(
    args: argparse.Namespace,
) -> tuple[DeliberationResult | None, str | None]:
    specs = (
        [spec.strip() for spec in args.members.split(",") if spec.strip()]
        if args.members
        else ["echo:optimist", "echo:skeptic", "echo:pragmatist"]
    )
    config = DeliberationConfig(
        rounds=args.rounds,
        timeout=args.timeout,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        max_workers=args.workers,
    )
    try:
        council = Council.from_specs(specs, config=config)
        result = council.deliberate(args.question)
    except (KeyError, ValueError) as exc:
        return None, str(exc)
    return result, None


def _emit(args: argparse.Namespace, result: DeliberationResult) -> None:
    if args.export:
        _export(args.export, result)
    if getattr(args, "json", False):
        payload = json.loads(result.model_dump_json())
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    print(render_summary(result, show_transcript=args.show_transcript))
    if args.export:
        print(f"Exported: {args.export}")


def _export(path: str, result: DeliberationResult) -> None:
    if path.lower().endswith(".md"):
        content = result.transcript.render_markdown(result.question)
    else:
        content = json.dumps(
            json.loads(result.model_dump_json()),
            indent=2,
            ensure_ascii=False,
        )
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def _serve(args: argparse.Namespace) -> int:
    try:
        import uvicorn

        from model_council.api.app import app as fastapi_app
    except ImportError as exc:  # pragma: no cover - guard rail
        print(
            "error: uvicorn is required to run the API server "
            f"({exc}). Install with: pip install 'model-council[api]'",
            file=sys.stderr,
        )
        return 2
    uvicorn.run(fastapi_app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
