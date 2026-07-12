<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# Helmet and effective headers

Verify security response headers by what routes actually emit, not by the presence of `helmet()`.

## Credit only headers that reach the route

Helmet (8.x) sets ~13 response headers by default: it adds a dozen (CSP,
Cross-Origin-Opener-Policy, Cross-Origin-Resource-Policy, Origin-Agent-Cluster,
Referrer-Policy, Strict-Transport-Security, X-Content-Type-Options, X-DNS-Prefetch-Control,
X-Download-Options, X-Frame-Options, X-Permitted-Cross-Domain-Policies, X-XSS-Protection)
and strips X-Powered-By. Cross-Origin-Embedder-Policy is off by default. Confirm the count
and set against the installed version—defaults shift across majors.

- Anti-pattern: `app.use(helmet())` mounted after routers, inside one sub-router, behind a
  `static`/proxy handler that returns first, or on an app the CDN/edge answers instead of.
  A `helmet()` call in `app.js` is not proof any given response carries the header.
- Fix: mount `helmet()` before route handlers on every app/router that serves responses,
  then confirm on the wire (`curl -sI <route>`)—credit a header only on routes where it
  actually appears, including error and asset routes.

## Configure CSP explicitly

- Anti-pattern: `helmet()` or `helmet.contentSecurityPolicy()` with no `directives`,
  relying on the terse built-in default; or a CSP string carrying `'unsafe-inline'` /
  `'unsafe-eval'` in `script-src`. Helmet's default `style-src` already includes
  `'unsafe-inline'`—verify the current default directives against the installed version.
- Fix: pass an explicit `directives` object (`default-src 'self'`, `object-src 'none'`,
  `base-uri 'self'`, `frame-ancestors 'self'`, tight `script-src`). Prefer nonces/hashes
  over `'unsafe-inline'`. See ../browser-and-http.md for CSP transport/report wiring.

## Disable a header only with a documented reason

- Anti-pattern: `helmet({ contentSecurityPolicy: false })`,
  `crossOriginResourcePolicy: false`, or `hsts: false` with no comment—usually pasted to
  silence a broken asset load, then forgotten.
- Fix: keep the header on; scope the exception (route-specific middleware, a relaxed
  directive) and comment why. A blanket `false` disables the control app-wide.

## Prefer CSP frame-ancestors; keep X-Frame-Options for legacy

CSP `frame-ancestors` supersedes X-Frame-Options in supporting browsers—the W3C CSP2 spec
states `frame-ancestors` obsoletes XFO and that when both are present `frame-ancestors`
SHOULD be enforced and XFO SHOULD be ignored (MDN itself only calls `frame-ancestors` the
"more comprehensive" option, and marks only XFO's `ALLOW-FROM` directive obsolete—not the
header as a whole). XFO has no allowlist-of-multiple-origins expressivity.

- Anti-pattern: framing policy expressed only via `X-Frame-Options` (e.g.
  `helmet.frameguard(...)` / `xFrameOptions`) with no `frame-ancestors` in the CSP, or the
  two disagreeing (`XFO: SAMEORIGIN` vs `frame-ancestors 'none'`).
- Fix: set `frame-ancestors` as the primary control; retain `X-Frame-Options: DENY`/
  `SAMEORIGIN` (Helmet default is `SAMEORIGIN`) as the legacy fallback and keep the two
  consistent.

## Do not double-emit at CDN and app

- Anti-pattern: HSTS, CSP, or X-Frame-Options set both at the edge/CDN/reverse proxy and by
  Helmet, so a response carries duplicate or conflicting values—`curl -sI` shows the header
  twice, or a weak edge value shadows the strict app value (override precedence varies by
  proxy).
- Fix: own each header in exactly one layer. If the edge is authoritative, disable the
  matching Helmet middleware there; otherwise ensure the edge passes the app value through
  unmodified. Verify the final on-the-wire value, not the intent.

## Primary sources

- [Helmet documentation](https://helmet.js.org/)
- [W3C CSP Level 2: frame-ancestors obsoletes X-Frame-Options](https://www.w3.org/TR/CSP2/#directive-frame-ancestors)
- [MDN: Content-Security-Policy frame-ancestors](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/frame-ancestors)
- [MDN: X-Frame-Options](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/X-Frame-Options)
- [OWASP HTTP Security Response Headers Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html)
