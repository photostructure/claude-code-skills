<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# Fail Closed on Exceptional Conditions

A security control that throws, times out, or loses a dependency must deny, not default to allow.

## Fail-open shapes to grep for

Every security decision has an error path; the review question is where that path lands.

- Auth/authz middleware whose `catch` (or validation-miss branch) calls `next()` with no
  argument, `return next()`, or drops through to the handler. Grep middleware for
  `catch` blocks that reach `next()` instead of `next(err)`, `res.status(401/403)`, or a
  thrown error. Fix: on any exception the branch must short-circuit with a 401/403 and
  never invoke the downstream handler.
- A JWT / webhook-signature / HMAC verify wrapped in `try/catch` that returns a truthy or
  default value on failure — `catch { return true }`, `catch { return decoded ?? {} }`,
  `catch { return user }`, or `.verify(...).catch(() => defaultClaims)`. Fix: verification
  is boolean-or-throw; the `catch` re-throws or returns `false`/denies, never a permissive
  default. Use the library's throwing verify (e.g. `jwt.verify`, `crypto.timingSafeEqual`
  for signatures) and let the error propagate — verify the throwing-vs-returning contract
  against the installed library version.
- Unhandled promise rejection in async middleware that bypasses the error path. Grep for
  `async` route/guard handlers with no surrounding rejection capture, `.then()` without
  `.catch()`, and `await` on a verify call that is not inside the deny-on-throw path. A
  rejected promise that is never routed to the error handler can leave the request
  proceeding. Fix: ensure async guards are wrapped so rejections reach the framework error
  handler (Express 5 forwards async rejections; Express 4 needs an async wrapper — confirm
  the installed major) and that the error handler denies rather than falling through.

## Dependency-outage fail-open

A control that consults an external system inherits that system's availability as a
security property.

- Rate limiter backed by Redis/Memcached that, on connection error or timeout, allows the
  request through unthrottled. Grep the limiter's error/`onError`/store-failure hook and
  any `catch` around the store call for a path that returns "allowed". Fix: on store
  failure the limiter must block or degrade to a conservative local limit — set the
  library's fail-closed lever explicitly rather than relying on its default (many limiters
  fail open by default; confirm the flag name and default in the installed version).
- Auth provider / OIDC / token-introspection / policy-store (OPA, feature-flag, entitlement
  service) outage where the guard treats "cannot reach the decision point" as allow. Grep
  for `catch`/timeout branches around introspection, JWKS fetch, or policy evaluation that
  return `allow`, `true`, or a cached-permissive default. Fix: an unreachable authorizer is
  a deny; only serve from cache within an explicit, bounded, signed-freshness window, never
  as an open-ended fallback.

## Fix: deny on any error in a security decision

- On any exception, timeout, or missing input inside a security decision, the outcome is
  DENY. The error handler returns 4xx/5xx; the request does not reach the protected action.
- Verification functions raise (or return an explicit `false`) — they never return a
  permissive default, a partially populated identity, or an empty-but-truthy object.
- Logging or alerting a control failure is NOT failing closed. An observed-and-logged
  bypass is still a bypass. Log the failure AND deny in the same path.
- Prefer propagating the error to the framework error boundary over local `try/catch`
  recovery; do not "recover" a security decision part way through. See the auth/session
  guidance in [../identity-sessions-and-secrets.md](../identity-sessions-and-secrets.md)
  and the operational error-boundary guidance in
  [../deployment-and-operations.md](../deployment-and-operations.md).

## Primary sources

- [OWASP Top 10 2025 A10 — Mishandling of Exceptional Conditions](https://owasp.org/Top10/2025/A10_2025-Mishandling_of_Exceptional_Conditions/)
- [CWE-636: Not Failing Securely ('Failing Open')](https://cwe.mitre.org/data/definitions/636.html)
- [CWE-703: Improper Check or Handling of Exceptional Conditions](https://cwe.mitre.org/data/definitions/703.html)
