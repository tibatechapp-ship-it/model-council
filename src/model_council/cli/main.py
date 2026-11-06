"""Command-line entry point for MODEL-COUNCIL."""

import argparse

from model_council import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="model-council",
        description="Multi-model AI consultation and evidence verification.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"MODEL-COUNCIL {__version__}",
    )
    return parser


def main() -> int:
    parser = build_parser()
    parser.parse_args()
    print(f"MODEL-COUNCIL {__version__}")
    print("Project status: early development")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
