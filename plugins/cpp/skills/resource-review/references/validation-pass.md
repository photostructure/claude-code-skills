# Single-Pass Resource Finding Validation

Independently try to disprove the candidate findings and scope supplied in the
task prompt. Complete one read-only validation pass and return the verdicts to
the caller; do not apply fixes.

For each candidate:

1. Re-read the complete lifetime from acquisition through every ownership
   transfer, use, and release.
2. Read [`proof-and-tooling.md`](./proof-and-tooling.md) and the relevant defect
   class or Node-API lifetime reference.
3. Search for RAII guards, cleanup hooks, upstream bounds checks, synchronization,
   ownership transfer, and teardown ordering that may refute the defect.
4. Prefer a sanitizer trace or deterministic reproducer; otherwise require a
   complete traced lifetime with `file:line` evidence.
5. Classify the candidate as:
   - **Confirmed:** a complete Proven proof survives refutation.
   - **Refuted:** concrete lifetime or runtime evidence breaks the proof.
   - **Unresolved:** the evidence remains a Lead because a required fact is
     unavailable.

Return one concise verdict per candidate. Never promote an unresolved lead or
static-analysis warning to a proven defect.
