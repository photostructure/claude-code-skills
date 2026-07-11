<!--
Database deployment & configuration security. See ../ATTRIBUTION.md.
Synthesized from the OWASP Database Security Cheat Sheet, official PostgreSQL, MySQL,
Redis, LevelDB, and Node Level documentation, and public exposure/ransomware reporting
for self-hosted DBs. CC BY-SA 4.0.
-->

# Database Deployment Security

**Load this file when** the scope includes a DB service in `docker-compose*.yml`,
`DATABASE_URL`/connection config, Redis config, a LevelDB location, migration runner
config, or DB setup/init scripts — i.e. how storage is *deployed and connected to*, as
opposed to application-level bugs in `vuln-classes.md`.

Treat the checks below as candidates. Report them under the **Deployment Hardening**
section with a Deployment-Risk rating (Critical / High / Medium) only after proving the
effective configuration, attacker reachability or capability, boundary removed, and
concrete impact. For example, a superuser app role needs a proven injection/RCE path to
amplify, disabled DB TLS needs an applicable network-attacker position, and a tracked
config needs a real exposed credential. Drop missing hardening alone.

## 1. Least-privilege DB account

- **Why (self-hosted especially):** install scripts routinely wire the app to connect as
  the DB **superuser** (`postgres`/`root`/`sa`) they just created, because there's no DBA
  to push back. One SQLi or RCE then owns the whole instance, not just the app's schema.
- **Detect:** `DATABASE_URL` / compose env / `.env.example` using a superuser role; the
  running app and the migration runner sharing one all-powerful credential.
- **Fix:** a dedicated app role scoped to its own schema/database with only the DML it
  needs (usually `SELECT`/`INSERT`/`UPDATE`/`DELETE`); keep the migration/superuser
  credential separate and out of the running app's environment.

## 2. Network exposure & default credentials

DB **binding scope** is covered in `self-hosting-hardening.md` §1 (the Docker-publishes-
past-UFW trap). The DB-specific additions:

- **Default / blank passwords.** Self-hosted DB images and quick-start compose files ship
  with well-known or empty passwords "for setup" that never get changed. Combined with a
  port on `0.0.0.0`, this is the #1 real-world self-hosted-DB compromise — researchers
  found 1.3M+ Postgres instances on default ports, and honeypots show ransom bots wiping
  exposed DBs within hours.
- **Detect:** DB config/env with blank or well-known passwords and no startup check that
  rejects them; `pg_hba.conf` / MySQL `bind-address` set to `0.0.0.0`/`*`.
- **Fix:** require a non-default password with no fallback default in the install script;
  bind the DB to localhost / the internal Docker network; scope any host port mapping to
  `127.0.0.1:5432:5432`.

## 3. Credentials in connection strings, logs & driver errors

- **Detect:** hardcoded `postgres://user:pass@host/db` literals in source; `.env` files
  tracked by git (`git ls-files | grep -E '^\.env'`); a raw DB-driver `Error` logged or
  returned to the client — driver errors (auth failure, host unreachable) often embed the
  **full connection string**. (See also `vuln-classes.md` → Secrets / Information
  disclosure.)
- **Fix:** credentials outside the web root with restrictive file perms, never in source
  control; never log or return the raw driver Error to a client.

## 4. Encryption in transit (TLS to the DB)

- **Why:** "same Docker network, so TLS doesn't matter" breaks the moment the DB is
  reachable from a wider segment (shared VLAN, k8s cluster networking).
- **Detect:** `pg`/`mysql2` config with `ssl: false` or no `ssl` key against a non-
  localhost host; `sslmode=disable` in a connection string; `rejectUnauthorized: false`
  outside a clearly dev-only path.
- **Fix:** require TLS whenever the DB host isn't localhost / a private-only network;
  never disable certificate verification in production.

## 5. Redis-specific boundary

- **Reachability first:** protected mode is a safety net, not authorization. Report a
  broad bind or published port only after establishing attacker reachability and an
  effective weak boundary such as `protected-mode no`, a passwordless/broad default
  user, or dangerous commands available to the app identity.
- **Least-privilege ACL:** use a named application user restricted to required commands,
  key patterns (`~app:*`), and Pub/Sub channels (`&app:*`). Avoid `+@all`; it includes
  module commands, while normal applications should not need administrative/dangerous
  commands such as `CONFIG`, `DEBUG`, `MODULE`, `REPLICAOF`, `FLUSHALL`, or `MIGRATE`.
- **Transport:** `AUTH` does not encrypt traffic. Require Redis TLS when credentials or
  sensitive data cross an untrusted/shared network, including replication links where
  applicable. A private-only local connection without TLS is not a finding by itself.
- **Persistence:** treat RDB/AOF files and copied volumes like database dumps. Prove a
  web-served path, permissive filesystem access, or another attacker-readable boundary
  before reporting exposure.

## 6. LevelDB filesystem boundary

- **Embedded, not networked:** LevelDB has no listener, TLS, or database authentication;
  the database directory's filesystem permissions and the application's authorization
  are its boundaries. Do not apply Redis/SQL network-hardening checks to it.
- **Location:** `ClassicLevel(location)` may recursively create a directory and obtains
  an exclusive lock. Require a server-controlled location under a restrictive data
  directory; investigate request/config flows into `destroy()` or `repair()`.
- **Files/backups:** LevelDB logs and table files belong outside web-served roots and
  backups need the same access restrictions as the live directory.
- **Process lock:** an exclusive-lock failure is availability-only unless the app falls
  back to a different/empty store and thereby loses authorization, session, or
  revocation state.

## 7. Migration safety

- **Why:** migrations run with elevated **DDL** privileges (often the one place the
  least-privilege app role is bypassed) and execute ambiently on deploy.
- **Detect:** a migration building SQL from a **variable** rather than hardcoded DDL (a
  rare but real injection surface with DDL-level blast radius); the migration runner
  configured with the app's full-privilege credential instead of a dedicated migration
  role.
- **Fix:** migrations contain hardcoded DDL only; if parameterized by environment,
  allowlist any identifier before interpolating (same rule as ORDER BY / identifier
  injection in `vuln-classes.md`).

## 8. Backup / dump exposure

- **Why:** a flat DB dump has **no query-layer access control**, so it bypasses every
  IDOR/authz control the app enforces — strictly worse than live-DB access.
- **Detect:** cron/backup scripts writing `db-backup-*.sql` / `*.dump` / `.env.bak` into a
  web-served directory (`public/`, `static/`); `express.static`/nginx `location` roots
  over a path that could contain dumps; backup/export/restore routes missing auth (see
  `vuln-classes.md` → Authorization, and `self-hosting-hardening.md` §10).
- **Fix:** write backups outside any web-served directory; require fresh re-auth (not just
  an ambient session) on any download/restore endpoint, and log access.

## Detection starters

```bash
# Superuser role in the app's connection config
grep -rniE "postgres://(postgres|root|sa):|DATABASE_URL=.*(postgres|root|sa)@" . --include="*.env*" --include="*.yml" --include="*.ts" --include="*.js"
# TLS disabled to the DB
grep -rniE "ssl:\s*false|sslmode=disable|rejectUnauthorized:\s*false|tls:\s*false" . --include="*.ts" --include="*.js"
# Tracked env files / hardcoded connection strings
git ls-files | grep -E '^\.env($|\.)'
grep -rniE "(postgres|mysql|mongodb|redis|rediss)://[^@[:space:]]*:[^@[:space:]]+@" . --include="*.ts" --include="*.js"
# Redis / LevelDB boundaries
grep -rniE "protected-mode\s+no|--protected-mode[= ]no|user\s+default.*nopass.*\+@all" . --include="*.conf" --include="*.yml"
grep -rniE "new ClassicLevel|ClassicLevel\.(destroy|repair)" . --include="*.ts" --include="*.js"
# Dumps under a served directory
grep -rniE "express\.static|sendFile" . --include="*.ts" --include="*.js"
```

## Sources

- [OWASP Database Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Database_Security_Cheat_Sheet.html)
- [node-postgres — SSL](https://node-postgres.com/features/ssl)
- [Redis security](https://redis.io/docs/latest/operate/oss_and_stack/management/security/) · [Redis ACL](https://redis.io/docs/latest/operate/oss_and_stack/management/security/acl/)
- [LevelDB documentation](https://github.com/google/leveldb/blob/main/doc/index.md) · [classic-level](https://github.com/Level/classic-level) · [abstract-level](https://github.com/Level/abstract-level)
- [Percona — MySQL Ransomware (Open Source DB Security)](https://www.percona.com/blog/mysql-ransomware-open-source-database-security-part-3/) · [Help Net Security — Postgres/MySQL ransomware bot](https://www.helpnetsecurity.com/2024/01/18/postgresql-mysql-ransomware-bot/)
- [CWE-530 — Exposure of Backup File](https://cwe.mitre.org/data/definitions/530.html)
