---
name: stage
description: Use when committing work from the current session to stage ONLY hunks the session touched, not the entire file. Prevents accidentally staging unrelated uncommitted changes from other work.
---

# Stage Session Changes

> More on these workflows: [photostructure.com/coding](https://photostructure.com/coding/) (no dedicated `stage` article yet)

Stage ONLY the changes that belong to the current body of work and compose a Conventional Commit message.

If, after checking the current git status, you find that all of your changes have been committed already, tell the user that: this skill is done.

**NEVER `git add` an entire modified file unless every hunk in its diff belongs to this work.**

Interactive staging may be unavailable. This skill includes
[`scripts/stage_hunks.py`](./scripts/stage_hunks.py) for deterministic,
non-interactive partial staging on Windows and POSIX hosts.

## One concern per commit

If the session touched **several distinct concerns**, you MUST propose splitting them into **separate commits** — one per concern. We want small, focused, coherent commits in git history, not dogpiles and junk drawers.

Signs the session's work should be split:

- Changes span unrelated features, bugs, or subsystems (e.g. a CSS tweak + an unrelated backend fix)
- You'd need "and" in the commit subject to describe it (`fix X and refactor Y`)
- The commit message would exceed 10 lines to explain everything
- Some changes are refactors/cleanup while others are behavior changes
- Tests for feature A are mixed with implementation of feature B

When splitting, run the full procedure below **once per commit**: inventory just that concern's files, stage them, compose a focused message, get approval, commit — then move on to the next concern. Do NOT stage everything at once and try to describe it in a single message.

When in doubt about whether changes belong together, **ask the user** which grouping they prefer before staging.

## Gather live context

Run these commands at invocation time; never rely on embedded or previously
captured output:

```text
git status --short
git diff --cached --stat
git log --oneline -5
```

## Procedure

### 1. Inventory Changes to Stage

Review the conversation and operation history. Collect:

- each changed file and the exact before/after content attributable to this
  body of work;
- new files created for this work;
- files deleted for this work.

Files you only inspected are not session changes. Do not stage them.

If the session is working from a plan or task document, its scope may extend beyond this conversation — prior work may have left related uncommitted changes. In that case, read the plan, and for each uncommitted file in `git status` decide whether it belongs to the same body of work; **ask the user** when unsure. Stage the plan/task file itself if it was updated this session.

### 2. Classify Each File

For each file you changed, run `git diff -- <file>` and compare every hunk with
the recorded changes from this body of work.

| Situation                                 | Action                 |
| ----------------------------------------- | ---------------------- |
| **New file** (`??` in status)             | `git add <file>` only if the whole file belongs to this work |
| **Deleted file**                          | `git rm <file>`        |
| **ALL hunks are yours**                   | `git add <file>`       |
| **SOME hunks are yours** (mixed)          | Partial-stage (step 3) |
| **NO hunks are yours**                    | Do not stage           |

### 3. Partial-stage mixed files

Resolve the bundled helper relative to this skill directory and use the host's
Python 3 launcher. It reads one tracked file's unstaged diff, numbers its hunks,
and passes only explicitly selected hunks to `git apply --cached`; it does not
create a fixed-path temporary file or modify the working tree.

First list the hunks:

```text
python3 scripts/stage_hunks.py path/to/file --list
```

Map each numbered hunk back to the recorded changes for this work. Then stage
only the matching hunk numbers:

```text
python3 scripts/stage_hunks.py path/to/file --include 1,3
```

On Windows, `py -3` is a common equivalent; otherwise use the host's documented
Python 3 launcher. Review the helper's displayed hunk summaries before
applying.

The helper refuses broadened path selections and file-level mode, rename,
copy, creation, or deletion metadata. Attribute and stage those changes
separately before selecting content hunks.

If one Git hunk mixes related and unrelated lines, **do not stage that hunk or
the whole file**. Stop and ask the user how to split or attribute the entangled
change. Preserving unrelated work is more important than forcing a commit.

### 4. Verify

```bash
git diff --cached --stat
git diff --cached
```

Every newly staged line must trace to this body of work. Also compare against
the staged diff that existed before this workflow so pre-existing staged work is
not mistaken for yours. If anything is uncertain, stop before committing and
ask the user; never clear or replace someone else's staged changes wholesale.

### 5. Compose Commit Message

Draft a [Conventional Commits v1.0.0](https://www.conventionalcommits.org/en/v1.0.0/) message from the staged diff.

#### Format

```
<type>[(<scope>)][!]: <description>

[optional body]

[optional footer(s)]
```

#### Spec summary

- **Type** (REQUIRED): a noun prefix. `feat` = new feature, `fix` = bug fix. Other common types: `refactor`, `perf`, `test`, `docs`, `style`, `build`, `ci`, `chore`.
- **Scope** (optional): a noun in parentheses after the type describing the section of the codebase, e.g. `fix(parser):`. Use the most significantly changed filename (no extension/path).
- **`!`** (optional): append immediately before `:` to flag a breaking change, e.g. `feat!:` or `feat(api)!:`.
- **Description** (REQUIRED): immediately after `: `. Short, imperative mood. **Focus on the _why_, not the _what_** — the diff already shows what changed. One sentence on motivation or consequence beats a list of renamed files.
- **Body** (optional): one blank line after description. Free-form, any number of paragraphs.
- **Footer(s)** (optional): one blank line after body. Format: `token: value` or `token #value`. A `BREAKING CHANGE:` footer (uppercase) is synonymous with `!` in the type prefix.

#### Trailers (attribution + references)

Add git trailers whenever the conversation provides the data, so credit and links aren't lost:

- `Reported-by: <name>` — a user reported the bug or requested the feature
- `Link: <url>` — a thread, issue, or message that gives context (no auto-close)
- `Refs: <#NNN | url>` — related issue you do **not** want to auto-close
- `Closes: #NNN` / `Fixes: #NNN` — a GitHub issue to auto-close on merge
- `Fixes: <12-char-sha> ("subject")` — the bug-introducing commit (Linux-kernel form)

Repeat a trailer for multiple values (one per line) — never `Reported-by: a, b`. Prefer `git commit --trailer "Reported-by=name" --trailer "Link=https://..."` (git ≥2.32) so formatting stays canonical.

#### Constraints

- **Total message must be under 10 lines** (subject + blank + body + footers).
- If it takes more than 10 lines to explain, the commit does too much. Go back to step 2 and split into multiple commits by topic.
- Match the style of the recent commits gathered above.

**NEVER include**: Co-Authored-By trailers, AI attribution, line-by-line enumeration.

### 6. Present and Await Approval

Show the staged diff summary and proposed commit message. **Do not commit until
the user explicitly approves that exact staged scope and message.** After
approval, pass the message to `git commit` using the host's normal non-
interactive argument or message-file mechanism; do not use shell substitution.

## STOP — Red Flags

- About to `git add .` or `git add -A` or `git add --all` — **STOP**
- About to `git add <file>` on a file with mixed changes — **STOP**, partial-stage
- Staged diff has lines you cannot trace to this work — **STOP** and preserve
  the user's existing index state
- Commit message exceeds 10 lines — **STOP**, split into multiple commits
- About to commit without user approval — **STOP**
