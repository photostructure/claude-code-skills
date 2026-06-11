---
name: stage
description: Use when committing work from the current session to stage ONLY hunks the session touched, not the entire file. Prevents accidentally staging unrelated uncommitted changes from other work.
allowed-tools: Bash, Read, Glob, Grep, Write
---

# Stage Session Changes

Stage ONLY the changes that belong to the current body of work and compose a Conventional Commit message.

If, after checking the current git status, you find that all of your changes have been committed already, tell the user that: this skill is done.

**NEVER `git add` an entire modified file unless every hunk in its diff belongs to this work.**

`git add -p` and `git add -i` require interactive input and don't work here. This skill uses non-interactive patch filtering instead.

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

## Live Context

- Working tree: !`git status --short`
- Already staged: !`git diff --cached --stat`
- Recent commits: !`git log --oneline -5`

## Procedure

### 1. Inventory Changes to Stage

Review your conversation history. Collect:

- **Edit tool calls**: file path + `old_string`/`new_string` for each
- **Write tool calls**: new files created from scratch
- **Deleted files**: files removed this session

Files you only **Read** are NOT session changes. Do not stage them.

If the session is working from a plan or task document, its scope may extend beyond this conversation — prior work may have left related uncommitted changes. In that case, read the plan, and for each uncommitted file in `git status` decide whether it belongs to the same body of work; **ask the user** when unsure. Stage the plan/task file itself if it was updated this session.

### 2. Classify Each File

For each file you edited, run `git diff -- <file>` and compare every hunk against your Edit calls.

| Situation                                 | Action                 |
| ----------------------------------------- | ---------------------- |
| **New file** (Write tool, `??` in status) | `git add <file>`       |
| **Deleted file**                          | `git rm <file>`        |
| **ALL hunks are yours**                   | `git add <file>`       |
| **SOME hunks are yours** (mixed)          | Partial-stage (step 3) |
| **NO hunks are yours**                    | Do not stage           |

### 3. Partial-Stage Mixed Files

Pick whichever strategy involves fewer hunks to handle:

#### Strategy A: Stage only your hunks (when MOST hunks are NOT yours)

```bash
git diff -- path/to/file > /tmp/stage-FILENAME.patch
```

Read the patch. Write a filtered copy keeping ONLY hunks matching your session edits:

- **Keep**: `diff --git` header, `---`/`+++` lines, `@@` + content for each session hunk
- **Remove**: Entire hunks (from one `@@` to the next) that don't match any Edit call

```bash
git apply --cached --recount /tmp/stage-FILENAME.patch
```

#### Strategy B: Stage whole file, then unstage non-session hunks (when MOST hunks ARE yours)

```bash
git add path/to/file
git diff --cached -- path/to/file > /tmp/unstage-FILENAME.patch
```

Read the patch. Write a filtered copy keeping ONLY the hunks that are NOT yours:

```bash
git apply --cached -R --recount /tmp/unstage-FILENAME.patch
```

#### Strategy C: Replay edits onto HEAD (last resort for heavily entangled diffs)

When the working tree has so many pre-existing changes that your session hunks can't be cleanly isolated — e.g., surrounding context lines have shifted, or `diff` merges adjacent hunks from different sessions into a single hunk — Strategies A and B both fail because there are no clean hunk boundaries to split on.

Instead, reconstruct a clean patch by replaying your edits onto the committed version of the file:

```bash
# 1. Extract the committed version
git show HEAD:path/to/file > /tmp/FILENAME.orig
cp /tmp/FILENAME.orig /tmp/FILENAME.mine

# 2. Apply ONLY your session's edits to the copy
#    (use the Edit tool on /tmp/FILENAME.mine, reproducing each edit from the conversation)

# 3. Diff using git diff --no-index (produces git-compatible patch format)
#    IMPORTANT: Do NOT use `diff -u` — its output format can silently mismatch
#    with `git apply`, especially when the index is dirty.
git diff --no-index /tmp/FILENAME.orig /tmp/FILENAME.mine \
  | sed 's|a/tmp/FILENAME.orig|a/path/to/file|;s|b/tmp/FILENAME.mine|b/path/to/file|' \
  > /tmp/stage-FILENAME.patch

# 4. Review the patch — every line must trace to a session edit

# 5. Stage the clean patch
git apply --cached --recount /tmp/stage-FILENAME.patch
```

This guarantees the staged diff contains exactly your edits and nothing else, regardless of how entangled the working tree is. The downside is you must re-apply every Edit call to the `/tmp` copy, which is tedious for files with many edits. Only use this when A and B aren't viable.

#### Notes

`--recount` recalculates hunk line counts so you don't need to manually fix `@@ -X,Y +A,B @@` after removing hunks from a patch file.

If apply fails, check that each kept hunk has its `@@` line and all context/change lines intact.

### 4. Verify

```bash
git diff --cached --stat
git diff --cached
```

Every staged line must trace to this session's edits. If an unrelated hunk leaked in:

```bash
git reset HEAD -- path/to/file
```

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
- Match the style of recent commits shown in Live Context above.

**NEVER include**: Co-Authored-By trailers, AI attribution, line-by-line enumeration.

### 6. Present and Await Approval

Show the staged diff summary and proposed commit message. **Do NOT commit until the user explicitly approves.**

```bash
git commit -m "$(cat <<'EOF'
type(scope): description

Optional body
EOF
)"
```

## STOP — Red Flags

- About to `git add .` or `git add -A` or `git add --all` — **STOP**
- About to `git add <file>` on a file with mixed changes — **STOP**, partial-stage
- Staged diff has lines you can't trace to a session edit — `git reset HEAD -- <file>`
- Commit message exceeds 10 lines — **STOP**, split into multiple commits
- About to commit without user approval — **STOP**
