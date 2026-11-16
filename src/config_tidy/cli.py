"""Command-line interface for config-tidy."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from config_tidy import __version__
from config_tidy.tidy import tidy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="config-tidy",
        description=(
            "Clean a GitHub Actions workflow YAML file: fix unambiguous indent, "
            "bump deprecated official actions, replace ::set-output, and add a "
            "minimal permissions block when missing. Prints a change report on stderr."
        ),
    )
    parser.add_argument("file", help="Path to a workflow YAML file")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write tidied YAML to FILE.tidy.yml (never overwrites FILE)",
    )
    parser.add_argument("--version", action="version", version=f"config-tidy {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    path = Path(args.file)
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as err:
        print(f"config-tidy: cannot read {path}: {err}", file=sys.stderr)
        return 1

    result = tidy(source)
    sys.stderr.write(result.report())
    if args.write:
        dest = path.with_name(path.stem + ".tidy.yml")
        dest.write_text(result.source, encoding="utf-8")
        sys.stderr.write(f"Wrote {dest}\n")
    else:
        sys.stdout.write(result.source)
        if result.source and not result.source.endswith("\n"):
            sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
