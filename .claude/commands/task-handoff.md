---
description: Mark the current task complete, update the task file with handoff notes, advance the Active Feature pointer in CLAUDE.md to the next task, and commit.
---

Complete the current task and hand off to the next one.

## Steps

1. **Verify the task is done** — run `/verify` if not already done. All 6 phases must pass (or failures must be documented with a reason).

2. **Read the current task file** — find it from `## Active Feature > Current task:` in `.claude/CLAUDE.md`.

3. **Update the task file handoff sections:**
   ```
   ## Handoff — What Was Done
   [1–3 bullet points: what was implemented, key decisions made]

   ## Handoff — Patterns Learned
   [Any conventions discovered, gotchas, or patterns the next session should know]

   ## Handoff — Files Changed
   [List of files created or modified]

   ## Status
   COMPLETE
   ```

4. **Determine the next task** — look at `.spec/tasks/` (or `.spec/<feature>/tasks/`) for the next `task-NNN.md` file in sequence.

5. **Update `.claude/CLAUDE.md`** — change the `Current task:` line under `## Active Feature` to point to the next task file. If there is no next task, write `Current task: ALL TASKS COMPLETE`.

6. **Update `bug-log.md`** — if any bugs were encountered and fixed during this task, append an entry:
   `## [YYYY-MM-DD] title | What broke: … | Root cause: … | Fix: … | File(s): …`

7. **Commit** — stage all changed files and commit with a conventional commit message:
   `feat: complete <task-name> — <one-line summary>`

8. **Tell the user** — state the next task file path and one-line summary of what it contains.
