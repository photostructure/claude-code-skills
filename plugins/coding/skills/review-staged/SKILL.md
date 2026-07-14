---
name: review-staged
description: Top-level, user-facing workflow to review the staged Git diff for verified bugs and then prepare a clean Conventional Commit. Use when the user directly asks to review staged changes or prepare their commit. Do not use for a delegated leaf review or finding-validation task.
---

# Review Git Staged Changes

> Documented in depth: [Most AI code reviews are noise. Here's how to fix that.](https://photostructure.com/coding/claude-code-review/)

Review the **staged** diff (`git diff --cached`) for potential issues and improvements.

## Leaf-mode guard

If the task identifies your role as `leaf-reviewer` or sets
`delegation-budget: 0`, read and follow
[`../review/references/single-pass.md`](../review/references/single-pass.md),
complete one review yourself, return the report to the caller, and stop before
the commit flow below.

Review critically — don't assume correctness. Question every design choice and flag anything that would fail a production code review. Assume any prior git state and file contents you gathered is stale, especially if the user re-runs this skill or asks you to re-read.

## Before you start

Study the project's coding standards and design principles — start with
`AGENTS.md`, then honor `CLAUDE.md` and relevant design docs when present.

Apply the scope, verification, and exclusion rules in
[`../review/references/single-pass.md`](../review/references/single-pass.md)
while performing the primary staged-diff review yourself. Use the top-level
response and commit-flow rules below instead of the reference's leaf return
behavior.

### Bounded delegation

Use at most **two** additional leaf-review tasks for the entire review: one
exploration pass for a large or complex staged diff and one batched validation
pass for all surviving candidates. Do not launch one task per file or finding,
and do not launch a second iteration round.

If the current host exposes the tool-restricted `coding:reviewer` agent, use it.
Otherwise use a general task-local subagent. Start each leaf prompt with
`role: leaf-reviewer` and `delegation-budget: 0`, point it at the resolved path
of `<plugin-root>/skills/review/references/single-pass.md`, omit workflow skill
names, and require one final report. When context inheritance is configurable,
do not pass the surrounding conversation. When no leaf mechanism is available,
perform the same work yourself.

Also decide whether the staged diff tells one coherent story. If not, recommend
how to split it before committing.

If you find zero real issues after thorough research, say "No issues found" — do not pad the list.

## What to look for

**Correctness**

- Logic or implementation errors; if correct but surprising, suggest a clearer equivalent or add a comment
- Don't trust docs or implementation as authoritative — if they disagree, flag it, consider what you think is correct (it may be neither!), and explain your reasoning

**Code quality**

- Violations of the project's design principles or coding standards
- Doc comments that have drifted from the implementation, or that merely restate the function name (suggest removing)
- Dead code — suggest deleting it

**Testing & documentation**

- Missing coverage for critical paths or edge cases
- Test fixture updates if needed

## Response format

1. Discard any issues that turned out to be noise after research.
2. Sort remaining issues by severity (Critical → High → Medium → Low).

**Step 1 — write up every issue as text first.** For each issue use a short unique ID (e.g. `#A`, `#B`) and include:

- **Priority**: Critical / High / Medium / Low
- **Problem**: What's wrong and the concrete scenario where it fails
- **Proof**: The specific code path or test that demonstrates the bug
- **Solution**: A concrete fix
- **Location**: File and line reference

**Step 2 — only after all issue blocks are written**, ask the user normally for
accept/veto decisions. Refer to the short IDs, but do not use an ID-only
question as a substitute for the write-up above. Do not implement accepted
fixes until the user explicitly authorizes the edits.

## Post-review commit flow

Do NOT commit directly after the review. Follow these steps in order:

1. List the files (and line ranges, if partial) that are staged for commit.
2. Compose a [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) message and ask the user to review or edit it before committing.
   - **Focus on the _why_, not the _what_** — the diff already shows what changed. One sentence on motivation or consequence beats a list of renamed files.
3. Only commit after explicit user approval.
