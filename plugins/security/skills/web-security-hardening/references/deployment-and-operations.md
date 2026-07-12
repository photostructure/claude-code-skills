<!-- OWASP/CIS/platform-derived guidance. CC BY-SA 4.0. See ../ATTRIBUTION.md. -->

# Deployment and Operations Hardening

## Contents

- [Effective deployment model](#effective-deployment-model)
- [TLS, proxies, and public origin](#tls-proxies-and-public-origin)
- [Network and service exposure](#network-and-service-exposure)
- [Rate limiting and resource consumption](#rate-limiting-and-resource-consumption)
- [Containers and host boundaries](#containers-and-host-boundaries)
- [Databases, caches, and embedded stores](#databases-caches-and-embedded-stores)
- [Configuration and secrets](#configuration-and-secrets)
- [Dependencies and supply chain](#dependencies-and-supply-chain)
- [CI/CD and artifacts](#cicd-and-artifacts)
- [Logging, errors, and monitoring](#logging-errors-and-monitoring)
- [Backups, updates, and incident readiness](#backups-updates-and-incident-readiness)

> **Technique cards** (concrete Node/JS anti-patterns and fixes; load per control):
> [`supply-chain-ci`](./techniques/supply-chain-ci.md), [`rate-limiting-dos`](./techniques/rate-limiting-dos.md),
> [`fail-closed`](./techniques/fail-closed.md), [`misconfiguration`](./techniques/misconfiguration.md),
> [`tls`](./techniques/tls.md).

## Effective deployment model

Determine what actually ships:

- production Dockerfile/image, compose/IaC, systemd/serverless config;
- reverse proxy, ingress, CDN/WAF, load balancer, and forwarded-header path;
- public/private ports, host binding, firewall/network policy, service discovery;
- runtime identity, filesystem mounts, secrets injection, writable paths;
- databases/caches/object storage/embedded data and backup destinations;
- build/publish/update workflow and who controls each boundary.

Examples and development defaults are evidence only when runtime falls back to them.
Keep every Gap applicability-aware: absence of a container control is not relevant to a
non-container deployment, and a private service is not automatically internet-reachable.

## TLS, proxies, and public origin

- Redirect HTTP to HTTPS where the product supports HTTPS; ensure sensitive traffic is
  never accepted over cleartext on another listener/path.
- Use current TLS libraries/config, valid certificate verification, and appropriate
  protocol/cipher policy supplied by the platform.
- Never globally disable certificate verification (`rejectUnauthorized: false`, unsafe
  agent defaults, `NODE_TLS_REJECT_UNAUTHORIZED=0`) outside tightly bounded local tests.
- Configure Express/Nest/other proxy trust to exact known proxy hops/subnets. A blanket
  `trust proxy=true` can make client-supplied forwarded headers authoritative.
- Require the edge proxy to overwrite inbound `Forwarded`/`X-Forwarded-*` headers.
- Build password-reset links, OAuth redirects, canonical URLs, and cookie security from
  trusted public-origin configuration—not request Host headers.
- Apply HSTS only after reliable HTTPS is established for every included host; treat
  subdomain/preload adoption as an operational commitment.
- Use TLS for database/cache/service links when they cross untrusted/shared networks;
  do not report missing TLS on an isolated local IPC/private boundary without context.

## Network and service exposure

- Bind databases, Redis, admin/debug/metrics ports, and development servers to loopback
  or private service networks unless public access is explicitly required.
- Do not assume a host firewall protects Docker-published ports; inspect effective
  published mappings and host/network policy.
- Require authentication and least privilege on every reachable management surface.
- Disable debug consoles, profilers, inspector ports, directory listings, and setup
  wizards in production or gate them with explicit administration controls.
- Keep health endpoints minimal; separate liveness from detailed diagnostics.
- Document trusted-network modes and make insecure exposure require explicit, visible
  opt-in. A LAN is not automatically a trusted identity boundary.
- Constrain outbound egress where SSRF, webhooks, importers, or supply-chain fetches make
  it valuable and operationally feasible.

## Rate limiting and resource consumption

- Rate-limit expensive, enumerable, and unauthenticated operations—search, export/report
  generation, bulk or fan-out actions, media/file processing, outbound fetches, and object
  enumeration—not only login. Back the limiter with a shared store so limits hold across
  instances, key on client IP plus authenticated principal, and return `429` with
  `Retry-After`.
- Require server-enforced pagination and a maximum page size on any attacker-influenced
  result set (SQL `LIMIT`/keyset, document-store `limit()`, Level range bounds), plus
  query/statement timeouts. For GraphQL, enforce depth, breadth, and cost/complexity limits.
- Set request and socket timeouts and body-size limits to bound slow-loris and oversized
  payloads, and cap concurrency for expensive operations.
- Evicting or exhausting session, authorization, rate-limit, queue, or lock state changes
  security behavior; size and isolate those stores deliberately.

## Containers and host boundaries

Treat these as contextual controls, not automatic findings:

- run as a dedicated non-root user;
- use minimal maintained base images and remove build-only tools/secrets;
- avoid `--privileged`, dangerous capabilities/devices, host PID/network namespaces,
  and writable host mounts;
- never mount `docker.sock` into an application container without an explicitly scoped
  proxy and threat analysis;
- use read-only rootfs plus narrowly scoped writable tmp/data mounts when compatible;
- drop capabilities and add back only required ones;
- set restrictive file ownership/modes at image build and runtime;
- configure resource limits and graceful shutdown according to availability needs;
- scan/sign/pin images according to the delivery threat model.

Running as root or lacking read-only rootfs is a hardening Gap only when containers are
in scope. Priority depends on reachable application primitives and host/mount privileges;
do not call either an exploitable vulnerability by itself.

## Databases, caches, and embedded stores

- Use a dedicated least-privilege runtime identity; separate migration/administrative
  privileges from the continuously running app.
- Reject shipped default/blank credentials and generate unique deployment secrets.
- Keep connection strings and driver errors out of clients/logs.
- Enforce transport security according to network boundary and verify certificates.
- Store dumps, WAL/AOF/RDB/SST/log files, and embedded DB directories outside web roots
  with restrictive permissions.
- Use separate tenant/owner authorization in application queries; DB role/key prefixes
  are compensating boundaries, not universal row-level authorization.
- Define safe migration rollback, backup consistency, restoration tests, and credential
  separation.

### Redis-specific checks

- Treat Redis as a trusted-service interface, not a public application protocol. Restrict
  the TCP/Unix socket to intended clients; protected mode is an accident guard, not a
  substitute for network policy and authentication.
- Prefer named ACL users. Allow only required commands/categories, key patterns, and
  Pub/Sub channel patterns; disable or narrow the permissive default user. Avoid `+@all`,
  `~*`, and `&*` unless the application genuinely requires them.
- Review the resolved Redis version before recommending ACL syntax. Key read/write
  distinctions, channel restrictions, selectors, modules, and managed Redis products
  differ by version/provider. Use ACLs rather than deprecated command renaming.
- Do not treat numbered logical databases or application key prefixes alone as tenant or
  privilege isolation. Enforce owner/tenant authorization in the application and use ACL
  key patterns as an additional service boundary where possible.
- Match persistence to semantics. A disposable cache may need none; sessions, queues,
  rate-limit state, locks, or primary records need an explicit RDB/AOF/failover data-loss
  analysis. Protect RDB/AOF files, replicas, and replication credentials as data copies.
- Set memory/resource limits and an intentional eviction policy. Evicting session,
  authorization, replay-prevention, queue, or lock keys can change security behavior;
  an unlimited dataset can make attacker-influenced writes an availability problem.
- Restrict `CONFIG`, module, scripting/function, debug, shutdown, replication, and
  keyspace-wide commands to identities that need them. Never construct Lua/function
  source or a command name from untrusted input.
- Require TLS with certificate verification when traffic crosses an untrusted/shared
  network. Authentication without transport protection does not hide Redis credentials.

### LevelDB and classic-level-specific checks

- Treat LevelDB as an embedded file store: it has no service authentication boundary.
  The process identity, directory permissions, backup controls, and host/disk encryption
  provide the storage boundary.
- Keep the database `location` server-controlled and outside served/upload directories.
  `classic-level` can create a missing directory recursively, so request-derived paths
  can turn traversal or arbitrary-location bugs into data exposure/corruption.
- Use `sublevel()` or an unambiguous structured/length-prefixed key encoding for logical
  namespaces. Ad-hoc string prefixes and delimiters can overlap; they are not a substitute
  for application authorization.
- Bound attacker-influenced range scans and `.all()` calls with strict ranges, limits,
  size quotas, and cancellation/time budgets. Level keys are lexicographically ordered;
  validate that range endpoints cannot cross a user's namespace.
- Use atomic batches when a primary record and its indexes/authorization metadata must
  change together. `clear()` is not guaranteed atomic, and parallel writes have no
  defined winner; do not build authorization-sensitive compare-then-write logic on an
  assumed transaction.
- Understand snapshot lifetime and close explicit snapshots/iterators. Long-lived
  snapshots can delay storage maintenance, while separate reads without a shared snapshot
  may not represent one consistent authorization decision.
- `classic-level` obtains an exclusive database lock. Plan single-writer process ownership,
  orderly shutdown, migrations, and backups instead of treating lock failures as an
  authentication control.
- The normal write mode may acknowledge after handing data to the operating system;
  `sync: true` requests an `fsync`-style durable write at a performance cost. Select it—or
  another recovery design—for security-critical state whose loss changes replay,
  authorization, recovery, or audit guarantees.

## Configuration and secrets

- Fail closed on missing required production secrets; do not silently use `changeme`,
  example, or development fallbacks.
- Separate development/test/production configuration and prevent test bypasses from
  activating through an ordinary client-controlled setting.
- Keep `.env*` and local credentials out of source, build context, static assets, and
  container layers. Treat example files as non-secret and unmistakably placeholders.
- Validate security-critical configuration on startup (public URL, cookie/TLS mode,
  trusted proxies, key lengths, storage paths, allowed origins).
- Restrict configuration/admin changes and audit them without values.
- Use deployment secret mounts/providers rather than command-line arguments or generated
  config with broad permissions when feasible.
- Ensure client-exposed variable conventions (`NEXT_PUBLIC_*`, `VITE_*`, etc.) cannot
  receive secrets.

Use `identity-sessions-and-secrets.md` for lifecycle/rotation requirements.

## Dependencies and supply chain

- Commit and enforce the lockfile; use deterministic/immutable installation in CI.
- Review install/postinstall scripts and packages with native/download behavior.
- Remove unused dependencies and separate development/build tooling from runtime images.
- Run supported vulnerability/advisory checks, but prioritize reachable runtime impact
  and available fixes rather than raw counts.
- Define an update cadence and ownership for Node, frameworks, runtime images, database
  engines, proxies, and critical libraries.
- Use registry/package allowlists, provenance/signature controls, or private mirrors when
  the supply-chain threat justifies them.
- Protect package publishing credentials with short lifetime/least privilege and require
  stronger authentication for maintainers.
- Pin external CI actions/images by immutable version/digest where practical; review
  automated update PRs before privileged execution.

## CI/CD and artifacts

- Give CI jobs only required repository, cloud, package, and deployment permissions.
- Prefer short-lived workload identity over static long-lived CI secrets.
- Do not expose secrets to untrusted fork PRs or execute contributor-controlled code in
  a context that holds deployment/signing credentials.
- Separate build/test from release/deploy approval and protect production environments.
- Prevent secret values from appearing in commands, debug output, test snapshots,
  coverage artifacts, caches, or uploaded logs.
- Preserve artifact integrity/provenance from reviewed source to deployed image/package.
- Scan generated browser bundles and images for unexpected secrets and development
  endpoints.
- Restrict who can change workflow files, deployment definitions, and branch protections.

## Logging, errors, and monitoring

- Log security-relevant events with stable event types, actor/subject, outcome, target,
  request/correlation ID, and trusted timestamp where appropriate.
- Cover authentication failures/successes, privilege changes, recovery, sensitive data
  access, admin/config changes, key/secret lifecycle, and security-control failures.
- Never log passwords, session IDs, bearer/reset tokens, private keys, full connection
  strings, or unnecessary sensitive payloads. Configure structured redaction and test it.
- Keep detailed stacks/driver errors server-side; return stable generic client errors.
- Fail closed when a security control errors or a security dependency is unavailable: if
  authentication, authorization, signature/token verification, validation, or an
  entitlement check throws or times out, deny the operation rather than let a `catch`,
  default value, or missing `else` resume it. In Express/Nest return 4xx/5xx or
  `next(err)`—never a bare `next()`—and have verification raise on error, not return a
  permissive default.
- Protect log integrity/access/retention and prevent user input from forging structure.
- Alert on actionable abuse patterns and control failures; missing generic audit logging
  can be a lower-priority maturity Gap, not automatically a vulnerability.
- Ensure monitoring endpoints and telemetry exporters do not expose secrets or private
  application state.

## Backups, updates, and incident readiness

- Encrypt/protect backups according to data sensitivity and keep them outside served
  roots; restrict restore/export operations more strongly than ordinary reads.
- Test restoration, including required keys/secrets and integrity checks.
- Define retention/deletion for backups, logs, object versions, and deprovisioned tenants.
- Make users/operators aware of security updates without forcing unsafe blind updates of
  stateful systems; pin releases and support rollback/migrations.
- Maintain a supported-version policy and remove known-insecure defaults during upgrade.
- Document credential rotation, token/session revocation, log preservation, and user
  notification procedures for likely incidents.
- Verify bootstrap/setup routes become permanently inaccessible after initialization.

## Primary sources

- [OWASP Transport Layer Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Transport_Layer_Security_Cheat_Sheet.html)
- [OWASP Docker Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html)
- [OWASP Database Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Database_Security_Cheat_Sheet.html)
- [OWASP Vulnerable Dependency Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Vulnerable_Dependency_Management_Cheat_Sheet.html)
- [OWASP CI/CD Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/CI_CD_Security_Cheat_Sheet.html)
- [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)
- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [Express behind proxies](https://expressjs.com/en/guide/behind-proxies.html)
- [Redis security](https://redis.io/docs/latest/operate/oss_and_stack/management/security/)
- [Redis ACL](https://redis.io/docs/latest/operate/oss_and_stack/management/security/acl/)
- [Redis persistence](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/)
- [Redis key eviction](https://redis.io/docs/latest/develop/reference/eviction/)
- [LevelDB documentation](https://github.com/google/leveldb/blob/main/doc/index.md)
- [`classic-level` documentation](https://github.com/Level/classic-level)
- [`abstract-level` ranges, sublevels, batches, and snapshots](https://github.com/Level/abstract-level)
