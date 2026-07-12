<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# Dependency & CI/CD Supply Chain

Harden how third-party code enters the build and how the build's trust and secrets are spent. See also `../identity-sessions-and-secrets.md` (token/OIDC handling) and `../../ATTRIBUTION.md`.

## Install-time execution

- Dependency lifecycle scripts can execute code during installation. Treat plain
  `npm install`/`npm ci` as a review point, not an automatic gap: some projects require
  vetted native/build scripts. Prefer npm's current dependency-script allowlist policy
  where supported, or `npm ci --ignore-scripts` followed by explicitly reviewed package
  rebuilds. Confirm the installed npm version and test that required artifacts still build.
- A release-age cooldown can reduce immediate uptake of a newly compromised version, at
  the cost of delaying fixes. Current npm supports `min-release-age` and scoped exclusions;
  verify the installed CLI and explicitly handle urgent security updates rather than
  copying a version-dependent setting from another package manager.
- Anti-pattern: floating ranges (`^`, `~`, `latest`) with no committed lockfile, or `npm
  install` (mutates the lockfile) in CI. Fix: commit the lockfile and use `npm ci`, which
  installs the locked tree exactly and fails on drift.

## CI/CD trigger and secret boundaries

- The `pull_request_target` "pwn-request" footgun: this GitHub Actions trigger runs the
  workflow from the base branch in a privileged context that may have write permissions
  and secrets (subject to explicit permissions, repository settings, and special actors
  such as Dependabot). Anti-pattern: `on: pull_request_target` plus an
  `actions/checkout` whose `ref:` is the PR head
  (`github.event.pull_request.head.sha`/`.ref`) followed by running that code — build,
  test, lint, `npm install` (lifecycle scripts!), or any `run:` over checked-out files.
  That executes attacker code inside a secret-bearing context. GitHub documents additional
  protection in `actions/checkout` v7+; verify the installed action and flag any
  `allow-unsafe-pr-checkout: true` opt-out, but do not assume it covers other fetch methods.
- Fix: run untrusted PR code under `on: pull_request` (fork PRs there get a read-only
  token and no secrets). If you must combine untrusted code with privileged actions, split
  it: an unprivileged job builds/tests the head, then a separately designed privileged
  workflow consumes only narrowly defined outputs. Treat artifacts as untrusted data—an
  archive, report, filename, or parser can itself carry an exploit—and require review or
  robust parsing before any privileged action. A protected environment limits secret use
  but does not make attacker-produced artifacts inert.
- Pin third-party actions by full commit SHA, not a mutable tag. Anti-pattern:
  `uses: some/action@v3` or `@main`; a moved tag silently ships new code into your
  pipeline. Fix: `uses: some/action@<full-length-commit-sha>` and verify the commit belongs
  to the intended repository.
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
- [npm CLI: dependency script policy](https://docs.npmjs.com/cli/install/)
- [npm: Generating provenance statements](https://docs.npmjs.com/generating-provenance-statements)
- [GitHub Security Lab: Keeping your GitHub Actions and workflows secure Part 1 — pwn requests](https://securitylab.github.com/resources/github-actions-preventing-pwn-requests/)
- [GitHub Docs: Security hardening for GitHub Actions](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions)
- [GitHub Docs: securely using `pull_request_target`](https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target)
