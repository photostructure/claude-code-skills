<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# Helmet and effective headers

Verify security response headers by what routes actually emit, not by the presence of `helmet()`.

## Credit only headers that reach the route

Helmet's default header set changes across releases. Inspect the installed version and
effective production response instead of relying on a copied count or list; some controls,
including cross-origin isolation, require application-specific opt-in.

- Anti-pattern: `app.use(helmet())` mounted after routers, inside one sub-router, behind a
  `static`/proxy handler that returns first, or on an app the CDN/edge answers instead of.
  A `helmet()` call in `app.js` is not proof any given response carries the header.
- Fix: mount `helmet()` before route handlers on every app/router that serves responses,
  then confirm with a safe local/integration request using the relevant method—credit a
  header only on routes where it actually appears, including applicable error and asset
  responses. Do not probe a production service merely to complete a static review.

## Configure CSP explicitly

- Review Helmet's default CSP against the application's actual scripts, styles, frames,
  workers, and outbound connections. A default policy is not automatically a gap; the gap
  is a policy that is ineffective, bypassed, or incompatible enough that operators disable
  it. Treat `'unsafe-inline'`/`'unsafe-eval'` in `script-src` as high-risk exceptions.
- Fix: pass an explicit `directives` object (`default-src 'self'`, `object-src 'none'`,
  `base-uri 'self'`, `frame-ancestors 'self'`, tight `script-src`). Prefer nonces/hashes
  over `'unsafe-inline'`. See ../browser-and-http.md for CSP transport/report wiring.

## Disable a header only with a documented reason

- Review `helmet({ contentSecurityPolicy: false })`, `crossOriginResourcePolicy: false`,
  or `hsts: false` in context. Disabling an inapplicable header is legitimate; disabling an
  applicable control merely to silence a deployment/asset failure is a gap.
- Scope necessary exceptions, document the compatibility or ownership reason, and verify
  the effective response. A blanket `false` affects the whole middleware mount.

## Prefer CSP frame-ancestors; keep X-Frame-Options for legacy

CSP `frame-ancestors` supersedes X-Frame-Options in supporting browsers—the W3C CSP2 spec
states `frame-ancestors` obsoletes XFO and that when both are present `frame-ancestors`
SHOULD be enforced and XFO SHOULD be ignored (MDN itself only calls `frame-ancestors` the
"more comprehensive" option, and marks only XFO's `ALLOW-FROM` directive obsolete—not the
header as a whole). XFO has no allowlist-of-multiple-origins expressivity.

- If the application already sends CSP, include `frame-ancestors` and keep it consistent
  with XFO. XFO alone can still be an effective legacy-compatible framing control; treat
  adding CSP as a recommended improvement rather than declaring XFO-only universally a gap.
- Prefer `frame-ancestors` as the primary control; retain `X-Frame-Options: DENY`/
  `SAMEORIGIN` (Helmet default is `SAMEORIGIN`) as the legacy fallback and keep the two
  consistent.

## Avoid conflicting edge and app policies

- Review HSTS, CSP, or X-Frame-Options set at both the edge and application. Duplicate and
  conflicting fields have header-specific semantics and can produce surprising effective
  policy; do not assume the edge or application simply wins.
- Fix: document which layer is authoritative and avoid conflicting duplicates. Multiple
  CSP fields are jointly enforced rather than simply “last one wins,” while other headers
  have different combination rules; do not assume generic proxy precedence. Verify the
  final on-the-wire fields and browser semantics.

## Primary sources

- [Helmet documentation](https://helmet.js.org/)
- [W3C CSP Level 2: frame-ancestors obsoletes X-Frame-Options](https://www.w3.org/TR/CSP2/#directive-frame-ancestors)
- [MDN: Content-Security-Policy frame-ancestors](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/frame-ancestors)
- [MDN: X-Frame-Options](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/X-Frame-Options)
- [OWASP HTTP Security Response Headers Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html)
