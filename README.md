# Claude Code coding skills

An opinionated [Claude Code](https://code.claude.com) plugin marketplace with five
workflow skills for disciplined planning, proof-based review, and clean commits.
Documented in depth at [photostructure.com/coding](https://photostructure.com/coding/).

| Skill            | What it does                                                                                   | Read more |
| ---------------- | ---------------------------------------------------------------------------------------------- | --------- |
| `replan`         | Iterative critique-and-refine planning. Forces multiple passes before committing to a design.  | [Claude picks the first idea that works. Make it pick the best one.](https://photostructure.com/coding/claude-code-replan/) |
| `review`         | Code review that requires *proof* before reporting — a short list of real bugs, not noise.     | [Most AI code reviews are noise. Here's how to fix that.](https://photostructure.com/coding/claude-code-review/) |
| `review-staged`  | The same proof-based review, scoped to `git diff --cached`, then drives a clean commit.        | [Most AI code reviews are noise. Here's how to fix that.](https://photostructure.com/coding/claude-code-review/) |
| `gitplan`        | Untangle a large working tree into coherent, single-purpose Conventional Commits.              | — |
| `stage`          | Stage only the hunks the current session touched — never the whole file — and commit cleanly.  | — |

## Install

```shell
# Add the marketplace (from GitHub: owner/repo)
/plugin marketplace add photostructure/claude-code-skills

# Install the bundled plugin
/plugin install coding@photostructure
```

Then invoke any skill — plugin skills are namespaced by the plugin name:

```shell
/coding:replan
/coding:review
/coding:gitplan
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
    └── coding/                 # the plugin (skills namespaced as /coding:<name>)
        ├── .claude-plugin/
        │   └── plugin.json
        └── skills/
            ├── replan/SKILL.md
            ├── review/SKILL.md
            ├── review-staged/SKILL.md
            ├── gitplan/SKILL.md
            └── stage/SKILL.md
```

## Adapting

These skills are intentionally generic. Each `SKILL.md` ends with an "Adapting for
your project" note — point them at your `CLAUDE.md`/`AGENTS.md`, add domain-specific
critique or review checks, and tune the strictness to taste.

## Further reading

The thinking behind these skills, on [photostructure.com/coding](https://photostructure.com/coding/):

- [Claude picks the first idea that works. Make it pick the best one.](https://photostructure.com/coding/claude-code-replan/) — why `replan` exists: defeating Claude's tendency to satisfice.
- [Most AI code reviews are noise. Here's how to fix that.](https://photostructure.com/coding/claude-code-review/) — the proof-before-reporting rule behind `review` and `review-staged`.
- [Claude Code has amnesia. So do PRs, changelogs, and your future self.](https://photostructure.com/coding/claude-code-tpp/) — Technical Project Plans, the planning docs these skills hand off to.
- [The LLM sycophancy antidote](https://photostructure.com/coding/you-are-absolutely-right/) — making Claude push back instead of agreeing.
- [If something is odd, inappropriate, confusing, or boring, it is probably important.](https://photostructure.com/coding/odd-inappropriate-confusing-or-boring/) — a code-review philosophy.
- [Uncertain, lazy, forgetful, & impatient: it's what you want your code to be.](https://photostructure.com/coding/uncertain-lazy-forgetful-and-impatient/) — the design values these skills enforce.

## Versioning

`plugin.json` has no `version` field, so while this marketplace is hosted in git every
commit counts as a new version and `/plugin update` picks up changes automatically.
Add an explicit `version` once you want stable, opt-in releases.

## License

MIT © Matthew McEachen
