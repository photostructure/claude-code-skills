---
name: handoff
description: Update the active Technical Project Plan for handoff when context is running low or the session is ending, so the next session continues instead of restarting.
---

# TPP Handoff

> Documented in depth: [Claude Code has amnesia. So do PRs, changelogs, and your future self.](https://photostructure.com/coding/claude-code-tpp/)

We're out of time and need to hand off the remaining work. The Technical Project
Plan (TPP) is the handoff document — whatever this session learned must land in
the file, or the next session re-learns it the hard way.

## Required Reading First

Before any work, you MUST read:

- The project's instructions: `AGENTS.md`, plus `CLAUDE.md` when present
- The project's TPP guide: `docs/TPP-GUIDE.md` if it exists; otherwise the
  bundled reference [TPP-GUIDE.md](../tpp/TPP-GUIDE.md)

## Your Task

1. Re-read the TPP and update progress.
2. Mark completed tasks and update the current phase.
3. Document discoveries, gotchas, and insights.
4. Record failed approaches and *why* they failed — the next session must not
   re-explore dead ends.
5. Clarify exactly what remains and any blockers.
6. Trim redundancy before saving: the TPP is a curated brief, not a transcript.
   Keep it under 400 lines; if that's impossible, propose splitting it.

The bar: the next session should be able to invoke the `tpp` skill with the plan path and
continue without asking what happened last time.

## Adapting for your project

- **Extend the required reading list** with the same project docs your `tpp`
  skill reads — the two skills should share one list.
- **Tune the length budget** if your project's guide sets a different limit.
