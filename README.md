# PhotoStructure coding skills

A dual [Codex](https://learn.chatgpt.com/docs/plugins) and
[Claude Code](https://code.claude.com) plugin marketplace for disciplined
planning, proof-based review, focused Git history, web and Electron security,
modern C++ native development, and maintainable Rust projects. The same 14 skills
are packaged natively for both products.

The `coding` plugin contains nine general engineering workflows. The `security`
plugin pairs proof-gated JavaScript/TypeScript web and Electron vulnerability review
with applicability-aware OWASP ASVS and Electron Security Checklist hardening
assessments. The `cpp` plugin provides
the corresponding defect-review and build-hardening pair for modern C++ and
Node.js native addons. The `rust` plugin sets up or assesses idiomatic safe Rust
projects, including Cargo policy, strict usable linting, testing, CI, packaging,
and publishing preparation.

## Skills

| Plugin | Skill | Purpose |
| --- | --- | --- |
| coding | `replan` | Iteratively critique alternatives before settling a complex design. |
| coding | `review` | Review code and report only issues proven through the full code path. |
| coding | `review-staged` | Apply the same proof gate to the staged diff before proposing a commit. |
| coding | `double-review` | Run two mutually blind reviews, then accept or veto every finding with evidence. |
| coding | `gitplan` | Untangle a mixed working tree into coherent Conventional Commits. |
| coding | `stage` | Stage only the hunks attributable to the current body of work. |
| coding | `tpp` | Continue the current phase of a living Technical Project Plan (TPP). |
| coding | `handoff` | Update the active TPP so a later session can continue without rediscovery. |
| coding | `tpp-orchestrate` | Drive a queue of TPPs through TDD, independent review gates, and coherent commits. |
| security | `web-security-review` | Trace JavaScript/TypeScript web and Electron data flow and report only proven vulnerabilities. |
| security | `web-security-hardening` | Assess applicable web and Electron preventive controls against ASVS- and Electron-guided baselines. |
| cpp | `resource-review` | Prove native memory/resource defects through traces, reproducers, or complete lifetime analysis. |
| cpp | `project-setup` | Assess cross-platform build hardening, analysis tooling, CI, and modern C++ conventions. |
| rust | `project-setup` | Set up or assess idiomatic safe Rust, strict linting, maintainability, CI, packaging, and publishing readiness. |

The workflows are documented in depth at
[photostructure.com/coding](https://photostructure.com/coding/). License and
source attribution remain alongside the skills that adapt or synthesize external
guidance.

## Install in Codex

Add this GitHub repository as a marketplace, then install any plugins you want:

```shell
codex plugin marketplace add photostructure/coding-skills
codex plugin add coding@photostructure
codex plugin add security@photostructure
codex plugin add cpp@photostructure
codex plugin add rust@photostructure
```

Enter `/plugins` in the Codex CLI to browse configured marketplaces and manage
plugins. Start a new task after installation so Codex discovers the bundled
skills.

Type `$` in a prompt to select a skill explicitly. Installed plugin skills are
namespaced by plugin, for example:

```text
$coding:replan
$coding:review
$coding:stage
$security:web-security-review
$security:web-security-hardening
$cpp:resource-review
$cpp:project-setup
$rust:project-setup
```

Codex can also invoke a skill implicitly when the request matches its
description.

### Test locally in Codex

Use a disposable, empty directory as `CODEX_HOME` so development installs do
not affect your normal Codex configuration. Set that environment variable using
your shell's normal syntax, then run:

```shell
codex plugin marketplace add /absolute/path/to/coding-skills
codex plugin list
codex plugin add coding@photostructure
codex plugin add security@photostructure
codex plugin add cpp@photostructure
codex plugin add rust@photostructure
codex plugin list
```

Confirm the versions reported by `codex plugin list` match each plugin's
`.codex-plugin/plugin.json`, then start a fresh Codex task under the same
disposable `CODEX_HOME` and verify the `$` skill picker sees all 14 skills.
Remove only that disposable directory when finished.

## Install in Claude Code

The original Claude Code marketplace and manifests remain supported:

```shell
/plugin marketplace add photostructure/coding-skills
/plugin install coding@photostructure
/plugin install security@photostructure
/plugin install cpp@photostructure
/plugin install rust@photostructure
```

Invoke Claude Code skills with their plugin namespace:

```text
/coding:replan
/coding:review
/coding:gitplan
/security:web-security-review
/security:web-security-hardening
/cpp:resource-review
/cpp:project-setup
/rust:project-setup
```

### Test locally in Claude Code

Point Claude Code at the repository root instead of the GitHub shorthand:

```shell
/plugin marketplace add /absolute/path/to/coding-skills
/plugin install coding@photostructure
/plugin install security@photostructure
/plugin install cpp@photostructure
/plugin install rust@photostructure
```

Start a new task after installing or updating a plugin before testing its
skills.

## Repository layout

```text
coding-skills/
├── .agents/
│   └── plugins/
│       └── marketplace.json       # native Codex marketplace
├── .claude-plugin/
│   └── marketplace.json           # Claude Code marketplace
├── plugins/
│   ├── coding/
│   │   ├── .codex-plugin/plugin.json
│   │   ├── .claude-plugin/plugin.json
│   │   ├── agents/reviewer.md       # Claude-enforced leaf reviewer
│   │   └── skills/
│   │       ├── <skill>/
│   │       │   ├── SKILL.md       # shared instructions
│   │       │   └── agents/
│   │       │       └── openai.yaml
│   │       ├── stage/scripts/stage_hunks.py
│   │       └── tpp/TPP-GUIDE.md
│   ├── security/
│   │   ├── .codex-plugin/plugin.json
│   │   ├── .claude-plugin/plugin.json
│   │   ├── agents/reviewer.md
│   │   └── skills/
│   │       └── <skill>/
│   │           ├── SKILL.md
│   │           ├── agents/openai.yaml
│   │           ├── references/
│   │           ├── ATTRIBUTION.md
│   │           └── LICENSE
│   ├── cpp/
│   │   ├── .codex-plugin/plugin.json
│   │   ├── .claude-plugin/plugin.json
│   │   ├── agents/reviewer.md
│   │   └── skills/
│   │       └── <skill>/
│   │           ├── SKILL.md
│   │           ├── agents/openai.yaml
│   │           ├── references/
│   │           ├── ATTRIBUTION.md
│   │           └── LICENSE
│   └── rust/
│       ├── .codex-plugin/plugin.json
│       ├── .claude-plugin/plugin.json
│       └── skills/project-setup/
│           ├── SKILL.md
│           ├── agents/openai.yaml
│           ├── references/
│           └── ATTRIBUTION.md
└── scripts/
    └── validate_repository.py
```

## Validation

Run the repository validator from the root:

```shell
python3 scripts/validate_repository.py
```

Before publishing, also run the current Codex `$skill-creator` validator for
every skill, the `$plugin-creator` validator for every plugin, parse both
marketplace JSON files, check relative Markdown links, and run
`git diff --check`. Test both marketplace installations in fresh tasks.

Review orchestration is bounded on both hosts. Claude Code uses each
review-capable plugin's tool-restricted `reviewer` agent, which has neither the
`Agent` nor `Skill` tool. Codex and other hosts use the same non-triggerable leaf
methodology through a `delegation-budget: 0` prompt contract and task-local
context. Review skills keep a leaf-mode guard so an implicit skill match cannot
restart orchestration. Setup-only plugins do not invent reviewer agents.

## Adapting the workflows

The skills are intentionally generic. Prefer durable project instructions in
`AGENTS.md`; also honor `CLAUDE.md` when a repository uses it for Claude Code
compatibility. Each skill's adaptation section identifies the project-specific
invariants, references, or review checks worth adding.

## Versioning and marketplace updates

Every native `.codex-plugin/plugin.json` uses strict Semantic Versioning. The
initial native release is `1.0.0`. Bump the patch version for compatible fixes,
the minor version for backward-compatible capability additions, and the major
version for breaking workflow or packaging changes.

The marketplace catalog has no version field. The unqualified
`photostructure/coding-skills` source follows the repository's default branch
when Codex adds or upgrades the marketplace snapshot. A plugin's manifest
version identifies the installed cache entry; it does not pin the marketplace
repository. Bump that version whenever published plugin content changes so the
cached copy has a distinct identity.

For a reproducible marketplace snapshot, pin a Git tag, commit, or branch with
`owner/repo@ref` or `codex plugin marketplace add owner/repo --ref <ref>`.
Repository tags are release bookkeeping unless the marketplace source is
explicitly pinned to one.

During unpublished local iteration, follow the current `$plugin-creator`
cachebuster/reinstall workflow. Use stable SemVer values for published plugin
content rather than treating every commit on the tracked branch as a release.

## Further reading

- [Claude picks the first idea that works. Make it pick the best one.](https://photostructure.com/coding/claude-code-replan/)
- [Most AI code reviews are noise. Here's how to fix that.](https://photostructure.com/coding/claude-code-review/)
- [Claude Code has amnesia. So do PRs, changelogs, and your future self.](https://photostructure.com/coding/claude-code-tpp/)
- [The LLM sycophancy antidote](https://photostructure.com/coding/you-are-absolutely-right/)
- [If something is odd, inappropriate, confusing, or boring, it is probably important.](https://photostructure.com/coding/odd-inappropriate-confusing-or-boring/)
- [Uncertain, lazy, forgetful, & impatient: it's what you want your code to be.](https://photostructure.com/coding/uncertain-lazy-forgetful-and-impatient/)

## License

MIT © Matthew McEachen, except the `security` and `cpp` plugin skills, which
are distributed under CC BY-SA 4.0 because they adapt CC BY-SA reference
material. The C++ skills also adapt SEI CERT standards prose under CC BY 4.0
and consult the C++ Core Guidelines under their custom license. See each
skill's `LICENSE` and `ATTRIBUTION.md` for details. The `rust` plugin is original
MIT-licensed guidance with its consulted sources recorded in `ATTRIBUTION.md`.
