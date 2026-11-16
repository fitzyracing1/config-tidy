"""Rule-based tidier for GitHub Actions workflow YAML.

Edits are applied as careful text substitutions so comments stay in place.
Current official action majors were taken from fitzyracing1/ci-doctor's
reference data (checked 2026-11-13).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Official actions this helper will bump when the major is older than current.
CURRENT_MAJORS = {
    "actions/checkout": 7,
    "actions/setup-node": 7,
    "actions/setup-python": 7,
    "actions/cache": 6,
    "actions/cache/restore": 6,
    "actions/cache/save": 6,
    "actions/upload-artifact": 7,
    "actions/download-artifact": 8,
}

OFFICIAL_OWNERS = frozenset({"actions", "github"})
SHA_RE = re.compile(r"^[0-9a-f]{7,40}$", re.I)
# uses: owner/repo@ref  or uses: owner/repo/path@ref
USES_RE = re.compile(
    r"^(?P<prefix>\s*(?:-\s*)?uses:\s*)"
    r"(?P<action>[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+)"
    r"@(?P<ref>[^\s#]+)"
    r"(?P<suffix>\s*(#.*)?)?$"
)
SET_OUTPUT_RE = re.compile(
    r"""(['"]?)::set-output\s+name=([A-Za-z0-9_-]+)::(.*?)(\1)"""
)
# Unquoted ::set-output name=foo::bar
SET_OUTPUT_BARE_RE = re.compile(
    r"""(?<![:\w])::set-output\s+name=([A-Za-z0-9_-]+)::(\S+)"""
)
SAVE_STATE_RE = re.compile(
    r"""(['"]?)::save-state\s+name=([A-Za-z0-9_-]+)::(.*?)(\1)"""
)
SAVE_STATE_BARE_RE = re.compile(
    r"""(?<![:\w])::save-state\s+name=([A-Za-z0-9_-]+)::(\S+)"""
)
VERSION_RE = re.compile(r"^v?(\d+)(?:\.\d+)*$", re.I)


@dataclass
class Change:
    kind: str
    message: str

    def line(self) -> str:
        return f"  [{self.kind}] {self.message}"


@dataclass
class TidyResult:
    source: str
    changes: list[Change] = field(default_factory=list)

    def report(self) -> str:
        lines = ["config-tidy report"]
        if not self.changes:
            lines.append("No changes or findings.")
            lines.append("")
            return "\n".join(lines)
        lines.append(f"Found {len(self.changes)} change(s)/finding(s):")
        for change in self.changes:
            lines.append(change.line())
        lines.append("")
        return "\n".join(lines)


def _major(ref: str) -> int | None:
    match = VERSION_RE.match(ref.strip())
    if not match:
        return None
    return int(match.group(1))


def _expand_tabs(text: str, changes: list[Change]) -> str:
    lines = text.splitlines(keepends=True)
    out = []
    converted = 0
    for line in lines:
        leading = len(line) - len(line.lstrip("\t"))
        if leading and line[:leading] == "\t" * leading:
            line = "  " * leading + line[leading:]
            converted += 1
        out.append(line)
    if converted:
        changes.append(
            Change("indent", f"Replaced leading tabs with 2 spaces on {converted} line(s)")
        )
    return "".join(out)


def _bump_actions(text: str, changes: list[Change]) -> str:
    lines = text.splitlines(keepends=True)
    out = []
    for line in lines:
        stripped_nl = line.endswith("\n")
        body = line[:-1] if stripped_nl else line
        cr = ""
        if body.endswith("\r"):
            cr = "\r"
            body = body[:-1]
        match = USES_RE.match(body)
        if not match:
            out.append(line)
            continue
        action = match.group("action")
        ref = match.group("ref")
        if SHA_RE.match(ref):
            out.append(line)
            continue
        target = CURRENT_MAJORS.get(action)
        if target is None:
            out.append(line)
            continue
        current = _major(ref)
        if current is None or current >= target:
            out.append(line)
            continue
        new_ref = f"v{target}"
        new_body = (
            f"{match.group('prefix')}{action}@{new_ref}{match.group('suffix') or ''}"
        )
        out.append(new_body + cr + ("\n" if stripped_nl else ""))
        changes.append(
            Change("action", f"Bumped {action}@{ref} to {action}@{new_ref}")
        )
    return "".join(out)


def _replace_set_output(text: str, changes: list[Change]) -> str:
    count = 0

    def quoted_output(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        name, value = match.group(2), match.group(3)
        return f'echo "{name}={value}" >> "$GITHUB_OUTPUT"'

    def bare_output(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        name, value = match.group(1), match.group(2)
        return f'echo "{name}={value}" >> "$GITHUB_OUTPUT"'

    def quoted_state(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        name, value = match.group(2), match.group(3)
        return f'echo "{name}={value}" >> "$GITHUB_STATE"'

    def bare_state(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        name, value = match.group(1), match.group(2)
        return f'echo "{name}={value}" >> "$GITHUB_STATE"'

    # Replace quoted forms first so the quotes are consumed, then bare forms.
    # A typical line is: echo "::set-output name=foo::bar"
    # After substitution we do not want a leftover echo.
    def line_fix(line: str) -> str:
        original = line
        # Common pattern: echo "::set-output name=X::Y"  or echo '...'
        m = re.search(
            r"""echo\s+(['"])::set-output\s+name=([A-Za-z0-9_-]+)::(.*?)\1""",
            line,
        )
        if m:
            line = (
                line[: m.start()]
                + f'echo "{m.group(2)}={m.group(3)}" >> "$GITHUB_OUTPUT"'
                + line[m.end() :]
            )
        m = re.search(
            r"""echo\s+(['"])::save-state\s+name=([A-Za-z0-9_-]+)::(.*?)\1""",
            line,
        )
        if m:
            line = (
                line[: m.start()]
                + f'echo "{m.group(2)}={m.group(3)}" >> "$GITHUB_STATE"'
                + line[m.end() :]
            )
        # Bare / already-partial forms.
        line = SET_OUTPUT_BARE_RE.sub(bare_output, line)
        line = SAVE_STATE_BARE_RE.sub(bare_state, line)
        if line != original and original == line:
            pass
        return line

    new_lines = []
    for line in text.splitlines(keepends=True):
        updated = line_fix(line)
        if updated != line:
            count += 1
        new_lines.append(updated)
    if count:
        changes.append(
            Change(
                "set-output",
                f"Replaced deprecated ::set-output / ::save-state on {count} line(s) "
                "with $GITHUB_OUTPUT / $GITHUB_STATE",
            )
        )
    return "".join(new_lines)


def _has_top_level_permissions(text: str) -> bool:
    for raw in text.splitlines():
        if raw.startswith("permissions:") or raw.startswith("permissions :"):
            return True
    return False


def _insert_permissions(text: str, changes: list[Change]) -> str:
    if _has_top_level_permissions(text):
        return text
    lines = text.splitlines(keepends=True)
    if not any(line.strip() for line in lines):
        return text

    insert_at = 0
    # Skip a leading document marker and comment/blank lines, then prefer after name:.
    i = 0
    while i < len(lines) and (
        not lines[i].strip() or lines[i].lstrip().startswith("#") or lines[i].strip() == "---"
    ):
        i += 1
        insert_at = i
    for idx, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("name:") and (len(line) - len(stripped) == 0):
            insert_at = idx + 1
            break

    block = "permissions:\n  contents: read\n"
    # Keep a blank line around the new block when the neighbors are not blank.
    before = lines[:insert_at]
    after = lines[insert_at:]
    pieces = []
    if before and not before[-1].endswith("\n"):
        pieces.append(before[-1])
        before = before[:-1]
    pieces = before[:]
    if pieces and pieces[-1].strip():
        if not pieces[-1].endswith("\n"):
            pieces[-1] += "\n"
        pieces.append("\n")
    pieces.append(block)
    if after and after[0].strip():
        pieces.append("\n")
    pieces.extend(after)
    changes.append(
        Change(
            "permissions",
            "Added top-level `permissions: contents: read` (workflow had no permissions: key)",
        )
    )
    return "".join(pieces)


def _flag_unpinned(text: str, changes: list[Change]) -> None:
    for raw in text.splitlines():
        body = raw.rstrip("\r")
        match = USES_RE.match(body)
        if not match:
            continue
        action = match.group("action")
        ref = match.group("ref")
        owner = action.split("/", 1)[0]
        if owner in OFFICIAL_OWNERS:
            continue
        if SHA_RE.match(ref):
            continue
        changes.append(
            Change(
                "unpinned",
                f"Third-party action {action}@{ref} is not pinned to a commit SHA",
            )
        )


def tidy(source: str) -> TidyResult:
    changes: list[Change] = []
    text = source
    text = _expand_tabs(text, changes)
    text = _bump_actions(text, changes)
    text = _replace_set_output(text, changes)
    text = _insert_permissions(text, changes)
    _flag_unpinned(text, changes)
    if text and not text.endswith("\n"):
        text += "\n"
        changes.append(Change("newline", "Added a trailing newline"))
    return TidyResult(source=text, changes=changes)
