---
name: review
description: Top-level, user-facing code-review workflow for verified issues in specific files, functions, diffs, or code sections. Use when the user directly requests a review and may need to adjudicate its findings. Do not use as an orchestrator for a delegated leaf review or finding-validation task.
---

# Code Review

> Documented in depth: [Most AI code reviews are noise. Here's how to fix that.](https://photostructure.com/coding/claude-code-review/)

Review the mentioned code for potential issues and improvements.

## Leaf-mode guard

If the task identifies your role as `leaf-reviewer` or sets
`delegation-budget: 0`, read and follow
[`references/single-pass.md`](./references/single-pass.md), complete one review
yourself, return the report to the caller, and stop before the orchestration and
user-interaction steps below.

Review critically — don't assume correctness. Question every design choice and flag anything that would fail a production code review. Assume any prior git state or file contents you gathered is stale, especially if the user re-runs this skill or asks you to re-read.

## Before you start

Study the project's coding standards and design principles — start with
`AGENTS.md`, then honor `CLAUDE.md` and relevant design docs when present.

Apply the scope, verification, and exclusion rules in
[`references/single-pass.md`](./references/single-pass.md) while performing the
primary review yourself. Use the top-level response and user-interaction rules
below instead of the reference's leaf return behavior.

### Bounded delegation

Use at most **two** additional leaf-review tasks for the entire review. Do not
launch one task per file or per finding, and do not launch a second iteration
round.

- For a large or complex change, use one leaf to cover a coherent file group or
  a distinct perspective such as repository-guidance compliance or historical
  context.
- If candidates survive your own pass, use one leaf to validate all candidates
  together, explicitly asking it to disprove them by tracing missed guards,
  callers, and design constraints.

If the current host exposes the tool-restricted `coding:reviewer` agent, use it.
Otherwise use a general task-local subagent. Start every leaf prompt with
`role: leaf-reviewer` and `delegation-budget: 0`, point it at the resolved path
of `<plugin-root>/skills/review/references/single-pass.md`, and do not include
workflow skill names in the prompt. When context inheritance is configurable,
do not pass the surrounding conversation. When no leaf mechanism is available,
perform the same exploration and validation yourself.

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
