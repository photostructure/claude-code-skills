<!--
Output template. See ../ATTRIBUTION.md.
Adapted from getsentry/skills (OWASP-derived, CC BY-SA 4.0) and
github/awesome-copilot security-review (MIT).
-->

# Report Format

Use this structure for the final report (workflow step 7). Summary table first,
findings grouped by vulnerability class, patches proposed but never auto-applied.

```markdown
## Security Review: <scope reviewed>

### Summary
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High     | 0 |
| Medium   | 0 |
| Low      | 0 |

**Scope:** <files / diff / path scanned>
**Overall risk:** Critical / High / Medium / Low / Clean

If deployment configuration was in scope, add a separate table so hardening findings
are not mixed into application-vulnerability counts:

### Deployment Hardening Summary
| Deployment Risk | Count |
|-----------------|-------|
| Critical        | 0     |
| High            | 0     |
| Medium          | 0     |
| Low             | 0     |

### Findings

#### SQL Injection

##### [SQLI-001] SQL Injection — `src/routes/users.ts:42` (High)
- **Proof (source → sink):** `req.query.id` → `pgClient.query(\`… ${id}\`)`, unparameterized
  with no validation on the reachable route. An input equivalent to `1 OR 1=1` changes
  the query predicate; this is static proof, not an instruction to test a live target.
- **Issue:** User-controlled `id` is interpolated into a raw SQL string.
- **Impact:** The shown `SELECT` can disclose rows outside the requested identifier;
  establish driver multi-statement behavior and DB-role privileges before claiming
  modification or broader compromise.
- **Evidence:**
  ```ts
  const rows = await pgClient.query(`SELECT * FROM users WHERE id = ${req.query.id}`);
  ```
- **Fix:** Use the target driver's parameter syntax; for node-postgres:
  ```ts
  const rows = await pgClient.query(
    "SELECT * FROM users WHERE id = $1",
    [req.query.id],
  );
  ```

### Needs Verification
Leads that look suspicious but whose applicable proof could not be completed — for
example, an unclear input source, exposure boundary, or effective configuration.
Phrase them as questions and do not count them as findings.

#### [VERIFY-001] Possible SSRF — `src/lib/webhook.ts:18`
- **Question:** Is `payload.callbackUrl` attacker-controlled, or set from server config
  upstream? Trace the caller before treating this as a finding.

### Proposed Patches
For each Critical/High finding, a minimal before→after diff. **Review each patch before
applying — nothing has been changed.**
```

## Rules

- Lead with the summary table; group findings by class, not by file. Keep deployment
  findings and their counts in a separate deployment section when that pass ran.
- Every finding: `file:line`, an evidence snippet, its **proof** (using the applicable
  data-flow, exposure, or configuration shape), a plain-English attacker scenario, and
  a concrete fix. No confidence scores — if it's reported, it's proven; if it's a lead,
  it goes under "Needs verification."
- For secret findings, redact evidence. Preserve only a variable/key name or a short,
  recognizable prefix/suffix (for example, `sk-live-ABCD…WXYZ`); never echo a complete
  API key, private key, password, token, or credential-bearing connection string.
- IDs are `<CLASS>-NNN` (e.g. `XSS-002`, `IDOR-001`) so findings are referenceable.
- Clean result: `No proven vulnerabilities identified in <scope>.` — and state what was
  scanned (and list any unresolved leads under "Needs verification").
- Never edit files as part of the review. Patches are proposals for human approval.
