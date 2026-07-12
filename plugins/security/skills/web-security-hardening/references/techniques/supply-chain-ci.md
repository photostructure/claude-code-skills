<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# Dependency & CI/CD Supply Chain

Harden how third-party code enters the build and how the build's trust and secrets are spent. See also `../identity-sessions-and-secrets.md` (token/OIDC handling) and `../../ATTRIBUTION.md`.

## Install-time execution

- Lifecycle scripts (`preinstall`/`install`/`postinstall`) run arbitrary code from every
  transitive dependency at install time. Anti-pattern: a plain `npm install`/`npm ci` in
  CI or a Dockerfile with no script suppression, so one compromised transitive version
  gets code execution on the builder.
- Fix: install with scripts disabled — `npm ci --ignore-scripts`, or set
  `ignore-scripts=true` in `.npmrc` so the default is safe. Then allowlist the few packages
  that genuinely need a build step and run only those explicitly (e.g. a rebuild step
  naming the native modules), rather than re-enabling scripts wholesale.
- Blunt compromised-new-version attacks with a release-age cooldown — malicious versions
  rely on fast automated pickup before takedown. Lever: npm `.npmrc` `min-release-age`
  (npm CLI ~11.10.0+); pnpm `minimumReleaseAge`, Yarn `npmMinimalAgeGate`, Bun
  `minimumReleaseAge`; or a Renovate/Dependabot cooldown window. Verify the exact key and
  supporting version against your installed manager — names/availability differ and are recent.
- Anti-pattern: floating ranges (`^`, `~`, `latest`) with no committed lockfile, or `npm
  install` (mutates the lockfile) in CI. Fix: commit the lockfile and use `npm ci`, which
  installs the locked tree exactly and fails on drift.

## CI/CD trigger and secret boundaries

- The `pull_request_target` "pwn-request" footgun: this GitHub Actions trigger runs the
  workflow from the **base** branch but with a **write** `GITHUB_TOKEN` and repo secrets,
  even for forked-PR runs. Anti-pattern (greppable): `on: pull_request_target` plus an
  `actions/checkout` whose `ref:` is the PR head
  (`github.event.pull_request.head.sha`/`.ref`) followed by running that code — build,
  test, lint, `npm install` (lifecycle scripts!), or any `run:` over checked-out files.
  That executes attacker code inside a secret-bearing context.
- Fix: run untrusted PR code under `on: pull_request` (fork PRs there get a read-only
  token and no secrets). If you must combine untrusted code with privileged actions, split
  it: an unprivileged job builds/tests the head, and a separate job gated behind a
  protected `environment:` (with required reviewers) consumes only inert artifacts — never
  checkout-and-execute head code in the privileged job. Treat labels/comments as
  bypassable gates, not trust.
- Pin third-party actions by full commit SHA, not a mutable tag. Anti-pattern:
  `uses: some/action@v3` or `@main`; a moved tag silently ships new code into your
  pipeline. Fix: `uses: some/action@<40-char-sha>`.
- Scope `permissions:` to least privilege (`contents: read` at the workflow top level,
  widen per-job only where needed). Verify the current default-token behavior against your
  org/repo settings — the platform default has changed over time.

## Provenance and verification

- Publish with build provenance so consumers can tie a package to its source and CI build:
  `npm publish --provenance` (or `provenance=true`/`NPM_CONFIG_PROVENANCE=true`) from
  OIDC-enabled trusted CI (GitHub Actions/GitLab). Requires `id-token: write` and a recent
  npm CLI (~9.5.0+); verify the minimum version against your toolchain. Anti-pattern:
  publishing from a laptop or a long-lived `NPM_TOKEN` with no attestation.
- Consumers verify with `npm audit signatures`, which checks registry signatures and
  provenance attestations for the installed tree. Provenance proves origin, not safety —
  it does not certify the code is non-malicious.

## Primary sources

- [npm CLI: npm ci](https://docs.npmjs.com/cli/commands/npm-ci)
- [npm CLI: npmrc / config (ignore-scripts)](https://docs.npmjs.com/cli/configuring-npm/npmrc)
- [npm: Generating provenance statements](https://docs.npmjs.com/generating-provenance-statements)
- [GitHub Security Lab: Keeping your GitHub Actions and workflows secure Part 1 — pwn requests](https://securitylab.github.com/resources/github-actions-preventing-pwn-requests/)
- [GitHub Docs: Security hardening for GitHub Actions](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions)
