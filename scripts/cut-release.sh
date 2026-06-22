#!/usr/bin/env bash
#
# cut-release.sh — bump Pennyworth to a new version, consistently, then tag it.
#
# Version lives in three places that MUST agree (the release workflow enforces
# this and refuses to publish a mismatch):
#   - pyproject.toml         [tool.poetry] version
#   - src/pennyworth/__init__.py   __version__
#   - the git tag            vX.Y.Z
#
# Usage:
#   scripts/cut-release.sh X.Y.Z
#
# What it does:
#   1. Sanity-checks the version string and a clean working tree.
#   2. Updates pyproject.toml and __init__.py.
#   3. Verifies CHANGELOG.md has a "## [X.Y.Z]" section (you write the notes).
#   4. Commits the bump and creates an annotated tag vX.Y.Z.
#
# It does NOT push. Review, then push the branch and the tag yourself:
#   git push origin master
#   git push origin vX.Y.Z      # this is what fires the Release workflow
set -euo pipefail

version="${1:-}"
if [ -z "$version" ]; then
  echo "usage: scripts/cut-release.sh X.Y.Z" >&2
  exit 2
fi

# Strict semver-ish check (X.Y.Z, optional pre-release suffix like 1.2.0rc1).
if ! [[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+([a-zA-Z0-9.]+)?$ ]]; then
  echo "error: '$version' is not a valid version (expected X.Y.Z)" >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [ -n "$(git status --porcelain)" ]; then
  echo "error: working tree is not clean — commit or stash first." >&2
  exit 1
fi

if git rev-parse "v$version" >/dev/null 2>&1; then
  echo "error: tag v$version already exists." >&2
  exit 1
fi

if ! grep -q "^## \[$version\]" CHANGELOG.md; then
  echo "error: CHANGELOG.md has no '## [$version]' section — add the release notes first." >&2
  exit 1
fi

echo "Bumping to $version ..."
poetry version "$version" >/dev/null

# Update __version__ in the package (portable in-place sed for macOS + Linux).
python3 - "$version" <<'PY'
import re, sys, pathlib
version = sys.argv[1]
path = pathlib.Path("src/pennyworth/__init__.py")
text = path.read_text()
new = re.sub(r'^__version__ = ".*"$', f'__version__ = "{version}"', text, flags=re.M)
if new == text:
    sys.exit("error: could not find __version__ in __init__.py")
path.write_text(new)
PY

git add pyproject.toml src/pennyworth/__init__.py
git commit -m "chore(release): v$version"
git tag -a "v$version" -m "Pennyworth v$version"

cat <<EOF

✅ Bumped to v$version and tagged.

Next:
  git push origin master
  git push origin v$version    # fires the Release workflow → PyPI + GitHub Release
EOF
