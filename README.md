# Claude Code coding skills

An opinionated [Claude Code](https://code.claude.com) plugin marketplace with five
workflow skills for disciplined planning, proof-based review, and clean commits.
Documented in depth at [photostructure.com/coding](https://photostructure.com/coding/).

| Skill            | What it does                                                                                   |
| ---------------- | ---------------------------------------------------------------------------------------------- |
| `replan`         | Iterative critique-and-refine planning. Forces multiple passes before committing to a design.  |
| `review`         | Code review that requires *proof* before reporting — a short list of real bugs, not noise.     |
| `review-staged`  | The same proof-based review, scoped to `git diff --cached`, then drives a clean commit.        |
| `gitplan`        | Untangle a large working tree into coherent, single-purpose Conventional Commits.              |
| `stage`          | Stage only the hunks the current session touched — never the whole file — and commit cleanly.  |

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

## Versioning

`plugin.json` has no `version` field, so while this marketplace is hosted in git every
commit counts as a new version and `/plugin update` picks up changes automatically.
Add an explicit `version` once you want stable, opt-in releases.

## License

MIT © Matthew McEachen
