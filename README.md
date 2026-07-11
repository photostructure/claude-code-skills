# Claude Code coding skills

An opinionated [Claude Code](https://code.claude.com) plugin marketplace. The
**`coding`** plugin bundles nine workflow skills for disciplined planning, proof-based
review, clean commits, and multi-session Technical Project Plans (TPPs). The
**`security`** plugin adds a JavaScript/TypeScript web security review.
Documented in depth at [photostructure.com/coding](https://photostructure.com/coding/).

| Skill            | What it does                                                                                   | Read more |
| ---------------- | ---------------------------------------------------------------------------------------------- | --------- |
| `replan`         | Iterative critique-and-refine planning. Forces multiple passes before committing to a design.  | [Claude picks the first idea that works. Make it pick the best one.](https://photostructure.com/coding/claude-code-replan/) |
| `review`         | Code review that requires *proof* before reporting — a short list of real bugs, not noise.     | [Most AI code reviews are noise. Here's how to fix that.](https://photostructure.com/coding/claude-code-review/) |
| `review-staged`  | The same proof-based review, scoped to `git diff --cached`, then drives a clean commit.        | [Most AI code reviews are noise. Here's how to fix that.](https://photostructure.com/coding/claude-code-review/) |
| `double-review`  | Validation gate: two independent reviews (codex + a Claude subagent) of the same diff, every finding vetted against ground truth before accept/veto. | [Most AI code reviews are noise. Here's how to fix that.](https://photostructure.com/coding/claude-code-review/) |
| `gitplan`        | Untangle a large working tree into coherent, single-purpose Conventional Commits.              | — |
| `stage`          | Stage only the hunks the current session touched — never the whole file — and commit cleanly.  | — |
| `tpp`            | Work on a Technical Project Plan: read the plan, do the current phase, record discoveries. Bundles a reference `TPP-GUIDE.md`. | [Claude Code has amnesia. So do PRs, changelogs, and your future self.](https://photostructure.com/coding/claude-code-tpp/) |
| `handoff`        | Update the active TPP before context runs out, so the next session continues instead of restarting. | [Claude Code has amnesia. So do PRs, changelogs, and your future self.](https://photostructure.com/coding/claude-code-tpp/) |
| `tpp-orchestrate` | Execute a queue of TPPs serially: TDD subagents, dual independent reviews, every finding vetted against ground truth, one commit per plan. | [Claude Code has amnesia. So do PRs, changelogs, and your future self.](https://photostructure.com/coding/claude-code-tpp/) |

### Security plugin

| Skill | What it does | Read more |
| ----- | ------------ | --------- |
| `web-security-review` | Audits JavaScript/TypeScript web apps (Node/Express/Nest/Next, React/Vue/Angular) for injection (incl. per-ORM raw + SQLite), XSS, authorization (IDOR/BOLA/mass-assignment), auth/session/JWT, SSRF, CSRF, secrets, and crypto — plus conditional passes for **self-hosted deployment hardening** (Docker/network exposure/reverse-proxy trust) and **OIDC/SSO account-takeover**. Traces data flow; reports only proven findings (a proof gate, not confidence scores). | A best-of-three composite of the [Sentry](https://github.com/getsentry/skills), [Anthropic](https://github.com/anthropics/claude-code-security-review), and [GitHub awesome-copilot](https://github.com/github/awesome-copilot) security-review skills, extended with OWASP/CIS/RFC-sourced self-hosting depth. See [ATTRIBUTION.md](plugins/security/skills/web-security-review/ATTRIBUTION.md). |

## Install

```shell
# Add the marketplace (from GitHub: owner/repo)
/plugin marketplace add photostructure/claude-code-skills

# Install the plugins you want
/plugin install coding@photostructure
/plugin install security@photostructure
```

Then invoke any skill — plugin skills are namespaced by the plugin name:

```shell
/coding:replan
/coding:review
/coding:gitplan
/security:web-security-review
```

To try it locally before publishing:

```shell
/plugin marketplace add /home/mrm/src/claude-code-skills
/plugin install coding@photostructure
```

## Layout

```text
claude-code-skills/
├── .claude-plugin/
│   └── marketplace.json        # marketplace catalog (name: photostructure)
└── plugins/
    ├── coding/                 # workflow skills (namespaced as /coding:<name>)
    │   ├── .claude-plugin/
    │   │   └── plugin.json
    │   └── skills/
    │       ├── replan/SKILL.md
    │       ├── review/SKILL.md
    │       ├── review-staged/SKILL.md
    │       ├── double-review/SKILL.md
    │       ├── gitplan/SKILL.md
    │       ├── stage/SKILL.md
    │       ├── tpp/
    │       │   ├── SKILL.md
    │       │   └── TPP-GUIDE.md    # bundled reference guide (project docs/TPP-GUIDE.md wins)
    │       ├── handoff/SKILL.md
    │       └── tpp-orchestrate/SKILL.md
    └── security/               # security skills (namespaced as /security:<name>)
        ├── .claude-plugin/
        │   └── plugin.json
        └── skills/
            └── web-security-review/
                ├── SKILL.md            # lean orchestrator (< 400 lines)
                ├── references/         # loaded on demand
                │   ├── javascript-web-patterns.md
                │   ├── false-positives.md
                │   ├── vuln-classes.md
                │   └── report-format.md
                ├── ATTRIBUTION.md      # credits the three upstream skills
                └── LICENSE             # CC BY-SA 4.0 (OWASP-derived content)
```

## Adapting

These skills are intentionally generic. Each `SKILL.md` ends with an "Adapting for
your project" note — point them at your `CLAUDE.md`/`AGENTS.md`, add domain-specific
critique or review checks, and tune the strictness to taste.

## Further reading

The thinking behind these skills, on [photostructure.com/coding](https://photostructure.com/coding/):

- [Claude picks the first idea that works. Make it pick the best one.](https://photostructure.com/coding/claude-code-replan/) — why `replan` exists: defeating Claude's tendency to satisfice.
- [Most AI code reviews are noise. Here's how to fix that.](https://photostructure.com/coding/claude-code-review/) — the proof-before-reporting rule behind `review` and `review-staged`.
- [Claude Code has amnesia. So do PRs, changelogs, and your future self.](https://photostructure.com/coding/claude-code-tpp/) — Technical Project Plans, the system behind `tpp`, `handoff`, and `tpp-orchestrate`.
- [The LLM sycophancy antidote](https://photostructure.com/coding/you-are-absolutely-right/) — making Claude push back instead of agreeing.
- [If something is odd, inappropriate, confusing, or boring, it is probably important.](https://photostructure.com/coding/odd-inappropriate-confusing-or-boring/) — a code-review philosophy.
- [Uncertain, lazy, forgetful, & impatient: it's what you want your code to be.](https://photostructure.com/coding/uncertain-lazy-forgetful-and-impatient/) — the design values these skills enforce.

## Versioning

`plugin.json` has no `version` field, so while this marketplace is hosted in git every
commit counts as a new version and `/plugin update` picks up changes automatically.
Add an explicit `version` once you want stable, opt-in releases.

## License

MIT © Matthew McEachen — except the `security` plugin's `web-security-review` skill,
which is distributed under **CC BY-SA 4.0** because it adapts OWASP-derived reference
material. See [its LICENSE](plugins/security/skills/web-security-review/LICENSE) and
[ATTRIBUTION.md](plugins/security/skills/web-security-review/ATTRIBUTION.md).
