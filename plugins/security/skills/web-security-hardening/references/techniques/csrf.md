<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# CSRF Tokens in Node Frameworks

Harden state-changing requests against cross-site forgery; recognize dead and naive controls in review.

## Do not reach for csurf

- Greppable: `require("csurf")`, `import csurf from "csurf"`, `app.use(csurf(...))`, or `"csurf"` in `package.json`. The `expressjs/csurf` repository is archived and no longer maintained (no issues, features, or fixes). Do not resolve a missing-CSRF finding by installing it.
- Fix: adopt a maintained control. A signed double-submit implementation (e.g. `csrf-csrf`) or a framework built-in is the durable lever, not a specific package name. Verify the replacement's current maintenance status (recent releases, open-issue responsiveness) against the installed version before recommending it—do not assume today's popular package is still healthy.
- Prefer a maintained framework control when one exists. Verify the installed version,
  adapter, route type, proxy/origin configuration, and actual coverage; framework defaults
  change and package presence is not evidence that every state-changing route is protected.

## Token pattern: synchronizer vs. signed double-submit

- Synchronizer token: server generates a per-session (or per-request) secret, stores it server-side, and compares the submitted token to the stored value. Use it for stateful sessions.
- Signed double-submit: token is an HMAC over a session-bound value using a server-side secret, sent in both a cookie and a request field; server recomputes and compares. Use this when stateless. Naive (unsigned) double-submit—cookie value compared to a mirrored field with no secret—is forgeable via subdomain/cookie-injection and is not an adequate control.
- Greppable weaknesses: token compared with `==`/`===` on attacker-writable values; token derived from static identity (`user.id`, email) instead of a session-dependent value; a single global token reused across users; no secret in the double-submit (no HMAC/`createHmac`). Fix: bind the token explicitly to a session-specific value (session id, or a random claim inside the JWT), sign with a server-held secret, and compare with a constant-time check (`crypto.timingSafeEqual`).

## Method and verb discipline

- Greppable: CSRF middleware mounted after a state-changing route, or routes that mutate state on `app.get(...)`. Validate the token only for unsafe methods (POST/PUT/PATCH/DELETE); treat GET/HEAD/OPTIONS as safe and never mutate on them.
- Reject (not silently skip) unsafe requests whose token is absent, malformed, or mismatched. Ensure the middleware runs before every mutating handler, including nested routers.

## Header-boundary fallback

- Origin/Referer check: for unsafe methods, compare the `Origin` header (fall back to `Referer`) against an allowlist of expected target origins using a real URL parser—normalized scheme/host/port, never a prefix/suffix match. These are forbidden headers browsers will not let script forge.
- Fetch Metadata: reject unsafe cross-origin requests where `Sec-Fetch-Site` is
  `cross-site` (and evaluate `same-site` per your subdomain trust). An absent header needs
  the rollout policy's fallback (often Origin/Referer); `Sec-Fetch-Site: none` is a distinct
  browser value for user-initiated contexts, not “missing,” and should follow the policy for
  the method/resource. Verify behavior for the supported browser matrix.
- `SameSite` cookies are normally defense-in-depth: `Lax` still permits cookies on some
  top-level cross-site safe-method navigations, while `Strict` is more restrictive, and
  same-site sibling subdomains remain in the same “site.” OWASP describes narrow conditions
  where an explicit `SameSite` policy can suffice; assess those conditions instead of
  treating either “always enough” or “never enough” as universal.

## Verifying "Met"

Mark CSRF handled after tracing at least one appropriate primary defense across every
state-changing browser-authenticated route: a synchronizer/signed-double-submit token,
a custom-header plus strict CORS design, or a supported Fetch Metadata/origin policy with
its documented fallback. Header checks are useful defense-in-depth for token designs, not
a mandatory second mechanism in every architecture. A cookie flag or installed package
alone is not proof.

See ../input-output-and-files.md for trust boundaries and ../../ATTRIBUTION.md.

## Primary sources

- [expressjs/csurf (archived/deprecated)](https://github.com/expressjs/csurf)
- [OWASP Cross-Site Request Forgery Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
- [MDN Sec-Fetch-Site (Fetch Metadata Request Headers)](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Sec-Fetch-Site)
