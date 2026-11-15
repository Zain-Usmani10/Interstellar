# Teammate setup (≈10 min per person)

Repo: https://github.com/Zain-Usmani10/Interstellar (private). Working branch: `dev`.
Run every command below in **Git Bash** (comes with Git for Windows).

| Who | Agents | Folders on your laptop |
|---|---|---|
| Abderrahmene (`ANaceri26`) | Claude (**leader**), Codex | `Interstellar` (Claude) + `Interstellar-codex` (Codex) |
| Sadat (`sadattanzim01`) | Claude, Cursor | `Interstellar` (Claude) + `Interstellar-cursor` (Cursor) |
| Affan (`AffanSyed07`) | Codex | `Interstellar` |
| Zain (`Zain-Usmani10`) | none (FPGA by hand in Quartus) | `Interstellar` |

## 1. Install (once)
- **Git for Windows** (includes Git Bash)
- **GitHub CLI** `gh`: https://cli.github.com (check `gh --version` works *inside Git Bash*)
- Your agent(s), logged in to **your own** account

## 2. Get the repo
Accept the GitHub invite first (email or github.com/notifications). Then:
```
gh auth login
gh repo clone Zain-Usmani10/Interstellar
cd Interstellar
git switch dev
git config core.hooksPath .githooks       # turns on the "only commit your own folders" guard
```

## 3. Tell the board who you are (once per folder)
```
tools/board iam claude        # or codex / cursor; Zain: human
tools/board whoami            # should print e.g. ANaceri26/claude
tools/board read -n 10
```

## 4. Second agent on the same laptop (Abderrahmene, Sadat)
Never run two agents in the same folder. From inside `Interstellar`:
```
git worktree add -b codex-start ../Interstellar-codex origin/dev     # Abderrahmene
git worktree add -b cursor-start ../Interstellar-cursor origin/dev   # Sadat
cd ../Interstellar-codex          # or ../Interstellar-cursor
tools/board iam codex             # or: tools/board iam cursor
```
Open agent #1 in `Interstellar`, agent #2 in the new folder. Cursor users: set Cursor's default terminal to Git Bash.

## 5. Secrets
`cp .env.example .env` and fill in locally. `.env` is gitignored. Never commit or post keys.

## 6. Start your agent
Open `docs/plan/TEAM_AGENT_PROMPTS.md` and paste **your** prompt (section 5 = leader, 7 = ANaceri26 Codex, 8 = Sadat Claude, 9 = Sadat Cursor, 10 = Affan Codex). Add this line at the top:

> Read AGENTS.md first; it overrides the plan files on roles and git policy. Plan files are in docs/plan/, code goes under app/. Run `tools/board unread`, then post `[<login>'s <Agent>] online` on the board.

**Start the leader (`@ANaceri26/claude`) first.** It publishes the contracts and creates task issues; everyone else can begin bring-up meanwhile.

## 7. Task loop (one branch per task)
```
git fetch origin
git switch -c <issue#>-<slug> origin/dev    # e.g. 7-uart-status
# ...agent works, you test...
git add <your files only>
git commit -m "[area] what changed"
git pull --rebase origin dev
git push -u origin <issue#>-<slug>
```
Open a PR into `dev` (template fills in), post the link on the board. **The leader merges it**, not you.

## 8. Staying in the loop (always-on agents)
An agent only works while it answers a prompt. When its task is done it goes idle until something prompts it again. To keep agents answering each other without you typing:

- **Claude Code:** tell it once: "keep watching the board". It runs `tools/board wait --mentions-only` in the background and wakes itself when a post tags it.
- **Codex:** open a spare Git Bash window in that agent's folder and leave this running:
  ```
  tools/agent-loop codex
  ```
  It waits for a post tagging that agent, then runs `codex exec resume --last` with the post as the prompt, and repeats. (`tools/agent-loop claude` does the same with `claude -p --continue`.)
- **Cursor:** no outside trigger. When `tools/board wait --mentions-only` prints in a spare window, tell Cursor "check the board".

Before leaving an agent unattended:
- Allow its usual commands (git, gh, `tools/board`, tests) in that CLI's settings, or it stops at the first approval prompt. Extra CLI flags go in `AGENT_ARGS`.
- The loop never pulls or merges. Agents rebase at the start of each task (step 7).
- Agents post only when they have something to report. Merges into `dev` stay with the leader and its human.

## Rules to remember
- Only edit your own folders (`AGENTS.md` section 4). The pre-commit hook blocks the rest.
- Never commit or post API keys. Never commit EEG recordings.
- Judges can ask YOU to explain any code your agent wrote. Read it.
