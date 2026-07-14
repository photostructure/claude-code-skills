# Single-Pass Security Finding Validation

Independently try to disprove the candidate findings and scope supplied in the
task prompt. Complete one read-only validation pass and return the verdicts to
the caller; do not apply fixes.

For each candidate:

1. Read the complete source-to-sink path and all relevant guards, middleware,
   framework behavior, and deployment configuration.
2. Read [`false-positives.md`](./false-positives.md) and the applicable proof
   shape in the parent skill.
3. Establish whether the source is attacker-controlled, the path is reachable,
   and the claimed security impact is observable.
4. Look specifically for upstream validation, sanitization, authorization,
   parameterization, auto-escaping, or trusted provenance that refutes it.
5. Classify the candidate as:
   - **Confirmed:** complete applicable proof survives refutation.
   - **Refuted:** concrete code or framework evidence breaks the proof.
   - **Unresolved:** a required fact cannot be established from the available
     repository and safe local checks.

Return one concise verdict per candidate with `file:line` evidence. Never turn
an unresolved fact into a vulnerability finding.
