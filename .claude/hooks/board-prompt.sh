#!/usr/bin/env bash
# Claude Code UserPromptSubmit hook.
# On every prompt, shows NEW board posts since the last check (if any).
# Silent when there is nothing new, so it adds no noise or tokens.
# Must NEVER block the prompt: always exits 0.

cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0
[ -f tools/board ] || exit 0
command -v gh >/dev/null 2>&1 || exit 0

out="$(bash tools/board unread 2>/dev/null)" || exit 0

if [ -n "$out" ]; then
  echo "=== New posts on the team board since your last check ==="
  printf '%s\n' "$out"
  echo "=== Handle anything tagging YOUR handle or @all before/alongside this prompt. ==="
fi
exit 0
