<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# CSRF Tokens in Node Frameworks

Harden state-changing requests against cross-site forgery; recognize dead and naive controls in review.

## Do not reach for csurf

- Greppable: `require("csurf")`, `import csurf from "csurf"`, `app.use(csurf(...))`, or `"csurf"` in `package.json`. The `expressjs/csurf` repository is archived and no longer maintained (no issues, features, or fixes). Do not resolve a missing-CSRF finding by installing it.
- Fix: adopt a maintained control. A signed double-submit implementation (e.g. `csrf-csrf`) or a framework built-in is the durable lever, not a specific package name. Verify the replacement's current maintenance status (recent releases, open-issue responsiveness) against the installed version before recommending it—do not assume today's popular package is still healthy.
- Framework built-ins are preferable where they exist: Fastify via `@fastify/csrf-protection` (NestJS has no built-in—its docs point to `csrf-csrf` for the Express adapter, `@fastify/csrf-protection` for the Fastify adapter). Full-stack frameworks that check the request origin by default: Next.js Server Actions compare `Origin` against `Host`/`X-Forwarded-Host` (POST-only, permissive when `Origin` is absent—verify against the installed version), and SvelteKit's `csrf.checkOrigin` is on by default for browser form posts. Remix ships no dedicated CSRF control—its only default is `SameSite=Lax` cookies (defense-in-depth, see below); add a token library (e.g. `remix-utils`) for a real control. Confirm any built-in is actually enabled, not merely available.

## Token pattern: synchronizer vs. signed double-submit

- Synchronizer token: server generates a per-session (or per-request) secret, stores it server-side, and compares the submitted token to the stored value. Strongest, but requires server session state.
- Signed double-submit: token is an HMAC over a session-bound value using a server-side secret, sent in both a cookie and a request field; server recomputes and compares. Use this when stateless. Naive (unsigned) double-submit—cookie value compared to a mirrored field with no secret—is forgeable via subdomain/cookie-injection and is not an adequate control.
- Greppable weaknesses: token compared with `==`/`===` on attacker-writable values; token derived from static identity (`user.id`, email) instead of a session-dependent value; a single global token reused across users; no secret in the double-submit (no HMAC/`createHmac`). Fix: bind the token explicitly to a session-specific value (session id, or a random claim inside the JWT), sign with a server-held secret, and compare with a constant-time check (`crypto.timingSafeEqual`).

## Method and verb discipline

- Greppable: CSRF middleware mounted after a state-changing route, or routes that mutate state on `app.get(...)`. Validate the token only for unsafe methods (POST/PUT/PATCH/DELETE); treat GET/HEAD/OPTIONS as safe and never mutate on them.
- Reject (not silently skip) unsafe requests whose token is absent, malformed, or mismatched. Ensure the middleware runs before every mutating handler, including nested routers.

## Header-boundary fallback

- Origin/Referer check: for unsafe methods, compare the `Origin` header (fall back to `Referer`) against an allowlist of expected target origins using a real URL parser—normalized scheme/host/port, never a prefix/suffix match. These are forbidden headers browsers will not let script forge.
- Fetch Metadata: reject unsafe cross-origin requests where `Sec-Fetch-Site` is `cross-site` (and evaluate `same-site` per your subdomain trust). Treat `none`/absent as legacy and fall through to Origin/Referer, which remains mandatory for browsers that omit `Sec-Fetch-*`. Support and header presence are version/client-sensitive—verify behavior for your supported browser matrix rather than assuming universal coverage.
- `SameSite` cookies (`Lax`/`Strict`) are defense-in-depth only: `Lax` blocks only unsafe cross-site methods, defaults vary across browser versions, and same-site subdomains bypass it. Do not mark CSRF handled because `SameSite` is set. Verify the framework's cookie default against the installed version; set it explicitly rather than relying on it.

## Verifying "Met"

Mark CSRF handled only after tracing a maintained control that binds the token to the session, rejects on token failure for every unsafe route, and has a header-boundary fallback. A set cookie flag or an installed package alone is not proof.

See ../input-output-and-files.md for trust boundaries and ../../ATTRIBUTION.md.

## Primary sources

- [expressjs/csurf (archived/deprecated)](https://github.com/expressjs/csurf)
- [OWASP Cross-Site Request Forgery Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
- [MDN Sec-Fetch-Site (Fetch Metadata Request Headers)](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Sec-Fetch-Site)
