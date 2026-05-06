#!/usr/bin/env sh
set -eu

repo_root="$(git rev-parse --show-toplevel)"

git -C "$repo_root" config core.hooksPath .githooks

echo "Configured Git hooks path: .githooks"
echo "Running pre-commit hook once to verify setup..."
"$repo_root/.githooks/pre-commit"
