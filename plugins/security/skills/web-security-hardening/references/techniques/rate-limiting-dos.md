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
- Fix: apply a default/global limiter as a floor AND a tighter per-route budget sized to
  each endpoint's cost — a heavy export gets a far smaller `limit` than a cheap read.
  Mount route-specific middleware (`router.post('/export', exportLimiter, ...)`). Budget
  by real cost (CPU, rows, outbound calls), not by uniform request count.

## Distributed, keyed limits with a shared store

- Anti-pattern to grep: `express-rate-limit` / `rate-limiter-flexible` with no `store`
  option (in-memory), so each instance/pod counts independently and N replicas multiply
  the effective limit by N; or `keyGenerator` on raw IP only, letting one authed account
  abuse from many IPs (or many accounts hide behind one NAT/proxy IP).
- Fix: back the limiter with a shared store (`rate-limit-redis` for express-rate-limit;
  `RateLimiterRedis` for rate-limiter-flexible) so counters hold across instances. Key on
  IP **and** the authenticated principal (user/tenant/API-key) where available. When
  composing a custom `keyGenerator`, use the library's IPv6-safe IP helper (express-rate-
  limit exposes `ipKeyGenerator`) rather than concatenating `req.ip` raw. Reject with
  `429 Too Many Requests` and a `Retry-After` header. Verify option names and defaults
  (e.g. `limit`/legacy `max`, `standardHeaders`, `legacyHeaders`, whether `Retry-After`
  is emitted) against the installed major version — these have changed across releases.

## Bound result-set and query work

- Anti-pattern to grep: list/search handlers with no server-enforced page size — a
  client-supplied `limit`/`pageSize` passed straight to the query, or an unbounded
  `find()`/`SELECT` with no `LIMIT`. Also raw queries with no timeout, and GraphQL with no
  depth/cost analysis (deeply nested or aliased fields fan out into huge resolutions).
- Fix: mandatory pagination with a server-enforced max page size (clamp the requested
  value to a ceiling; never trust the client's number). Always emit `LIMIT`/`.limit()` on
  collection reads. Set query/statement timeouts at the driver or DB (e.g. Postgres
  `statement_timeout`, Mongo `maxTimeMS`) so one query cannot run unbounded — confirm the
  exact knob for your driver/version. For GraphQL, enforce max query depth and a
  cost/complexity budget with a maintained plugin, and disable introspection in prod.

## Bound request size, time, and concurrency

- Anti-pattern to grep: body parsers with a large or default `limit` (`express.json()`
  with no `limit`, `bodyParser` set to `50mb`); no server `requestTimeout`/`headersTimeout`
  (slow-loris: a client dribbles bytes and holds a socket open); and unbounded fan-out on
  expensive work (`Promise.all(items.map(expensiveCall))` over an attacker-sized array).
- Fix: set a body-size `limit` on JSON/urlencoded/multipart parsers sized to real payloads
  and reject oversize with `413`. Set request/socket timeouts (Node `http.Server`
  `requestTimeout`/`headersTimeout`; a reverse proxy read timeout) to bound slow clients.
  Cap concurrency for expensive operations with a bounded queue/pool (`p-limit`, worker
  pool) instead of firing one task per input element. Verify current default timeout
  values against the installed Node version rather than assuming a protective default.

## Primary sources

- [OWASP Denial of Service Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Denial_of_Service_Cheat_Sheet.html)
- [OWASP ASVS 5.0.0](https://github.com/OWASP/ASVS/tree/v5.0.0)
- [express-rate-limit documentation](https://express-rate-limit.mintlify.app/)
- [OWASP GraphQL Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/GraphQL_Cheat_Sheet.html)
