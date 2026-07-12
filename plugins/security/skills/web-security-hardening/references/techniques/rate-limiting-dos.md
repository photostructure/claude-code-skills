<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# Rate Limiting & Resource Consumption

Hardening for unauthenticated-abuse and application-layer DoS: bound how much work any one
caller can force per request and over time. See also `../input-output-and-files.md`
(runtime schemas, uploads), `../deployment-and-operations.md` (timeouts, resource limits),
and `./redos.md` (regex CPU).

## Limit the expensive endpoints, not just login

- Anti-pattern to grep: a rate limiter applied only to `/login`/`/auth` (or a single
  `app.use(limiter)` with no per-route budget), while search, export/report, bulk
  create/update, media/thumbnail processing, outbound-fetch (webhook test, link preview),
  and object-enumeration routes (`GET /api/:resource/:id` scanned sequentially) run
  uncapped. Enumerable/expensive endpoints are the DoS and scraping surface.
- Fix: where the threat model warrants it, apply an aggregate limiter as a floor and
  tighter per-route budgets sized to endpoint cost—a heavy export gets a smaller budget
  than a cheap read. Account for trusted internal traffic and asynchronous job designs.
  Mount route-specific middleware (`router.post('/export', exportLimiter, ...)`). Budget
  by real cost (CPU, rows, outbound calls), not by uniform request count.

## Distributed, keyed limits with a shared store

- Anti-pattern to grep: `express-rate-limit` / `rate-limiter-flexible` with no `store`
  option (in-memory), so each instance/pod counts independently and N replicas multiply
  the effective limit by N; or `keyGenerator` on raw IP only, letting one authed account
  abuse from many IPs (or many accounts hide behind one NAT/proxy IP).
- Fix: back the limiter with a shared store or enforce it at a common edge so counters hold
  across instances. Apply separate budgets for network identity and authenticated
  principal (user/tenant/API key) where available; a composite key alone can be evaded by
  changing either component. When
  composing a custom `keyGenerator`, use the library's IPv6-safe IP helper (express-rate-
  limit exposes `ipKeyGenerator`) rather than concatenating `req.ip` raw. Reject excess
  requests with `429 Too Many Requests`; RFC 6585 says the response **may** include
  `Retry-After`, so emit it when a meaningful retry time is known. Verify option names and defaults
  (e.g. `limit`/legacy `max`, `standardHeaders`, `legacyHeaders`, whether `Retry-After`
  is emitted) against the installed major version — these have changed across releases.

## Bound result-set and query work

- Anti-pattern to grep: list/search handlers with no server-enforced page size — a
  client-supplied `limit`/`pageSize` passed straight to the query, or an unbounded
  `find()`/`SELECT` with no `LIMIT`. Also raw queries with no timeout, and GraphQL with no
  depth/cost analysis (deeply nested or aliased fields fan out into huge resolutions).
- Fix: use pagination or another server-enforced result/work bound appropriate to the
  operation; clamp client page sizes. Bound collection reads unless the dataset is
  demonstrably bounded by design. Set query/statement timeouts at the driver or DB (e.g. Postgres
  `statement_timeout`, Mongo `maxTimeMS`) so one query cannot run unbounded — confirm the
  exact knob for your driver/version. For GraphQL, enforce max query depth and a
  cost/complexity budget with a maintained implementation. Treat introspection exposure as
  a separate configuration decision, not a DoS control.

## Bound request size, time, and concurrency

- Anti-pattern to grep: body parsers whose effective limit is too large for the route
  (`bodyParser` set to `50mb` without need); no effective server/proxy
  `requestTimeout`/`headersTimeout`
  (slow-loris: a client dribbles bytes and holds a socket open); and unbounded fan-out on
  expensive work (`Promise.all(items.map(expensiveCall))` over an attacker-sized array).
- Fix: set a body-size `limit` on JSON/urlencoded/multipart parsers sized to real payloads
  and reject oversize with `413`. Express's JSON parser already has a version-dependent
  default limit, so absence of an option is a verification point, not automatically a gap.
  Set request/socket/proxy timeouts appropriate to payload size and network conditions.
  Cap concurrency for expensive operations with a bounded queue/pool (`p-limit`, worker
  pool) instead of firing one task per input element. Verify current default timeout
  values against the installed Node version rather than assuming a protective default.

## Primary sources

- [OWASP Denial of Service Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Denial_of_Service_Cheat_Sheet.html)
- [OWASP ASVS 5.0.0](https://github.com/OWASP/ASVS/tree/v5.0.0)
- [express-rate-limit documentation](https://express-rate-limit.mintlify.app/)
- [OWASP GraphQL Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/GraphQL_Cheat_Sheet.html)
- [RFC 6585 §4 — 429 Too Many Requests](https://www.rfc-editor.org/rfc/rfc6585.html#section-4)
