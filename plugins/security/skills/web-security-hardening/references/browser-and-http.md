<!-- OWASP/MDN/Helmet-derived guidance. CC BY-SA 4.0. See ../ATTRIBUTION.md. -->

# Browser and HTTP Hardening

## Contents

- [Assess effective responses](#assess-effective-responses)
- [Helmet and security headers](#helmet-and-security-headers)
- [Content Security Policy](#content-security-policy)
- [Cookies and sessions](#cookies-and-sessions)
- [Forms and CSRF](#forms-and-csrf)
- [CORS](#cors)
- [Framing, MIME, referrer, and cache](#framing-mime-referrer-and-cache)
- [Cross-origin isolation and permissions](#cross-origin-isolation-and-permissions)

> **Technique cards** (concrete Node/JS anti-patterns and fixes; load per control):
> [`cors`](./techniques/cors.md), [`csrf`](./techniques/csrf.md),
> [`security-headers`](./techniques/security-headers.md).

## Assess effective responses

Build a response-type inventory before checking headers:

- browser HTML/SSR pages;
- static JS/CSS/fonts/images;
- authenticated downloads and sensitive documents;
- JSON APIs and redirects;
- OAuth/OIDC callbacks and pages that contain tokens;
- error responses and proxy/CDN-generated responses.

Inspect middleware order and upstream proxy/CDN behavior. A header set after a response
is sent, only on the happy path, or overwritten upstream is not effective. Do not require
browser-only headers on machine-consumed JSON unless they protect a real browser use case.

## Helmet and security headers

Helmet is an implementation aid, not the baseline itself. Current Helmet documentation
describes thirteen default response headers, but defaults and application compatibility
vary by version.

Check:

- `helmet()` or equivalent executes before applicable routes and errors;
- disabled headers have documented, profile-specific reasons;
- CSP directives match actual script/style/resource loading;
- development exceptions cannot leak into production;
- CDN/reverse-proxy headers do not conflict with application headers;
- tests or local response inspection verify the effective policy.

Do not mark the domain Met from package presence. Conversely, do not require Helmet when
the framework/proxy emits equivalent effective headers.

## Content Security Policy

CSP is primarily relevant to browser-rendered content. Prefer a strict nonce- or
hash-based policy for scripts over growing hostname allowlists.

Baseline considerations:

- `default-src` provides an intentional fallback;
- `script-src` uses per-response unpredictable nonces or build-time hashes where feasible;
- avoid `unsafe-inline` and `unsafe-eval` for scripts; document unavoidable legacy use;
- `object-src 'none'` unless active plugin content is deliberately required;
- constrain `base-uri`, `frame-ancestors`, and `form-action`;
- scope `connect-src`, `img-src`, `font-src`, `media-src`, and `worker-src` to real needs;
- do not put secrets or stable authorization values in nonces/report payloads;
- review third-party scripts as trusted code, not harmless URLs.

Roll out complex policy safely:

1. test the candidate with `Content-Security-Policy-Report-Only`, retaining any existing
   enforced policy while evaluating a stricter replacement;
2. collect and deduplicate violations without logging sensitive page data;
3. remove inline/eval patterns and narrow required sources;
4. enforce the policy;
5. retain monitoring and regression tests.

Do not claim CSP fixes an existing XSS sink. It is defense-in-depth; unsafe rendering
still needs contextual encoding or sanitization.

Helmet's default policy is a starting point, not automatically a strict CSP. Verify the
installed version and effective directives. Its default `upgrade-insecure-requests` may
break local HTTP development (notably `localhost` in some browsers), so keep environment
handling explicit.

## Cookies and sessions

For authentication/session cookies, assess:

- `Secure` whenever the production origin is HTTPS;
- `HttpOnly` unless JavaScript access is explicitly required and justified;
- explicit `SameSite=Strict` or `Lax` for same-site sessions; `None` only with `Secure`
  and a proven cross-site requirement;
- narrow `Domain` and `Path`; omit `Domain` where host-only scope is intended;
- treat `Path` as delivery scoping, not an authorization boundary between same-origin
  applications;
- `__Host-` prefix where compatible (`Secure`, no `Domain`, `Path=/`);
- session identifiers are opaque, random, rotated after login/privilege change, and
  invalidated server-side at logout/expiry;
- idle and absolute timeouts match sensitivity and are enforced server-side;
- persistent “remember me” tokens are separately scoped, rotatable, and revocable;
- cookie signing is not confused with encryption/confidentiality.

Inventory every security-relevant cookie. Do not treat a global default as proof if
individual calls override it.

## Forms and CSRF

CSRF applies when browsers automatically attach ambient credentials, usually cookies.
For every state-changing route reachable with such credentials:

- use a synchronizer token or well-implemented signed double-submit token, or an
  equivalent framework control;
- verify `Origin`/`Referer` or Fetch Metadata as an additional/fallback boundary;
- treat `SameSite` as defense-in-depth unless the narrow conditions for relying on it
  alone are documented and satisfied;
- never assign requested state-changing semantics to HTTP safe methods (GET, HEAD,
  OPTIONS, or TRACE);
- require reauthentication/user confirmation for especially sensitive changes;
- ensure CORS does not turn a custom-header CSRF design into a permissive cross-origin API.

HTML forms can send “simple” cross-origin requests using
`application/x-www-form-urlencoded`, `multipart/form-data`, or `text/plain` without a
CORS preflight. Requiring JSON alone is useful only if the server rejects simple content
types and the CORS policy is restrictive.

For forms themselves, also check autocomplete behavior for passwords/OTPs, server-side
validation, duplicate-parameter handling, safe error redisplay, and that hidden fields
are never trusted as authorization.

Bearer-only endpoints are not cookie-CSRF candidates when the browser cannot attach the
credential automatically. Still assess token storage and client-side request construction.

## CORS

CORS relaxes the browser same-origin policy; it is not authentication.

- Prefer no CORS headers when cross-origin browser access is unnecessary.
- Use exact configured origins for credentialed/private APIs.
- Never combine reflected arbitrary origins with `Access-Control-Allow-Credentials: true`.
- Validate the complete parsed origin (scheme, host, port); avoid substring/suffix regexes.
- Keep allowed methods and headers minimal and cache preflights deliberately.
- Include `Vary: Origin` when the response uses a specific origin selected dynamically
  from the request, so caches do not reuse it for another origin.
- Public read-only APIs may intentionally use `*`; document that data is public and
  credentials are not accepted.
- Test `null` origins and trusted-subdomain assumptions where relevant.

## Framing, MIME, referrer, and cache

- Use CSP `frame-ancestors` for framing policy; retain `X-Frame-Options` only for legacy
  coverage when compatible. JSON APIs and redirects generally gain little from it.
- Set accurate `Content-Type` and `X-Content-Type-Options: nosniff` for browser resources.
- Choose `Referrer-Policy` based on outbound-link and analytics needs; token-bearing or
  recovery/callback pages should avoid leaking URLs.
- Use `Cache-Control: no-store` for responses containing session identifiers, reset
  tokens, highly sensitive personal data, or one-time secrets. Distinguish browser and
  shared-cache behavior.
- Consider `Clear-Site-Data` for logout/account teardown only after assessing its broad
  effect on cookies, cache, and client storage.
- Remove unnecessary disclosure headers, but classify `X-Powered-By` removal as low-value
  defense-in-depth rather than a major control.

HSTS is appropriate only after HTTPS is reliably available for the origin. Start with a
safe rollout; add `includeSubDomains` or preload only when every affected host is ready.
For self-hosted/local-first products, unconditional HSTS can lock users out of HTTP-only
LAN deployments and must be profile-aware.

## Cross-origin isolation and permissions

COOP, COEP, and CORP can strengthen process/resource isolation but may break OAuth
popups, third-party embeds, fonts, images, and analytics. Mark them Recommended or
Optional according to actual cross-origin behavior; do not require them blindly.

Use `Permissions-Policy` to disable sensitive browser capabilities the app does not
need (camera, microphone, geolocation, etc.) or scope them to intended origins. This is
normally defense-in-depth, not an Essential gap.

## Primary sources

- [Helmet reference](https://helmetjs.github.io/)
- [MDN Content Security Policy guide](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CSP)
- [MDN practical CSP implementation](https://developer.mozilla.org/en-US/docs/Web/Security/Practical_implementation_guides/CSP)
- [OWASP HTTP Security Response Headers Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html)
- [OWASP Content Security Policy Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html)
- [OWASP CSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
- [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- [MDN `Set-Cookie`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie)
- [MDN CORS guide](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CORS)
- [RFC 9110 safe methods](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.1)
