<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# CORS misconfiguration

CORS relaxes the browser same-origin policy; it is authorization for *reading cross-origin
responses*, not authentication. A permissive policy plus credentials lets any site read a
victim's authenticated data. Review the resolved `Access-Control-Allow-*` headers, not the
intent.

## Reflected and wildcard origins

- **Anti-pattern:** `cors({ origin: true })` — the `cors` middleware documents `true` as
  "reflect the request origin, as defined by `req.header('Origin')`", so every caller's
  `Origin` is echoed into `Access-Control-Allow-Origin`. Manually
  `res.header('Access-Control-Allow-Origin', req.headers.origin)` is the same reflection.
  Separately, `app.use(cors())` with no options defaults to `Access-Control-Allow-Origin: *`
  (all origins allowed, no credentials) — overly permissive, though not credential-exploitable.
  Confirm the default against the installed `cors` version.
  **Fix:** pass an explicit allowlist — `cors({ origin: ['https://app.example.com'] })` or a
  callback that compares against a configured set and calls `callback(null, false)` for
  misses. Prefer *no* CORS headers when cross-origin browser access is unnecessary.
- **Anti-pattern:** a custom `origin` function that echoes `req` `Origin` after a loose test
  (`.test()` on a broad `RegExp`, `.startsWith`, `.includes`). Any reflect-after-loose-match
  is arbitrary-origin reflection.
  **Fix:** resolve the request origin to a member of a fixed allowlist and return that stored
  value, never the raw request value.

## Wildcard is incompatible with credentials

- **Anti-pattern:** `Access-Control-Allow-Origin: *` together with
  `Access-Control-Allow-Credentials: true` (e.g. `cors({ origin: '*', credentials: true })`).
  Browsers prevent the calling script from reading such a response. Do not treat that
  failure as CSRF protection: a credentialed request may still reach the server and cause
  side effects, subject to cookie `SameSite` and other browser rules.
  **Fix:** a credentialed API must return a **single exact origin** echoed from an allowlist,
  plus `Vary: Origin`. If credentials are not needed, drop `credentials: true` rather than
  narrowing the origin. `*` is acceptable only for genuinely public, unauthenticated,
  cookie-free resources.

## Match the full origin by equality

- **Anti-pattern:** substring/suffix matching — `origin.includes('example.com')` matches
  `example.com.attacker.com`; `origin.endsWith('example.com')` (no leading dot) matches
  `evilexample.com` and `notexample.com`. Even a leading-dot suffix ignores scheme/port, and
  regexes with an unescaped `.` (`/example.com/`) match `exampleXcom`.
  **Fix:** parse with `new URL(origin)` and compare the full normalized origin
  (`url.origin`, i.e. scheme + host + port) by string equality against allowlist entries.
  Anchor any RegExp (`^https://([a-z0-9-]+\.)?example\.com$`) and escape literal dots.
  See ../input-output-and-files.md (URL parsing, not string prefixes).

## Caching, null origin, and minimal surface

- **Anti-pattern:** a per-origin `Access-Control-Allow-Origin` on a cacheable response with no
  `Vary: Origin` — a shared cache serves one origin's ACAO to another.
  **Fix:** emit `Vary: Origin` whenever the response varies by `Origin`. The `cors` middleware
  adds it for dynamic origins; verify it appears on your actual responses (including error
  paths and CDN-cached routes) against the installed version.
- Treat the serialized `null` origin as untrusted by default. Sandboxed documents and
  privacy-sensitive contexts can legitimately produce it, and an attacker can create a
  sandboxed document with that origin. Allow it only for a documented use case with a
  separate trust mechanism; it does not identify one caller.
- Keep `methods` and `allowedHeaders` limited to what the API needs, and only set
  `Access-Control-Allow-Credentials` when cookies/auth are actually required. An expansive
  `Access-Control-Allow-Headers` is not an authorization bypass by itself, but it enlarges
  what an already-allowed origin can send; keep it aligned with the API contract. See
  ../browser-and-http.md.

Middleware defaults and reflection behavior are version-sensitive; confirm the resolved
response headers against the installed `cors` (or framework) version rather than trusting the
option name.

## Primary sources

- [MDN: Cross-Origin Resource Sharing (CORS)](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CORS)
- [npm `cors` middleware README](https://github.com/expressjs/cors#configuration-options)
- [OWASP HTML5 Security Cheat Sheet — CORS](https://cheatsheetseries.owasp.org/cheatsheets/HTML5_Security_Cheat_Sheet.html)
