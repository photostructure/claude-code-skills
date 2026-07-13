---
name: tpp-orchestrate
description: Work through a queue of Technical Project Plans serially — delegate each to a TDD subagent, run two independent reviews, empirically vet every finding, and land one coherent commit per plan. Use when executing a documented plan queue such as _todo/ or _feat-name/ for a port, migration, or multi-stage feature.
---

# TPP Orchestration

> Documented in depth: [Claude Code has amnesia. So do PRs, changelogs, and your future self.](https://photostructure.com/coding/claude-code-tpp/)

You are the **orchestrator** for a documented queue of Technical Project Plans
(TPPs) — self-contained plan files that carry research, design decisions, and
acceptance criteria across sessions. The queue may be a backlog such as
`_todo/` or a temporary feature integration queue such as `_feat-auth/`; plans
move to `_done/` when finished, and a roadmap or queue `README.md` defines the
order. The TPP system itself — layouts, frontmatter, the plan template — is
defined in the bundled [TPP-GUIDE.md](../tpp/TPP-GUIDE.md), or the project's own
`docs/TPP-GUIDE.md`, which wins. The sibling `tpp` and `handoff` skills work a
_single_ plan within a session; this skill is the loop that drives a whole queue
of them through subagents and review gates.

Two failure modes motivate this loop:

1. **A subagent's green test suite is not proof of correctness.** Agents satisfice: they implement until _their own_ tests pass, and real bugs (semantic mismatches with the spec, stateful-API gotchas, edge cases the tests never pin) survive. Independent review catches these.
2. **Reviewers are confidently wrong, too.** Every review pass produces a mix of real bugs and plausible-but-wrong findings. Accepting blindly injects regressions; vetoing blindly ships the bugs. Only _empirical verification against ground truth_ settles a finding.

So: delegate, review twice, and vet everything with evidence.

## Before the first TPP

- Read the roadmap and every queued TPP's summary. Confirm dependency order.
- Identify the project's **ground truth** — the thing a disputed finding can be tested against: a reference implementation you can execute, a spec with runnable examples, the real runtime/API. Write down _how_ to query it (the exact command). If there is no executable ground truth, say so and agree on the fallback (spec text, maintainer decision) with the user.
- Ask the user any clarifying questions **now** — scope ambiguities are cheapest
  to resolve before any code exists.

## The loop, per TPP

Work **serially**: one TPP through the full loop before starting the next. Only parallelize TPPs within a wave when their file sets are provably disjoint _and_ neither depends on the other's decisions — review gates stay per-TPP either way.

### 1. Scope and clarify

Read the TPP and its sources of truth. If anything is ambiguous or the plan contradicts what you find in the code, ask the user before delegating — don't let a subagent guess.

### 2. Delegate with TDD

Launch an implementation subagent through the host's available collaboration
mechanism. Select the strongest available model and higher reasoning effort for
large, novel, security-sensitive, or weakly specified work. Use a faster model
or moderate reasoning effort only when the TPP, reference behavior, and existing
tests pin the implementation tightly. If the surface does not expose model
selection, keep the same risk-based scrutiny in the prompt and review gate.

The prompt must include:

- The TPP path and the sources of truth (spec files, reference implementation paths).
- **Tests first**: port or write the acceptance tests before implementing, then implement until green. The _full_ suite must stay green — not just the new tests.
- Project pitfalls relevant to this TPP (from `AGENTS.md`, optional
  `CLAUDE.md`, or the TPP itself).
- "You cannot talk to the user. Record open questions, assumptions you made, and every intentional divergence from the plan in your final report."

### 3. Relay questions

Triage the subagent's open questions. Ask the user about decision-worthy ones
**before** the review gate — a review of code built on a wrong assumption is
wasted.

### 4. Review twice, independently

Run the double-review gate on the TPP's diff — read and follow
[../double-review/SKILL.md](../double-review/SKILL.md): use two independent,
mutually blind reviewers through the host's available collaboration mechanisms over
the identical scope, while you read the new code yourself as the third
reviewer — the only one who knows the whole roadmap. Scope both reviewer
prompts with this TPP's spec/reference files, the diff range, and a scrutiny
list of the riskiest areas the plan touches. Use an external reviewer only when
the revised gate requires its fallback.

### 5. Vet every finding — accept and veto only with proof

Per the gate (steps 3-4 of `double-review`): test each finding against the
ground truth you identified before the first TPP; accept or veto only with
that evidence; every accepted finding gets a pinning test whose expected
values come from ground truth. Full suite green again.

### 6. Record the verdicts

Add a "Post-review fixes" section to the TPP listing every finding — accepted **and** vetoed — with the evidence for each verdict. Vetoes especially: the next session will see the same "bug" and must not re-litigate it.

### 7. Close out

Move the TPP to `_done/`, update the roadmap's status section, and make **one coherent commit per TPP** (implementation + tests + TPP move together), following the repo's commit conventions. Then start the next TPP.

## Guidelines

- **Never let a review gate slip.** "The agent's tests pass and the diff looks clean" is exactly the state in which review has found real bugs.
- **Rebuild before testing built artifacts.** CLI/dist tests against a stale build silently test old code.
- **Report honestly.** The per-TPP summary to the user lists: what shipped, findings accepted/vetoed (with one-line reasons), open questions, and anything you diverged on.

## Adapting for your project

- **Name the ground truth explicitly** — e.g. "CPython 3.12 via `uv run python -c ...` in the reference submodule", "the staging API", "the RFC's test vectors". The vetting step is only as strong as this.
- **Reviewer choices and scrutiny-list tuning** live in the gate — adapt [../double-review/SKILL.md](../double-review/SKILL.md), and this loop inherits it.
- **Tune the model heuristic** to your roster — the invariant is "risk decides the model", not the specific names.
- **Rename the file conventions** (`_todo/`, `_feat-<name>/`, `_done/`, and the roadmap or queue README) to whatever your plan system uses; the loop doesn't care about paths.
