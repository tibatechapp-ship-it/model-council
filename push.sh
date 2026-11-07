#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# MODEL-COUNCIL release push script (v20.0.0)
#
# Pushes the prepared release commit and the v20.0.0 tag to GitHub.
#
# SECURITY MODEL
#   * This script NEVER stores a token: it reads GITHUB_TOKEN from the
#     environment at runtime and passes it to git over the push URL only.
#   * It is never written to .git/config, to disk, or echoed.
#   * The previously leaked token must be REVOKED before you run this.
#     Create a new fine-grained token: https://github.com/settings/tokens
#
# USAGE
#   GITHUB_TOKEN=<YOUR_NEW_TOKEN> ./push.sh        # explicit token
#   ./push.sh                                      # uses your git credentials
#
# EXIT CODES: 0 success, 1 missing tool/token, 2 push failed.
# ---------------------------------------------------------------------------
set -euo pipefail

cd "$(dirname "$0")"

GITHUB_USER="${GITHUB_USER:-tibatechapp-ship-it}"
REPO="${GITHUB_USER}/model-council"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"

echo "== MODEL-COUNCIL release push =="
echo "Repository : https://github.com/${REPO}"
echo "Branch     : ${BRANCH}"
echo

# 1. Preflight -------------------------------------------------------------
command -v git >/dev/null 2>&1 || { echo "error: git not found"; exit 1; }

VERSION="$(python -c 'import model_council; print(model_council.__version__)' \
           2>/dev/null || echo '20.0.0')"
if [[ "${VERSION}" != "20.0.0" ]]; then
    echo "error: expected version 20.0.0, found ${VERSION}"
    exit 1
fi

if ! git rev-parse -q --verify refs/tags/v20.0.0 >/dev/null; then
    echo "error: tag v20.0.0 not found. Run: git tag -a v20.0.0 -m 'MODEL-COUNCIL v20.0.0'"
    exit 1
fi

# 2. Push -------------------------------------------------------------------
if [[ -n "${GITHUB_TOKEN:-}" ]]; then
    # Token goes to git via the push URL only; nothing is persisted.
    REMOTE="https://x-access-token:${GITHUB_TOKEN}@github.com/${REPO}.git"
    echo "Pushing main and tag v20.0.0 using GITHUB_TOKEN (not stored)..."
    git push "${REMOTE}" "${BRANCH}:main" || { echo "push failed"; exit 2; }
    git push "${REMOTE}" "v20.0.0"       || { echo "tag push failed"; exit 2; }
else
    echo "GITHUB_TOKEN not set - using your local git credentials..."
    git push origin "${BRANCH}:main"     || { echo "push failed"; exit 2; }
    git push origin "v20.0.0"            || { echo "tag push failed"; exit 2; }
fi

echo
echo "Success: main + tag v20.0.0 are on GitHub."
echo
echo "Create the GitHub release (optional, needs GitHub CLI):"
echo "  gh release create v20.0.0 --title 'MODEL-COUNCIL v20.0.0' \\"
echo "    --notes 'First full release: deliberation engine, 6 providers, CLI, REST API, 69 offline tests.'"
