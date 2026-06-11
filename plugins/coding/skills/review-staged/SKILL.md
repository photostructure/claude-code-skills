---
name: review-staged
description: Review the git staged diff for verified bugs before committing, then drive a clean Conventional Commit.
allowed-tools: Bash, Read, Glob, Grep, Edit, Write, WebSearch
---

# Review Git Staged Changes

Review the **staged** diff (`git diff --cached`) for potential issues and improvements.

Review critically — don't assume correctness. Question every design choice and flag anything that would fail a production code review. Assume any prior git state and file contents you gathered is stale, especially if the user re-runs this skill or asks you to re-read.

## Before you start

Study the project's coding standards and design principles — e.g. `CLAUDE.md`, `AGENTS.md`, or design docs in the repo, if present.

**Only report verified bugs — things that are actually wrong.** Do NOT report:

- Style, organization, or naming preferences
- Speculative future risks ("if someone later removes this guard...")
- Feature requests or suggestions disguised as issues
- Things you haven't proven with concrete evidence from the codebase

For EVERY potential issue, you MUST complete these steps before reporting:

1. **Read the actual code** (not just the diff) — follow the full call chain
2. **Search for all callers/usages** to understand context
3. **Read any design docs or plans** that explain the rationale
4. **Construct a concrete failing scenario** — if you can't describe exactly how the bug manifests, it's not an issue
5. **Discard it** if your research shows it's intentional or already handled

**Use subagents liberally:**

- **Exploration**: When more than three files are staged, or the code is complex, launch Explore subagents (one per file/area) to gather findings
- **Validation**: Before reporting ANY issue, launch a subagent to verify it — have it trace the full call chain, search for guards/handlers you might have missed, and read the relevant design docs. If the subagent can't confirm the issue, discard it
- **Iteration**: After your initial analysis, launch a second round of subagents to dig deeper into the most promising findings — check edge cases, race conditions, and interaction effects between the changed files
- **Refinement**: Are all the staged diffs a single coherent "story" or "theme"? If not, recommend how they should be split into separate commits before committing.

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

**Step 2 — only after all issue blocks are written**, use `AskUserQuestion` to collect accept/veto decisions. The question text is just the ID (e.g. `Accept #A?`) — it is NOT a substitute for the write-up above. Never jump straight to `AskUserQuestion` without the text write-up; the user can't evaluate `#A` if they've never seen what `#A` is.

## Post-review commit flow

Do NOT commit directly after the review. Follow these steps in order:

1. List the files (and line ranges, if partial) that are staged for commit.
2. Compose a [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) message and use `AskUserQuestion` to let the user edit it before committing.
   - **Focus on the _why_, not the _what_** — the diff already shows what changed. One sentence on motivation or consequence beats a list of renamed files.
3. Only commit after explicit user approval.
