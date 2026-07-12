# Claude Code coding skills

An opinionated [Claude Code](https://code.claude.com) plugin marketplace. The
**`coding`** plugin bundles nine workflow skills for disciplined planning, proof-based
review, clean commits, and multi-session Technical Project Plans (TPPs). The
**`security`** plugin adds complementary JavaScript/TypeScript vulnerability-review and
security-hardening skills. The **`cpp`** plugin adds complementary modern-C++ native-addon
memory/resource review and cross-platform project-setup/hardening skills.
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
| `web-security-hardening` | Assesses applicable preventive controls and secure defaults against **OWASP ASVS 5.0.0**: headers/Helmet/CSP, forms/CSRF, runtime validation and contextual encoding, uploads, passwords/MFA/sessions/secrets, framework defaults, databases/Redis/LevelDB, containers, CI, logging, and backups. Reports evidence-backed **Met / Gap / Not applicable / Needs verification** states and remediation priorities—not vulnerability severity. | Synthesizes OWASP, NIST, MDN, and official framework/library guidance while filtering generic listicles and inapplicable controls. See [ATTRIBUTION.md](plugins/security/skills/web-security-hardening/ATTRIBUTION.md). |

### C++ plugin

For cross-platform modern-C++ (C++17) native projects — especially Node.js addons built
with node-gyp and node-addon-api. The pair mirrors the security plugin: one proves defects,
the other assesses preventive controls.

| Skill | What it does | Read more |
| ----- | ------------ | --------- |
| `resource-review` | Traces object and resource **lifetimes** across the C++/C and native/JS boundaries and reports only **proven** memory/resource defects — use-after-free, double/mismatched free, memory and handle/fd leaks, out-of-bounds read/write, uninitialized reads, integer overflow/truncation, TOCTOU, data races, and Node-API misuse (call-scoped handles, reference/handle-scope leaks, finalizer-timing hazards, threadsafe-function imbalance, exceptions crossing the C ABI). Proof is a sanitizer trace, a reproducer, or a fully traced lifetime — a proof gate, not confidence scores. | Grounded in CWE, SEI CERT, the C++ Core Guidelines, and the AddressSanitizer/Valgrind and Node-API docs. See [ATTRIBUTION.md](plugins/cpp/skills/resource-review/ATTRIBUTION.md). |
| `project-setup` | Assesses applicable preventive controls for a cross-platform native build: **node-gyp/binding.gyp** anatomy, **per-OS/per-arch compiler & linker hardening** (arch-gated so nothing hard-errors), **sanitizer + clang-tidy + CI** wiring and suppression discipline, **prebuilds/supply-chain** for glibc/musl/arm64 and vendored C sources, and **maintainable modern-C++ conventions** (RAII, ownership, rule of five, exception safety across the C ABI). Reports evidence-backed **Met / Gap / Not applicable / Needs verification** states and remediation priorities—not defect severity. | Synthesizes the OpenSSF Compiler Hardening Guide, C++ Core Guidelines, and official compiler/node-gyp/Node-API docs, credits toolchain defaults, and filters inapplicable flags. See [ATTRIBUTION.md](plugins/cpp/skills/project-setup/ATTRIBUTION.md). |

## Install

```shell
# Add the marketplace (from GitHub: owner/repo)
/plugin marketplace add photostructure/claude-code-skills

# Install the plugins you want
/plugin install coding@photostructure
/plugin install security@photostructure
/plugin install cpp@photostructure
```

Then invoke any skill — plugin skills are namespaced by the plugin name:

```shell
/coding:replan
/coding:review
/coding:gitplan
/security:web-security-review
/security:web-security-hardening
/cpp:resource-review
/cpp:project-setup
```

To try it locally before publishing:

```shell
/plugin marketplace add /home/mrm/src/claude-code-skills
/plugin install coding@photostructure
/plugin install security@photostructure
/plugin install cpp@photostructure
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
    ├── security/               # security skills (namespaced as /security:<name>)
    │   ├── .claude-plugin/
    │   │   └── plugin.json
    │   └── skills/
    │       ├── web-security-review/
    │       │   ├── SKILL.md            # proven-vulnerability orchestrator
    │       │   ├── references/         # vulnerability guidance loaded on demand
    │       │   ├── ATTRIBUTION.md
    │       │   └── LICENSE
    │       └── web-security-hardening/
    │           ├── SKILL.md            # applicability-aware ASVS orchestrator
    │           ├── references/         # hardening guidance loaded on demand
    │           ├── ATTRIBUTION.md
    │           └── LICENSE
    └── cpp/                    # modern-C++ native-addon skills (namespaced as /cpp:<name>)
        ├── .claude-plugin/
        │   └── plugin.json
        └── skills/
            ├── resource-review/
            │   ├── SKILL.md            # proof-gated memory/resource-defect orchestrator
            │   ├── references/         # defect classes, N-API model, proof/tooling, report format
            │   ├── ATTRIBUTION.md
            │   └── LICENSE
            └── project-setup/
                ├── SKILL.md            # applicability-aware build/hardening orchestrator
                ├── references/         # build, compiler hardening, sanitizers, CI, conventions
                ├── ATTRIBUTION.md
                └── LICENSE
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

MIT © Matthew McEachen — except the `security` and `cpp` plugins' skills, which are
distributed under **CC BY-SA 4.0** because they adapt CC BY-SA reference material (OWASP
for `security`; cppreference for `cpp`). The C++ skills also adapt SEI CERT standards prose
under CC BY 4.0 and consult the C++ Core Guidelines under their custom license. See the
licenses and attribution for
[web-security-review](plugins/security/skills/web-security-review/LICENSE),
[web-security-hardening](plugins/security/skills/web-security-hardening/LICENSE),
[resource-review](plugins/cpp/skills/resource-review/LICENSE), and
[project-setup](plugins/cpp/skills/project-setup/LICENSE).
