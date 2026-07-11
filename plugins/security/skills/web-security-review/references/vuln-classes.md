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

**Per-ORM raw escape hatches** — the exact method that bypasses parameterization:

| ORM | Dangerous (with request data) | Safe form |
|-----|-------------------------------|-----------|
| Sequelize | `sequelize.query(str)`, `literal(...)`+`replacements` in one `where` | `query(sql, { replacements: { id } })` / `sql` tag |
| Knex | `.raw(str)`, `.whereRaw(str)`, `.orderByRaw(str)` with concat | `.raw("?? = ?", [col, val])` (`?`=value, `??`=identifier) |
| Prisma | `$queryRawUnsafe(str)`, `$executeRawUnsafe(str)`, `Prisma.raw(str)` | ``$queryRaw`… ${value}` `` tagged template; `Prisma.sql`/`join` |
| TypeORM | `dataSource.query(str)` with concat; identifier fn `() => userInput` | named params `query("… :id", { id })`; `sql` tag |
| Drizzle | `sql.raw(str)`; `sql.identifier()`/`.as()` fed request data | ``sql`… ${value}` `` tag; allowlist identifiers |

- **Object/array injection into where-clause shorthand** — looks parameterized but
  isn't. Express's `qs` parser turns `?id[$gt]=` / `?id[name]=x` into an *object*, and
  `.where({ id: req.query.id })` compiles it into extra SQL (Knex CVE-2016-20018 dropped
  the WHERE clause → returns all rows). **Detect:** `.where({ col: req.query|body|params.x })`
  or `findOne({ where: req.query })` with no scalar type-check. **Fix:** reject
  non-scalar values (`typeof x === "string" || "number"`) before the query.
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

- **`ATTACH DATABASE` escalation:** any confirmed SQLi on SQLite upgrades to **arbitrary
  file write / RCE** (`'; ATTACH DATABASE '/var/www/x.php' AS y; …`) if the DB process
  can write under a served directory. Not greppable — it's a severity escalator for a
  confirmed injection. **Fix:** `SQLITE_DBCONFIG_DEFENSIVE`, no attach if unused.
- **`load_extension()` = RCE:** loading a native extension from a request-influenced
  path is code execution. **Detect:** `.loadExtension(`, `enable_load_extension`,
  `sqlite3_enable_load_extension` reachable from config/upload/plugin-discovery data
  (off by default — flag where explicitly enabled).
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

- **Password hashing:** argon2id (≥19 MiB, 2 iterations, parallelism 1) or bcrypt (cost
  ≥ 10, legacy). **Flag:** `createHash("md5"|"sha1")` near a password, `bcrypt.hash(pw,
  <10)`, or `password === row.password` (plaintext compare).
- **Constant-time comparison:** reset tokens, API keys, HMAC signatures, CSRF tokens
  must use `crypto.timingSafeEqual(Buffer.from(a), Buffer.from(b))` — **flag** `===`/
  `==`/`.equals()` comparing a secret. (Buffers must be equal length or it throws — hash
  both sides first if lengths vary.)
- **Account enumeration:** login/reset/signup returning different status/message/shape
  by account existence, or a fast `return` before the (deliberately slow) hash on the
  user-not-found path (a **timing oracle** — µs miss vs ms hash). **Fix:** identical
  generic message + run a dummy hash on the not-found path.
- **Password reset tokens:** `Math.random()` or short tokens; no TTL/`expiresAt`; not
  single-use (row not invalidated on redemption); reset link host from
  `req.get("host")`/`X-Forwarded-Host` (**host-header poisoning** → token theft — see
  SSRF & `self-hosting-hardening.md`); missing `Referrer-Policy: no-referrer` on the
  reset page. **Fix:** `crypto.randomBytes(≥16).toString("base64url")`, short TTL,
  single-use, hardcoded/allowlisted base URL.
- **Session cookies:** missing `httpOnly`/`Secure`/`SameSite`; prefer the `__Host-`
  prefix (forces `Secure`, `Path=/`, no `Domain` — blocks subdomain cookie injection).
- **Session fixation:** regenerate the session id (`req.session.regenerate()`) on **all**
  of: login, re-login, password change, **and any privilege/role change** (the
  commonly-missed one).
- **Timeout / logout invalidation:** logout that only clears the client cookie with no
  server-side `session.destroy()` / JWT revocation; no idle/absolute timeout. Stateless
  JWT with **no revocation** (`jti` denylist or per-user `tokenVersion`/`passwordChangedAt`
  claim checked each request) means "logout does nothing."
- **Session-id entropy:** built from `Date.now()`, counters, `Math.random()`, or UUID v1
  → predictable. Use `crypto.randomUUID()` / `randomBytes(≥16)`.
- **JWT:** `alg:none` accepted; algorithm not pinned (RS256↔HS256 confusion); weak/
  hardcoded HMAC secret; `exp` **and `aud`/`iss`** not validated; signature not verified
  (`jwt.decode` vs `jwt.verify`); `verify()` with no `algorithms` option (re-opens
  jsonwebtoken CVE-2022-23540 default-to-`none`). **Fix:** `verify(t, key, { algorithms:
  ["RS256"], audience, issuer })`. **Flag** `localStorage.setItem("token"…)` — XSS-
  exfiltrable; prefer an httpOnly cookie.

---

## SSRF (Server-Side Request Forgery)

- **Signals:** `fetch`/`axios`/`http.get`/webhook target built from user input where the
  attacker controls **host or protocol**. Impact shifts by deployment: cloud VM → cloud
  metadata (`169.254.169.254`, `metadata.google.internal`) → IAM creds; LAN box →
  internal unauth services (`192.168.x.x`). Common sinks: avatar-by-URL, RSS/webhook
  test-fire, remote-thumbnail proxy, OIDC discovery fetch.
- **Not a finding here:** path-only control (host/protocol fixed) — check under path
  traversal instead. See `false-positives.md`.
- **Safe:** allowlist hosts/protocols; resolve-then-check the **IP** (block private/link-
  local) and re-check on redirect (DNS rebinding).

---

## CSRF

- **Signals:** state-changing route (POST/PUT/PATCH/DELETE) authenticated by an **ambient
  cookie** with **no** CSRF token / no `SameSite` cookie / no origin check.
- **Not CSRF-able:** routes authenticated *only* by an `Authorization: Bearer` header —
  the browser doesn't auto-send it, so there's no ambient-credential attack. Don't flag
  those. A route that mixes cookie session auth *and* mutates state **is** a candidate.
- **Safe:** `SameSite=Lax|Strict` cookies + token or origin/referer check. GET handlers
  that mutate state are a smell — check them.

---

## Deserialization & data handling

- **Signals:** `JSON.parse` then spread into an object (prototype pollution — see
  `javascript-web-patterns.md`); `node-serialize`/`funcster`-style eval-on-deserialize;
  js-yaml **3.x** `load()` on attacker input; js-yaml **4.x** `load()` only when code
  supplies dangerous custom schemas/types; XXE in XML parsers with external entities
  enabled.
- **Version gate:** determine the installed js-yaml version from the lockfile. In 4.x,
  ordinary `load()` uses the safe schema and `safeLoad()` was removed, so do not flag
  ordinary `load()` or recommend `safeLoad()`. For affected 3.x code, upgrade to 4.x
  or use 3.x `safeLoad()` while upgrading.
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

- **Signals:** hardcoded API keys/tokens/passwords/private keys; a **placeholder fallback**
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
  reaching a DB-driver error turns blind injection into sighted (leaks query structure/
  schema), and driver `Error` objects can contain the **connection string** verbatim.
  **Fix:** generic client message; full error only to server-side logs.

---

## Business logic & race conditions

- **Signals:** multi-step flows where a check and its use are separable (TOCTOU) —
  balance/quota checked then spent without a lock/transaction; negative or overflowing
  quantities in financial math; workflow steps that can be skipped or replayed;
  predictable resource identifiers enabling enumeration.
- **Bar:** report only when concretely exploitable (double-spend, auth check/use gap),
  not theoretical timing windows.
