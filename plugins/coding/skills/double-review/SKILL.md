---
name: double-review
description: Validation gate for freshly written code — run two independent, mutually blind reviews over the same scoped diff, then empirically vet every finding against ground truth before accepting or vetoing it. Use after landing a work item, especially subagent-written code, and before committing.
---

# Double Review

> Documented in depth: [Most AI code reviews are noise. Here's how to fix that.](https://photostructure.com/coding/claude-code-review/)

Gate the change you just landed behind two independent reviews and an
empirical vetting pass. This is a *validation gate*, not a discussion: it
ends with every finding either *accepted with proof* or *vetoed with proof*,
the accepted ones fixed and pinned by tests.

Two failure modes motivate the gate:

1. **A green test suite is not proof of correctness.** Implementers
   (subagents especially) satisfice: they code until *their own* tests pass.
   Semantic mismatches with the spec, stateful-API gotchas, and edge cases
   the tests never pin all survive.
2. **Reviewers are confidently wrong, too.** Every review pass mixes real
   bugs with plausible-but-wrong findings. Accepting blindly injects
   regressions; vetoing blindly ships the bugs.

So: review twice, independently — then trust neither until ground truth has
spoken.

## 1. Scope the gate

Before launching anything, write down:

- **The diff range** — commit range, staged diff, or working-tree diff, plus
  the file list. Both reviewers get exactly the same scope.
- **The ground truth** — the thing a disputed finding can be tested against:
  a reference implementation you can execute, a spec with runnable examples,
  the real API. Write the *exact command* to query it. No executable ground
  truth? Say so, and name the fallback (spec text, maintainer ruling).
- **A scrutiny list** — the 3-6 riskiest spots you'd check first: stateful
  APIs, encoding boundaries, off-by-one-prone length math, error paths,
  concurrency. Both reviewers get this list; it aims them without capping
  them.

## 2. Launch two independent reviewers

Use the current host's available collaboration or subagent mechanism to launch two review
tasks concurrently. Give both reviewers the identical scope, ground-truth
description, scrutiny list, and the methodology in
[`../review/SKILL.md`](../review/SKILL.md): proof before reporting, a concrete
failing scenario per finding, and "No issues found" instead of padding. Require
`file:line` evidence for every finding.

Keep the reviewers mutually blind:

- Start each from the scoped prompt and repository state, not from the other
  reviewer's output or your suspected findings.
- Do not relay interim results between them.
- Collect both final reports before comparing overlap or disagreement.

If the current surface cannot provide two independent internal reviewers,
use a separate external coding reviewer for the missing pass only. Run it with
read-only repository access, use the host's managed process and temporary-file
APIs rather than shell-specific backgrounding or redirection, and capture only
its final review report. If neither a second subagent nor an external reviewer
is available, stop and report that the two-reviewer gate is incomplete.

Don't idle while they grind: **read the new code yourself**. You are yet
another reviewer, and the only one who knows the full context of what the
change was supposed to do. If a reviewer goes silent well past its usual
turnaround, keep analyzing locally while you wait, but do not complete the
gate without two final independent reports. Replace a stalled reviewer with
another independent reviewer or report the gate as incomplete.

## 3. Vet every finding — accept and veto only with proof

For each finding from either reviewer (and from your own read):

1. Construct the empirical test: run ground truth and the new code on the
   same input; compare. A finding you can't test this way gets downgraded to
   a question, not silently accepted.
2. **Accept** only when ground truth confirms the bug.
3. **Veto** only when ground truth confirms the code is right — or the
   finding demands fidelity nothing requires (e.g. mimicking a reference's
   internals on a path no contract pins).
4. When the diagnosis is right but the proposed fix is mediocre, take the
   better fix — reviewers identify problems; you own the remedy.

Reviewer confidence, eloquence, and *agreement between reviewers* are not
evidence. Two reviewers converging on the same wrong finding is common; one
command against ground truth beats both.

## 4. Fix and pin

Apply accepted fixes. **Every accepted finding gets a pinning test** whose
expected values come from ground truth (paste the command that produced them
into the test's comment). The *full* suite must be green again — not just
the new tests.

## 5. Report the verdicts

Summarize for the user (and for whatever plan/PR document tracks this work):
every finding, accepted **and** vetoed, with one-line evidence for each
verdict. Record vetoes especially — the next session (or reviewer) will
rediscover the same "bug" and must not re-litigate it.

## Adapting for your project

- **Name the ground truth explicitly** — e.g. "the vendored reference
  implementation via `./third-party/tool/run`", "CPython 3.12 via
  `uv run python -c ...`", "the RFC's test vectors". The vetting step is
  only as strong as this.
- **Swap reviewers freely.** The invariant is two independent, mutually blind
  reviews. Prefer the host's subagents; use an external reviewer only as a fallback.
- **Tune the scrutiny list** to your codebase's recurring failure modes and
  bake the worst offenders into this file.
- **Callers welcome**: other skills (e.g. `tpp-orchestrate`) reference this
  file as their review gate. Keep the gate generic here; put
  workflow-specific bookkeeping (where verdicts get recorded, commit
  conventions) in the calling skill.
