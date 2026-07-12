<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# JWT algorithm confusion & key selection

A JWT header is attacker-controlled input. Constrain algorithms and bind key selection to
trusted issuer configuration; do not treat header parameters as policy.

## Pin the algorithm; separate keys by algorithm

- Anti-pattern: a `verify` call with no reviewed algorithm constraint, use of decode-only
  output as authenticated claims, or code that reads `header.alg` to select a verifier.
  Library defaults differ by version and key type, so missing an explicit option is a
  verification point. If one verifier accepts both RSA signatures and HMAC with the same
  key material, an attacker can re-sign an
  `HS256` token using the known RSA **public** key (public PEM, JWKS `n`/`e`, or `/certs`
  endpoint) as the HMAC secret; the server HMACs with that same public key and the forgery
  verifies. This is the RS256 -> HS256 confusion attack (RFC 8725 §2.1).
- Fix: pass an explicit algorithm allowlist to the verifier (for example,
  `algorithms: ['RS256']` in `jsonwebtoken` or jose's `jwtVerify` options), and ensure each
  verification key is used with exactly one algorithm as RFC 8725 requires. An application
  may support multiple token profiles, but each profile needs separate issuer, key, claim,
  and algorithm configuration; never let one verifier consume both an HMAC secret and an
  asymmetric public key.
- Verify against the installed version: library defaults for accepted algorithms change
  across versions and are drift-prone. Confirm the installed version's default `algorithms`
  set and whether `alg: "none"` / unsecured JWTs are ever accepted before marking Met — do
  not assume a documented default holds.

## Treat the `kid` header as untrusted; allowlist key lookup

- Anti-pattern: a `kid` value from the token header flowing into a key lookup sink —
  `readFileSync(header.kid)` / `path.join(keyDir, header.kid)`, or a SQL/ORM query
  interpolating `kid` (`WHERE kid = '${kid}'`). The attacker controls `kid`; path/query
  injection can select unintended bytes as the verification key.
- Fix: use `kid` only as an opaque lookup value within the trusted issuer's configured key
  set (a local map, parameterized store query, or issuer-bound JWKS). Reject unknown or
  duplicate/ambiguous matches. Never interpolate it into a path, query, URL, or command.

## Allowlist or ignore key-URL headers; validate the claim set

- Anti-pattern: the verifier honoring a `jku`/`x5u` URL (or `jwk`/`x5c` inline key) from the
  token header — fetching the JWKS/cert from a token-supplied URL. An attacker points it at
  a host they control, serves their own public key, and signs with the matching private key
  (RFC 8725 §3.10; also an SSRF sink — see ./ssrf.md).
- Fix: ignore token-supplied key URLs/inline keys unless the token profile explicitly uses
  them and applies RFC 8725's trust rules. Normally configure the issuer and JWKS endpoint
  server-side and ensure any fetched key belongs to that issuer; do not fetch an arbitrary
  header URL.
- Anti-pattern: a decoded token used for authorization without checking the claims required
  by its profile—for example, missing expected issuer/audience checks or ignoring an
  `exp`/`nbf` that the profile requires.
- Fix: validate the claims required by the token profile: exact expected `iss` and `aud`,
  expiration/not-before when present or required, and mutually exclusive validation rules
  (often including explicit `typ`) for access, refresh, and ID tokens. Do not assume every
  JWT profile requires the same registered claims.

## Primary sources

- [OWASP JSON Web Token Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_Cheat_Sheet.html)
- [RFC 8725 — JSON Web Token Best Current Practices](https://datatracker.ietf.org/doc/html/rfc8725)
- [`jsonwebtoken` README — `verify` options](https://github.com/auth0/node-jsonwebtoken#jwtverifytoken-secretorpublickey-options-callback)
- [jose `jwtVerify` API](https://github.com/panva/jose/blob/main/docs/jwt/verify/functions/jwtVerify.md)
