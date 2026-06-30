---
name: tpp-orchestrate
description: Work through a queue of Technical Project Plans serially — delegate each to a TDD subagent, double-review the result with codex and a Claude /review subagent, empirically vet every finding before accepting or vetoing it, and land one coherent commit per plan. Use when executing a roadmap of plan files (e.g. a _todo/ directory) for a port, migration, or multi-stage feature.
allowed-tools: Bash, Read, Glob, Grep, Edit, Write, Task, Agent, AskUserQuestion
---

# TPP Orchestration

> Documented in depth: [Claude Code has amnesia. So do PRs, changelogs, and your future self.](https://photostructure.com/coding/claude-code-tpp/)

You are the **orchestrator** for a queue of Technical Project Plans (TPPs) — self-contained plan files that carry research, design decisions, and acceptance criteria across sessions (typically `_todo/*.md`, moving to `_done/` when finished, with a roadmap file as the index). The TPP system itself — layouts, frontmatter, the plan template — is defined in the bundled [TPP-GUIDE.md](../tpp/TPP-GUIDE.md), or the project's own `docs/TPP-GUIDE.md`, which wins. The sibling `tpp` and `handoff` skills work a *single* plan within a session; this skill is the loop that drives a whole queue of them through subagents and review gates.

Two failure modes motivate this loop:

1. **A subagent's green test suite is not proof of correctness.** Agents satisfice: they implement until *their own* tests pass, and real bugs (semantic mismatches with the spec, stateful-API gotchas, edge cases the tests never pin) survive. Independent review catches these.
2. **Reviewers are confidently wrong, too.** Every review pass produces a mix of real bugs and plausible-but-wrong findings. Accepting blindly injects regressions; vetoing blindly ships the bugs. Only *empirical verification against ground truth* settles a finding.

So: delegate, review twice, and vet everything with evidence.

## Before the first TPP

- Read the roadmap and every queued TPP's summary. Confirm dependency order.
- Identify the project's **ground truth** — the thing a disputed finding can be tested against: a reference implementation you can execute, a spec with runnable examples, the real runtime/API. Write down *how* to query it (the exact command). If there is no executable ground truth, say so and agree on the fallback (spec text, maintainer decision) with the user.
- Ask clarifying questions **now** (`AskUserQuestion`) — scope ambiguities are cheapest to resolve before any code exists.

## The loop, per TPP

Work **serially**: one TPP through the full loop before starting the next. Only parallelize TPPs within a wave when their file sets are provably disjoint *and* neither depends on the other's decisions — review gates stay per-TPP either way.

### 1. Scope and clarify

Read the TPP and its sources of truth. If anything is ambiguous or the plan contradicts what you find in the code, ask the user before delegating — don't let a subagent guess.

### 2. Delegate with TDD

Launch an implementation subagent. Pick the model by risk: a stronger model (opus-class) for large, novel, or weakly-specified work; a faster one (sonnet-class) when the TPP and existing tests pin the behavior tightly.

The prompt must include:

- The TPP path and the sources of truth (spec files, reference implementation paths).
- **Tests first**: port or write the acceptance tests before implementing, then implement until green. The *full* suite must stay green — not just the new tests.
- Project pitfalls relevant to this TPP (from `CLAUDE.md` or the TPP itself).
- "You cannot talk to the user. Record open questions, assumptions you made, and every intentional divergence from the plan in your final report."

### 3. Relay questions

Triage the subagent's open questions. Decision-worthy ones go to the user (`AskUserQuestion`) **before** the review gate — a review of code built on a wrong assumption is wasted.

### 4. Review twice, independently

Run two reviews of the TPP's diff, blind to each other:

- **codex**: `codex exec --sandbox read-only "/review <scoped prompt>"` — run it in the background with output to a file; reviews take minutes.
- **A Claude subagent** running the `/review` skill (or its methodology: proof-before-reporting) on the same diff.

Scope both prompts identically: name the spec/reference files, the diff range, and an explicit **scrutiny list** of the riskiest areas (the things you'd check first — stateful APIs, encoding boundaries, off-by-one-prone length math, whatever this TPP touches).

While the reviews run, **read the new code yourself**. You are the third reviewer, and the only one who knows the whole roadmap.

### 5. Vet every finding — accept and veto only with proof

For each finding from either reviewer (and your own reading):

1. Construct the empirical test: run the ground truth and the new code on the same input; compare.
2. **Accept** only when ground truth confirms the bug. **Veto** only when ground truth confirms the code is right (or the finding demands fidelity nothing requires — e.g. mimicking a reference's internals on a path no contract pins).
3. If a reviewer's diagnosis is right but its fix is mediocre, take the better solution — reviewers identify problems; you own the remedy.

Reviewer confidence, eloquence, and agreement between reviewers are **not** evidence. Two reviewers agreeing on a wrong finding is common; one command against ground truth beats both.

### 6. Fix and pin

Apply accepted fixes. **Every accepted finding gets a pinning test** whose expected values are derived from ground truth (paste the command that produced them into the test's comment). Full suite green again.

### 7. Record the verdicts

Add a "Post-review fixes" section to the TPP listing every finding — accepted **and** vetoed — with the evidence for each verdict. Vetoes especially: the next session will see the same "bug" and must not re-litigate it.

### 8. Close out

Move the TPP to `_done/`, update the roadmap's status section, and make **one coherent commit per TPP** (implementation + tests + TPP move together), following the repo's commit conventions. Then start the next TPP.

## Guidelines

- **Never let a review gate slip.** "The agent's tests pass and the diff looks clean" is exactly the state in which review has found real bugs.
- **Rebuild before testing built artifacts.** CLI/dist tests against a stale build silently test old code.
- **Long-running reviewers run in the background**; keep working (your own read of the code) while they grind.
- **Report honestly.** The per-TPP summary to the user lists: what shipped, findings accepted/vetoed (with one-line reasons), open questions, and anything you diverged on.

## Adapting for your project

- **Name the ground truth explicitly** — e.g. "CPython 3.12 via `uv run python -c ...` in the reference submodule", "the staging API", "the RFC's test vectors". The vetting step is only as strong as this.
- **Swap reviewers freely**: the structure needs two *independent* reviews, not codex specifically. Any external reviewer plus a Claude `/review` subagent works.
- **Tune the model heuristic** to your roster — the invariant is "risk decides the model", not the specific names.
- **Rename the file conventions** (`_todo/`, `_done/`, the roadmap) to whatever your plan system uses; the loop doesn't care about paths.
