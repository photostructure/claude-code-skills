# Technical Project Plan (TPP) Guide

> Bundled reference copy. If the project has its own `docs/TPP-GUIDE.md`, that
> file wins — this one is the generalized template from
> <https://photostructure.com/coding/claude-code-tpp/>.

## What is a TPP?

A TPP is a living handoff document for complex work that may span multiple agent
sessions or multiple engineers.

Each engineer reads it, does work, documents discoveries, and updates the file
so the next engineer can continue without starting over.

Every bit of context in the TPP should help the next engineer succeed.

## Golden rule

A good TPP transfers expertise, not just instructions.

It should explain:

- What problem we are solving for users
- Which approaches were considered
- Which approaches failed, and why
- Which tests and edge cases reveal the problem
- How to adapt if nearby architecture changes

These same answers serve four readers: the next session, the reviewer of the PR, the engineer drafting release notes, and whoever inherits this code years from now. Write once; serve all four.

## Typical process

1. An issue is raised, initial design and research is done, and a TPP is created.
2. Engineer A works on the TPP and updates it with discoveries, challenges, and
   next steps.
3. Engineer B picks up where Engineer A left off, using the TPP to continue the
   work.
4. The cycle continues until the TPP is complete.
5. The completed TPP moves to `_done/`.

Update the TPP as progress is made. The file is the handoff.

## Where TPPs live

Choose one primary backlog layout for this project. A temporary feature
integration queue may overlay either layout.

### Simple layout

- `_todo/`: unfinished TPPs
- `_done/`: completed TPPs

### Priority layout

- `_active/`: actively being worked on or targeting the next release
- `_p1/`: high-impact work that should become active soon
- `_p2/`: planned near-term work
- `_p3/`: worthwhile but not imminent
- `_p4/`: nice-to-have work with no timeline
- `_done/`: completed TPPs

Filenames should be date-prefixed:

```text
YYYYMMDD-feature-name.md
```

If using priority folders, moving a file between folders changes its priority.
The filesystem location is the source of truth.

### Feature integration queues

Use `_feat-<name>/` when several TPPs must be coordinated and landed together
on a feature branch, for example `_feat-auth/` or `_feat-face/`. This is a
temporary integration queue, not another priority level.

Each feature queue must contain a `README.md` defining its purpose, owning
branch or worktree, dependency and landing order, completion gate, and the
priority/frontmatter policy for its TPPs. Remove the queue after its completed
plans move to `_done/` and the feature lands.

## Frontmatter

Use YAML frontmatter when scripts, dashboards, issue trackers, or backlog tools
need structured data.

```yaml
---
title: Face detection and clustering
section: AI & Vision
priority: p1
issue: https://github.com/example/project/issues/122
votes: 42
---
```

Adapt the fields to this project. Common fields:

- `title`: human-readable task title
- `section`: product area or subsystem
- `priority`: `p1`, `p2`, `p3`, or `p4` if using priority folders
- `issue`, `forum`, `discord`: links to discussion
- `votes`, `views`: demand signals
- `shelved: true`: evaluated and deferred indefinitely

If using priority folders, `priority` must match the folder. For a TPP in a
`_feat-<name>/` queue, follow the effective priority documented by the
project-specific guide or that queue's `README.md`.

## Placeholder TPPs

Lower-priority work may start as a placeholder TPP: frontmatter plus a short
description. Do not add phases, alternatives, or task breakdowns until the work
is close enough to need real scoping.

```markdown
---
title: "On this day" gallery
section: UX & Viewer
priority: p3
issue: https://github.com/example/project/issues/232
votes: 17
---

# TPP: "On this day" gallery

Show assets from the same calendar date in prior years. Natural companion to tag
galleries; likely needs date-aware aggregation and a viewer entry point.
```

## Full TPP structure

```markdown
---
title: Feature name
section: Product area
priority: p1
---

# TPP: Feature name

## Summary

Short description of the problem, under 10 lines.

## Current phase

- [ ] Research & Planning
- [ ] Write and validate breaking tests (if relevant)
- [ ] Design alternatives and iterate to an optimal approach
- [ ] Breakdown of tasks
- [ ] Implementation of tasks
- [ ] Review & Refinement
- [ ] Final Integration verification
- [ ] Review

## Required reading

YOU MUST study these before continuing. Work may be rejected if you skip them.

- **AGENTS.md**: project structure, local rules, and verification commands
- **CLAUDE.md** (when present): additional compatibility instructions
- **[TPP-GUIDE.md](./TPP-GUIDE.md)**: this workflow
- Add project-specific design, testing, API, and architecture docs here
- Add source files that define the subsystem

## Description

Detailed context about the problem, under 20 lines.

## Lore

- Non-obvious details that will help the next engineer
- Prior gotchas that tripped up previous sessions
- Relevant functions, classes, constraints, and historical context

## Solutions

It is OK to be unsure. Mark uncertainty clearly so the next engineer knows what
to verify.

### Option A (preferred)

Describe the preferred approach. Include pros, cons, code snippets, and why this
approach is preferred when useful.

### Option B (alternative)

Describe any serious alternative and why it was rejected or deferred.

## Tasks

Each task should include:

- Clear deliverable
- Implementation details
- Integration points
- Verification command
```

## Keeping TPPs useful

Do not let the TPP become a transcript. Trim redundant notes, stale observations,
and obvious commentary. Preserve the facts that will save the next session time.

Try to keep full TPPs under 400 lines. If that is impossible, split the work into
multiple TPPs.

## Handoff rules

When context is running low or the session is ending:

1. Re-read the TPP.
2. Mark completed tasks.
3. Update the current phase.
4. Add discoveries, gotchas, and failed approaches.
5. Clarify exactly what remains.
6. Trim redundancy before saving.

The next session should be able to invoke the `tpp` skill with the plan path, read the
TPP, and continue without asking what happened last time.
