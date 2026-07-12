<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# JWT algorithm confusion & key selection

A JWT header is attacker-controlled input. If the verifier lets the token choose its own
algorithm or its own key, signature verification proves nothing. Pin the algorithm and
select the key server-side.

## Pin the algorithm; separate keys by algorithm

- Anti-pattern: a `verify`/`decode` call with no algorithm constraint, or one that derives
  the algorithm from the token — `jwt.verify(token, key)` with no `algorithms` option
  (recent `jsonwebtoken` derives the default set from the key type, e.g. an RSA key defaults
  to `['RS256','RS384','RS512']`, but older versions inferred the algorithm from the token
  header, and any config admitting both an HMAC and an RSA algorithm re-opens the confusion —
  verify against the installed version), `jwtVerify(token, key)` without a fixed `alg` (jose
  defaults to every `alg` applicable to the supplied key), or any code reading `header.alg` to pick a
  verifier. With a single RSA verifier that also accepts HMAC, an attacker re-signs an
  `HS256` token using the known RSA **public** key (public PEM, JWKS `n`/`e`, or `/certs`
  endpoint) as the HMAC secret; the server HMACs with that same public key and the forgery
  verifies. This is the RS256 -> HS256 confusion attack (RFC 8725 §2.1).
- Fix: pass an explicit single-algorithm allowlist to the verifier — `algorithms: ["RS256"]`
  in `jsonwebtoken`, `algorithms: ["RS256"]` in jose's `jwtVerify` options, or a fixed RSA
  algorithm bound into the verifier for java-jwt (`Algorithm.RSA256(pub, null)`; recent
  java-jwt deprecates the two-key form in favor of a single public key or a `KeyProvider` —
  verify against the installed version) — and reject any token
  whose `alg` is not on it. Never load a symmetric secret and an asymmetric key into the
  same verifier; keep signing material segregated by algorithm so an HMAC path can never
  consume an RSA key. RFC 8725 §3.1: each key is used with exactly one algorithm.
- Verify against the installed version: library defaults for accepted algorithms change
  across versions and are drift-prone. Confirm the installed version's default `algorithms`
  set and whether `alg: "none"` / unsecured JWTs are ever accepted before marking Met — do
  not assume a documented default holds.

## Treat the `kid` header as untrusted; allowlist key lookup

- Anti-pattern: a `kid` value from the token header flowing into a key lookup sink —
  `readFileSync(header.kid)` / `path.join(keyDir, header.kid)` (path traversal to an
  attacker-known file, e.g. `../../dev/null` or a predictable public file used as the HMAC
  secret), a SQL/ORM query interpolating `kid` (`WHERE kid = '${kid}'`), or a Redis/lookup
  key built from `kid`. The attacker controls `kid`, so they steer which bytes become the
  verification key.
- Fix: never use `kid` to construct a filesystem path, query, or command. Resolve it only
  through a fixed server-side map (`allowedKeys[kid]`) or a validated JWKS `keys[]` lookup,
  and reject any `kid` not present. If `kid` must hit a store, bind it as a parameter and
  constrain its charset — see ./path-traversal.md and ./sql-injection.md.

## Allowlist or ignore key-URL headers; validate the claim set

- Anti-pattern: the verifier honoring a `jku`/`x5u` URL (or `jwk`/`x5c` inline key) from the
  token header — fetching the JWKS/cert from a token-supplied URL. An attacker points it at
  a host they control, serves their own public key, and signs with the matching private key
  (RFC 8725 §3.10; also an SSRF sink — see ./ssrf.md).
- Fix: ignore `jku`/`x5u`/`jwk`/`x5c` from untrusted tokens, or resolve them only against a
  strict allowlist of known-good issuer URLs. Configure the JWKS source in server config, not
  from the token.
- Anti-pattern: a decoded token used for authorization without checking registered claims —
  no `issuer`/`audience` option passed, or `exp`/`nbf` unenforced.
- Fix: validate `iss` and `aud` against expected values (`issuer` / `audience` verify
  options), enforce `exp` and `nbf` (reject expired / not-yet-valid), and check `typ` where
  the design distinguishes token types, so an access token cannot be replayed as a refresh
  or ID token. See also ../identity-sessions-and-secrets.md.

## Primary sources

- [OWASP JSON Web Token Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_Cheat_Sheet.html)
- [RFC 8725 — JSON Web Token Best Current Practices](https://datatracker.ietf.org/doc/html/rfc8725)
