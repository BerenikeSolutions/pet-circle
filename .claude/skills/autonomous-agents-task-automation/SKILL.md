---
name: autonomous-agents-task-automation
description: Execute long, multi-step tasks autonomously using planning, memory, loop architectures, parallel orchestration, and multi-agent delegation. Use when independently completing complex tasks involving research, coding, file operations, or multi-stage workflows.
---

# Autonomous Agent Execution — Best Practices

---

## 1. Planning Before Execution

Before writing a single line of code or running any command, create an explicit plan.

- Analyze the full request and identify what the user actually wants (the goal), not just what they literally said (the surface request).
- Decompose the task into concrete, ordered steps. Each step must have a clear success condition and an independently verifiable done state — aim for units completable in roughly 15 minutes.
- Identify dependencies between steps. Steps that depend on each other must be ordered; steps that do not can run in parallel.
- Identify unknowns upfront. If critical information is missing (credentials, ambiguous requirements, API keys, access), ask the user before starting — not mid-task.
- Write out the plan as a numbered list before executing. Share it with the user briefly if the task is long or involves destructive operations.
- Distinguish between "planning mode" (information gathering, exploration, producing a plan) and "execution mode" (making changes). Do not conflate the two.
- Define explicit acceptance criteria before execution begins. Completion without measurable criteria is untestable.

**Rule:** The work plan is the single highest-leverage intervention point — a well-structured plan with clear acceptance criteria prevents most mid-task failures.

---

## 2. Loop Architecture Selection

Choose the right loop pattern before starting. From simplest to most sophisticated:

| Pattern | Complexity | Best For |
|---------|-----------|----------|
| Sequential Pipeline (`claude -p`) | Low | Daily dev steps, scripted workflows |
| NanoClaw REPL | Low | Interactive persistent sessions |
| Infinite Agentic Loop | Medium | Parallel content generation, spec-driven work |
| Continuous Claude PR Loop | Medium | Multi-day iterative projects with CI gates |
| dmux Parallel Workflows | Medium | Divide-and-conquer across independent files/domains |
| Ralphinho / RFC-DAG | High | Large features, multi-unit parallel work with merge queue |

**Decision flow:**

```
Single focused change?
├─ Yes → Sequential Pipeline or NanoClaw
└─ No → Written spec/RFC available?
         ├─ Yes → Need parallel implementation?
         │        ├─ Yes → Ralphinho (DAG orchestration)
         │        └─ No → Continuous Claude (iterative PR loop)
         └─ No → Need many variations of the same thing?
                  ├─ Yes → Infinite Agentic Loop
                  └─ No → Sequential Pipeline + de-sloppify
```

**Rule:** Match loop complexity to problem complexity. Ralphinho for single-file changes is overhead; a sequential pipeline for a multi-unit RFC will produce merge conflicts.

---

## 3. Sequential Pipeline Pattern

Break tasks into a sequence of focused, non-interactive `claude -p` calls. Each call is isolated — fresh context window, clear prompt, single concern.

```bash
#!/bin/bash
set -e

# Step 1: Implement
claude -p "Read the spec in docs/auth-spec.md. Implement OAuth2 login in src/auth/. Write tests first (TDD)."

# Step 2: De-sloppify (separate cleanup pass)
claude -p "Review all files changed by the previous commit. Remove unnecessary type tests, overly defensive checks, and tests of language features. Keep real business logic tests. Run the test suite after cleanup."

# Step 3: Verify
claude -p "Run the full build, lint, type check, and test suite. Fix any failures. Do not add new features."

# Step 4: Commit
claude -p "Create a conventional commit for all staged changes."
```

Key design principles:
- Each step is isolated — no context bleed between `claude -p` calls.
- Order matters — each step builds on the filesystem state left by the previous.
- Use `set -e` so exit codes propagate and halt the pipeline on failure.
- Avoid negative instructions in Implementer prompts ("don't do X"). Use a separate cleanup pass instead (see Section 5).
- Route models by task complexity: Haiku for narrow edits, Sonnet for implementation, Opus for architecture and root-cause analysis.

**Rule:** Two focused agents outperform one constrained agent. Never add negative instructions to restrict the Implementer — add a separate cleanup pass to remove what it over-produced.

---

## 4. NanoClaw REPL Pattern

Use NanoClaw for interactive, session-persistent workflows where context accumulates across turns.

```bash
# Start the default session
node scripts/claw.js

# Named session with skill context
CLAW_SESSION=my-project CLAW_SKILLS=tdd-workflow,security-review node scripts/claw.js
```

NanoClaw loads conversation history from `~/.claude/claw/{session}.md`, sends each user message to `claude -p` with full history as context, and appends responses to the session file (Markdown-as-database). Sessions persist across restarts.

Key commands: `/model` (switch model), `/load` (dynamic skill loading), `/branch` (branch before high-risk changes), `/compact` (compact after major milestones), `/search` (cross-session search), `/export` (export before archival).

| Use Case | NanoClaw | Sequential Pipeline |
|----------|----------|-------------------|
| Interactive exploration | Yes | No |
| Scripted automation | No | Yes |
| Session persistence | Built-in | Manual |
| Context accumulation | Grows per turn | Fresh each step |
| CI/CD integration | Poor | Excellent |

**Rule:** Keep NanoClaw sessions task-focused. Branch before high-risk changes. Compact after milestones, not during active debugging.

---

## 5. De-Sloppify Pattern

Add a dedicated cleanup pass after every Implementer step in any loop. This is an add-on, not a standalone pattern.

The problem: when asked to implement with TDD, an LLM writes tests that verify TypeScript's type system, framework behavior, or impossible runtime states — none of which test business logic. Adding negative instructions to the Implementer prompt causes it to skip legitimate edge case tests.

The solution: let the Implementer be thorough, then run a focused cleanup agent in a separate context window:

```bash
claude -p "Review all changes in the working tree. Remove:
- Tests that verify language/framework behavior rather than business logic
- Redundant type checks the type system already enforces
- Over-defensive error handling for impossible states
- console.log statements and commented-out code

Keep all business logic tests. Run the test suite after cleanup to confirm nothing breaks."
```

**Rule:** Always run de-sloppify as a separate `claude -p` invocation — never in the same context as the Implementer, and never via a negative constraint in the Implementer's prompt.

---

## 6. Infinite Agentic Loop Pattern

Use for specification-driven parallel generation of multiple independent outputs (variations, test cases, content pieces).

Architecture: an Orchestrator reads a spec, scans existing output for the highest iteration number, then deploys N Sub-Agents in parallel — each assigned a unique creative direction and iteration number.

Create `.claude/commands/infinite.md`:

```markdown
Parse from $ARGUMENTS: spec_file, output_dir, count (integer or "infinite").

PHASE 1: Read and deeply understand the specification.
PHASE 2: List output_dir, find highest iteration number. Start at N+1.
PHASE 3: Plan creative directions — each agent gets a DIFFERENT theme/approach.
PHASE 4: Deploy sub-agents in parallel (Task tool). Each receives:
  - Full spec text
  - Current directory snapshot
  - Their assigned iteration number
  - Their unique creative direction
PHASE 5 (infinite mode): Loop in waves of 3–5 until context is low.
```

Batching strategy: 1–5 items all at once; 6–20 in batches of 5; infinite in waves of 3–5 with progressive sophistication.

**Rule:** The Orchestrator assigns each agent a specific creative direction and iteration number — never rely on agents to self-differentiate. Assignment prevents duplicate concepts across parallel agents.

---

## 7. Continuous Claude PR Loop Pattern

Use for multi-day iterative projects requiring CI gate enforcement and automatic merge.

Core loop per iteration:
1. Create branch (`continuous-claude/iteration-N`)
2. Run `claude -p` with enhanced prompt
3. Optional reviewer pass (separate `claude -p`)
4. Commit changes
5. Push and create PR (`gh pr create`)
6. Wait for CI checks (`gh pr checks --watch`)
7. CI failure → auto-fix pass (`claude -p` with CI log context)
8. Merge PR (squash/merge/rebase)
9. Return to main and repeat

```bash
continuous-claude --prompt "Add unit tests for all untested functions" --max-runs 10
continuous-claude --prompt "Fix all linter errors" --max-cost 5.00
continuous-claude --prompt "Improve test coverage" --max-duration 8h
```

Cross-iteration context bridge — use `SHARED_TASK_NOTES.md` to persist progress across independent `claude -p` invocations:

```markdown
## Progress
- [x] Added tests for auth module (iteration 1)
- [ ] Still need: rate limiting tests, error boundary tests

## Next Steps
- Focus on rate limiting module next
```

Claude reads this file at iteration start and updates it at iteration end.

Completion signal: output `CONTINUOUS_CLAUDE_PROJECT_COMPLETE` three consecutive times to stop the loop automatically.

**Rule:** Always set at least one of `--max-runs`, `--max-cost`, or `--max-duration`. Unbounded loops are a cost and correctness failure mode.

---

## 8. dmux Parallel Workflows

Use dmux (tmux pane manager) to run multiple independent agent sessions simultaneously across different files, concerns, or AI harnesses.

```bash
# Start dmux session
dmux
# Press 'n' to create a new pane with a prompt
# Press 'm' to merge pane output back to main session
```

Common workflow patterns:

**Multi-file feature** — parallelize across independent files:
```
Pane 1: "Create the database schema and migrations for the billing feature"
Pane 2: "Build the billing API endpoints in src/api/billing/"
Pane 3: "Create the billing dashboard UI components"
# Merge all, then do integration in main pane
```

**Parallel review perspectives:**
```
Pane 1: "Review src/api/ for security vulnerabilities"
Pane 2: "Review src/api/ for performance issues"
Pane 3: "Review src/api/ for test coverage gaps"
```

**Cross-harness routing** — use different AI tools for different task types:
```
Pane 1 (Claude Code): "Review the security of the auth module"
Pane 2 (Codex): "Refactor the utility functions for performance"
```

For file-conflict-prone parallel work, use git worktrees per pane:
```bash
git worktree add -b feat/auth ../feature-auth HEAD
git worktree add -b feat/billing ../feature-billing HEAD
# Run agents in separate worktrees, then merge branches
```

Use the ECC orchestration helper for programmatic worktree setup:
```bash
node scripts/orchestrate-worktrees.js plan.json --execute
```

**Rule:** Only parallelize independent tasks. Each pane uses API tokens — keep total panes under 5–6. Use git worktrees whenever parallel agents might touch overlapping files.

---

## 9. Ralphinho / RFC-DAG Orchestration

Use for large features too big for a single agent pass. Decomposes an RFC into a dependency DAG, runs each unit through a tiered quality pipeline, and lands them via an agent-driven merge queue.

### Decomposition

AI reads the RFC and produces work units:

```
id           — kebab-case identifier
depends_on   — other unit IDs (real code dependencies only)
scope        — files and concerns touched
acceptance   — concrete, testable acceptance criteria
risk_level   — Tier 1 / Tier 2 / Tier 3
rollback_plan
```

Decomposition rules:
- Prefer fewer, cohesive units — minimizes merge risk.
- Minimize cross-unit file overlap — avoids conflicts.
- Keep tests WITH implementation — never separate "implement X" and "test X" into different units.
- Add dependencies only where a real code dependency exists.

The dependency DAG determines execution order:
```
Layer 0: [unit-a, unit-b]     ← no deps, run in parallel
Layer 1: [unit-c]             ← depends on unit-a
Layer 2: [unit-d, unit-e]     ← depend on unit-c
```

### Complexity Tiers

| Tier | Risk Level | Pipeline Stages |
|------|------------|----------------|
| Tier 1 / trivial | Isolated file edits | implement → test |
| Tier 2 / small | Multi-file behavior changes | implement → test → code-review |
| Tier 2 / medium | Moderate integration risk | research → plan → implement → test → PRD-review + code-review → review-fix |
| Tier 3 / large | Schema/auth/perf/security | research → plan → implement → test → PRD-review + code-review → review-fix → final-review |

### Separate Context Windows

Each pipeline stage runs in its own agent process to eliminate author bias:

| Stage | Model | Purpose |
|-------|-------|---------|
| Research | Sonnet | Read codebase + RFC, produce context doc |
| Plan | Opus | Design implementation steps |
| Implement | Sonnet/Codex | Write code following the plan |
| Test | Sonnet | Run build + test suite |
| PRD Review | Sonnet | Spec compliance check |
| Code Review | Opus | Quality + security check |
| Review Fix | Sonnet | Address review issues |
| Final Review | Opus | Quality gate (large tier only) |

The reviewer never wrote the code it reviews — this eliminates the most common source of missed issues.

### Merge Queue

After quality pipelines, units enter the merge queue:
1. Rebase onto main — conflict triggers eviction
2. Run build + tests — failure triggers eviction
3. Pass → fast-forward main, push, delete branch

Non-overlapping units land speculatively in parallel. Overlapping units land one-by-one with rebase between each.

When evicted, full context (conflicting files, diffs, test output) feeds back into the implementer on the next pass:

```markdown
## MERGE CONFLICT — RESOLVE BEFORE NEXT LANDING
Your previous implementation conflicted with a unit that landed first.
Restructure your changes to avoid the conflicting files/lines below.
{full eviction context with diffs}
```

### Data Flow Between Stages

```
research.contextFile ─────────────────→ plan
plan.implementationSteps ─────────────→ implement
implement.{filesCreated, whatWasDone} → test, reviews
test.failingSummary ──────────────────→ reviews, implement (next pass)
reviews.{feedback, issues} ──────────→ review-fix → implement (next pass)
evictionContext ──────────────────────→ implement (after merge conflict)
```

Outputs: RFC execution log, unit scorecards, dependency graph snapshot, integration risk summary.

**Rule:** The work plan (decomposed units with acceptance criteria) is the single highest-leverage human review point. Invest in it before any implementation begins.

---

## 10. Memory and State Management

Autonomous tasks are stateful. Treat state management as a first-class concern.

- Use files as external memory. Write progress notes, intermediate outputs, contracts, and plans to disk so they survive across steps and can be referenced later.
- Before starting a step, read any relevant files written in previous steps. Never rely purely on in-context memory for facts produced earlier.
- If building a multi-component system (frontend + backend + database), write a `contracts.md` file early: API contracts, what is mocked, what the backend must implement, and how integration works. This is the shared source of truth across all components.
- Track IDs, paths, configuration values, and artifacts explicitly. Never guess or reconstruct what a previous step produced.
- For loops with fresh context windows per iteration, use `SHARED_TASK_NOTES.md` as the cross-iteration context bridge.
- Repeat your plan or current phase summary periodically in your reasoning when context windows are long — the earliest messages may be effectively truncated.

**Rule:** Write critical state to files, not only to context. Files survive context truncation; context does not.

---

## 11. Model Routing and Cost Discipline

| Model | Use For |
|-------|---------|
| Haiku | Classification, boilerplate transforms, narrow edits, formatting |
| Sonnet | Implementation, refactors, research, test runs |
| Opus | Architecture decisions, root-cause analysis, security review, multi-file invariants |

**Rule:** Escalate model tier only on demonstrated reasoning failure. Haiku for narrow edits, Opus for architectural decisions — never the reverse.

---

## 12. Parallel Execution

Speed up execution by identifying what can run concurrently.

- At each planning step, explicitly identify which steps have no dependencies on each other — those can run in parallel.
- Parallelizable patterns: searching multiple sources simultaneously, reading multiple files needed for the same task, running independent test suites, building frontend and writing API contracts simultaneously.
- When issuing multiple tool calls, batch independent calls in a single response turn rather than sequentially.
- For sub-agent delegation, launch multiple sub-agents simultaneously when they do not depend on each other's output.
- Be conservative about parallelizing writes. Sequential reads are always safe to parallelize; writes to the same resource must be carefully ordered.
- When two parallel agents might touch the same files, use git worktrees to isolate them.

**Rule:** Be conservative about parallelizing writes. Parallel reads are always safe; parallel writes to the same resource require explicit isolation via worktrees or sequential landing.

---

## 13. Error Recovery

Errors are expected in autonomous execution. Respond to them systematically, not reactively.

- When an error occurs, stop and read the full error message before acting. Do not immediately retry the same operation.
- Distinguish between: transient errors (retry once), configuration errors (fix the root cause), and environmental errors (report to user and work around).
- Categorize before acting: code bug, environment issue, missing dependency, wrong assumption, API error, permissions issue.
- Apply the fix at the root cause, not at the symptom. Patching around an error without understanding it creates cascading problems.
- After fixing, verify the fix actually resolved the problem. Run the relevant test or check again.
- If a fix introduces a new error, step back and reconsider the approach from the prior stable state — do not keep patching forward.
- If three consecutive attempts at a sub-problem fail, pause and ask the user for guidance. Do not keep spinning.
- Never modify tests to make them pass. If tests fail, the bug is in the code under test.
- Use web search to escape error loops — searching for the actual error message often surfaces a solution faster than reasoning from memory alone.
- Environmental failures (broken environment, missing system dependencies) should be reported to the user, not fixed autonomously. Find a workaround path instead.

For looping workflows, when a unit stalls: evict from the active queue, snapshot all findings and error context, regenerate a narrowed unit scope, and retry with updated constraints.

**Rule:** Log what was tried and why it failed. This prevents re-attempting the same failed approaches and provides context for intelligent recovery.

---

## 14. When to Pause vs. Proceed

Good autonomous behavior is not always proceeding without stopping. Know when to pause.

**Always pause and ask the user before:**
- Performing irreversible or destructive operations (deleting files, dropping data, force-pushing, sending emails, making purchases).
- Mocking data or using a placeholder when real data or a real API key was expected.
- Hitting a blocker where the only paths forward require a decision only the user can make.
- Needing credentials, API keys, or permissions that have not been provided.
- Requirements are genuinely ambiguous and the wrong interpretation would waste significant effort.

**Proceed autonomously when:**
- The next step follows logically from prior steps and the user's stated intent.
- A reasonable default exists and the cost of being wrong is low.
- The user has explicitly said to proceed without checking in.
- The information needed can be found through available tools without needing the user.

**Rule:** Ask once, upfront, for everything critical. Mid-task interruptions for things that could have been identified in planning are a failure of the planning step.

---

## 15. Tool Orchestration

Choose tools strategically. The right tool for the right job.

- Always prefer dedicated tools over shell workarounds. If a tool exists for a task (reading a file, searching, editing), use it instead of a shell command equivalent.
- Never use shell commands to view, create, or edit files when read/write/edit tools are available.
- Never use grep or find in a shell when a content-search or file-search tool is available.
- For web information, always visit the actual page rather than guessing or relying on training knowledge.
- When multiple data sources might contain the answer, search them in parallel rather than sequentially.
- Choose the least-powerful tool that accomplishes the goal. Avoid side-effect-producing commands when a read-only tool suffices.
- When calling sub-agents or delegating to task tools, communicate the goal and context — not a step-by-step script. Over-specifying instructions degrades agent performance.
- Verify that libraries and dependencies actually exist in the project before using them. Check `package.json`, `requirements.txt`, or equivalent — never assume a library is available.

**Rule:** Communicate goal and context to sub-agents, not scripts. Over-specified delegation produces brittle agents; under-specified delegation produces correct ones.

---

## 16. Verification and Testing

Never declare a task complete without verifying it actually works.

- After writing code, run it (or run the relevant tests). Do not assume correctness from inspection alone.
- Run linters and static checks if the project has them configured.
- Test the specific behavior the user asked for, not just that the code runs without crashing.
- For integrations, verify the integration works end-to-end with real data, not just that the code compiles.
- For AI-generated code, raise the testing bar: require regression coverage for touched domains, explicit edge-case assertions, and integration checks for interface boundaries.
- Before reporting completion, critically examine your work: did you actually fulfill the user's request and intent? Did you complete all verification steps? Did you edit all locations that needed changing?
- If verification reveals a bug, fix it in the same task rather than reporting completion and leaving the bug for the user to find.

In AI-first workflows, review generated code for: behavior regressions, security assumptions, data integrity, failure handling, and rollout safety. Minimize time spent on style issues already covered by automated formatting/lint.

**Rule:** Verification is not optional. A task completed but not verified is a task not completed.

---

## 17. Progress Reporting

Keep the user informed without creating noise.

- At the start of a complex task, share a concise plan (what you will do, in what order).
- After completing each major phase, emit a brief status update: what was done, what is next.
- When you hit a significant decision point, name it: "I found two approaches. I'm going with X because Y."
- Do not narrate every micro-action. Report at the phase level, not the keystroke level.
- If a task is taking longer than expected, say so and explain why.
- At the end of the task, provide a concise summary: what was built/done, what was mocked or approximated, and what the user should verify.
- Acknowledge mistakes or backtracking openly: "I tried X, which didn't work because Y. I'm now doing Z instead."
- Always use the same language the user used when communicating progress.

**Rule:** Summaries should be under 100 words, high-signal, and always mention any mocking or approximation.

---

## 18. Loop Termination Conditions

Know when to stop. Infinite loops without exit conditions are a failure mode.

A task is complete when ALL of the following are true:
1. Every step in the plan has been executed.
2. The output has been verified against the original requirements and acceptance criteria.
3. All tests, linters, and checks pass (or known failures are explicitly documented and accepted).
4. The user has been given a clear summary of what was done, what was approximated or mocked, and what they should verify.

Stop early and ask the user when:
- The task has become undefined or requirements have changed in a way that makes the current plan invalid.
- Three or more consecutive attempts at a sub-problem have failed and no new approach is evident.
- A required resource (API key, credential, permission, external service) is unavailable and no workaround exists.
- The correct next action requires a decision only the user can make.

Do NOT continue looping when:
- You are making fixes to issues already resolved.
- You are adding features or polish that were not requested.
- You are running the same failing command repeatedly hoping for a different result.
- The task was completed but you are second-guessing whether the user is satisfied.

**Rule:** Set at least one hard exit condition (max-runs, max-cost, max-duration, or completion signal) for every automated loop before starting it.

---

## 19. Data Security

**Rule:** Never commit, log, or expose secrets/credentials. For external communication (email, API calls, webhooks), confirm with the user before sending.

---

## Quick Reference: Decision Checklist

Before each major action, ask yourself:

- Do I have all the information I need, or am I about to guess?
- Is this action reversible? If not, have I confirmed with the user?
- Am I at the right step in my plan, or have I drifted?
- Have I checked what already exists before creating something new?
- Can this step be parallelized with others currently in progress?
- Will I be able to verify this action's success after completing it?
- If this fails, do I have a recovery plan?
- Am I using the right loop pattern for the complexity of this task?
- Have I set exit conditions on any automated loop I'm starting?
