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
section with a Deployment-Risk rating (Critical / High / Medium / Low) only after proving the
effective configuration, attacker reachability or capability, boundary removed, and
concrete impact. For example, a superuser app role needs a proven injection, credential
exposure, or RCE path to amplify; disabled DB TLS needs an applicable network-attacker
position; and a tracked config needs a real exposed credential. Drop missing hardening
alone.

## 1. Least-privilege DB account

- **Why:** some install scripts wire the app to connect as
  the DB **superuser** (`postgres`/`root`/`sa`) they just created. A proven SQL injection,
  credential exposure, or application RCE then has the role's instance-wide privileges
  instead of only the application's required objects.
- **Detect:** `DATABASE_URL` / compose env / `.env.example` using a superuser role; the
  running app and the migration runner sharing one all-powerful credential.
- **Fix:** a dedicated app role scoped to its own schema/database with only the object,
  sequence, and routine privileges it actually needs; keep the migration/superuser
  credential separate and out of the running app's environment.

## 2. Network exposure & default credentials

DB **binding scope** is covered in `self-hosting-hardening.md` §1 (the Docker-publishes-
past-UFW trap). The DB-specific additions:

- **Default / blank passwords.** Investigate explicit blank, well-known, or trust-mode
  credentials in the effective deployment. Do not assume official images accept a blank
  password: for example, the official PostgreSQL image refuses first initialization
  without `POSTGRES_PASSWORD` unless `POSTGRES_HOST_AUTH_METHOD=trust` is explicitly set.
- **Detect:** DB config/env with blank or well-known passwords and no startup check that
  rejects them; PostgreSQL `listen_addresses` or MySQL `bind-address` set broadly;
  PostgreSQL `pg_hba.conf` trust rules are an authentication check, not a bind setting.
- **Fix:** require a non-default password with no fallback default in the install script;
  bind the DB to localhost / the internal Docker network; scope any host port mapping to
  `127.0.0.1:5432:5432`.

## 3. Credentials in connection strings, logs & driver errors

- **Detect:** hardcoded `postgres://user:pass@host/db` literals in source; tracked `.env`
  files containing real credentials; a raw DB-driver error returned to clients or sent
  to attacker-readable logs. Inspect the actual driver's error fields and logger
  serialization — do not assume every driver error embeds a connection string. (See
  also `vuln-classes.md` → Secrets / Information disclosure.)
- **Fix:** credentials outside the web root with restrictive file perms, never in source
  control; return generic client errors and redact sensitive server-log fields.

## 4. Encryption in transit (TLS to the DB)

- **Why:** TLS matters when a network actor can observe or alter the connection; network
  placement and platform controls determine whether that capability exists.
- **Detect:** `pg`/`mysql2` config with `ssl: false` or no `ssl` key against a non-
  localhost host; `sslmode=disable` in a connection string; `rejectUnauthorized: false`
  outside a clearly dev-only path.
- **Fix:** require TLS with certificate/hostname verification across untrusted or shared
  networks. A private address alone does not prove the network trustworthy; conversely,
  a same-host Unix socket is not a missing-TLS finding.

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

- **Why:** migrations often run with elevated **DDL** privileges (often the one place the
  least-privilege app role is bypassed) and execute ambiently on deploy.
- **Detect:** a migration inserting an untrusted variable as SQL/DDL syntax rather than
  binding a value or mapping an identifier from an allowlist; the migration runner
  configured with the app's full-privilege credential instead of a dedicated migration
  role.
- **Fix:** keep migration structure developer-controlled. Bind data values where the
  driver/statement permits; map dynamic identifiers or DDL fragments from a fixed
  allowlist rather than concatenating untrusted input.

## 8. Backup / dump exposure

- **Why:** a flat DB dump has **no query-layer access control**, so disclosure can expose
  rows that application authorization would otherwise filter.
- **Detect:** cron/backup scripts writing `db-backup-*.sql` / `*.dump` / `.env.bak` into a
  web-served directory (`public/`, `static/`); `express.static`/nginx `location` roots
  over a path that could contain dumps; backup/export/restore routes missing auth (see
  `vuln-classes.md` → Authorization, and `self-hosting-hardening.md` §10).
- **Fix:** write backups outside any web-served directory; require explicit privileged
  authorization on download/restore endpoints. Consider recent reauthentication for
  high-impact operations according to the application's threat model.

## Detection starters

```bash
# Superuser role in the app's connection config
rg -ni -g '*.env*' -g '*.yml' -g '*.ts' -g '*.js' "postgres://(postgres|root|sa):|DATABASE_URL=.*(postgres|root|sa)@" .
# TLS disabled to the DB
rg -ni -g '*.ts' -g '*.js' "ssl:\s*false|sslmode=disable|rejectUnauthorized:\s*false|tls:\s*false" .
# Tracked env files / hardcoded connection strings
git ls-files | rg '^\.env($|\.)'
rg -ni -g '*.ts' -g '*.js' "(postgres|mysql|mongodb|redis|rediss)://[^@[:space:]]*:[^@[:space:]]+@" .
# Redis / LevelDB boundaries
rg -ni -g '*.conf' -g '*.yml' "protected-mode\s+no|--protected-mode[= ]no|user\s+default.*nopass.*\+@all" .
rg -ni -g '*.ts' -g '*.js' "new ClassicLevel|ClassicLevel\.(destroy|repair)" .
# Dumps under a served directory
rg -ni -g '*.ts' -g '*.js' "express\.static|sendFile" .
```

## Sources

- [OWASP Database Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Database_Security_Cheat_Sheet.html)
- [PostgreSQL role attributes](https://www.postgresql.org/docs/current/role-attributes.html) · [PostgreSQL client authentication](https://www.postgresql.org/docs/current/client-authentication.html) · [Official PostgreSQL image](https://github.com/docker-library/docs/blob/master/postgres/README.md)
- [node-postgres — SSL](https://node-postgres.com/features/ssl)
- [Redis security](https://redis.io/docs/latest/operate/oss_and_stack/management/security/) · [Redis ACL](https://redis.io/docs/latest/operate/oss_and_stack/management/security/acl/)
- [LevelDB documentation](https://github.com/google/leveldb/blob/main/doc/index.md) · [classic-level](https://github.com/Level/classic-level) · [abstract-level](https://github.com/Level/abstract-level)
- [CWE-530 — Exposure of Backup File](https://cwe.mitre.org/data/definitions/530.html)
