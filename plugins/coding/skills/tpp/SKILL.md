---
name: tpp
description: Work on a Technical Project Plan — read the plan, identify the current phase, do that phase's work, and update the plan with discoveries. Use when starting or resuming multi-session work tracked in a plan file.
argument-hint: "[path-to-tpp]"
disable-model-invocation: false
allowed-tools: Bash, Read, Glob, Grep, Edit, Write, WebSearch, Skill
---

# Work on TPP

> Documented in depth: [Claude Code has amnesia. So do PRs, changelogs, and your future self.](https://photostructure.com/coding/claude-code-tpp/)

A Technical Project Plan (TPP) is a living handoff document: it carries research,
design decisions, failed approaches, and next steps across sessions, so the next
session (or the next engineer) continues instead of restarting.

Make progress on the referenced TPP. Determine the current phase and take
appropriate action.

## Required Reading First

Before any work, you MUST read:

- The project's instructions: `CLAUDE.md` and/or `AGENTS.md`, if present
- The project's TPP guide: `docs/TPP-GUIDE.md` if it exists; otherwise the
  bundled reference [TPP-GUIDE.md](TPP-GUIDE.md)

## Process

1. Read the referenced TPP. It will live in `_todo/`, or in a priority folder
   (`_active/`, `_p1/`…`_p4/`) if this project uses them.
2. Identify the current phase.
3. Do the work for that phase.
4. Update the TPP with progress and discoveries — gotchas, rejected approaches,
   and the *why* behind decisions, not a transcript.

When context runs low before the work is done, run the `handoff` skill rather
than letting the session end silently. When the TPP is complete, move it to
`_done/`.

## Adapting for your project

- **Create a project `docs/TPP-GUIDE.md`** (start from the bundled reference)
  and tailor the layout, frontmatter fields, and template to your conventions —
  the project guide always takes precedence over the bundled copy.
- **Extend the required reading list** with your high-value docs
  (`DESIGN-PRINCIPLES.md`, `TDD.md`, architecture decisions). Every listed file
  is read on every invocation, so keep it short.
- **Consider a system-prompt wrapper** (`claude.sh` with
  `--append-system-prompt`) so sessions reliably write to TPPs when exiting
  plan mode — see the article for the pattern.
