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

### Findings

#### [SQLI-001] SQL Injection — `src/routes/users.ts:42` (Critical)
- **Proof (source → sink):** `req.query.id` → `db.query(\`… ${id}\`)`, unparameterized
  and unreachable by any validation on the route. Repro: `?id=1 OR 1=1`.
- **Issue:** User-controlled `id` is interpolated into a raw SQL string.
- **Impact:** Attacker reads/modifies arbitrary rows, e.g. `id=1 OR 1=1`.
- **Evidence:**
  ```ts
  const rows = await db.query(`SELECT * FROM users WHERE id = ${req.query.id}`);
  ```
- **Fix:** Use a parameterized query.
  ```ts
  const rows = await db.query("SELECT * FROM users WHERE id = ?", [req.query.id]);
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

- Lead with the summary table; group findings by class, not by file.
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
