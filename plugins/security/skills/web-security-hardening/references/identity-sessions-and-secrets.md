<!-- NIST/OWASP-derived guidance. CC BY-SA 4.0. See ../ATTRIBUTION.md. -->

# Identity, Sessions, and Secrets

## Contents

- [Identity architecture](#identity-architecture)
- [Password policy](#password-policy)
- [Password storage](#password-storage)
- [Login and account lifecycle](#login-and-account-lifecycle)
- [MFA and passkeys](#mfa-and-passkeys)
- [Recovery and reset](#recovery-and-reset)
- [Session lifecycle](#session-lifecycle)
- [Bearer tokens and JWT](#bearer-tokens-and-jwt)
- [OAuth and OIDC](#oauth-and-oidc)
- [Application cryptography](#application-cryptography)
- [Secret lifecycle](#secret-lifecycle)

> **Technique cards** (concrete Node/JS anti-patterns and fixes; load per control):
> [`authorization`](./techniques/authorization.md), [`authentication`](./techniques/authentication.md),
> [`jwt`](./techniques/jwt.md), [`crypto-aead`](./techniques/crypto-aead.md),
> [`secrets-exposure`](./techniques/secrets-exposure.md).

## Identity architecture

Map every identity type and boundary:

- anonymous, user, administrator, support/operator, service, webhook, and background job;
- local password, passkey/WebAuthn, OAuth/OIDC, SAML, API key, mTLS, or delegated gateway;
- account creation/invitation, linking, privilege changes, suspension, deletion, recovery;
- browser sessions, mobile/API tokens, service credentials, and impersonation/support flows.

Require server-side authentication and authorization on every protected operation. UI
visibility, route naming, UUIDs, and client claims are not authorization. Use deny-by-
default policy and centralize common enforcement without hiding route-specific ownership.

## Password policy

Use NIST SP 800-63B-4 as the current policy baseline for centrally verified passwords:

- require at least **15 characters** when password is the sole authentication factor;
- a password used only within MFA may be shorter, but not below **8 characters**;
- permit a maximum length of at least **64 characters**, spaces, and broadly usable
  Unicode/printing characters;
- compare the complete prospective password against a blocklist of common, expected,
  context-specific, and compromised passwords;
- do not impose character-class composition rules;
- do not require periodic rotation without evidence of compromise;
- do not truncate; verify the complete password;
- allow password managers, autofill, paste, and a reveal-password control;
- do not use security questions or unauthenticated password hints.

Apply normalization consistently if Unicode passwords are accepted; never silently
change an established password's representation between creation and login.

Assess rate limiting/account throttling separately. Long passwords do not remove online
guessing risk, and throttling must avoid turning account locking into an easy denial of
service. Prefer progressive delay/risk signals and secure recovery over permanent lockout.

## Password storage

- Store salted adaptive password hashes, never plaintext, reversible encryption, or
  fast general-purpose hashes.
- Prefer Argon2id. Current OWASP minimum guidance includes `m=19 MiB`, `t=2`, `p=1`;
  benchmark and raise cost as practical for the deployment.
- If Argon2id is unavailable, follow current OWASP scrypt guidance. Use bcrypt only for
  legacy compatibility, with cost 10+ and explicit handling of its 72-byte input limit.
- For FIPS-driven environments, use current approved PBKDF2 parameters and HMAC variant.
- Let maintained libraries generate unique salts. A pepper is optional defense-in-depth
  and belongs in a secrets manager, separate from the password database.
- Store algorithm/parameters with the hash and rehash after successful login when policy
  increases.
- Bound password input length high enough for passphrases but low enough to prevent
  pathological hashing work; never truncate to enforce the bound.
- Compare hashes using library verification functions and avoid timing-distinguishable
  user-existence paths.

Verify installed library defaults rather than recognizing an algorithm name alone.

## Login and account lifecycle

- Use generic external responses for invalid username/password and recovery requests;
  align status, body, and timing enough to resist practical enumeration.
- Apply throttling to login, signup/invite acceptance, reset, MFA, recovery-code, and
  verification endpoints, preferably with per-account plus abuse-aware signals.
- Regenerate session identifiers after authentication and privilege changes.
- Notify users of consequential changes (password, MFA, email, recovery, new device)
  through an independent channel without including secrets.
- Require recent authentication or a stronger factor for password/email/MFA changes,
  credential export, destructive actions, and administrative elevation.
- Verify email/phone ownership before using it as an authentication/recovery factor.
- Prevent self-service fields from setting role, tenant, billing, verification, or
  ownership state.
- Define deprovisioning: disable sessions/tokens/API keys and remove or transfer access
  when accounts, memberships, or employees are removed.
- Treat support impersonation as a privileged workflow with explicit authorization,
  reason, visibility, time bounds, and audit records.

## MFA and passkeys

- Prefer phishing-resistant authenticators (passkeys/WebAuthn/security keys) for
  privileged/high-risk users and offer them broadly when feasible.
- Do not weaken the account through recovery: recovery codes, help-desk reset, remembered
  devices, and factor replacement need protection commensurate with the strongest factor.
- Store recovery codes as one-way verifiers, show once, make single-use, and regenerate/
  revoke as a set.
- Protect TOTP seeds and provisioning QR data as secrets; prevent replay within the
  accepted time window and rate-limit attempts.
- Require recent authentication and notify the user when enrolling/removing/replacing a
  factor.
- Define step-up authentication based on operation risk rather than only login state.
- Avoid SMS as the only strong factor for high-risk systems; document when it remains a
  recovery/compatibility tradeoff.

## Recovery and reset

- Return a consistent response whether an account exists.
- Generate reset/verification tokens with a CSPRNG and sufficient entropy.
- Store tokens as hashes where database disclosure is in scope; bind to user, purpose,
  and intended state transition.
- Make tokens short-lived, single-use, and atomically consumed.
- Invalidate prior tokens when issuing a replacement and invalidate relevant sessions
  after a successful password reset according to product policy.
- Build reset URLs from trusted public-origin configuration, never request Host headers.
- Keep tokens out of logs, analytics, referrers, third-party resources, and support tools.
- Do not automatically sign the user in after reset unless the complete flow intentionally
  establishes a new authenticated session with equivalent protections.
- Treat email change as an account-takeover-sensitive flow; notify old and new addresses
  and provide a secure recovery path.

## Session lifecycle

For server sessions:

- use opaque high-entropy identifiers; keep authorization state server-side or
  integrity-protected and freshness-checked;
- rotate identifiers at login, privilege change, and other trust transitions;
- enforce server-side idle and absolute timeouts appropriate to the application;
- invalidate server state at logout, reset, account disablement, and relevant credential
  changes—not only the browser cookie;
- provide users visibility/control over active sessions when account risk justifies it;
- constrain concurrent sessions according to product requirements without assuming one
  universal policy;
- protect session stores with least privilege, TLS/network boundaries, persistence and
  backup controls;
- prevent sensitive authenticated responses and session identifiers from being cached.

Cookie attributes and CSRF are covered in `browser-and-http.md`.

## Bearer tokens and JWT

- Prefer opaque server-revocable tokens when self-contained claims are unnecessary.
- Verify signature/MAC with an allowlisted algorithm and correct key; never trust the
  header's algorithm or key URL without policy.
- Validate issuer, audience, expiration, not-before where used, token type/purpose, and
  subject semantics.
- Keep access tokens distinct from ID tokens, refresh tokens, reset tokens, and session
  cookies; reject cross-use.
- Keep claims minimal and non-secret; signed JWT payloads are normally readable.
- Use short-lived access tokens and protected, rotating refresh tokens with reuse
  detection where feasible.
- Define revocation for logout, account disablement, compromise, and privilege changes;
  document the accepted propagation window for self-contained tokens.
- Never place bearer tokens in URLs. Redact them from logs/errors/traces.
- Store browser tokens according to the XSS/CSRF threat model rather than prescribing
  localStorage or cookies universally.

## OAuth and OIDC

- Use maintained protocol libraries and exact registered redirect URIs.
- Bind authorization requests to the initiating browser with unguessable session-bound
  `state`; use and validate OIDC `nonce` for ID-token replay protection.
- Validate signature, issuer, audience, expiration, and token type before trusting claims.
- Key accounts by immutable `(issuer, subject)` rather than email alone.
- Require strict `email_verified === true` before any email-based decision; do not
  silently auto-link an existing local account solely by matching email.
- Use PKCE for public clients and wherever the concrete flow benefits; do not label its
  absence a vulnerability without applicable attack preconditions.
- Keep client secrets and tokens out of browser bundles, URLs, logs, and analytics.
- Protect dynamic registration, discovery configuration, setup wizards, and provider
  changes as privileged administration.

## Application cryptography

Applies when the application itself encrypts, signs, or MACs data (fields, files, tokens,
cookies) rather than delegating confidentiality to TLS, the database, or an IdP.

- Use a vetted authenticated-encryption (AEAD) primitive—AES-256-GCM or
  XChaCha20-Poly1305 via Node `crypto`, WebCrypto, or libsodium—never a hand-rolled
  construction. Do not use ECB; it leaks plaintext structure.
- Generate a unique per-message IV/nonce from a CSPRNG and never reuse a nonce under one
  key. GCM/CTR nonce reuse enables keystream recovery and message forgery.
- Require an authentication tag (AEAD) or a verified MAC (encrypt-then-MAC) so tampering
  is detected; bind associated data (AAD) when surrounding context must be authenticated.
- Source every key, IV, salt, and security token from a CSPRNG (`crypto.randomBytes`,
  `crypto.randomUUID`, or WebCrypto `getRandomValues`), never `Math.random()`.
- Avoid broken primitives: no MD5/SHA-1 for signatures or integrity, no DES/3DES/RC4 for
  encryption. Separate keys by purpose and manage their lifecycle as secrets (below).

## Secret lifecycle

Inventory API keys, database credentials, signing/encryption keys, webhook secrets,
OAuth secrets, CI tokens, package credentials, and recovery material.

For each secret assess:

- generation strength and unique value per environment/tenant where appropriate;
- storage in a secret manager or protected deployment facility, not source/images/public
  bundles;
- least-privilege identity, resource scope, environment scope, and lifetime;
- secure injection without command-line/process-list, log, error, or build-layer leakage;
- rotation mechanism, overlap window, rollback, revocation, and compromise playbook;
- auditability of access/changes without logging the value;
- redaction in application logs, traces, crash reports, CI output, tickets, and reports;
- separation of signing, encryption, authentication, and development purposes;
- backup and disaster-recovery handling.

Do not echo complete secrets as review evidence. Preserve only a variable name or short
recognizable prefix/suffix. Never test a suspected credential against a live service.

## Primary sources

- [NIST SP 800-63B-4](https://pages.nist.gov/800-63-4/sp800-63b.html)
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
- [OWASP Forgot Password Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html)
- [OWASP Multifactor Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Multifactor_Authentication_Cheat_Sheet.html)
- [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [OWASP OAuth 2.0 Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/OAuth2_Cheat_Sheet.html)
- [OWASP Cryptographic Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html)
