"""Run the research-only KAN-15 Abshodeh Behavioral Fingerprint Engine."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from typing import Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from pipelines.behavioral_fingerprint import (  # noqa: E402
    BehavioralFingerprintArtifact,
    build_behavioral_fingerprint,
    load_policy,
)
from pipelines.behavioral_fingerprint.artifact import (  # noqa: E402
    BehavioralFingerprintAudit,
    build_compact_audit,
)
from scripts.run_abshodeh_source_semantics import (  # noqa: E402
    DEFAULT_CONFIG as SOURCE_SEMANTICS_CONFIG,
    DEFAULT_OUTPUT as SOURCE_SEMANTICS_OUTPUT,
    _protected_input_paths,
    build_evidence_bundle,
)


DEFAULT_CONFIG = Path(
    "configs/research/abshodeh-behavioral-fingerprint-v1.json"
)
DEFAULT_OUTPUT = Path(
    "outputs/research/KAN-15/abshodeh-behavioral-fingerprint.json"
)
DEFAULT_AUDIT_OUTPUT = Path(
    "docs/audits/artifacts/KAN-15-abshodeh-behavioral-fingerprint.json"
)
_IMPLEMENTATION_ROOTS = (
    Path("pipelines/behavioral_fingerprint"),
    Path("pipelines/canonical"),
    Path("pipelines/historical_labeling"),
    Path("pipelines/source_semantics"),
)
_IMPLEMENTATION_FILES = (
    Path("scripts/run_behavioral_fingerprint.py"),
    Path("scripts/run_abshodeh_source_semantics.py"),
    DEFAULT_CONFIG,
    Path("configs/research/abshodeh-historical-labeling-v2.json"),
    Path("configs/research/abshodeh-source-semantics-v1.json"),
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research", action="store_true")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(argv)


def _path(value: Path) -> Path:
    return value if value.is_absolute() else REPOSITORY_ROOT / value


def _implementation_revision() -> str:
    digest = hashlib.sha256()
    paths = list(_IMPLEMENTATION_FILES)
    for root in _IMPLEMENTATION_ROOTS:
        paths.extend(
            path.relative_to(REPOSITORY_ROOT)
            for path in sorted(_path(root).rglob("*.py"))
        )
    for relative in sorted(set(paths), key=lambda item: item.as_posix()):
        path = _path(relative)
        digest.update(relative.as_posix().encode("ascii"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"content-sha256:{digest.hexdigest()}"


def _validate_output_path(
    output: Path,
    *,
    fingerprint_config: Path,
) -> None:
    if output.is_symlink():
        raise ValueError("KAN-15 output must not be a symbolic link.")
    protected = set(
        _protected_input_paths(_path(SOURCE_SEMANTICS_CONFIG))
    )
    protected.add(fingerprint_config.resolve())
    aliases = output.exists() and any(
        item.exists() and output.samefile(item) for item in protected
    )
    if output.resolve() in protected or aliases:
        raise ValueError(
            "KAN-15 output must not overwrite a protected dataset, manifest, "
            "or configuration input."
        )


def _write_if_changed(path: Path, content: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    state = "unchanged" if path.is_file() and path.read_bytes() == content else "written"
    if state == "written":
        path.write_bytes(content)
    return state


def build_outputs(
    *,
    config_path: Path,
) -> tuple[BehavioralFingerprintArtifact, BehavioralFingerprintAudit]:
    policy = load_policy(config_path)
    bundle = build_evidence_bundle(
        cli_arguments=("--research",),
        config_path=_path(SOURCE_SEMANTICS_CONFIG),
        output_path=_path(SOURCE_SEMANTICS_OUTPUT),
    )
    fingerprint = build_behavioral_fingerprint(
        bundle.extraction,
        policy=policy,
        code_revision=_implementation_revision(),
    )
    audit = build_compact_audit(
        fingerprint,
        extraction=bundle.extraction,
        source_semantics=bundle.artifact,
        policy=policy,
    )
    return fingerprint, audit


def main(argv: Sequence[str] | None = None) -> int:
    arguments = tuple(sys.argv[1:] if argv is None else argv)
    args = parse_args(arguments)
    if not args.research:
        print(
            "KAN-15 full-corpus fingerprint requires explicit --research.",
            file=sys.stderr,
        )
        return 2
    config = _path(args.config)
    if config != _path(DEFAULT_CONFIG):
        print("Only the reviewed KAN-15 fingerprint config is supported.", file=sys.stderr)
        return 2
    output = _path(args.output)
    audit_output = _path(args.audit_output)
    try:
        _validate_output_path(output, fingerprint_config=config)
        _validate_output_path(audit_output, fingerprint_config=config)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if output.resolve() == audit_output.resolve():
        print("Full catalog and compact audit require separate paths.", file=sys.stderr)
        return 2

    fingerprint, audit = build_outputs(
        config_path=config,
    )
    catalog_bytes = fingerprint.to_json_bytes()
    audit_bytes = audit.to_json_bytes()
    if args.check:
        if not output.is_file() or not audit_output.is_file():
            print("KAN-15 fingerprint outputs are missing or stale.")
            return 1
        try:
            BehavioralFingerprintArtifact.model_validate_json(
                output.read_text(encoding="ascii")
            )
            BehavioralFingerprintAudit.model_validate_json(
                audit_output.read_text(encoding="ascii")
            )
        except ValueError:
            print("KAN-15 fingerprint outputs are missing or stale.")
            return 1
        if output.read_bytes() != catalog_bytes or audit_output.read_bytes() != audit_bytes:
            print("KAN-15 fingerprint outputs are missing or stale.")
            return 1
        print("KAN-15 fingerprint: G6 PASS; G7-G9 NOT_EVALUATED; outputs current.")
        return 0

    catalog_state = _write_if_changed(output, catalog_bytes)
    audit_state = _write_if_changed(audit_output, audit_bytes)
    print(
        "KAN-15 fingerprint: G6 PASS; G7-G9 NOT_EVALUATED; "
        f"catalog {catalog_state}; compact audit {audit_state}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
