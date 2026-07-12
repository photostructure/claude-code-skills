<!--
OIDC / OAuth / SSO review checklist. See ../ATTRIBUTION.md.
Synthesized from OpenID Connect Core, RFC 9700 (OAuth 2.0 Security BCP), RFC 9207,
RFC 8252, OWASP guidance, and upstream security advisories. CC BY-SA 4.0.
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
      registered allowlist — not prefix match, not "same domain", not regex. The RFC
      8252 exception is a native app's loopback redirect, where only the ephemeral port
      may vary; it is not an exception for ordinary web clients.
- [ ] No open redirect on an allowlisted host that could be chained
      (`https://trusted//evil.com` path tricks — cf. express-openid-connect
      CVE-2022-24794).
- [ ] **The app's own post-login redirect** (`?next=`/`returnTo`/`redirect`, or a
      `returnTo` carried inside `state`) is validated against a local-destination
      policy. An open redirect is prohibited by RFC 9700, but does not automatically
      leak a code or token. Prove whether token-bearing query/fragment data is
      preserved, an OAuth redirect URI can be chained through it, or the only impact
      is phishing. Reject absolute URLs and protocol-relative `//host` values after
      parsing and require the expected origin/path policy.
- [ ] Loopback redirects are used only for native-app clients and follow RFC 8252
      (loopback IP literal recommended, exact path match, variable port allowed).

## B. State (CSRF) and nonce (replay)

- [ ] The client uses a valid transaction-bound CSRF mechanism. RFC 9700 permits a
      client to rely on correctly enforced PKCE when it has established authorization-
      server support; otherwise use a one-time `state` bound to the user agent, or an
      OIDC `nonce` under the RFC's conditions. Do not report missing `state` when PKCE
      or `nonce` demonstrably supplies the required binding.
- [ ] When `nonce` is used, it is transaction-specific, **persisted** (session/cache),
      sent in the authentication request, and compared with the returned ID token's
      claim. Confirm a stored expected value exists; generating and sending a nonce
      without retaining it cannot validate the response.
- [ ] **Unsolicited / IdP-initiated responses are rejected.** A callback with no matching
      stored transaction (`state`, PKCE verifier, or nonce as applicable) must be
      refused unless the application deliberately implements a separately secured
      IdP-initiated protocol. Do not assume one particular transaction mechanism.

## C. ID token validation

- [ ] Signature verified against the IdP's JWKS via a real library
      (`openid-client`/`jose`), **not** a hand-rolled `jwt.decode()`. An ID token alone is
      not proof — validate signature, `iss`, `aud`, and `exp`, plus `nonce` when one was
      sent. Apply the precise OpenID Connect validation rules for the flow and token
      endpoint; do not replace them with a generic JWT checklist.
- [ ] `iss` and `aud` claims checked (and `azp` when the token has multiple audiences);
      allowed algorithms follow trusted client/issuer metadata or explicit application
      configuration rather than the token header's `alg` alone.
- [ ] `exp` is enforced with bounded clock-skew tolerance; validate `iat`/`nbf` when
      present and security-relevant to the library/profile.
- [ ] Keys come from the trusted issuer's configured/discovered **JWKS endpoint**.
      Header `kid` may select a key only within that trusted set; attacker-controlled
      `jku`/`x5u` or a `kid` used as a URL/file path can create key confusion, traversal,
      or SSRF.
- [ ] Multi-IdP setups defend against mix-up by validating RFC 9207 `iss` (or another
      authorization-response issuer signal as RFC 9700 permits), or by using and
      checking a distinct redirect URI per issuer.

## D. Account linking / email trust — highest-impact self-hosted bug class

- [ ] Callback user lookup keys off the immutable **`(iss, sub)`** pair, **not email
      alone**.
- [ ] If email is a linking fallback, `email_verified` is checked **and fails closed** —
      a missing, non-boolean, or string `"false"` value is treated as *unverified*. This
      type/coercion failure appears in **Coder CVE-2026-55076**; the **Nhost** advisory
      demonstrates the broader fail-open class, where provider adapters ignored or
      incorrectly manufactured email-verification status. Also verify that the issuer
      is explicitly trusted and that its documented `email_verified` semantics establish
      the assurance the application assumes; strict boolean handling cannot make an
      arbitrary or misconfigured IdP trustworthy.
- [ ] Auto-linking an OIDC identity to an **existing local-password account** requires an
      explicit confirmation while already authenticated, or 2FA on that account — silent
      link-by-email lets an attacker with a matching (or spoofable-unverified) IdP email
      take over a pre-existing account (**Vaultwarden GHSA-6x5c-84vm-5j56**).
- **Detect in code:** `findOrCreate({ where: { email: claims.email } })` (or equivalent)
  sourced from ID-token claims with no trusted-issuer policy, no strict
  `email_verified === true` guard, or no check for an existing different-provider link.

## E. PKCE

- [ ] Public clients use PKCE with `S256`; RFC 9700 requires this. Confidential clients
      should use PKCE too; a confidential OIDC client may instead use the specified
      nonce-based precautions. Report an omission only after proving the applicable
      client type/flow and code-injection or redemption consequence.

## F. Token leakage

- [ ] Implicit flow (`response_type=token`) is avoided. RFC 9700 recommends code flow
      because access tokens issued in authorization responses have additional leakage,
      injection, and replay exposure. Do not claim URL fragments are sent in HTTP
      `Referer` headers; identify the actual leakage mechanism in this application.
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
**authorization** (what the bearer may call, normally intended for a resource server).
They are often handled together, but an access token may be opaque or a JWT; do not infer
token purpose from serialization.

- [ ] **The user's identity comes from validated OIDC identity data**: an ID token, or a
      UserInfo response whose `sub` exactly matches the ID token. Do not treat arbitrary
      access-token claims as an ID token; access-token validation is profile/API-
      specific and its audience is normally the resource server, not the client.
- [ ] **The ID token is not sent to APIs as a bearer credential**, and an inbound access
      token is validated as intended for this API according to its profile (`aud` when
      applicable, or authoritative introspection) before it is trusted.
- [ ] **`openid` scope is actually requested** (else no ID token is issued and code tends
      to fall back to trusting the access token / userinfo).
- [ ] **Userinfo response**, if used, is fetched over TLS with the access token and its
      `sub` is checked to match the ID token's `sub` — not trusted as a standalone
      identity.
- [ ] Refresh tokens issued to public clients are sender-constrained or rotated as RFC
      9700 requires. Verify storage against the client architecture; browser storage
      readable by application JavaScript increases XSS theft impact, while an httpOnly
      cookie introduces ambient-credential/CSRF considerations.

## Sources

- [RFC 9700 — OAuth 2.0 Security Best Current Practice](https://datatracker.ietf.org/doc/rfc9700/)
- [OpenID Connect Core 1.0 incorporating errata set 2](https://openid.net/specs/openid-connect-core-1_0.html)
- [RFC 9207 — OAuth 2.0 Authorization Server Issuer Identification](https://datatracker.ietf.org/doc/html/rfc9207) · [RFC 8252 — OAuth 2.0 for Native Apps](https://datatracker.ietf.org/doc/html/rfc8252)
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- Upstream advisories: [Coder CVE-2026-55076 / GHSA-75vm-6w67-gwvp](https://github.com/coder/coder/security/advisories/GHSA-75vm-6w67-gwvp) · [Vaultwarden GHSA-6x5c-84vm-5j56](https://github.com/dani-garcia/vaultwarden/security/advisories/GHSA-6x5c-84vm-5j56) · [Nhost GHSA-6g38-8j4p-j3pr](https://github.com/nhost/nhost/security/advisories/GHSA-6g38-8j4p-j3pr) · [Roadiz GHSA-3gx8-q682-38mx](https://github.com/roadiz/core-bundle-dev-app/security/advisories/GHSA-3gx8-q682-38mx) · [express-openid-connect GHSA-7p99-3798-f85c](https://github.com/auth0/express-openid-connect/security/advisories/GHSA-7p99-3798-f85c) · [feathersjs GHSA-ppf9-4ffw-hh4p](https://github.com/feathersjs/feathers/security/advisories/GHSA-ppf9-4ffw-hh4p)
