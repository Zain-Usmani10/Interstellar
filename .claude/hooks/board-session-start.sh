#!/usr/bin/env bash
# Claude Code SessionStart hook.
# Prints unread posts from the team board (pinned GitHub issue) so they are
# added to the agent's context when a session starts/resumes/clears.
# Must NEVER block or fail the session: always exits 0.

cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0
[ -f tools/board ] || exit 0

if ! command -v gh >/dev/null 2>&1; then
  echo "[board] GitHub CLI (gh) not found. Install it and run: gh auth login"
  exit 0
fi

out="$(bash tools/board unread 2>/dev/null)"
status=$?

if [ $status -ne 0 ]; then
  echo "[board] Could not reach GitHub. Run 'tools/board unread' later."
  exit 0
fi

if [ -n "$out" ]; then
  echo "=== Unread posts on the team board (issue #${BOARD_ISSUE:-1}) ==="
  printf '%s\n' "$out"
  echo "=== Act on posts that tag YOUR handle or @all (see AGENTS.md section 0). Ignore other handles. ==="
else
  echo "[board] No unread posts on the team board."
fi
exit 0
