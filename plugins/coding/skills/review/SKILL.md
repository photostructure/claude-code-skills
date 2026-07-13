---
name: review
description: Review code for potential issues and improvements. Use when asked to review specific files, functions, or code sections.
---

# Code Review

> Documented in depth: [Most AI code reviews are noise. Here's how to fix that.](https://photostructure.com/coding/claude-code-review/)

Review the mentioned code for potential issues and improvements.

Review critically — don't assume correctness. Question every design choice and flag anything that would fail a production code review. Assume any prior git state or file contents you gathered is stale, especially if the user re-runs this skill or asks you to re-read.

## Before you start

Study the project's coding standards and design principles — start with
`AGENTS.md`, then honor `CLAUDE.md` and relevant design docs when present.

**Only report verified bugs — things that are actually wrong.** Do NOT report:

- Style, organization, or naming preferences
- Speculative future risks ("if someone later removes this guard...")
- Feature requests or suggestions disguised as issues
- Things you haven't proven with concrete evidence from the codebase
- Anything a linter, typechecker, or compiler will catch — CI handles those
- Issues the code explicitly silences (`// eslint-disable`, `# noqa`) — the author already made that call
- Real issues on lines the change does not touch — out of scope

For EVERY potential issue, you MUST complete these steps before reporting:

1. **Read the actual code** (not just the diff) — follow the full call chain
2. **Search for all callers/usages** to understand context
3. **Read any design docs or plans** that explain the rationale
4. **Construct a concrete failing scenario** — if you can't describe exactly how the bug manifests, it's not an issue
5. **Discard it** if your research shows it's intentional or already handled

**When subagents are available, use them along two axes: perspective and mode.**

Perspectives (run in parallel, one subagent each):

- **Repository-guidance compliance** — audit the change against `AGENTS.md`,
  optional `CLAUDE.md`, and the project's written design principles
- **Shallow bug scan** — read just the diff and flag obvious logic errors, off-by-ones, missing awaits, etc.
- **Historical context** — `git blame` and `git log` on the changed lines. Understand *why* the code is the way it is before suggesting it should be different. Check prior PR comments on the same files; past review consensus often still applies
- **In-code constraints** — read comments adjacent to the change. They often spell out invariants the diff alone doesn't reveal

Modes:

- **Exploration**: When more than three files need review, or the code is complex, launch Explore subagents (one per file/area) to gather findings
- **Validation**: Before reporting ANY issue, launch a subagent to verify it — have it trace the full call chain, search for guards/handlers you might have missed, and read the relevant design docs. If the subagent can't confirm the bug, discard the issue
- **Iteration**: After your initial analysis, launch a second round of subagents to dig deeper into the most promising findings — check edge cases, race conditions, and interaction effects between the changed files

If you find zero real issues after thorough research, say "No issues found." Do not pad the list.

## What to look for

**Correctness**

- Logic or implementation errors
- If correct but surprising, suggest a clearer equivalent or a comment
- Don't trust docs or implementation as authoritative — if they disagree, flag it, consider what you think is correct (it may be neither!), and explain your reasoning

**Code quality**

- Violations of the project's design principles or coding standards
- Dead code (suggest deleting it)
- Comments that merely restate the function name (suggest removing)

**Testing gaps**

- Missing coverage for critical paths or edge cases

## Response format

1. Completely omit any issues that are irrelevant after research and analysis.
2. Sort remaining issues by severity (Critical > High > Medium > Low).

**Step 1 — write up every issue as text first.** For each issue use a short ID (e.g. `#A`, `#B`) and include:

- **Priority**: Critical / High / Medium / Low
- **Problem**: What's wrong, why, and the concrete scenario where it fails
- **Proof**: The specific code path or test that demonstrates the bug
- **Solution**: A concrete fix
- **Location**: File and line reference

**Step 2 — only after all issue blocks are written**, ask the user normally
whether to accept, veto, or comment on each one. Refer to the short IDs, but do
not use an ID-only question as a substitute for the write-up above.

A review request is read-only: do not implement fixes merely because you found
an issue. Apply a fix and run its validation only after the user explicitly
authorizes that change.

## Adapting for your project

- Replace "the project's coding standards and design principles" with explicit
  paths (`AGENTS.md`, optional `CLAUDE.md`, `docs/DESIGN-PRINCIPLES.md`, etc.).
- Add project-specific "what to look for" items (e.g. "new public APIs have rate limiting", "DB queries use parameterized inputs", "error messages don't leak internal paths").
- Tune the exclusion list if your team *does* want style or refactor feedback. The default is strict because noise is the bigger problem.
