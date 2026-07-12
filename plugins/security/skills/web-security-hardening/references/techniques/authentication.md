<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# Credential Stuffing, Throttling, Step-Up

Harden the login and sensitive-action paths against high-volume automated attacks and secret-comparison leaks; recognize the naive controls in review. See also `../identity-sessions-and-secrets.md` (password storage, MFA, session lifecycle) and `../../ATTRIBUTION.md`.

## Credential stuffing is not single-account brute force

- Distinction: brute force tries many passwords against one account; credential stuffing replays known-valid username/password pairs (leaked elsewhere) across many accounts, so per-account lockout barely slows it — each account sees only one or two attempts while the attacker fans out over thousands. Password spraying is the inverse (one weak password against many accounts). MFA mitigates all three, but stuffing specifically demands volume/anomaly controls, not just lockout.
- Primary defense — MFA: greppable gap is a login handler that issues a session/JWT immediately after the password check with no second-factor branch. Fix: require a phishing-resistant factor (passkey/WebAuthn) or at least TOTP before minting an authenticated session; prefer it for admin and high-risk accounts. This is the single highest-leverage control (OWASP's Credential Stuffing cheat sheet cites Microsoft's analysis that MFA would have stopped ~99.9% of account compromises).
- Breached-credential check: greppable gap is signup/reset/login that validates only length/complexity and never consults a compromised-password corpus. Fix: check the candidate password against a breach set at registration, reset, and (risk-permitting) login. Use the HaveIBeenPwned Pwned Passwords range API with k-anonymity — send only the first 5 hex chars of the SHA-1 hash and match the suffix locally; never send the full password or full hash. Verify the current API host/version and hash prefix length against its docs before implementing.
- Bot mitigation on abnormal volume: greppable gap is a login endpoint with no CAPTCHA/challenge and no IP/device signal. Fix: trigger a challenge (CAPTCHA, proof-of-work, or JS requirement) and weigh IP classification / geovelocity / device fingerprint reputation when volume or failure rate is anomalous. Do not rely on IP blocking alone — attackers rotate through proxy pools. Layer these; none is sufficient standalone.

## Throttle with a shared store; compare secrets in constant time

- Greppable anti-pattern: an in-memory counter (a module-level `Map`/object, or `express-rate-limit` with no `store:`) — it resets on restart and does not span workers/instances, so a clustered or serverless deploy has effectively no limit. Fix: back the limiter with a shared store (Redis/Memcached) via `rate-limiter-flexible` or `express-rate-limit` with a distributed store adapter. Key the limiter on account identifier **and** client IP together (plus a global cap) so stuffing across many accounts still trips a ceiling and a single victim account is protected independently. Confirm the trusted client IP derives from a correctly configured proxy, not a spoofable `X-Forwarded-For`.
- Greppable anti-pattern: `token === expected`, `apiKey == stored`, or `hmac !== sig` on a secret/MAC/reset-token — `===` short-circuits on the first differing byte and leaks length/prefix through timing. Fix: compare with `crypto.timingSafeEqual(a, b)`. It requires equal-length `Buffer`/`TypedArray`/`DataView` inputs and throws `RangeError` on a length mismatch, so guard lengths first (compare a fixed-size digest of each side, e.g. HMAC both values under a random key, rather than branching on `a.length === b.length` which itself leaks length). It is not for passwords — verify those against a slow salted hash (see `../identity-sessions-and-secrets.md`). Verify argument/throw behavior against the installed Node version.

## Step-up: re-prove presence on the sensitive request

- Greppable anti-pattern: a high-risk handler (change email/password, disable MFA, add payee, export data) gated only by `req.session.user` / a valid JWT — the login could be hours old or a stolen long-lived session. Fix: gate the sensitive request **itself**, not just session existence, on recent authentication — check a server-recorded last-auth timestamp against a short freshness window, or require a fresh WebAuthn assertion (`navigator.credentials.get`, verified server-side) at the moment of the action. Scope step-up by operation risk, not only by whether the user is logged in.
- TOTP replay: greppable anti-pattern is a verify that only checks the current code arithmetically (`speakeasy`/`otplib` `verify(...)`) and returns success without recording what was used — a code stays valid for its whole ~30s step (plus any drift window), so a captured code is replayable until it expires. Fix: persist the last-accepted time-step/counter per user and reject any code whose step is `<=` the last one used; combine with per-user attempt rate-limiting. Protect TOTP seeds/QR provisioning data as secrets. Verify the acceptance window and drift options against the installed OTP library.

## Primary sources

- [OWASP Credential Stuffing Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Credential_Stuffing_Prevention_Cheat_Sheet.html)
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [OWASP Multifactor Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Multifactor_Authentication_Cheat_Sheet.html)
- [Node.js crypto.timingSafeEqual](https://nodejs.org/api/crypto.html#cryptotimingsafeequala-b)
- [HaveIBeenPwned Pwned Passwords range API](https://haveibeenpwned.com/API/v3#PwnedPasswords)
