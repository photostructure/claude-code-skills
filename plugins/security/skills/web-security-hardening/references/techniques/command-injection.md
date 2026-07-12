<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# OS Command & Argument Injection

Data reaching a process-spawning sink can inject commands (via a shell) or flags (even without one).

## Greppable sinks

Trace request/config data into these before marking anything Met:

- `child_process.exec(` / `execSync(` — always spawn a shell; the whole string is
  shell-parsed, so metacharacters (`;`, `|`, `&&`, `$()`, backticks) execute.
- Template-string or concatenated commands: `` exec(`convert ${name} …`) ``,
  `exec("git " + arg)` — attacker controls shell syntax.
- `{ shell: true }` (or `shell: "/bin/sh"`) passed to `spawn`/`execFile`/`spawnSync`/
  `execFileSync` — re-enables the shell and its metacharacter parsing.
- `spawnSync`/`execFileSync`/`spawn` whose command string embeds interpolated arguments
  while a shell is on.

Node's own docs: "Never pass unsanitized user input to [`exec`]. Any input containing
shell metacharacters may be used to trigger arbitrary command execution," and the same
warning applies whenever `shell` is enabled.

## Prefer no shell

- Use `execFile`/`spawn` with the command and an **argument array**, and keep
  `shell:false` (the default) — `execFile("git", ["clone", url])`. Each array element is
  passed as one literal `argv` entry, so shell metacharacters are inert.
- Keep the **command name server-selected** (a constant or allowlist key), never derived
  from request data. User data may only ever become an *argument*, not the executable.
- Better still, avoid spawning: use a library/binding (`fs.mkdir`, a native client) instead
  of shelling out. OWASP's primary defense is to not call OS commands at all.
- Verify against the installed Node version: `shell` defaults to `false` for
  `spawn`/`execFile` in current releases, but confirm no wrapper flips it and that
  Windows `.cmd`/`.bat` handling matches your version's behavior.

## Argument injection survives shell:false

`shell:false` stops *command* injection, not *argument* injection. An argument-array value
that starts with `-` is still parsed by the target program as a flag/option:

- `git` — `--upload-pack=<cmd>` (on `clone`/`fetch`/`pull`/`ls-remote`) reaches code
  execution; subcommand-specific write flags (e.g. `git archive --output=<path>`) reach
  arbitrary writes.
- `tar` — `--checkpoint-action=exec=<cmd>`, `--to-command`.
- `curl` — `-o <path>` / `--output` writes attacker-chosen files; `-K` reads a config file.

Fix, in order:

- **Allowlist** the value against expected set/shape (regex-anchored) whenever the domain
  permits it — the durable control.
- Insert a `--` **separator** before user operands so the program treats subsequent values
  as positional, not options: `execFile("git", ["clone", "--", url])`. Confirm the specific
  program honors `--` (most GNU tools do; verify per binary and version).
- Otherwise **reject flag-like values** (leading `-`) before use.
- Escaping helpers (`escapeshellarg` and friends) are a shell-era fallback, not the
  primary control — removing the shell and using arg arrays is preferred.

See [../input-output-and-files.md](../input-output-and-files.md) for the broader
input-validation and trust-boundary model. Attribution: [../../ATTRIBUTION.md](../../ATTRIBUTION.md).

## Primary sources

- [OWASP OS Command Injection Defense Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/OS_Command_Injection_Defense_Cheat_Sheet.html)
- [Node.js child_process documentation](https://nodejs.org/api/child_process.html)
