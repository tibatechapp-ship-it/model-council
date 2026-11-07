"""CLI tests executed in-process via ``main(argv)``."""

from __future__ import annotations

import json

import pytest

from model_council.cli.main import main


def test_version(capsys):
    # argparse's --version action terminates via SystemExit(0).
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert "MODEL-COUNCIL 20.0.0" in capsys.readouterr().out


def test_no_command_prints_help(capsys):
    assert main([]) == 2
    assert "usage" in capsys.readouterr().out.lower()


def test_providers_command(capsys):
    assert main(["providers"]) == 0
    out = capsys.readouterr().out
    assert "echo" in out
    assert "offline test double" in out
    assert "openai" in out


def test_demo_json_is_parseable(capsys):
    exit_code = main(["demo", "--json"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "completed"
    assert payload["winner"]
    assert len(payload["positions"]) == 3


def test_demo_human_output(capsys):
    exit_code = main(["demo"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "COUNCIL VERDICT" in out
    assert "STRUCTURED DISAGREEMENTS" in out


def test_ask_with_export(tmp_path, capsys):
    target = tmp_path / "result.json"
    exit_code = main(
        [
            "ask",
            "Should we enable two-factor authentication for admins?",
            "--rounds",
            "0",
            "--export",
            str(target),
            "--json",
        ]
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["rounds_completed"] == 0
    saved = json.loads(target.read_text(encoding="utf-8"))
    assert saved["council_id"] == payload["council_id"]


def test_deliberate_markdown_export(tmp_path, capsys):
    target = tmp_path / "transcript.md"
    exit_code = main(
        [
            "deliberate",
            "Should we rewrite the payments service in Rust?",
            "--members",
            "echo:optimist,echo:skeptic",
            "--export",
            str(target),
        ]
    )
    assert exit_code == 0
    content = target.read_text(encoding="utf-8")
    assert content.startswith("# MODEL-COUNCIL Deliberation Transcript")
    assert "Phase: VOTE" in content


def test_unknown_member_exits_with_usage_error(capsys):
    exit_code = main(
        ["ask", "Test question for the council?", "--members", "nosuch:model"]
    )
    assert exit_code == 2
    assert "error" in capsys.readouterr().err.lower()


def test_short_question_rejected(capsys):
    exit_code = main(["ask", "hi"])
    assert exit_code == 2


def test_transcript_flag(capsys):
    exit_code = main(
        [
            "ask",
            "Adopt trunk-based development?",
            "--show-transcript",
            "--rounds",
            "0",
        ]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "FULL TRANSCRIPT" in out
