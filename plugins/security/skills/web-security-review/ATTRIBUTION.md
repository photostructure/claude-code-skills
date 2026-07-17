# Attribution

`web-security-review` is a composite adapted from three upstream security-review
skills. It is not affiliated with or endorsed by any of them. Each contributed a
distinct strength; this skill combines them and narrows the scope to JavaScript /
TypeScript web and Electron desktop applications.

## Upstream sources

| Source | License | What was taken |
|--------|---------|----------------|
| [getsentry/skills](https://github.com/getsentry/skills) — `security-review` | [Apache-2.0 repository license](https://github.com/getsentry/skills/blob/main/LICENSE); the skill marks its OWASP-derived reference material as [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) | The report-vs-research discipline, the attacker- vs server-controlled taxonomy, the framework-mitigated (auto-escape/parameterization) tables, and the JavaScript/TypeScript framework pattern catalog. |
| [anthropics/claude-code-security-review](https://github.com/anthropics/claude-code-security-review) — `.claude/commands/security-review.md` | [MIT © 2025 Anthropic](https://github.com/anthropics/claude-code-security-review/blob/main/LICENSE) | The hard-exclusions and precedents lists, and the find → refute-in-parallel sub-agent verification architecture. |
| [github/awesome-copilot](https://github.com/github/awesome-copilot) — `skills/security-review` | [MIT](https://github.com/github/awesome-copilot/blob/main/LICENSE) | The ordered end-to-end workflow (scope → dependency audit → secrets → deep scan → cross-file data-flow → self-verify → report → propose patches), the "reason like a security researcher" framing, and the propose-patches-for-human-approval step. |

## Changes made

- **Scope narrowed** to JavaScript/TypeScript web frameworks (Node/Express/Nest/Next,
  React/Vue/Angular) and Electron desktop applications; non-JS language and general
  infrastructure guides were dropped.
- **Merged** the three sources' overlapping guidance into one workflow and de-duplicated
  the vulnerability-class references.
- **Reorganized** into a lean orchestrator `SKILL.md` (kept under 400 lines) plus
  section-specific reference docs loaded on demand.
- **Reference tables** in `javascript-web-patterns.md`, `false-positives.md`,
  `vuln-classes.md`, and `report-format.md` were trimmed, reframed, and re-tabulated
  from the upstream material.
- **Replaced numeric confidence scoring** (Anthropic's >80% threshold / 1–10 scores)
  with a **proof gate** — a finding is reported only with concrete data-flow, exposure,
  or configuration proof, otherwise it's a "Needs verification" lead or dropped. This
  aligns with the sibling `coding/review` and `coding/double-review` skills' rule that
  reviewer confidence is not evidence; only proof is.
- **Added self-hosting and DB depth** beyond the three upstreams, synthesized from the
  broader OWASP Cheat Sheet Series (SQL/NoSQL Injection, Mass Assignment, Authentication,
  Session Management, JWT, Authorization, Forgot Password, Database Security, Docker
  Security, HTTP Headers), OWASP ASVS 5.0.0, RFC 9700 (OAuth 2.0
  Security BCP), per-ORM security docs (Sequelize/Knex/Prisma/TypeORM/Drizzle), SQLite,
  Redis, LevelDB, and Node Level documentation, and public account-takeover / exposure
  CVEs in self-hosted apps. These inform `references/self-hosting-hardening.md`,
  `references/database-deployment-security.md`,
  `references/oidc-sso-review.md`, and the expanded `references/vuln-classes.md`. OWASP cheat-sheet content is CC BY-SA
  4.0 (consistent with this skill's license). Security assertions were independently
  checked against the cited standards, official project documentation, and upstream
  advisories; the wording here is original except where attribution says otherwise.
- **Added Electron vulnerability coverage**, synthesized in original wording from the
  official Electron security checklist, API and packaging documentation, release
  timelines, and Electron security advisories. The unmaintained Apache-2.0-licensed
  [Electronegativity](https://github.com/doyensec/electronegativity) project was consulted
  as a historical inventory of lead patterns; no source code, prose, assigned severity,
  confidence score, or stale default was imported. Every lead remains subject to this
  skill's proof gate and current official Electron behavior.

## Licensing

This combined skill is distributed under **CC BY-SA 4.0** (ShareAlike), matching the
OWASP-derived reference material it adapts. The upstream repository license labels
above were verified against their linked `LICENSE` files; their notices are retained
in `LICENSE`. See
[`LICENSE`](./LICENSE).
