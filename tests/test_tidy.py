"""Tests for config-tidy."""

from __future__ import annotations

from pathlib import Path

from config_tidy.cli import main
from config_tidy.tidy import tidy

SAMPLES = Path(__file__).parent / "samples"


def test_tabs_actions_set_output_permissions_and_unpinned():
    source = (SAMPLES / "messy.yml").read_text(encoding="utf-8")
    result = tidy(source)
    kinds = [c.kind for c in result.changes]
    assert "indent" in kinds
    assert "action" in kinds
    assert "set-output" in kinds
    assert "permissions" in kinds
    assert "unpinned" in kinds
    text = result.source
    assert "\t" not in text
    assert "actions/checkout@v7" in text
    assert "actions/checkout@v2" not in text
    assert "actions/setup-node@v7" in text
    assert "actions/setup-python@v7" in text
    assert "actions/cache@v6" in text
    assert "actions/upload-artifact@v7" in text
    assert "actions/download-artifact@v8" in text
    # Already-current and SHA pins are left alone.
    assert text.count("actions/checkout@v7") >= 1
    assert "actions/checkout@8e5e7e5ab8b370d6c329ec480221332ada57f0ab" in text
    assert 'echo "tag=v1.2.3" >> "$GITHUB_OUTPUT"' in text
    assert "::set-output" not in text
    assert "permissions:" in text
    assert "contents: read" in text
    # Comment preserved.
    assert "# Keep this comment" in text
    assert "# third party" in text
    # Finding only — the third-party pin is not rewritten.
    assert "some-org/cool-action@v1" in text
    assert any("some-org/cool-action@v1" in c.message for c in result.changes)


def test_already_clean_is_unchanged_except_unpinned_sha_is_ok():
    source = (SAMPLES / "already-clean.yml").read_text(encoding="utf-8")
    result = tidy(source)
    assert result.source == source or result.source == source if source.endswith("\n") else source + "\n"
    kinds = {c.kind for c in result.changes}
    assert "action" not in kinds
    assert "permissions" not in kinds
    assert "set-output" not in kinds
    assert "unpinned" not in kinds


def test_permissions_inserted_when_name_is_missing():
    source = (SAMPLES / "permissions-only.yml").read_text(encoding="utf-8")
    result = tidy(source)
    assert "permissions:" in result.source
    assert "# header" in result.source
    assert result.source.index("# header") < result.source.index("permissions:")


def test_does_not_downgrade_newer_major():
    source = "name: CI\njobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/cache@v6\n"
    result = tidy(source)
    assert "actions/cache@v6" in result.source
    assert not any(c.kind == "action" for c in result.changes)


def test_cli_write_does_not_overwrite(tmp_path, capsys):
    src = tmp_path / "ci.yml"
    original = (SAMPLES / "messy.yml").read_text(encoding="utf-8")
    src.write_text(original, encoding="utf-8")
    assert main([str(src), "--write"]) == 0
    assert src.read_text(encoding="utf-8") == original
    dest = tmp_path / "ci.tidy.yml"
    assert dest.is_file()
    text = dest.read_text(encoding="utf-8")
    assert "actions/checkout@v7" in text
    err = capsys.readouterr().err
    assert "Wrote" in err
    assert "Bumped" in err
