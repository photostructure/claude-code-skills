<!--
Composite reference for self-hosted deployment hardening. See ../ATTRIBUTION.md.
Detection guidance synthesized from the OWASP Cheat Sheet Series (Docker Security,
Database Security, SSRF Prevention, HTTP Headers), OWASP ASVS V14, the CIS Docker
Benchmark, the Express "behind proxies" guide, and public CVE write-ups for
self-hosted apps. Facts and API names; expression is original. CC BY-SA 4.0.
-->

# Self-Hosting / Deployment Hardening

**Load this file when the scope includes** `Dockerfile`, `docker-compose*.yml`,
`.env*`, entrypoint/init scripts, systemd units, or reverse-proxy config — or when the
user asks for a "deployment", "Docker", or "self-hosting" review.

## Why this is a separate pass

For a **self-hosted, database-backed app run by non-experts on their own hardware**,
deployment configuration can be the effective security boundary. Use this pass to
investigate that boundary, but keep every candidate behind the same proof gate as app
findings.

**Report proven items under their own "Deployment Hardening" section** with a
Deployment-Risk rating (Critical / High / Medium), separate from the app-vuln severity
table. For each item, establish the effective configuration, attacker reachability or
capability, the boundary removed, and concrete impact. A missing `USER`, read-only
rootfs, capability drop, security header, update notifier, or similar hardening control
alone is theoretical and must be dropped. The exclusions in
[`false-positives.md`](./false-positives.md) still apply.

---

## 1. Network exposure

| Check | Risk | Detection |
|-------|------|-----------|
| DB/cache/admin port published to all interfaces | **Critical** | `ports:` in compose or `-p` on `docker run` without a `127.0.0.1:` prefix, esp. for `postgres`/`mysql`/`redis`/`mongo`/`elasticsearch` |
| App server binds `0.0.0.0`/`::` implicitly | High | `.listen(port)` with no host arg (Node defaults to all interfaces) |
| "Firewall protects the DB port" assumption | **Critical** | Docker writes its own iptables rules **before** UFW's INPUT chain — `ufw deny 5432` does **nothing** for a published container port |

- **Remediation:** bind sensitive services to `127.0.0.1:<port>:<port>` (or drop
  `ports:` entirely and use the compose network); add `DOCKER-USER` iptables rules for
  defense-in-depth. Publicly reachable MongoDB, Elasticsearch, Redis, and SQL services
  without authentication have repeatedly been ransomed or destroyed.
- For DB-specific deployment hardening (least-privilege roles, default credentials, TLS
  in transit, migrations, dump exposure), see `database-deployment-security.md`.

## 2. Reverse proxy & TLS

Self-hosted apps sit behind a user-chosen proxy (nginx/Caddy/Traefik/NPM), so trust of
forwarded headers is the recurring bug.

- **Express `trust proxy` misconfiguration → IP/host spoofing.** `app.set("trust
  proxy", true)` (pasted from Stack Overflow to "fix HTTPS behind nginx") makes Express
  take the **left-most**, attacker-supplied `X-Forwarded-For` as `req.ip` — defeating
  IP rate-limits, allowlists, and audit logs — and makes `req.hostname`/`req.protocol`
  attacker-controlled. **Detect:** `app.set("trust proxy"` set to `true` or a bare
  number. **Fix:** set it to the exact proxy IP/subnet (or the named `loopback`/
  `uniquelocal` ranges), and require the proxy to overwrite inbound `X-Forwarded-*`.
  *(This is a concrete app-code trust-boundary bug — also cross-listed in
  `vuln-classes.md`.)*
- **Host header trusted for absolute URLs → password-reset poisoning.** Building reset
  links / OAuth redirect URIs / webhook callbacks from `req.get("host")` or
  `X-Forwarded-Host` lets an attacker point the link at their domain and steal the
  token. **Detect:** `req.hostname` / `req.get("host")` / `req.headers["x-forwarded-
  host"]` feeding an emailed or redirected URL. **Fix:** require an explicit
  `PUBLIC_URL`/`baseUrl` setting; never derive link domains from request headers.
- **HSTS caution (self-hosted inversion of SaaS advice).** Self-hosted installs are
  often first reached over plain HTTP on a LAN IP. Shipping
  `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload` by default
  — or preloading — can **lock an admin out of their own instance** for up to two
  years. **Fix:** emit HSTS only when the app confirms it's served over TLS
  (proxy-confirmed `X-Forwarded-Proto` or app-terminated TLS); keep `max-age` short
  until the admin opts in; never preload by default.

## 3. First-run / bootstrap

- **Unauthenticated setup wizard left reachable post-install.** A one-time `/setup`
  route with nothing disabling it after completion is a pre-auth takeover (cf.
  Appsmith CVE-2024-55963 default-no-password Postgres → RCE; ChurchCRM install-wizard
  pre-auth RCE). **Detect:** setup/onboarding routes (`/setup`, `/install`, `/init`,
  `/onboarding`) not gated by a **server-persisted** "claimed"/"initialized" flag
  checked in middleware on **every** request to that tree (frontend-only gating fails).
  *(Concrete auth-bypass — also in `vuln-classes.md`.)*
- **Hardcoded / predictable default signing secret.** A shipped default `SECRET_KEY`/
  session/HMAC key that's never rotated lets attackers forge admin cookies or JWTs
  (Superset default `SECRET_KEY` → forged admin sessions, ~67% of exposed instances
  still on a known key years later; Dokploy hardcoded `BETTER_AUTH_SECRET` → forged
  JWT → RCE, CVSS 10.0). **Detect:** a string-literal fallback on a secret env var —
  `process.env.SECRET_KEY ?? "..."`, `|| "changeme"` — or a `.env.example` default
  that's also the runtime default when unset. **Fix:** generate + persist a random
  secret on first boot; **refuse to start** if a known placeholder is present in prod.
- **No default `admin/admin`.** Bootstrap must force the admin to set a password, not
  ship working default credentials.

## 4. Container & filesystem hardening

| Check | Risk | Detection / Fix |
|-------|------|-----------------|
| Runs as root | Context only | Do not report alone. Escalate only when a proven attacker primitive reaches the container and root materially expands file, device, namespace, or host-mount impact. Fix: `useradd -r -u 1000 app` + `USER app` |
| `docker.sock` mounted into a container | **Critical** | `docker.sock` in `volumes:` = root-equivalent host access. Fix: never mount it into an app container; if needed, use a scoped read-only socket proxy |
| No read-only rootfs / caps not dropped | Context only | Do not report their absence alone. Use them only to establish added impact for a proven exploit; `--privileged` or dangerous added capabilities remain candidates when attacker reachability is shown |
| World-readable data dir / DB file | High | `fs.writeFile`/`mkdir` with no restrictive `mode:`, or `chmod -R 777` in entrypoint. Fix: `0600`/`0700` under a dedicated non-root UID |

## 5. Secrets management

- **`.env` tracked in git.** `git ls-files | grep -E '^\.env($|\.)'`. Fix: `.gitignore`
  + `.dockerignore` all `.env*`.
- **Secrets baked into image layers.** `ENV`/`ARG` assigning `*_SECRET|*_PASSWORD|
  *_KEY|*_TOKEN` in a Dockerfile persist in image history forever (`docker history`),
  even after a later "removal". Fix: BuildKit `--mount=type=secret` for build-time
  secrets; Compose `secrets:` (mounted at `/run/secrets/`) for runtime.
- **Client-bundle leakage.** `NEXT_PUBLIC_*` / `VITE_*` / `REACT_APP_*` vars are shipped
  to the browser — never put secrets there.
- **Secrets logged.** Grep log calls for secret-shaped values; logging a live secret is
  a finding (see `false-positives.md` precedents).

## 6. CORS

- **Reflected `Origin` + `Access-Control-Allow-Credentials: true`.** Because every
  install has a different origin, developers reflect whatever `Origin` was sent — which
  is functionally `*` + credentials and lets any site make authenticated requests.
  **Detect:** `cors({ origin: true, credentials: true })` or `Access-Control-Allow-
  Origin` set from `req.headers.origin` with credentials. **Fix:** validate `Origin`
  against the instance's configured public URL(s). *(Also in `vuln-classes.md`.)*

## 7. SSRF in a self-hosted context

"Self-hosted ⇒ SSRF is low risk" is **false** — the target just shifts:

- **Cloud-VM deployments** (many self-hosters use a DO/AWS/GCP droplet): SSRF can reach
  the metadata endpoint (`169.254.169.254`, `metadata.google.internal`) and steal IAM
  credentials.
- **LAN deployments:** SSRF reaches other unauthenticated services on the LAN (router
  admin UI, an unauth'd Redis/Prometheus on `192.168.x.x`).
- Common SSRF-prone features in this app category: fetch-avatar-by-URL, RSS/podcast
  import, webhook test-fire, remote-thumbnail proxy, OIDC discovery-URL fetch.
- **Fix:** resolve-then-validate the **IP** (not just hostname) against private/link-
  local ranges before connecting, and re-validate on redirect (DNS-rebinding). Path-
  only SSRF stays a non-finding (host/protocol fixed) — check it under path traversal.

## 8. Update & patch cadence

- **Stale long-lived instance.** Self-hosted installs only get patched if the admin
  acts (Log4Shell is still exploited years later precisely in unmanaged deployments).
  Check for *any* in-app update-availability signal (version-check banner, changelog
  surfacing). **Fix:** ship an opt-in, privacy-respecting "new version available" check.
- **The opposite failure: blind auto-update.** Pulling a mutable `latest` tag and
  restarting can jump a major version or recreate a DB container mid-write. **Fix:** pin
  image tags to digests; prefer notify-only / manual-approval for stateful containers.

## 9. Security headers (admin panels)

Do not report missing generic headers alone. Where a concrete browser attack exists,
evaluate whether `helmet()` (or equivalent) would mitigate it: CSP tuned to actual sources,
`X-Content-Type-Options: nosniff`, `frame-ancestors`/`X-Frame-Options` (clickjacking
admin actions), `Referrer-Policy`. These controls are defense-in-depth, not standalone
findings.

## 10. Backups

- **Backup dumps world-readable or on an unauth route.** A flat DB dump has **no
  query-layer access control**, so it bypasses all the app's IDOR/authz work. **Detect:**
  static-file config (`express.static`, nginx `location`) over a web root that could
  hold `*.sql`/`*.dump`/`*.bak`/`.env*`; backup-export routes missing auth middleware.
  **Fix:** write backups outside any web-served dir; require fresh re-auth (not just an
  ambient session) on any download endpoint, and log access.

## 11. "Expose without auth" / trusted-network flags

Many self-hosted apps ship an explicit escape hatch (e.g. `EXPOSE_NETWORK_WITHOUT_AUTH`,
`SKIP_AUTH`, `DISABLE_AUTH`, `TRUST_NETWORK`) justified as "it's just my LAN." **A LAN
is not a trust boundary** — it's a broadcast domain shared with guest Wi-Fi, a
compromised IoT device pivoting laterally, or a forgotten UPnP rule; and CSRF works
against a LAN app from the admin's own browser regardless. **Detect:** env-gated auth
bypasses; confirm the flag is loudly warned at startup and cannot silently combine with
a `0.0.0.0` bind. **Fix:** bind loopback by default regardless of the flag; require a
second explicit opt-in to bind non-loopback; warn on every request while active. This
is the one deliberate exception to `false-positives.md` exclusion #11 — the risk is the
flag's default **binding scope**, not "can an attacker set env vars."

## 12. Authentication endpoint hardening (brute-force)

Generic API rate-limiting is out of scope (noise). But an **authentication** endpoint
(login / password-reset / signup) with **zero** brute-force defense is a real
credential-stuffing exposure for an internet-reachable self-hosted app. Report it as a
Deployment-Risk item only after establishing that reachability and the absence of all
effective defenses; do not infer deployment exposure from the route alone.

- **Detect:** a login route/service with no failed-attempt counter, no backoff, no
  CAPTCHA, and no rate-limit middleware (`express-rate-limit`, `rate-limiter-flexible`)
  in its chain. If dynamic confirmation is useful, use only an isolated local fixture
  with synthetic accounts and no external network or persistent side effects.
- **Fix:** per-**account** lockout/backoff (IP-only is evaded by rotation), but always
  allow password reset while locked (else lockout becomes a DoS). Pair with the
  enumeration and timing defenses in `vuln-classes.md` → Authentication.

## 13. Database deployment

DB deployment hardening (least-privilege roles, default credentials, TLS in transit,
migration privilege, dump exposure) lives in its own reference:
**`database-deployment-security.md`**. Load it whenever a DB service, connection config,
or migration runner is in scope.

---

## Detection starters

```bash
# Ports published to all interfaces (want a 127.0.0.1: prefix on sensitive services)
grep -rnE '^\s*-\s*"?[0-9]+:[0-9]+' docker-compose*.yml
grep -rn "0.0.0.0" docker-compose*.yml Dockerfile
# Root container / socket mount / privileged
grep -rniE "^\s*user:\s*root|--privileged|docker\.sock" Dockerfile docker-compose*.yml
grep -Ln "^USER " Dockerfile        # Dockerfiles with NO USER directive
# Secrets in image / tracked env files
grep -rniE "^(ENV|ARG)\s+\w*(SECRET|PASSWORD|KEY|TOKEN)" Dockerfile
git ls-files | grep -E '^\.env($|\.)'
# Express trust-proxy / host-header / CORS
grep -rn "trust proxy" .
grep -rnE "req\.(hostname|get\(.host|headers\[.host|headers\.host)" .
grep -rnE "origin:\s*true|Access-Control-Allow-Origin" .
# Placeholder secret fallbacks
grep -rnE "process\.env\.\w*(SECRET|KEY|TOKEN)\w*\s*(\?\?|\|\|)\s*[\"']" .
# Auth-bypass flags
grep -rniE "EXPOSE.*WITHOUT_AUTH|SKIP_AUTH|DISABLE_AUTH|TRUST_NETWORK" .
```

## Sources

- [OWASP Docker Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html)
- [OWASP Database Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Database_Security_Cheat_Sheet.html)
- [OWASP SSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
- [OWASP HTTP Headers Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html)
- [OWASP ASVS V14 — Configuration](https://github.com/OWASP/ASVS/blob/master/4.0/en/0x22-V14-Config.md)
- [Express — Behind proxies](https://expressjs.com/en/guide/behind-proxies.html)
- [CIS Docker Benchmark](https://docs.docker.com/dhi/core-concepts/cis/) · [Why Docker bypasses UFW](https://github.com/docker/for-linux/issues/690) · [ufw-docker](https://github.com/chaifeng/ufw-docker)
- CVE write-ups: [Appsmith CVE-2024-55963](https://rhinosecuritylabs.com/research/cve-2024-55963-unauthenticated-rce-in-appsmith/) · [Superset CVE-2023-27524](https://horizon3.ai/attack-research/disclosures/cve-2023-27524-insecure-default-configuration-in-apache-superset-leads-to-remote-code-execution/) · [runc CVE-2019-5736](https://unit42.paloaltonetworks.com/breaking-docker-via-runc-explaining-cve-2019-5736/) · [Grafana CVE-2021-43798](https://labs.detectify.com/security-guidance/how-i-found-the-grafana-zero-day-path-traversal-exploit-that-gave-me-access-to-your-logs/) · [Password-reset poisoning](https://portswigger.net/web-security/host-header/exploiting/password-reset-poisoning)
