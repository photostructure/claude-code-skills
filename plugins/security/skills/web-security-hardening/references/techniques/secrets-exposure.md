<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# Handling an Exposed Secret

Response and hardening for a credential that has leaked into source, git history, a
build artifact, or a client bundle. See also
[Secret lifecycle](../identity-sessions-and-secrets.md#secret-lifecycle).

## Treat exposure as compromise: rotate first

The moment a secret reaches source control, CI logs, an image layer, or a shipped
client bundle, assume it is captured. Removing the file, force-pushing, or rewriting
history does **not** undo the exposure — clones, forks, mirrors, CI caches, CDN copies,
and scrapers may already hold it.

- Anti-pattern to grep: literal high-entropy strings assigned to identifiers like
  `apiKey`, `secret`, `token`, `password`, `PRIVATE KEY`, `AWS_SECRET_ACCESS_KEY`,
  `DATABASE_URL`, or provider-specific prefixes (`sk_live_`, `ghp_`, `AKIA…`, `xoxb-`)
  in tracked files, `.env` committed to the tree, or fixtures/seed data.
- Fix: rotate/revoke at the issuer (new key pair, new DB password, new signing key,
  new OAuth client secret) and invalidate the old value. Prefer revocation you can
  confirm at the provider over "we deleted the line." Only after rotation is history
  scrubbing worthwhile, and only as cleanup — never as the remediation.
- Fix: move the live value into a secret manager or protected deployment facility and
  reference it at runtime; ignore files that contain live local secrets while retaining
  deliberately non-secret templates such as `.env.example`. Do not paste the full secret
  into tickets, chat, or review evidence — record a variable name or short prefix only.

## Scan history and artifacts, not just HEAD

A clean working tree says nothing about past commits or generated output. Grep of the
current checkout misses a secret introduced then reverted.

- Anti-pattern to grep: reviewing only `git status`/HEAD; assuming a deleted `.env`,
  a `.gitignore` entry added after the fact, or a squashed branch is safe.
- Fix: run a history-aware secret scanner (gitleaks / trufflehog-class) over the full
  commit graph, all branches, and tags — not just the tip. Wire the same scanner into
  CI/pre-commit so new leaks fail the build. Verify the exact tool, ruleset, and
  `--since`/full-history flags against the installed version.
- Fix: scan build/deploy outputs too — bundled/minified JS and source maps, Docker
  image layers, CI logs and job artifacts, `npm pack` tarballs, and cached `node_modules`.
  A secret can be absent from source yet inlined into `dist/` (see next section).

## Client-inlined env conventions must never carry secrets

Framework "public env" prefixes are compile-time string substitution into browser code.
Anything so prefixed is world-readable in the shipped bundle by design — not hidden,
just embedded.

- Anti-pattern to grep: a real secret assigned to a client-exposed name —
  `NEXT_PUBLIC_*` (Next.js) or `VITE_*` (Vite)—e.g.
  `NEXT_PUBLIC_STRIPE_SECRET`, `VITE_API_SECRET`, `VITE_AWS_SECRET_ACCESS_KEY`.
- Next.js inlines any `NEXT_PUBLIC_`-prefixed variable into the JS sent to the browser
  at `next build` — every `process.env.NEXT_PUBLIC_*` reference is replaced with a
  hard-coded value, so it is world-readable by design. Vite exposes `VITE_`-prefixed
  variables via `import.meta.env`, statically substituted into the client bundle at
  build time, and its docs explicitly warn `VITE_*` must not contain sensitive data.
- Fix: keep secrets in server-only env (unprefixed `process.env`, read in route
  handlers / server components / serverless/edge functions) and expose only a
  server-mediated result to the client. If a secret was already shipped under a public
  prefix, it is compromised — rotate it, then rename the variable to an unprefixed,
  server-only form. Confirm which prefix your framework/version treats as client-public
  against its installed env docs before trusting a name.

## Primary sources

- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [Next.js — Environment Variables (`NEXT_PUBLIC_` bundling)](https://nextjs.org/docs/app/guides/environment-variables)
- [Vite — Env Variables and Modes (`VITE_` exposure)](https://vite.dev/guide/env-and-mode)
