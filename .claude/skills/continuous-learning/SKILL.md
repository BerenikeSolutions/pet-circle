---
name: continuous-learning
description: Extract reusable instincts from Claude Code sessions via hooks, score them by confidence, and evolve them into skills, commands, or agents.
---

# Continuous Learning

---

## 1. Observation Hooks

Use `PreToolUse` and `PostToolUse` hooks — never rely on skills to observe. Hooks fire 100% of the time; skills fire only 50–80%.

Register `observe.sh` for both hook events in `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse":  [{ "matcher": "*", "hooks": [{ "type": "command", "command": "~/.claude/skills/continuous-learning-v2/hooks/observe.sh" }] }],
    "PostToolUse": [{ "matcher": "*", "hooks": [{ "type": "command", "command": "~/.claude/skills/continuous-learning-v2/hooks/observe.sh" }] }]
  }
}
```

**Rule:** Never use a Stop hook as the sole observation point — it misses mid-session patterns.

---

## 2. Project Detection (v2.1)

Detect project context in this priority order:

1. `CLAUDE_PROJECT_DIR` env var (highest priority)
2. `git remote get-url origin` — hashed to 12 chars, portable across machines
3. `git rev-parse --show-toplevel` — fallback, machine-specific
4. Global scope — when no project is detected

Store project instincts under `~/.claude/homunculus/projects/<hash>/instincts/`, global instincts under `~/.claude/homunculus/instincts/personal/`.

**Rule:** Default new instincts to project scope; only promote to global when seen in 2+ projects.

---

## 3. Instinct Lifecycle

Move instincts through four stages: **observe → extract → validate → promote**.

| Stage | Action |
|---|---|
| Observe | Hook captures tool calls, prompts, outcomes, project context |
| Extract | Background observer (Haiku) detects user corrections, repeated patterns, error resolutions |
| Validate | Confidence rises with repeated confirmation; falls with user corrections |
| Promote | Project instinct with avg confidence ≥ 0.8 in 2+ projects → promote to global |

Each instinct is atomic: one trigger, one action, one domain tag (code-style, testing, git, debugging, workflow).

---

## 4. Confidence Scoring

Score every instinct on a 0.3–0.9 scale:

| Score | Meaning | Behavior |
|---|---|---|
| 0.3 | Tentative | Suggested, not enforced |
| 0.5 | Moderate | Applied when relevant |
| 0.7 | Strong | Auto-approved |
| 0.9 | Near-certain | Core behavior |

Increase confidence when the pattern recurs without correction. Decrease when the user explicitly contradicts it or it goes unobserved for extended periods.

**Rule:** Never hard-code an instinct at 0.9 from first observation — require at least 3 confirming occurrences.

---

## 5. Scope Decision Guide

| Pattern Type | Scope |
|---|---|
| Language/framework conventions, file structure, code style, error handling | project |
| Security practices, general best practices, git conventions, tool workflow | global |

---

## 6. Instinct Commands

```
/instinct-status    — Show all instincts (project + global) with confidence scores
/evolve             — Cluster related instincts into skills, commands, or agents
/instinct-export    — Export instincts (filterable by scope/domain)
/instinct-import    — Import instincts from a file
/promote [id]       — Promote a project instinct to global scope
/projects           — List all known projects and their instinct counts
```

Run `/evolve` after accumulating 10+ instincts in a domain to cluster them into a reusable skill.

---

## 7. Storage Layout

```
~/.claude/homunculus/
  projects.json                         # Registry: hash → name/path/remote
  instincts/personal/                   # Global auto-learned instincts
  instincts/inherited/                  # Global imported instincts
  evolved/{agents,skills,commands}/     # Global evolved artifacts
  projects/<hash>/
    project.json
    observations.jsonl
    instincts/personal/                 # Project-scoped instincts
    evolved/{skills,commands,agents}/
```

**Rule:** Never store raw conversation content in instincts — store only the extracted pattern.

---

## 8. Anti-Patterns

- Do not mix v1 Stop-hook sessions with v2 without running both in parallel during transition.
- Do not auto-promote instincts below 0.8 average confidence.
- Do not create instincts for one-time fixes, simple typos, or external API issues.
- Do not edit an instinct's confidence manually without evidence.
