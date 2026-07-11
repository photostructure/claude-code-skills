<!--
OIDC / OAuth / SSO review checklist. See ../ATTRIBUTION.md.
Synthesized from the OWASP Authentication Cheat Sheet, RFC 9700 (OAuth 2.0 Security
BCP), the PortSwigger OAuth guidance, and public account-takeover CVEs in self-hosted
apps (Coder, Vaultwarden, Nhost, Roadiz, express-openid-connect). CC BY-SA 4.0.
-->

# OIDC / OAuth / SSO Review

Load when the scope includes an OAuth/OIDC login flow — a callback route
(`/auth/callback`, `/oidc/callback`, `/sso/...`), an `openid-client`/`passport`/
`next-auth`/`@node-oauth` dependency, or "Login with …" config.

Self-hosted apps that bolt on SSO get this wrong in recurring, high-impact ways —
several are account-takeover CVEs (2025–2026) against exactly this class of software.
Treat every item below as a candidate, not a finding. For each absent control, trace
the applicable flow, attacker capability, missing protection, and concrete token,
session, or account impact. Drop a checklist miss that cannot pass the proof gate in
`false-positives.md`.

## A. Redirect URI validation

- [ ] Authorization server validates `redirect_uri` by **exact string match** against a
      registered allowlist — not prefix match, not "same domain", not regex.
- [ ] No open redirect on an allowlisted host that could be chained
      (`https://trusted//evil.com` path tricks — cf. express-openid-connect
      CVE-2022-24794).
- [ ] **The app's own post-login redirect** (`?next=`/`returnTo`/`redirect`, or a
      `returnTo` carried inside `state`) is allowlist-validated to a local path. An open
      redirect here forwards the just-issued code/token to an attacker → account
      takeover, even with a perfectly locked-down `redirect_uri`. Reject absolute URLs
      and protocol-relative `//host` values.
- [ ] `localhost`/dev redirect URIs aren't permitted in production config.

## B. State (CSRF) and nonce (replay)

- [ ] `state` is generated per-request, unguessable, **bound to the browser session**
      (cookie/session-stored), and validated on callback. Its absence lets an attacker
      log a victim into the *attacker's* account (login CSRF).
- [ ] `nonce` is generated, **persisted** (session/cache), sent in the auth request, and
      the returned ID token's `nonce` is compared to the stored value. **Confirm a stored
      value actually exists** — the recurring real bug (Roadiz GHSA-3gx8-q682-38mx) is
      generating a nonce, sending it, and never storing it, so the check is a no-op.
- [ ] **Unsolicited / IdP-initiated responses are rejected.** A callback with no matching
      **stored** `state` (i.e. the RP never started this flow) must be refused — there's
      no session baseline, so nonce/PKCE/state all vanish. "Accept a login the app never
      initiated" is a login-CSRF / token-injection foothold.

## C. ID token validation

- [ ] Signature verified against the IdP's JWKS via a real library
      (`openid-client`/`jose`), **not** a hand-rolled `jwt.decode()`. An ID token alone is
      not proof — signature **and** `iss` **and** `aud` **and** `exp` **and** `nonce` must
      all be checked.
- [ ] `iss` and `aud` claims checked (and `azp` when the token has multiple audiences);
      algorithm **pinned** (don't trust the token header's `alg`).
- [ ] `exp` enforced with only small clock-skew tolerance; `iat`/`nbf` sane. Don't accept
      long-lived or already-expired ID tokens.
- [ ] Keys come from the IdP's **discovery/JWKS endpoint**, never from a URL or `kid`
      supplied in the token header (`jku`/`x5u` injection → key confusion / SSRF).
- [ ] Multi-IdP setups defend against mix-up (RFC 9207 `iss` param, or a distinct
      redirect URI per IdP) so an IdP-A token can't be replayed on the IdP-B flow.

## D. Account linking / email trust — highest-impact self-hosted bug class

- [ ] Callback user lookup keys off the immutable **`(iss, sub)`** pair, **not email
      alone**.
- [ ] If email is a linking fallback, `email_verified` is checked **and fails closed** —
      a missing, non-boolean, or string `"false"` value is treated as *unverified*. This
      exact type-coercion bug caused **Coder CVE-2026-55075/55076** and the **Nhost**
      advisory.
- [ ] Auto-linking an OIDC identity to an **existing local-password account** requires an
      explicit confirmation while already authenticated, or 2FA on that account — silent
      link-by-email lets an attacker with a matching (or spoofable-unverified) IdP email
      take over a pre-existing account (**Vaultwarden GHSA-6x5c-84vm-5j56**).
- **Detect in code:** `findOrCreate({ where: { email: claims.email } })` (or equivalent)
  sourced from ID-token claims with no strict `email_verified === true` guard and no
  check for an existing different-provider link.

## E. PKCE

- [ ] PKCE (`code_challenge`/`code_verifier`) used for public/SPA clients (no secret),
      where interception or code injection provides a concrete attack path. RFC 9700
      recommends PKCE for confidential clients too, but omission alone is not a finding
      when a server-side client secret and the rest of the flow prevent code redemption
      or injection; prove those preconditions individually.

## F. Token leakage

- [ ] Implicit flow (`response_type=token`) is **not** used — tokens land in URL
      fragments, history, and `Referer`.
- [ ] Tokens aren't logged; callback/reset pages set `Referrer-Policy: no-referrer` if
      they can link out or load third-party resources.

## G. Self-hosted specifics

- [ ] OIDC client secret / signing keys aren't hardcoded example-config defaults admins
      forget to rotate (see `self-hosting-hardening.md` §3).
- [ ] The setup wizard that configures OIDC / creates the first admin locks itself down
      once an admin exists (not reachable unauthenticated post-setup).
- [ ] Dynamic client registration, if the library supports it, isn't exposed
      unauthenticated.

## H. Token type & misuse (the most common integration error)

ID token = **authentication** (who the user is, audience = the client). Access token =
**authorization** (what the bearer may call, audience = an API). They arrive together and
both are JWTs, so they get swapped — insecurely.

- [ ] **The user's identity is taken from the validated *ID token***, not from an access
      token. Treating a bearer access token as proof of identity is a real gap: it isn't
      audience-bound to this client and its claims aren't meant for authentication.
- [ ] **The ID token is not sent to APIs as a bearer credential**, and an inbound access
      token is validated for **`aud` = this API** before it's trusted (stops token
      pass-through / confused-deputy from another service's token).
- [ ] **`openid` scope is actually requested** (else no ID token is issued and code tends
      to fall back to trusting the access token / userinfo).
- [ ] **Userinfo response**, if used, is fetched over TLS with the access token and its
      `sub` is checked to match the ID token's `sub` — not trusted as a standalone
      identity.
- [ ] Refresh tokens (if used) are rotated, revocable, and stored server-side / in an
      httpOnly cookie — never in `localStorage` (see `vuln-classes.md` → JWT).

## Sources

- [RFC 9700 — OAuth 2.0 Security Best Current Practice](https://datatracker.ietf.org/doc/rfc9700/)
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html) · [PortSwigger — OAuth 2.0 vulnerabilities](https://portswigger.net/web-security/oauth)
- [GitGuardian — OIDC for developers: why your auth integration could be broken](https://blog.gitguardian.com/oidc-for-developers-auth-integration/) · [Auth0 — ID token vs access token](https://auth0.com/blog/id-token-access-token-what-is-the-difference/) · [HackTricks — OAuth to account takeover](https://book.hacktricks.xyz/pentesting-web/oauth-to-account-takeover)
- CVEs: [Coder CVE-2026-55075/55076](https://advisories.gitlab.com/golang/github.com/coder/coder/v2/CVE-2026-55076/) · [Vaultwarden GHSA-6x5c-84vm-5j56](https://github.com/dani-garcia/vaultwarden/security/advisories/GHSA-6x5c-84vm-5j56) · [Nhost GHSA-6g38-8j4p-j3pr](https://github.com/nhost/nhost/security/advisories/GHSA-6g38-8j4p-j3pr) · [Roadiz GHSA-3gx8-q682-38mx](https://github.com/roadiz/core-bundle-dev-app/security/advisories/GHSA-3gx8-q682-38mx) · [express-openid-connect GHSA-7p99-3798-f85c](https://github.com/auth0/express-openid-connect/security/advisories/GHSA-7p99-3798-f85c) · [feathersjs GHSA-ppf9-4ffw-hh4p (OAuth callback open redirect)](https://github.com/feathersjs/feathers/security/advisories/GHSA-ppf9-4ffw-hh4p)
