# config-tidy

Clean a GitHub Actions workflow YAML file: fix unambiguous indentation, bump deprecated official actions, replace `::set-output`, add a minimal `permissions:` block when missing, and flag unpinned third-party actions.

This helper is **rule-based** (no AI). It uses careful text edits so comments stay in place, and it never overwrites the input file. Sponsor: [github.com/sponsors/fitzyracing1](https://github.com/sponsors/fitzyracing1).

## Install

```bash
pipx install git+https://github.com/fitzyracing1/config-tidy
```

Or from a checkout:

```bash
pip install -e .
```

## Usage

Print tidied YAML on stdout (the change report goes to stderr):

```bash
config-tidy .github/workflows/ci.yml
python -m config_tidy .github/workflows/ci.yml
```

Write a new file named `ci.tidy.yml` (the original is never overwritten):

```bash
config-tidy --write .github/workflows/ci.yml
```

## What it does

- Replaces leading tabs with 2 spaces (unambiguous indent only; mixed or odd space widths are left alone).
- Bumps official actions when their major is older than the current one:
  - `actions/checkout` → `@v7`
  - `actions/setup-node` → `@v7`
  - `actions/setup-python` → `@v7`
  - `actions/cache` (and `/restore`, `/save`) → `@v6`
  - `actions/upload-artifact` → `@v7`
  - `actions/download-artifact` → `@v8`
  - SHA pins and already-current (or newer) majors are left unchanged.
- Replaces `::set-output name=foo::bar` with `echo "foo=bar" >> "$GITHUB_OUTPUT"` (and `::save-state` with `$GITHUB_STATE`).
- Adds a top-level `permissions: contents: read` block when the workflow has no `permissions:` key, and reports that addition.
- Reports (but does not rewrite) third-party actions that are not pinned to a commit SHA.

Current majors follow [ci-doctor](https://github.com/fitzyracing1/ci-doctor) reference data last checked on 2026-11-13. Newer majors already in a workflow are not downgraded.

## License

MIT. Copyright (c) 2026 Joshua Almeida (fitzyracing1).
