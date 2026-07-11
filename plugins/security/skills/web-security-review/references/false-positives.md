<!--
Composite reference. See ../ATTRIBUTION.md.
- Attacker- vs server-controlled taxonomy & framework-mitigated tables:
  adapted from getsentry/skills (OWASP-derived, CC BY-SA 4.0).
- Hard exclusions & precedents: adapted from anthropics/claude-code-security-review
  (.claude/commands/security-review.md, MIT).
Trimmed and reframed for JavaScript/TypeScript web apps.
-->

# False Positives: What NOT to Flag

The difference between a useful review and noise. Read this before reporting anything,
and again during self-verification (workflow step 6).

## The core question: attacker-controlled or server-controlled?

A vulnerable-looking sink is only a vulnerability if attacker-controlled input reaches
it. Trace the source.

This taxonomy applies to data-flow flaws. For exposure and configuration flaws, use
the equivalent proof shapes in `SKILL.md`; do not invent an attacker-controlled input.

| Attacker-controlled (investigate)              | Server-controlled (usually safe)         |
| ---------------------------------------------- | ---------------------------------------- |
| `req.query`, `req.params`, `req.body`          | `process.env.*` set at deploy time       |
| `req.headers` (most), `req.cookies` (unsigned) | `config.*`, app settings, constants      |
| URL path segments (`/users/:id`)               | hardcoded internal URLs                  |
| file uploads (content **and** filename)        | signed/verified session data             |
| WebSocket / `postMessage` data                 | trusted DB content written by the system |
| DB content originally written by other users   | framework/library defaults               |

**SSRF — same pattern:**

```js
fetch(req.query.url); // FLAG: attacker controls host
fetch(`${config.API_BASE}/${path}`); // CHECK: is `path` attacker-controlled?
fetch(process.env.SEER_URL); // SAFE: server config
```

## Framework already mitigates it

Do not flag these — they are safe **unless** the escape hatch is used (see
`javascript-web-patterns.md`):

| Pattern                                                       | Why safe             | Only flag when                                                |
| ------------------------------------------------------------- | -------------------- | ------------------------------------------------------------- |
| React `{value}`, Vue `{{ value }}`, Angular `{{ value }}`     | auto-escaped         | `dangerouslySetInnerHTML` / `v-html` / `bypassSecurityTrust*` |
| `Model.findOne({ where: { id } })`, `db.query(sql, [params])` | parameterized        | `.raw()` / string interpolation into SQL                      |
| Mongo `findOne({ _id: id })` after scalar validation          | literal comparison   | scalar validation is absent or filter structure is attacker-controlled |
| Redis `get`/`set` with normal client arguments                | binary-safe protocol | dynamic command/Lua source, manual RESP, or cross-tenant key access |
| LevelDB `get`/`put` with a caller-derived key                 | no query interpreter | missing key authorization or attacker-controlled DB location |
| `res.json(...)`                                               | serialized           | manual HTML string building                                   |
| `res.render(...)` with escaped template directives only       | template-escaped     | EJS `<%-`, Handlebars `{{{`/`{{&`, Pug `!=`/`!{` raw output   |
| `element.textContent = x`                                     | text only            | `innerHTML` / `outerHTML` / `document.write`                  |

## Never flag

- **Test files** and test-only fixtures/helpers (unless the task is reviewing test security).
- **Dead code, commented-out code, documentation/markdown** files.
- Sinks fed only by **constants or server-controlled config**.
- **Client-side** "missing" auth/permission/validation checks. Client code is
  untrusted by design; those checks belong on the server. Flag the _server_ gap, not
  the client one. (Same for any data the client sends to the backend — the backend
  is responsible for validating it.)

## Hard exclusions

Do **not** report these classes (out of scope for this skill; handled elsewhere or
not genuine web-app vulnerabilities):

1. **Denial of Service / resource exhaustion** — memory, CPU, connection floods.
2. **Rate limiting / brute-force hardening** absence on a **generic** API endpoint.
   _Carve-out:_ an **authentication** endpoint (login / password-reset / signup) with
   **zero** brute-force defense is a deployment candidate only when attacker reachability
   and credential-attack impact are proven (see `self-hosting-hardening.md` §12).
3. **App-level regex injection / ReDoS** — user input compiled into `new RegExp(...)`
   for application string-matching. _Carve-out:_ request data reaching a NoSQL
   `$regex`/`$where` operator is query injection and remains in scope.
4. **SSRF that only controls the path** (not host or protocol) — the blast radius is the
   same fixed internal target regardless of deployment, so it's a path-traversal-flavored
   bug, not an SSRF host-pivot. Keep it out of SSRF, but still check it under path traversal.
5. **Log spoofing** — un-sanitized user input written to logs is not, by itself, a vuln.
6. **Missing audit logs.**
7. **Outdated dependencies without a concrete, reachable exploit** — INFO, not a finding.
8. **Lack of hardening / best-practice gaps** with no concrete exploit. Code need not
   implement every best practice; flag concrete vulnerabilities only.
9. **Missing input validation on non-security-critical fields** with no proven impact.
10. User-controlled content placed into an **LLM/AI prompt** is not, by itself, a vuln.
11. Findings whose only trigger requires **controlling an env var or CLI flag** — those
    are trusted in a secure deployment.

## Precedents

Calibrate borderline calls against these:

- **Secrets:** logging a high-value secret/password/PII in plaintext **is** a finding.
  Logging URLs or non-PII "sensitive-ish" data is assumed safe.
- **UUIDs** may be assumed unguessable; their absence of validation is not IDOR by
  itself (sequential/enumerable IDs are the concern).
- **React / Angular / Vue XSS:** these frameworks are secure against XSS by default.
  Do not report XSS in `.jsx`/`.tsx`/`.vue`/Angular templates **unless** an unsafe
  method is used (`dangerouslySetInnerHTML`, `v-html`, `bypassSecurityTrust*`).
- **Open redirect, tabnabbing, XS-Leaks, prototype pollution:** report only with a
  concrete, proven attack path and real impact — these are noise otherwise.
- **Race conditions / TOCTOU:** report only when concretely exploitable (e.g. double-
  spend, auth check/use gap), not theoretical.
- **Redis / LevelDB keys:** a caller-derived key is not injection by itself. Check
  whether it crosses a tenant/owner namespace or selects a protected record without
  authorization.
- **LevelDB durability and process locking:** asynchronous durability or single-process
  locking is not a finding without a concrete replay, authorization, or unsafe-fallback
  impact. Availability-only effects remain excluded.
- **Command injection in build/shell scripts:** rarely fed untrusted input — require a
  concrete attacker-input path before reporting.
- **Bearer-token-only routes are not CSRF-able:** a route authenticated solely by an
  `Authorization: Bearer` header has no ambient credential the browser auto-sends — don't
  flag CSRF there. (A route mixing cookie-session auth with a state change still is.)
- **"LAN-only" / "single-user" is not a reason to drop a CSRF finding:** CSRF fires from
  the admin's own browser while they're authenticated; the attacker never needs LAN
  access. Treat a trusted-network assumption the same way as a client-side check — it
  doesn't remove the server-side gap.
- **MEDIUM findings:** include only when obvious and concrete. When in doubt, drop it.

## The reporting gate: prove it or drop it

This skill reports **proven findings, not probabilities** — no numeric confidence
scores. During self-verification, put every surviving candidate through one gate:

> **Can you complete the applicable data-flow, exposure, or configuration proof shape
> from `SKILL.md` — concretely enough that someone could verify the impact?**

- **Yes** → report it, and include the complete proof. Reproduce only against an
  isolated local fixture or mock with external networking disabled and no persistent
  side effects. Never send exploit payloads to a repository's configured database,
  service, shared environment, or production target; static proof is sufficient when
  no safe fixture exists.
- **Suspicious, but a proof element is unconfirmed** → it's a *lead*, not a finding.
  List it under "Needs verification" as a question.
- **Only a pattern match or best-practice gap** → drop it.

Reviewer confidence and eloquence are not evidence, and neither is a second tool
agreeing with you — two reviewers converge on the same wrong finding all the time. The
complete proof is the evidence. If you can't build it, you don't have a finding.
