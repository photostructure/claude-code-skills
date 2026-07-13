---
name: gitplan
description: Plan and execute coherent Conventional Commit groupings for tangled working tree changes — multiple intertwined logical edits that need to land as separate, reviewable commits.
---

**Applicability is about how tangled the changes are, not how many files they touch.** Invoke this skill when the working tree mixes multiple intertwined logical changes that need untangling into separate commits — even if that's only a handful of files. Skip it when the changes are trivial or superficial, no matter how many files they touch: formatter runs, lint autofixes, typo/grammar fixes, or edits that obviously belong in a single commit.

# Review and plan git commits

> More on these workflows: [photostructure.com/coding](https://photostructure.com/coding/)

**Never create megacommits.** Each commit should be focused, coherent, and reviewable.

If the repository has a layered structure (e.g. shared utilities → core → feature packages → app), work through it from the lowest-level layer upward so dependencies land before their consumers.

## Workflow

### Phase 1: Identify Themes

1. Scan all current changes with `git status` and `git diff --stat`. When
   subagents are available and the diff is large, use them to preserve context
   and summarize distinct areas.
2. For complex diffs, use `git diff -U150` but limit JSON/lockfiles to the first ~50 lines.
3. Identify logical themes/groupings. Each theme must have a **single coherent purpose** — a unifying "why" that explains every file in the group. If you can't state the purpose in one sentence without using "and", split the theme. **Never create catch-all buckets** like "housekeeping", "misc", "cleanup", or "various fixes". Every file belongs in a theme because of what it _does_, not because it's small or doesn't fit elsewhere. Orphan files that truly don't relate to any theme get their own single-file commit.
4. **Bundle related docs/plans with their code changes.** If a planning doc, design note, or task file corresponds to a theme, commit it alongside the code it describes — never lump it into a separate "docs" commit. Docs that don't correspond to any code change can go in a docs-only commit.
5. Present the themes to the user as a numbered list with brief descriptions. Order by increasing complexity/risk.
6. Ask: "Which theme should we focus on first?"

### Phase 2: Stage, Review, and Commit (per theme)

1. Stage only files belonging to the selected theme using `git add <files>`, including any related docs/plans decided in Phase 1.
2. Review the staged changes (use the `review-staged` skill if available). Use a capable model — reviews are important.
3. If issues are found:
   - Present them clearly with priority, problem, and proposed fix.
   - Apply fixes incrementally, re-staging as needed.
   - Re-review until clean.
4. Present the proposed commit message and ask for approval. When the user approves, commit immediately — no second confirmation.
   - **Commit messages drive the changelog.** The body should describe user-facing behavior changes (what users will see/experience), not just implementation details. Lead with the "what changed for users" — implementation notes are secondary.

### Phase 3: Repeat

1. Check `git status` for remaining changes.
2. If more changes exist, return to Phase 1 and pick the next theme.
3. Continue until all changes are committed or the user stops.

## Review Guidelines

Review the staged code for potential issues and improvements. Follow project
conventions in `AGENTS.md`, optional `CLAUDE.md`, and contributing guides.

## Review Focus

### Critical Issues First

- Logic errors, security vulnerabilities, performance problems
- Breaking changes or API compatibility issues
- Resource leaks (memory, file handles, database connections)

### Code Quality

- Adherence to the project's language conventions and error-handling patterns
- Anti-patterns: hardcoded paths, magic numbers, tight coupling
- Missing documentation on exported functions

### Testing & Documentation

- Test coverage for critical paths and edge cases
- Documentation accuracy and completeness
- Test fixture updates if needed

## Response Format

For each issue:

- **Priority**: Critical/High/Medium/Low
- **Code**: Quote specific problematic code
- **Problem**: Clear explanation of the issue
- **Solution**: Concrete fix or improvement suggestion
- **Context**: File/line reference for easy navigation

For documentation or trivial implementation issues, suggest the edit to the user and apply if they accept.

For other issues, provide a unique identifier for each issue (e.g. #A or #B), a summary of the issue, where it's located, and a proposed solution. Ask the user and apply if they accept.
