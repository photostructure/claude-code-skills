---
name: web-security-review
description: Security code review for JavaScript/TypeScript web applications. Use when asked to "security review", "find vulnerabilities", "check for security issues", "audit security", "OWASP review", "is this secure?", or to review Node/Express/React/Vue/Next/Nest/Angular code for database/storage security (SQL, MongoDB, Redis, LevelDB), XSS, authentication, authorization (IDOR/BOLA), SSRF, CSRF, deserialization, secrets, or crypto issues. Traces data flow, reasons like a security researcher, and reports only findings with concrete data-flow, exposure, or configuration proof — never confidence-scored guesses.
allowed-tools: Read, Grep, Glob, Bash, Agent, WebFetch, WebSearch
license: CC-BY-SA-4.0
---

# Web Security Review (JavaScript / TypeScript)

Identify **exploitable** security vulnerabilities in JavaScript/TypeScript web
applications. Reason about the code the way a security researcher would — trace
data flow, understand framework protections, and report only findings you can
justify with concrete proof. Signal over noise.

> This skill is a best-of-three composite. See [ATTRIBUTION.md](./ATTRIBUTION.md).

## Scope

**In scope:** Node.js/TypeScript backends (Express, NestJS, Fastify, Next.js API
routes) and browser/SSR frontends (React, Vue, Angular, Next.js). Server-side and
client-side JS/TS, plus the config, CI/CD, and IaC files that ship with them.

**Out of scope:** other languages (defer to a language-specific reviewer) and the
exclusions in [`references/false-positives.md`](./references/false-positives.md).

### Report vs. research — the prime directive

- **Report on:** only the file, diff, or path the user asked about.
- **Research:** the _entire_ codebase to establish the facts before reporting.

Before flagging anything, trace where the input actually comes from, whether it is
validated/sanitized upstream, how it is configured, and what framework protection
applies. **Never report on pattern-match alone.** Investigate first, report second.

## Reporting gate: proof, not probability

Report a finding only when you can **construct concrete proof** appropriate to the
class. If you can't describe how the bug actually manifests, it isn't a finding.
Use one of these proof shapes:

- **Data-flow flaw:** the exact attacker-controlled input, its route through the code,
  and the security-sensitive sink it reaches.
- **Exposure flaw:** the sensitive value or resource, where an attacker can observe or
  retrieve it, and why the value is real and security-relevant. Never validate a
  suspected credential against a live service.
- **Configuration flaw:** the effective unsafe setting, the attacker capability or
  reachable operation it affects, the security boundary it removes, and the concrete
  resulting impact.

Every shape must establish attacker capability, affected boundary, and impact. Signal
over noise: better to miss a theoretical issue than to flood the report.

Do **not** assign confidence percentages or 1–10 scores — reviewer confidence is not
evidence, and neither is a second tool agreeing with you. The complete proof is the
evidence. Every candidate is in exactly one state:

| State           | You have…                                                                              | Action                                                            |
| --------------- | -------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| **Proven**      | one complete proof shape above with a concrete exploit or exposure you can describe | **Report**, with that proof in the finding                        |
| **Lead**        | a suspicious path, exposure, or setting with a missing proof element after investigation | List under **"Needs verification"** as a question — not a finding |
| **Theoretical** | only a pattern match, best-practice gap, or defense-in-depth nit                       | **Drop**                                                          |

For a data-flow candidate, first ask whether the input is attacker-controlled or
server-controlled. For exposure and configuration candidates, identify the attacker-
reachable boundary and concrete impact instead. See the taxonomy, proof gate, and hard
exclusion / precedent lists in
[`references/false-positives.md`](./references/false-positives.md) — read it before
reporting anything.

## Review workflow

Run these steps in order. Load reference files as each step needs them — don't
front-load everything into context.

### 1. Scope resolution

- If a path/diff was given, review only that. Otherwise review the working changes,
  including untracked files. Establish the default scope with:
  ```bash
  if git rev-parse --verify --quiet origin/HEAD >/dev/null; then
    git diff --merge-base origin/HEAD
  else
    git diff HEAD
  fi
  git ls-files --others --exclude-standard
  ```
  Treat the diff output plus every listed untracked path as the review scope.
- Detect frameworks and versions from `package.json` / lockfile (React, Vue,
  Angular, Express, Nest, Next, ORM/driver/ODM, Redis clients, LevelDB adapters, and
  validation libraries like `zod`/`joi`).
- Verify version-sensitive framework, dependency, and vulnerability behavior against
  primary sources: official project documentation, release notes/advisories, standards,
  or NVD/CISA records. Do not rely on search snippets or third-party summaries.

### 2. Map the attack surface

For each file, decide which vulnerability classes are even reachable, then load the
matching sections of [`references/vuln-classes.md`](./references/vuln-classes.md):

| Code under review                        | Primary classes to check                                 |
| ---------------------------------------- | -------------------------------------------------------- |
| API routes / controllers                 | authorization (IDOR/BOLA), authentication/JWT, injection |
| DB/storage access / ORM/ODM/client        | SQL/NoSQL injection; Redis/LevelDB authz, path, atomicity |
| Templates / DOM / components             | XSS                                                      |
| Outbound `fetch`/`http`/webhooks         | SSRF                                                     |
| State-changing endpoints                 | CSRF                                                     |
| Uploads / file paths                     | path traversal, file handling                            |
| Cookies / tokens / hashing               | crypto, session, secrets                                 |
| Login / password reset / signup          | auth — hashing, enumeration, reset tokens, brute-force   |
| OAuth / OIDC callback routes             | OIDC/SSO — see `oidc-sso-review.md`                       |
| Object merge / `JSON.parse` spread       | prototype pollution, mass assignment                     |
| Money / counters / multi-step flows      | business logic, race conditions                          |
| Dockerfile / compose / `.env` / IaC            | deployment hardening — see `self-hosting-hardening.md` |
| DB service / connection config / migrations    | DB deployment — see `database-deployment-security.md`  |

Load [`references/javascript-web-patterns.md`](./references/javascript-web-patterns.md)
for the framework-specific safe-vs-dangerous catalog (what auto-escapes, which sinks
are exploitable, which APIs bypass protection).

**Conditional passes.** If the scope includes deployment files (Dockerfile,
`docker-compose*.yml`, `.env*`, IaC) or the user asks for a deployment/Docker/self-
hosting review, additionally run
[`references/self-hosting-hardening.md`](./references/self-hosting-hardening.md), and
when a DB service / connection config / migration runner is in scope also run
[`references/database-deployment-security.md`](./references/database-deployment-security.md).
Report proven findings in a **Deployment Hardening** section with a Deployment-Risk
rating (not the app-vuln severity table). Deployment checklist matches remain subject
to the proof gate: reachability and concrete impact are required, and a missing
hardening control alone is not a finding. If an OAuth/OIDC login flow is in scope,
also run [`references/oidc-sso-review.md`](./references/oidc-sso-review.md).

### 3. Dependency & secrets quick pass

Fast, high-value wins before the deep scan:

- **Dependencies:** scan `package.json` + lockfile for known-vulnerable packages. When
  available and permitted, corroborate with
  `npm audit --omit=dev` — but only report a dependency finding with a concrete,
  reachable exploit path; otherwise omit it from findings or put the missing
  reachability fact under **Needs verification**.
- **Secrets:** scan all files — including `.env`, config, CI/CD, Dockerfiles, IaC —
  for hardcoded API keys, tokens, private keys, and DB connection strings with
  embedded credentials. Real high-value secrets in source/logs are findings;
  see the precedents in [`references/false-positives.md`](./references/false-positives.md).

### 4. Deep vulnerability scan

The core pass. **Reason about the code; do not grep-and-report.** For each reachable
class in step 2, apply the detection signals, safe patterns, and escalation checkers
in [`references/vuln-classes.md`](./references/vuln-classes.md). For every candidate,
confirm the framework does not already neutralize it (auto-escaping, parameterized
queries, `SameSite` cookies, middleware) using
[`references/javascript-web-patterns.md`](./references/javascript-web-patterns.md).

### 5. Cross-file data-flow analysis

Step back and look holistically. Trace attacker-controlled input from entry points
(HTTP params/body/headers/cookies, route segments, uploads, WebSocket messages)
across files to dangerous sinks (DB queries, `exec`, HTML output, file writes,
outbound requests). Catch **second-order** issues (value stored safely, used unsafely
later) and broken trust boundaries between modules/services that no single-file view
reveals.

### 6. Adversarial self-verification

For each surviving candidate, **try to refute it** before it makes the report. When
subagents are available and the candidate set is non-trivial, launch an independent
validation pass for each candidate in parallel, instructing each reviewer to disprove
exploitability using
[`references/false-positives.md`](./references/false-positives.md):

- Re-read the code with fresh eyes. Is it _actually_ reachable with attacker input?
- Is there validation, sanitization, or an allowlist upstream that was missed?
- Does a framework/middleware handle it already?
- Is the source truly attacker-controlled, or server-controlled config?
- For an exposure, is the value/resource genuinely sensitive and attacker-observable?
- For configuration, is the setting effective on a reachable path, and does it cause
  the claimed impact rather than merely omit defense-in-depth?

Drop anything that lacks a complete applicable proof shape after refutation. This
find → refute-in-parallel → keep-only-what-survives loop is what keeps the report
actionable.

### 7. Report

Emit the report in the structure defined by
[`references/report-format.md`](./references/report-format.md): a severity summary
table first, then findings grouped by class, each with location, proof (the traced
data flow, exposure, or effective configuration), evidence, impact, and fix. If nothing
survives, say so explicitly and state what was scanned — "No proven vulnerabilities
identified in <scope>."

### 8. Propose fixes (do not auto-apply)

For each Critical/High finding, propose a concrete, minimal patch: show vulnerable →
fixed, preserve surrounding style and names, and explain what changed and why. State
plainly: **"Review each patch before applying — nothing has been changed."** Never
edit files as part of the review unless the user explicitly asks.

## Severity

Assign severity from the proven impact, attacker prerequisites, affected data or
privilege, and scope — never from a sink name alone. Use these anchors:

| Severity     | Anchor                                                                 |
| ------------ | ---------------------------------------------------------------------- |
| **Critical** | Pre-auth compromise of the application/host or similarly systemic loss |
| **High**     | Major confidentiality/integrity loss or account takeover               |
| **Medium**   | Meaningful but constrained security-boundary violation                  |
| **Low**      | Limited, demonstrable impact with narrow scope                          |

For example, raw-HTML rendering may be Low through High depending on who controls and
views the content; SSRF may be Low through Critical depending on reachable targets and
credentials; and a hardcoded value is not a finding until it is real, sensitive, and
exposed. State the assumptions that drive severity.

## Output rules

- Lead with a findings **summary table** (counts by severity).
- **Group by vulnerability class**, not by file.
- Every finding: file:line, an evidence snippet, its **proof** (using the applicable
  shape above), a plain-English attacker scenario, and a fix. For secrets, redact the
  value; never reproduce a complete credential, private key, password, or connection
  string in the report.
- Never auto-apply patches — present them for human review.
- A clean result is a valid result: say what was scanned and that nothing was found.

## Reference files

Load on demand — keep SKILL.md context lean.

| File                                                                               | Load during   | Covers                                                                                                                                                                           |
| ---------------------------------------------------------------------------------- | ------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`references/javascript-web-patterns.md`](./references/javascript-web-patterns.md) | steps 2, 4, 6 | Framework catalog: React/Vue/Angular/Express/Next/Nest safe-vs-dangerous sinks, DOM XSS, prototype pollution, `zod` runtime validation, search starters                          |
| [`references/vuln-classes.md`](./references/vuln-classes.md)                       | steps 2, 4    | Per-class detection signals, safe patterns, escalation checkers (SQL/Mongo injection, Redis/LevelDB storage boundaries, per-ORM/ODM raw + SQLite, XSS, authz/mass-assignment, authn/session/JWT, SSRF, CSRF, deserialization, path traversal, crypto, secrets, info disclosure, business logic) |
| [`references/false-positives.md`](./references/false-positives.md)                 | steps 3, 4, 6 | Attacker- vs server-controlled taxonomy, hard exclusions, precedents                                                                                                             |
| [`references/self-hosting-hardening.md`](./references/self-hosting-hardening.md)   | conditional (deployment scope) | Network exposure, reverse-proxy/`trust proxy`/host-header trust, container/root, secrets in images, CORS, backups, brute-force posture |
| [`references/database-deployment-security.md`](./references/database-deployment-security.md) | conditional (DB deployment scope) | Least-privilege DB/Redis roles, default creds, TLS, Redis ACLs, LevelDB filesystem boundary, migration privilege, dump exposure |
| [`references/oidc-sso-review.md`](./references/oidc-sso-review.md)                 | conditional (OAuth/OIDC scope) | redirect_uri + post-login open redirect, state/nonce + unsolicited-response rejection, ID-token validation (sig/iss/aud/exp/JWKS), account-linking takeover, PKCE, token leakage, access-token-vs-ID-token misuse |
| [`references/report-format.md`](./references/report-format.md)                     | step 7        | Output template and finding card                                                                                                                                                 |

## Adapting for your project

Point this skill at your `CLAUDE.md`/`AGENTS.md` for the app's threat model, trusted
inputs, and auth boundaries. Add project-specific safe patterns (your validation
layer, your ORM conventions) to `references/false-positives.md` so the review stops
re-flagging them, and add any bespoke sinks to `references/vuln-classes.md`.
