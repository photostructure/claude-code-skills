<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# Credential Stuffing, Throttling, Step-Up

Harden the login and sensitive-action paths against high-volume automated attacks and secret-comparison leaks; recognize the naive controls in review. See also `../identity-sessions-and-secrets.md` (password storage, MFA, session lifecycle) and `../../ATTRIBUTION.md`.

## Credential stuffing is not single-account brute force

- Distinction: brute force tries many passwords against one account; credential stuffing replays known-valid username/password pairs (leaked elsewhere) across many accounts, so per-account lockout barely slows it — each account sees only one or two attempts while the attacker fans out over thousands. Password spraying is the inverse (one weak password against many accounts). MFA mitigates all three, but stuffing specifically demands volume/anomaly controls, not just lockout.
- MFA: require an appropriate additional factor or multi-factor authenticator for the
  accounts and assurance level in scope; prefer phishing-resistant WebAuthn with the
  required user-verification policy for privileged or high-impact access. A passkey may
  replace the password rather than act as a literal “second factor.” MFA
  materially limits reuse of a stolen password, but it does not replace throttling or
  anomaly detection and should not be reported as a universal requirement without the
  application's assurance profile.
- Compromised-password check: at password establishment and change, compare the complete
  candidate against a blocklist of common and compromised passwords. NIST requires this at
  establishment/change, not on every login. If using the HIBP range API, follow its current
  k-anonymity protocol (currently the first five SHA-1 hex characters, suffix matched
  locally) and never send the password or full hash.
- Risk-based bot controls: challenges and IP/device/network signals can supplement
  throttling during anomalous traffic. Account for accessibility and privacy, and do not
  make CAPTCHA or device fingerprinting an unconditional baseline gap.

## Throttle with a shared store; compare secrets in constant time

- An in-memory limiter resets on restart and each process/instance has an independent
  counter. That can be acceptable for one long-lived process; clustered, serverless, and
  horizontally scaled deployments need a store or edge control shared at the intended
  scope. Apply **separate** per-account and per-network/client budgets, plus an aggregate
  ceiling where useful; a single composite `account + IP` key is easy to evade by changing
  either component. Trust `req.ip` only after configuring the proxy boundary correctly.
- Use `crypto.timingSafeEqual` for fixed-length MACs, authentication tags, and comparable
  secret values. Decode and validate their fixed format/length before comparison; the API
  throws when byte lengths differ, and Node explicitly warns that it does not make
  surrounding code timing-safe. Verify asymmetric digital signatures with
  `crypto.verify` / `Verify.verify`, not a byte comparison. Do not use `timingSafeEqual`
  for passwords—use the password-hash verifier.

## Step-up: re-prove presence on the sensitive request

- Greppable anti-pattern: a high-risk handler (change email/password, disable MFA, add payee, export data) gated only by `req.session.user` / a valid JWT — the login could be hours old or a stolen long-lived session. Fix: gate the sensitive request **itself**, not just session existence, on recent authentication — check a server-recorded last-auth timestamp against a short freshness window, or require a fresh WebAuthn assertion (`navigator.credentials.get`, verified server-side) at the moment of the action. Scope step-up by operation risk, not only by whether the user is logged in.
- TOTP replay: greppable anti-pattern is a verify that only checks the current code arithmetically (`speakeasy`/`otplib` `verify(...)`) and returns success without recording what was used — a code stays valid for its whole ~30s step (plus any drift window), so a captured code is replayable until it expires. Fix: persist the last-accepted time-step/counter per user and reject any code whose step is `<=` the last one used; combine with per-user attempt rate-limiting. Protect TOTP seeds/QR provisioning data as secrets. Verify the acceptance window and drift options against the installed OTP library.

## Primary sources

- [OWASP Credential Stuffing Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Credential_Stuffing_Prevention_Cheat_Sheet.html)
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [OWASP Multifactor Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Multifactor_Authentication_Cheat_Sheet.html)
- [Node.js crypto.timingSafeEqual](https://nodejs.org/api/crypto.html#cryptotimingsafeequala-b)
- [HaveIBeenPwned Pwned Passwords range API](https://haveibeenpwned.com/API/v3#PwnedPasswords)
- [NIST SP 800-63B — Password Verifiers](https://pages.nist.gov/800-63-4/sp800-63b.html#passwordver)
- [RFC 6238 §5.2 — TOTP validation and replay](https://www.rfc-editor.org/rfc/rfc6238.html#section-5.2)
