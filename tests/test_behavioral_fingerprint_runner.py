from __future__ import annotations

from pathlib import Path

from scripts import run_behavioral_fingerprint as runner


class _BytesArtifact:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def to_json_bytes(self) -> bytes:
        return self.payload


def test_runner_requires_explicit_research_opt_in(capsys) -> None:
    assert runner.main([]) == 2
    assert "requires explicit --research" in capsys.readouterr().err


def test_runner_rejects_protected_configuration_output(capsys) -> None:
    assert (
        runner.main(
            [
                "--research",
                "--output",
                str(runner.DEFAULT_CONFIG),
                "--audit-output",
                "/tmp/kan15-safe-audit.json",
            ]
        )
        == 2
    )
    assert "must not overwrite" in capsys.readouterr().err


def test_runner_writes_separate_catalog_and_audit(
    monkeypatch,
    tmp_path: Path,
) -> None:
    catalog = tmp_path / "catalog.json"
    audit = tmp_path / "audit.json"
    monkeypatch.setattr(
        runner,
        "build_outputs",
        lambda **_: (
            _BytesArtifact(b"{\"catalog\":true}\n"),
            _BytesArtifact(b"{\"audit\":true}\n"),
        ),
    )

    assert (
        runner.main(
            [
                "--research",
                "--output",
                str(catalog),
                "--audit-output",
                str(audit),
            ]
        )
        == 0
    )
    assert catalog.read_bytes() == b"{\"catalog\":true}\n"
    assert audit.read_bytes() == b"{\"audit\":true}\n"


def test_runner_rejects_one_path_for_both_outputs(
    tmp_path: Path,
    capsys,
) -> None:
    shared = tmp_path / "shared.json"

    assert (
        runner.main(
            [
                "--research",
                "--output",
                str(shared),
                "--audit-output",
                str(shared),
            ]
        )
        == 2
    )
    assert "require separate paths" in capsys.readouterr().err
