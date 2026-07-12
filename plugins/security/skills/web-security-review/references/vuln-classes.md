<!--
Composite reference for web vulnerability classes. See ../ATTRIBUTION.md.
Detection guidance adapted from getsentry/skills (OWASP-derived, CC BY-SA 4.0) and
github/awesome-copilot security-review (MIT), and synthesized from the OWASP Cheat
Sheet Series (SQL Injection, NoSQL Injection, Mass Assignment, Authentication, Session
Management, JWT, Authorization, Forgot Password) plus per-ORM and SQLite security
docs. Focused on JS/TS web apps.
-->

# Web Vulnerability Classes

Per-class detection signals, safe patterns, and escalation checkers. Load the sections
relevant to the code under review (workflow step 2). For each candidate, confirm the
input is attacker-controlled and not framework-mitigated — see `false-positives.md`.

---

## Injection

### SQL / ORM

- **Signals:** template literals or `+` concatenation inside a query; a user-controlled
  **table/column/ORDER BY** identifier (can't be parameterized — must allowlist); or an
  ORM "raw" escape hatch fed request data (table below).
- **Safe:** parameterized/bound queries — `db.query("… WHERE id = ?", [id])`,
  `Model.findOne({ where: { id } })` **when `id` is a scalar** (see object-injection
  below).
- **Deployment:** least-privilege DB roles, TLS in transit, and migration privilege are
  in `database-deployment-security.md`, not here.

**Per-ORM raw SQL review** — version-gate every API against the installed package.
An API named `Unsafe` or `raw` can still accept bound values; the vulnerability is
attacker data becoming SQL syntax rather than a parameter.

| ORM | Dangerous (with request data) | Safe form |
|-----|-------------------------------|-----------|
| Sequelize | concatenated `sequelize.query(str)` or `literal(str)` | v6 `query` with `replacements`/`bind`; v7 `sql` tag (values only) |
| Knex | concatenated `.raw`/`.whereRaw`/`.orderByRaw` | bindings: `?` for values, `??` for identifiers; still allowlist which identifiers may be selected |
| Prisma | concatenation passed to `$queryRawUnsafe`/`$executeRawUnsafe`; tainted `Prisma.raw` | ``$queryRaw`… ${value}` `` / ``$executeRaw`…` `` tagged templates; bound arguments to unsafe methods are also parameterized |
| TypeORM | concatenated `dataSource.query(str)`; function interpolation inside the `sql` tag | `dataSource.sql` value interpolation, or driver-specific placeholders with `query(sql, values)` |
| Drizzle | tainted text passed to `sql.raw(str)` | ``sql`… ${value}` `` parameterizes runtime values; use schema table/column objects and allowlist dynamic choices |

- **Unexpected structured values in where-clause shorthand.** JSON bodies can carry
  objects/arrays; query strings can too, depending on the configured parser. MongoDB
  filters interpret operator objects. SQL ORM behavior is library/version-specific and
  may reject, stringify, or structurally interpret such values. **Detect:** request
  values passed to `.where(...)`/`findOne(...)` without schema validation. **Fix:**
  require the expected scalar or explicitly build an allowlisted structured filter,
  then inspect the generated query before claiming SQL injection.
- **Unparameterizable identifiers (ORDER BY / column / table):** `` `ORDER BY ${col}` ``,
  `.orderByRaw(req.query.sort)`. **Fix:** map against a fixed `const ALLOWED = [...]`
  allowlist and fall back on no match — never pass the raw string through, even
  "validated."
- **Escalation — second-order:** a value stored safely (parameterized insert) then read
  back and concatenated into a *different* query later (report jobs, exports, audit
  queries). Trace DB-read values into raw SQL, not just `req.*`. "Already in the DB" is
  **not** a trust boundary — parameterize on every use.

### SQLite-specific (self-hosted single-file DBs)

Load when `package.json` shows `better-sqlite3` / `sqlite3` / `@photostructure/sqlite` /
`node:sqlite`.

- **`ATTACH DATABASE` escalation:** injected SQL may open, create, and write SQLite
  database files within the process's filesystem permissions. That is not automatically
  an arbitrary-content write or RCE. Prove a sensitive existing database can be read or
  modified, or that creating a valid SQLite-format file at a chosen path has concrete
  impact. `SQLITE_DBCONFIG_DEFENSIVE` does **not** disable `ATTACH`; where supported,
  disable attach-create/write, set the attached-database limit appropriately, or deny
  `SQLITE_ATTACH` with an authorizer when the application does not need it.
- **Loadable extensions:** loading an attacker-provided native library is code execution.
  Path control alone is insufficient unless the attacker can place/select a compatible
  malicious library. Check `.loadExtension(`, `enable_load_extension`, and
  `sqlite3_enable_load_extension`; SQLite and `node:sqlite` disable extension loading by
  default, so establish that the effective connection enables it.
- **File exposure:** the DB file's ACL *is* its access control. **Detect:**
  `express.static`/`res.sendFile` roots at or above the data dir, or `path.join(base,
  req.params.file)` that can resolve to the `.sqlite`/`-wal`/`-shm` (the WAL holds
  recently-written rows). **Fix:** `0600` file / `0700` dir; never serve the data dir.

### NoSQL / MongoDB

- **Signals:** a request object passed directly as a filter or aggregation stage;
  request-derived equality values that can remain objects/arrays; `$where` fed attacker
  input; or attacker-controlled `$regex` used as a data-extraction oracle.
- **Operator injection:** JSON bodies and parsed query strings preserve nested objects.
  In `{ username: req.body.username }`, an attacker can send
  `{ "username": { "$ne": null } }` and change a literal comparison into an operator
  predicate. This is especially severe when the query authenticates or authorizes.
- **Safe only after scalar validation:** `findOne({ _id: id })` is safe when the request
  value has first been validated as the expected string/number, not merely because the
  driver accepts a structured filter. When an ObjectId is required, validate a scalar
  string and construct a new trusted ObjectId from it. Reject request-derived objects
  and arrays before building the query; schema validation must run before the
  ODM/driver call.
- **Whole-filter input:** never pass `req.body`/`req.query` directly to `find`,
  `findOne`, `$match`, or Mongoose query helpers. Build a new filter from allowlisted,
  type-validated fields. Sanitizers that strip `$` keys are defense-in-depth, not a
  substitute for an allowlisted schema.
- **Scope boundary:** report `$regex`/`$where` when the operator enables query behavior,
  authentication bypass, or data extraction. Drop performance-only ReDoS/DoS claims.

### Redis

- **Do not invent injection:** normal Redis clients encode commands as length-prefixed,
  binary-safe argument arrays. `get(userKey)` or `set(key, userValue)` is not string
  injection merely because an argument is attacker-controlled.
- **Command/script control:** flag attacker-selected commands or argument arrays passed
  to generic APIs such as `sendCommand`, manual RESP written to a socket, and attacker-
  composed Lua supplied to `EVAL`. Also investigate attacker-selected cached scripts or
  functions passed to `EVALSHA`/`FCALL` when that selection expands their capability.
  Keep Lua source server-controlled and pass data through `KEYS`/`ARGV`; allowlist any
  dynamic command capability.
- **Key/channel authorization:** a request-derived key, glob, or Pub/Sub channel can
  cross tenant/owner namespaces. Derive prefixes from the authenticated principal and
  prove the effective key/channel access before reporting IDOR. Redis ACL key (`~`) and
  channel (`&`) patterns are additional server-side boundaries, not replacements for
  application authorization.
- **Atomic security state:** consume one-time tokens atomically with `GETDEL` (Redis
  6.2+) or a fixed script/transaction. For check-and-set flows, use a fixed atomic Lua
  script or `WATCH`/`MULTI` and handle aborted transactions; separate reads and writes
  can permit replay or double use.
- **TTL gotcha:** successful plain `SET` discards an existing TTL. For sessions, reset
  tokens, lockouts, or other expiring security state, set `EX`/`PX` on every overwrite
  or deliberately use `KEEPTTL`. Report only when the lost expiry creates concrete
  unauthorized persistence or replay.
- **Deployment:** network reachability, TLS, protected mode, ACLs, dangerous commands,
  persistence files, and modules belong in `database-deployment-security.md`.

### LevelDB / classic-level

- **No query injection surface:** LevelDB is an embedded ordered key/value library.
  Caller-controlled keys and values are not query language; evaluate authorization and
  namespace boundaries instead.
- **Filesystem path control:** `new ClassicLevel(location)` opens or recursively creates
  a directory. Attacker control of `location`, `ClassicLevel.destroy(location)`, or
  `ClassicLevel.repair(location)` is a path traversal/cross-store/destructive-operation
  candidate. Require a server-controlled resolved data directory.
- **Key namespaces:** build keys from server-derived tenant/owner identifiers and prefer
  server-selected `sublevel()` namespaces over delimiter concatenation. A sublevel is
  organization, not authorization; still verify ownership before reads/writes.
- **Atomicity/consistency:** use one atomic batch for security invariants spanning keys
  (record + authorization index, token + consumed marker). Use a shared snapshot for
  multi-read authorization decisions and close explicit snapshots when finished.
- **Durability:** classic-level writes are asynchronous by default and may lose recent
  updates on machine failure. Use `sync: true` for durable revocation/token-consumption
  state when loss would enable concrete replay. Do not report default async writes as
  hardening noise without that impact.
- **Process model:** LevelDB permits one process to open a store. Treat lock failures as
  availability-only unless fallback behavior creates a separate empty authorization or
  session store and thereby changes security decisions.

### Command

- **Signals:** `exec`/`execSync`/`child_process.exec` with user input; `spawn(cmd, {
  shell: true })` where `cmd` is tainted; backticks/`os` calls with request data.
- **Safe:** `execFile`/`spawn` with an **argument array** and `shell:false`; allowlist
  the command; never interpolate user input into a shell string.

### Template / other

- Server-side template injection: `Vue.compile`, `new Function`, EJS/Handlebars/Pug
  compiled from user input. Also watch LDAP, XPath, and header injection where present.

---

## Cross-Site Scripting (XSS)

- **Reflected/stored:** user input rendered into HTML without escaping. Trace stored
  values too — safe on write, unsafe on later render is still stored XSS.
- **DOM-based:** a taint source (`location.hash/search`, `document.referrer`,
  `window.name`, `postMessage`) flows to a sink (`innerHTML`, `document.write`, …).
- **Framework rule:** React/Vue/Angular auto-escape — only flag the escape hatches
  (`dangerouslySetInnerHTML`, `v-html`, `bypassSecurityTrust*`) or raw DOM sinks. See
  `javascript-web-patterns.md`.
- **Safe:** `textContent`; `DOMPurify.sanitize()` before any raw-HTML sink.

---

## Authorization

### Object-level (IDOR / BOLA)

- **Signals:** a resource fetched/mutated by an ID from the request with **no ownership
  check** — `Order.findByPk(req.params.id)` returned without `where userId = me`.
- **Escalation:** enumerable/sequential IDs make BOLA trivial; UUIDs reduce (not
  eliminate) it. Confirm the check is **server-side** and applies to every method (GET
  *and* PATCH/DELETE).
- **Multi-tenant isolation:** the self-hosted-multi-user variant — a query scoped to
  "does this row exist" (`WHERE id = ?`) but not "does it belong to *this* tenant/org"
  (missing `AND tenantId = ?`). Common when multi-user is bolted onto a single-user
  schema. **Fix:** bake tenant/user scoping into a shared query helper so it can't be
  forgotten per-callsite.

### Function-level (missing role gate)

- Distinct from IDOR: the ownership check can be perfect while the **endpoint itself**
  (`/admin/users`, `/api/settings`) has no role gate and is reachable by any
  authenticated user. **Detect:** a route registered without the `requireRole("admin")`
  guard its sibling admin routes have; a role check present only in the frontend.
  **Fix:** deny-by-default global guard (Nest `@UseGuards`, router-level middleware),
  not ad-hoc per-handler checks.

### Mass assignment → privilege escalation

- **Signals:** `Model.create(req.body)`, `Model.update(req.body)`, `new User(req.body)`,
  `Object.assign(entity, req.body)`, `{...req.body}` into `.save()` — where the schema
  has a privilege field (`role`, `isAdmin`, `permissions`, `ownerId`, `tenantId`,
  `verified`). Any authenticated (or at signup, unauthenticated) user can set it.
- **Fix per ORM:** Sequelize `create(body, { fields: ["name","email"] })`; NestJS global
  `ValidationPipe({ whitelist: true, forbidNonWhitelisted: true })` + DTOs; Prisma/
  TypeORM/Drizzle — pick fields explicitly, never `data: req.body` / `.set(req.body)`.

### Unauthenticated admin/backup/export endpoints

- **Signals:** routes like `/backup`, `/export`, `/dump`, `/admin/db`, `/setup` missing
  the auth/role middleware their siblings have ("not linked from the UI" ≠ protected).
  Real CVEs: Nginx-UI `/api/backup` leaked decryption keys in a header; setup wizards
  left open → pre-auth RCE. A DB dump has **no query-layer access control**, so it
  bypasses all IDOR/authz work. **Fix:** same-or-stricter authz; backups outside any
  served dir; re-auth on download.

---

## Authentication / Session / JWT

For **OAuth/OIDC/SSO** flows, see `oidc-sso-review.md`.

- **Password hashing:** OWASP's current baseline is Argon2id with at least 19 MiB,
  2 iterations, parallelism 1; bcrypt with work factor at least 10 is a legacy fallback
  (and has a 72-byte input limit). Fast hashes or plaintext password storage are strong
  candidates. A work factor below a published baseline is not automatically a proven
  vulnerability: establish the effective parameters and credible offline-guessing
  impact, or route it to hardening review.
- **Secret comparison timing:** use a vetted verifier or constant-time primitive for
  MAC/signature verification and other comparisons where an attacker can make repeated
  measurements and a prefix-dependent timing difference leaks a useful secret. Do not
  flag every `===` over reset tokens, API keys, or CSRF tokens on pattern alone. Prove
  the comparison leaks progressively useful information across the real transport.
  Node's `timingSafeEqual` requires equal-length byte inputs and does not make surrounding
  code timing-safe; hash fixed-domain variable-length values before comparison when the
  protocol requires it.
- **Account enumeration:** login/reset/signup returning different status/message/shape
  by account existence, or a fast `return` before the (deliberately slow) hash on the
  user-not-found path (a **timing oracle** — µs miss vs ms hash). **Fix:** identical
  generic message + run a dummy hash on the not-found path.
- **Password reset tokens:** `Math.random()` or short tokens; no TTL/`expiresAt`; not
  single-use (row not invalidated on redemption); reset link host from
  `req.get("host")`/`X-Forwarded-Host` (**host-header poisoning** → token theft — see
  SSRF & `self-hosting-hardening.md`); missing `Referrer-Policy: no-referrer` on the
  reset page. **Fix:** `crypto.randomBytes(≥16).toString("base64url")`, short TTL,
  single-use, hardcoded/allowlisted base URL. Treat the missing header alone as
  hardening; report leakage only when a token-bearing URL can be sent as a referrer to
  a concrete cross-origin navigation/resource under the browser's effective policy.
- **Session cookies:** inspect `HttpOnly`, `Secure`, `SameSite`, `Domain`, and `Path` in
  context. Missing `Secure` is exploitable when HTTP disclosure is reachable; missing
  `HttpOnly` amplifies a proven script-read path; missing `SameSite` matters when CSRF
  is otherwise unmitigated. Prefer the `__Host-` prefix when host-only scope fits (it
  requires `Secure`, `Path=/`, and no `Domain`). Do not report an absent flag without
  the corresponding attacker path.
- **Session fixation:** investigate whether an attacker can set or learn a pre-auth
  session identifier and the server preserves that identifier across login or another
  privilege transition. Missing `req.session.regenerate()` alone is not proof; show
  both attacker control/knowledge and identifier continuity. Regenerate and invalidate
  the old identifier at authentication and privilege-level changes.
- **Timeout / logout invalidation:** server-side sessions should be invalidated on
  logout and have appropriate idle/absolute limits. A stateless access token commonly
  remains valid until expiry; lack of a denylist is not automatically a vulnerability.
  Report when the application promises immediate logout/revocation, uses excessive
  lifetimes, or fails to invalidate tokens after a proven high-risk event. Short-lived
  access tokens plus refresh-token revocation/rotation may be the intended design.
- **Session-id entropy:** built from `Date.now()`, counters, `Math.random()`, or UUID v1
  → predictable. Use `crypto.randomUUID()` / `randomBytes(≥16)`.
- **JWT:** investigate unsigned tokens, algorithm/key confusion, weak HMAC secrets,
  missing signature verification, and claims not validated for the token profile
  (`exp`, expected `iss`, intended `aud`, and mutually exclusive rules for different
  token kinds). Pin allowed algorithms from application configuration. For
  `jsonwebtoken`, CVE-2022-23540 affects versions through 8.5.1 under its documented
  preconditions; version 9 removed implicit `none` support, so a missing `algorithms`
  option is not by itself proof on current versions. Browser storage readable by
  JavaScript increases the impact of a proven XSS; `localStorage.setItem("token", …)`
  alone is a hardening concern, not an XSS finding. HttpOnly cookies reduce token theft
  but require CSRF analysis because browsers send them ambiently.

---

## SSRF (Server-Side Request Forgery)

- **Signals:** `fetch`/`axios`/`http.get`/webhook target built from user input where the
  attacker controls **host or protocol**. Impact shifts by deployment: cloud VM → cloud
  metadata (`169.254.169.254`, `metadata.google.internal`) → IAM creds; LAN box →
  internal unauth services (`192.168.x.x`). Common sinks: avatar-by-URL, RSS/webhook
  test-fire, remote-thumbnail proxy, OIDC discovery fetch.
- **Fixed host is not an automatic exclusion:** path-only control cannot pivot hosts,
  but it can still abuse the server's credentials or network position to invoke a
  privileged route on that service. Do not call URL-path manipulation filesystem path
  traversal unless it actually reaches a filesystem path sink.
- **Mitigation:** prefer an allowlist of schemes and destinations. When arbitrary hosts
  are required, parse/canonicalize, resolve all addresses, reject disallowed ranges,
  make the connection use the validated result, and re-apply policy on every redirect.

---

## CSRF

- **Signals:** state-changing route (POST/PUT/PATCH/DELETE) authenticated by an **ambient
  cookie** where none of the effective defenses apply: framework CSRF token, suitable
  `SameSite` policy, validated origin, or another documented mechanism.
- **Not CSRF-able:** routes authenticated *only* by an `Authorization: Bearer` header —
  the browser doesn't auto-send it, so there's no ambient-credential attack. Don't flag
  those. A route that mixes cookie session auth *and* mutates state **is** a candidate.
- **Mitigations:** use the framework's synchronizer-token or signed double-submit
  pattern as appropriate; origin verification and Fetch Metadata can add protection.
  `SameSite` is defense in depth and must match the flow; `Lax` still permits cookies on
  some top-level navigations, so state-changing GET endpoints remain exposed. Confirm
  the complete route/method/browser behavior before declaring the endpoint safe.

---

## Deserialization & data handling

- **Signals:** parsed attacker objects merged through unsafe recursive/key-copy logic
  (ordinary `JSON.parse` plus object spread is not automatically prototype pollution;
  see
  `javascript-web-patterns.md`); `node-serialize`/`funcster`-style eval-on-deserialize;
  vulnerable deserializers that reconstruct executable values; XXE in XML parsers with
  external entities enabled.
- **Version gate:** determine the installed js-yaml version from the lockfile. In 4.x,
  ordinary `load()` uses the safe schema and `safeLoad()` was removed, so do not flag
  ordinary `load()` or recommend `safeLoad()`. In 3.x, investigate `load()` with the
  full schema only when attacker YAML can instantiate a dangerous JavaScript-specific
  type and that value reaches an execution sink; prefer upgrading to 4.x or use 3.x
  `safeLoad()` while upgrading.
- **Safe:** schema-validate parsed input (`zod`/`joi`); disable external entities;
  never deserialize attacker data into executable structures.

---

## Path traversal & file handling

- **Signals:** `fs`/`res.sendFile`/`path.join(base, userInput)` where user input can
  contain `../`; upload filename used as a destination path unsanitized. (See also
  SQLite file exposure above.)
- **Safe:** use a segment-aware containment check; a string-prefix check accepts
  siblings such as `/srv/uploads-private` for base `/srv/uploads`.
  ```js
  const root = path.resolve(base);
  const target = path.resolve(root, name);
  const rel = path.relative(root, target);
  const contained = rel === "" ||
    (rel !== ".." && !rel.startsWith(`..${path.sep}`) && !path.isAbsolute(rel));
  ```
  Reject unless `contained`; generate server-side filenames and validate content type
  and size.

---

## Cryptography

- **Signals:** MD5/SHA1/DES for a **security** purpose; `Math.random()` for tokens,
  session ids, or password reset (use `crypto.randomBytes`/`randomUUID`); hardcoded
  IV/salt; disabled TLS verification (`rejectUnauthorized: false`,
  `NODE_TLS_REJECT_UNAUTHORIZED=0`).
- **Context matters:** MD5 for a cache key / file checksum is fine; `Math.random()` for
  UI jitter is fine. Flag only security uses.

---

## Secrets exposure

- **Signals:** hardcoded API keys/tokens/passwords/private keys; an effective known
  **placeholder fallback**
  on a secret (`process.env.SECRET ?? "changeme"`); DB connection strings with embedded
  credentials; secrets in `NEXT_PUBLIC_*`/`VITE_*` (shipped to browser); a full model/row
  passed to a logger (`logger.info(user)` serializing a hash/PII). Scan `.env`, config,
  CI/CD, Dockerfiles, IaC.
- **Precedent:** logging a real secret/PII is a finding; logging URLs is not. Confirm the
  value is a *live/high-value* secret, not a placeholder or test fixture. Log by id +
  explicit safe fields; configure logger redaction (`pino` `redact`).

---

## Information disclosure

- **Verbose DB errors to the client:** `res.status(500).json(err)` / `res.send(err.stack)`
  can expose query text, schema, filesystem paths, or credentials depending on the
  actual driver and serialization. Inspect the concrete error object; do not assume a
  connection string is present or claim exploit escalation without showing it.
  **Fix:** return a generic client message and redact sensitive server-log fields.

---

## Business logic & race conditions

- **Signals:** multi-step flows where a check and its use are separable (TOCTOU) —
  balance/quota checked then spent without a lock/transaction; negative or overflowing
  quantities in financial math; workflow steps that can be skipped or replayed;
  predictable resource identifiers enabling enumeration.
- **Bar:** report only when concretely exploitable (double-spend, auth check/use gap),
  not theoretical timing windows.

## Authoritative references

- [OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/): [SQL Injection](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html), [NoSQL Security](https://cheatsheetseries.owasp.org/cheatsheets/NoSQL_Security_Cheat_Sheet.html), [Authorization](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html), [Authentication](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html), [Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html), [CSRF](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html), and [SSRF](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
- [RFC 8725 — JSON Web Token Best Current Practices](https://datatracker.ietf.org/doc/html/rfc8725) · [Auth0 `jsonwebtoken` security bulletin](https://auth0.com/docs/secure/security-guidance/security-bulletins/2022-12-21-jsonwebtoken)
- [Node.js `crypto.timingSafeEqual`](https://nodejs.org/api/crypto.html#cryptotimingsafeequala-b) · [Node.js `child_process`](https://nodejs.org/api/child_process.html)
- [SQLite ATTACH](https://sqlite.org/lang_attach.html) · [SQLite connection configuration](https://sqlite.org/c3ref/c_dbconfig_defensive.html) · [SQLite authorizer action codes](https://sqlite.org/c3ref/c_alter_table.html) · [SQLite loadable extensions](https://sqlite.org/loadext.html) · [Node.js SQLite](https://nodejs.org/api/sqlite.html)
- ORM documentation: [Sequelize v6 raw queries](https://sequelize.org/docs/v6/core-concepts/raw-queries/), [Sequelize v7 raw SQL](https://sequelize.org/docs/v7/querying/raw-queries/), [Knex raw bindings](https://knexjs.org/guide/raw.html), [Prisma raw queries](https://www.prisma.io/docs/orm/prisma-client/using-raw-sql/raw-queries), [TypeORM SQL tag](https://typeorm.io/docs/guides/sql-tag/), [Drizzle `sql` operator](https://orm.drizzle.team/docs/sql)
- [Redis security](https://redis.io/docs/latest/operate/oss_and_stack/management/security/) · [classic-level](https://github.com/Level/classic-level) · [abstract-level](https://github.com/Level/abstract-level)
