---
name: code-writing-software-development
description: Write, edit, refactor, and understand code across any language or framework. Use when the user wants to implement features, fix bugs, refactor code, or get coding assistance. Synthesizes best practices from Anthropic Claude Code, Cursor, Windsurf, Augment Code, Cline, Kiro, and others.
---

# Code Writing & Software Development Skill

---

## 1. Read Before You Edit

Never modify a file you have not read in the current session. Before making any edit:

- Read the target file fully to understand its current content, structure, and conventions.
- Read neighboring files (same directory, same module) to understand patterns, naming conventions, and framework choices.
- If the file is large, read the relevant sections (imports, the function/class to be changed, and adjacent code).
- If you edited a file earlier but more than a few exchanges have passed, re-read it before editing again.
- Never guess at file contents; always verify with tools.

**Rule:** Read → Understand → Edit. Never edit blind.

---

## 2. Understand the Codebase Before Acting

For any non-trivial task, do a discovery pass before writing a single line of code:

- Search broadly first (architecture, entry points, module structure) then narrow to specifics.
- Use glob/file search to locate relevant files; use grep/search to find specific symbols, patterns, or usages.
- Check the dependency manifest (`package.json`, `requirements.txt`, `Cargo.toml`, `go.mod`, etc.) before assuming any library is available.
- Look at git history or existing similar implementations to understand how the team has solved related problems.
- When in doubt about how something is connected, search for all call sites before changing a function signature.

**Rule:** Bias toward gathering information rather than guessing. Use tools extensively, in parallel where possible.

---

## 3. Follow Existing Conventions — Do Not Impose New Ones

When editing an existing codebase, mirror its style exactly:

- Match indentation style, naming conventions (camelCase/snake_case/PascalCase), import ordering, file and folder naming.
- Match the existing patterns for error handling, logging, and state management.
- Use the same libraries and utilities already in use.
- When adding a new component, function, or module, look at two or three existing examples first and make yours consistent with them.
- Do not reformat code that is not part of your change.

**Rule:** Be a skilled new team member joining an established project — blend in, do not rewrite the culture.

---

## 4. Code Quality Standards

Write code that a senior engineer would be proud to review.

**Naming:** Use full, descriptive names. Functions should be verbs or verb-phrases (`fetchUserData`). Variables should be nouns (`userList`). Avoid non-standard abbreviations.

**Control flow:** Use guard clauses and early returns. Keep nesting to 2–3 levels maximum. Handle error and edge cases first.

**Comments:** Explain *why*, not *what*. Use language-specific docstrings for public APIs. Never leave TODO comments — implement or create a tracked issue.

**Type safety:** Annotate all function signatures and public APIs explicitly. Avoid `any`, unsafe casts, or type assertions unless justified with a comment.

**No duplication:** Before writing new logic, search for existing utilities. Extract repeated patterns into shared functions.

**KISS / YAGNI:** Prefer the simplest solution that works. Do not build features before they are needed. Add complexity only when required.

**Immutability:** Prefer immutable data structures and pure functions. Use spread operators (`{ ...obj }`, `[...arr]`) over direct mutation.

**Named constants:** Replace magic numbers and strings with named constants (`MAX_RETRY_COUNT = 3`).

---

## 5. Code Quality Auditing (Plankton / QA Patterns)

Use write-time enforcement and auditing to catch issues as they are introduced, not just at review time.

**Code smell detection — flag these patterns immediately:**
- Functions longer than ~50 lines (split them)
- Nesting deeper than 3 levels (apply early returns)
- Magic numbers or unexplained string literals (name them)
- `any` types in TypeScript (replace with proper types)
- Direct state mutation (use spread / immutable updates)
- Missing error handling in async functions
- `console.log` left in production paths

**Linting and formatting gates (run before marking a task done):**

```bash
# TypeScript / JavaScript
npx tsc --noEmit 2>&1 | head -30
npm run lint 2>&1 | head -30

# Python
ruff check . 2>&1 | head -30
```

**Config tamper guard:** Never modify linter configs (`.ruff.toml`, `biome.json`, `tsconfig.json`, `.eslintrc*`) to suppress violations. Fix the code instead. If a config change is genuinely needed, flag it explicitly for review.

**Package manager enforcement:**
- JS/TS: prefer `bun`; use `npm`/`yarn`/`pnpm` only when the project requires it
- Python: prefer `uv`; avoid `pip` / `poetry` / `pipenv` unless the project requires it

---

## 6. Verification Loop (QA Gate System)

Run this gate after completing a feature, before creating a PR, or after significant refactoring.

**Phase 1 — Build:**
```bash
npm run build 2>&1 | tail -20
```
If build fails, stop and fix before continuing.

**Phase 2 — Type check:**
```bash
npx tsc --noEmit 2>&1 | head -30   # TypeScript
pyright . 2>&1 | head -30           # Python
```

**Phase 3 — Lint:**
```bash
npm run lint 2>&1 | head -30
ruff check . 2>&1 | head -30
```

**Phase 4 — Tests:**
```bash
npm run test -- --coverage 2>&1 | tail -50
# Target: 80% minimum coverage
```

**Phase 5 — Security scan:**
```bash
grep -rn "sk-\|api_key\|password" --include="*.ts" --include="*.js" src/ | head -10
grep -rn "console\.log" --include="*.ts" --include="*.tsx" src/ | head -10
```

**Phase 6 — Diff review:**
```bash
git diff --stat
git diff HEAD~1 --name-only
```
Review each changed file for unintended changes, missing error handling, and edge cases.

**Output format:**
```
VERIFICATION REPORT
==================
Build:     [PASS/FAIL]
Types:     [PASS/FAIL] (X errors)
Lint:      [PASS/FAIL] (X warnings)
Tests:     [PASS/FAIL] (X/Y passed, Z% coverage)
Security:  [PASS/FAIL] (X issues)
Diff:      [X files changed]

Overall:   [READY/NOT READY] for PR
```

Run verification at mental checkpoints: after completing each function, after finishing a component, before moving to the next task.

---

## 7. Regex vs LLM for Structured Text Parsing

**Rule:** Start with regex. Reserve LLM calls only for low-confidence edge cases.

**Decision framework:**
```
Is the text format consistent and repeating?
├── Yes (>90% follows a pattern) → Start with Regex
│   ├── Regex handles 95%+ → Done, no LLM needed
│   └── Regex handles <95% → Add LLM for edge cases only
└── No (free-form, highly variable) → Use LLM directly
```

**Hybrid pipeline:**
```
Source Text
    │
[Regex Parser] ─── Extracts structure (95-98% accuracy)
    │
[Confidence Scorer] ─── Flags low-confidence extractions
    │
    ├── High confidence (≥0.95) → Direct output
    └── Low confidence (<0.95) → [LLM Validator] → Output
```

**Confidence scoring — flag items when:**
- Fewer than expected choices/fields extracted
- Required fields are missing
- Text is abnormally short or malformed

**LLM validator:** Use the cheapest model available (Haiku-class) for validation. Pass the flagged item and original text; ask it to return corrected JSON or confirm accuracy.

**Real-world benchmark (410 items):** Regex success rate 98%, LLM calls needed ~5, cost savings vs all-LLM ~95%.

**Anti-patterns:**
- Sending all text to an LLM when regex handles 95%+ (expensive and slow)
- Using regex for free-form, highly variable text
- Skipping confidence scoring and hoping regex "just works"
- Mutating parsed objects during cleaning/validation steps

**Use for:** quiz/exam parsing, form data extraction, invoice/receipt processing, document structure parsing, any structured text with repeating patterns where cost matters.

---

## 8. Multi-File Operations

When a task spans multiple files:

- Plan all changes before starting. Identify every file that needs to change and in what order.
- Make changes in a logical sequence: data models first, then business logic, then API/interface layer, then UI.
- After renaming a symbol, search the entire codebase for all usages and update them all.
- When adding a new export to a module, check whether an index/barrel file needs to be updated.
- Run search-and-replace for renamed identifiers rather than editing files one by one manually.

**Rule:** A multi-file change is only complete when every affected file is consistent with every other affected file.

---

## 9. Error Handling and Iteration

- Address the root cause, not the symptom. Never mask errors with broad catches or silent fallbacks.
- Add descriptive error messages that include context (what was being attempted, what value was unexpected).
- If a command or test fails, read the full error output before attempting a fix.
- Do not loop on the same fix attempt more than 3 times. Stop and explain the situation; ask for guidance.
- When debugging, add targeted logging or assertions to isolate the problem, then remove them after the fix.
- When a linter error is introduced by your change, fix it before considering the task done.

---

## 10. Testing Considerations

- Before running tests, discover how the project's test suite works: check README, package.json scripts, Makefile, or CI config.
- When adding a new function or module, suggest or write accompanying unit tests.
- When fixing a bug, consider whether a test should be added that would have caught it.
- Write tests that test behavior, not implementation details. Tests should survive internal refactors.
- Use the AAA pattern: Arrange, Act, Assert. Use descriptive test names (`returns empty array when no markets match query`).
- Do not run tests automatically unless the user has asked, or it is clearly part of their workflow.

---

## 11. Security Practices

**Rule:** For any feature touching auth, input, secrets, or APIs — load and follow the `security-review` skill.

---

## 12. Package and Dependency Management

- Always use the project's package manager to add or remove dependencies — never manually edit lock files.
- When choosing a package version, prefer the version already in use across the project.
- If an external library is not already in the project, ask yourself whether the standard library or an existing dependency covers the need.

---

## 13. Refactoring Patterns

- Refactor in small, isolated steps. Each step should leave the code working and tests passing.
- Separate refactoring commits from behavior-change commits — do not mix the two.
- Apply the "Boy Scout Rule": leave code slightly cleaner than you found it, but do not over-scope.
- Never refactor code in a way that changes observable behavior without clearly flagging this to the user.

---

## 14. Git Awareness

- Never commit changes unless the user explicitly asks you to commit. This is non-negotiable.
- Never amend, force-push, or rebase unless the user explicitly requests it.
- Never run destructive git operations without explicit user instruction.
- When suggesting a commit, write a concise, meaningful commit message: imperative mood, short subject line.

---

## 15. When to Ask vs. When to Proceed

**Proceed without asking when:** the task is clearly scoped, you can discover necessary information through tools, the change is low-risk and easily reversible.

**Stop and ask when:** intent is genuinely ambiguous, a destructive or irreversible action is required, you are about to take action with significant scope beyond what was asked, you have tried 2–3 approaches and none have worked, or required information cannot be found through tools.

**Rule:** Use tools to find answers before asking the user. Ask only when tools cannot provide the answer.

---

## 16. Communication and Response Style

Be concise. Lead with the action, not the preamble. Use backticks for identifiers, fenced code blocks for code. Do not narrate tool usage.

---

## 17. Generated Code Must Work Immediately

- Include all necessary import statements. Never produce code with missing imports.
- Include all required dependencies and note if new packages need to be installed.
- Handle all edge cases that are obvious from context.
- For very large changes (300+ lines), break them into multiple logical edits rather than one giant replacement.
- After implementing, if lint/type commands are known, run them to verify correctness before reporting completion.

---

## 18. Language-Agnostic Best Practices

- **Separation of concerns:** Keep data access, business logic, and presentation in separate layers.
- **Single responsibility:** Each function, class, and module should do one thing well.
- **Fail fast:** Validate inputs early. Do not let invalid data propagate deep into the system.
- **Consistent error handling:** Use the project's established error handling pattern throughout.
- **Accessibility (UI code):** Use semantic HTML, proper ARIA attributes, descriptive alt text, keyboard navigability. Minimum 44px touch targets.
- **Responsive design (UI code):** Design mobile-first. Use responsive breakpoints. Never hardcode pixel widths for layout.
- **Performance awareness:** Avoid unnecessary re-computation in loops, N+1 query patterns, and blocking operations on the main thread.

---

## Quick Reference Checklist

Before starting any coding task:
- [ ] Do I understand the full scope of what's being asked?
- [ ] Have I read the files I plan to modify?
- [ ] Have I checked the existing conventions (naming, patterns, libraries)?
- [ ] Have I verified that libraries/frameworks I plan to use are already in the project?

Before completing any coding task:
- [ ] Does the code follow existing style and conventions?
- [ ] Are all import statements present and correct?
- [ ] Are there any hardcoded secrets, SQL injection risks, or XSS vectors?
- [ ] Have I updated all call sites if I changed a function signature?
- [ ] Have I run (or suggested running) the verification loop (build, types, lint, tests)?
- [ ] Is there anything I should flag to the user before finishing?
