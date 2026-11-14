# START HERE (Zain)

> **ARCHIVED.** Written before the plan in `docs/plan/` and the leader change. Do not follow; see `AGENTS.md`.

## 1. Unzip into the repo
Unzip this pack into `C:\Users\zainu\Projects\Interstellar` (merge folders). You get:
- `CONTEXT.md` (root)
- `docs/HANDOFF.md`: full context for your Claude Code (everything from the planning chat)
- `docs/TEAM_SETUP.md`: send this to teammates
- `docs/START_HERE.md`: this file
- `.claude/hooks/board-session-start.sh` + `board-prompt.sh`: the missing hook scripts

## 2. Commit and push (Git Bash or cmd, in the repo)
```
git switch dev
git pull
git add CONTEXT.md docs .claude/hooks
git update-index --chmod=+x .claude/hooks/board-session-start.sh .claude/hooks/board-prompt.sh
git commit -m "Add handoff docs, context and board hooks"
git push
```

## 3. Your own Claude account
1. Browser: log out of friend's account → log in/sign up as you → upgrade to **Pro** (includes Claude Code).
2. Terminal: `claude` → `/logout` (if friend's account is there) → `/login` → Claude account → you.
3. If `claude` isn't installed: follow the official install page at claude.com/claude-code (Windows needs Git for Windows).

## 4. First prompt to Claude Code (run `claude` in the repo folder)
> You are @Zain-Usmani10/claude, the team lead agent. Read AGENTS.md, CONTEXT.md and docs/HANDOFF.md fully before doing anything. Then follow HANDOFF.md section 8 ("Your first actions"), one step at a time, asking me before any non-trivial change. Keep answers short and direct.

## 5. Send teammates
`docs/TEAM_SETUP.md` (or the GitHub link to it once pushed).

## 6. Done when
All 6 agents posted "online" on board issue #1. Then decide the open items in HANDOFF.md section 7 with your Claude Code.

## Key deadlines
- **Draft on Devpost: Sun 12:00 AM (midnight tonight)**
- **Final: Sun 12:00 PM, no late entries**
- Demos: Sun 1:15 PM
