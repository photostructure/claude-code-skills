<!--
Composite reference for self-hosted deployment hardening. See ../ATTRIBUTION.md.
Detection guidance synthesized from the OWASP Cheat Sheet Series (Docker Security,
Database Security, SSRF Prevention, HTTP Headers), OWASP ASVS 5.0.0, official Docker
and Express documentation, and upstream security advisories. CC BY-SA 4.0.
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
Deployment-Risk rating (Critical / High / Medium / Low), separate from the app-vuln severity
table. For each item, establish the effective configuration, attacker reachability or
capability, the boundary removed, and concrete impact. A missing `USER`, read-only
rootfs, capability drop, security header, update notifier, or similar hardening control
alone is theoretical and must be dropped. The exclusions in
[`false-positives.md`](./false-positives.md) still apply.

---

## 1. Network exposure

| Candidate | Detection and proof required |
|-----------|------------------------------|
| DB/cache/admin port published to all interfaces | `ports:` in Compose or `-p` without a host IP publishes on all host addresses by default. Prove the host is reachable and the service's effective authentication/authorization permits impact. |
| App server binds `0.0.0.0`/`::` implicitly | `.listen(port)` with no host argument accepts on the unspecified address. This is often intentional; report only when it crosses a documented boundary and exposes a sensitive service. |
| Deployment relies only on UFW for a Docker-published port | Docker documents that published-container traffic is diverted before UFW's `INPUT`/`OUTPUT` chains. Verify the actual Docker firewall backend and host rules before concluding the port is reachable. |

- **Remediation:** bind sensitive services to `127.0.0.1:<port>:<port>` (or drop
  `ports:` entirely and use the Compose network). Apply host filtering appropriate to
  Docker's configured firewall backend; `DOCKER-USER` is the iptables path, while the
  nftables backend uses separately managed base chains and priorities.
- For DB-specific deployment hardening (least-privilege roles, default credentials, TLS
  in transit, migrations, dump exposure), see `database-deployment-security.md`.

## 2. Reverse proxy & TLS

Many self-hosted apps sit behind a user-chosen proxy (nginx/Caddy/Traefik/NPM), making
forwarded-header trust important to verify.

- **Express `trust proxy` misconfiguration → forwarded-header spoofing.** With `true`,
  Express trusts the left-most `X-Forwarded-For`; this is unsafe only if the last trusted
  proxy does not overwrite inbound forwarded headers or the app is reachable without
  that proxy. A numeric hop count can also fail when paths of different lengths reach
  the app. Trace the actual topology and show a security decision based on spoofable
  `req.ip`, `req.hostname`, or `req.protocol`. **Fix:** configure the exact trusted
  proxy IP/subnet or a topology-appropriate trust function and make the edge proxy
  replace inbound `X-Forwarded-*` values.
  *(This is a concrete app-code trust-boundary bug — also cross-listed in
  `vuln-classes.md`.)*
- **Host header trusted for absolute URLs → password-reset poisoning.** Building reset
  links / OAuth redirect URIs / webhook callbacks from `req.get("host")` or
  `X-Forwarded-Host` lets an attacker point the link at their domain and steal the
  token. **Detect:** `req.hostname` / `req.get("host")` / `req.headers["x-forwarded-
  host"]` feeding an emailed or redirected URL. **Fix:** require an explicit
  `PUBLIC_URL`/`baseUrl` setting; never derive link domains from request headers.
- **HSTS deployment fit.** Browsers ignore HSTS received over HTTP and HSTS applies to
  domain names, not IP-address hosts. On an HTTPS domain, a long `max-age`,
  `includeSubDomains`, or preload enrollment can make certificate/configuration errors
  non-bypassable and can affect subdomains. Treat this as deployment design, not a
  vulnerability; verify every covered host supports durable HTTPS before recommending
  those directives.

## 3. First-run / bootstrap

- **Unauthenticated setup wizard left reachable post-install.** A one-time `/setup`
  route with nothing disabling it after completion can be a pre-auth takeover when it
  can create an administrator or alter security configuration. **Detect:** setup/
  onboarding routes (`/setup`, `/install`, `/init`,
  `/onboarding`) not gated by a **server-persisted** "claimed"/"initialized" flag
  checked in middleware on **every** request to that tree (frontend-only gating fails).
  *(Concrete auth-bypass — also in `vuln-classes.md`.)*
- **Hardcoded / predictable default signing secret.** A publicly known shipped default
  `SECRET_KEY`/session/HMAC key lets attackers forge protected values whenever the
  application accepts that default. **Detect:** a string-literal fallback
  on a secret env var —
  `process.env.SECRET_KEY ?? "..."`, `|| "changeme"` — or a `.env.example` default
  that's also the runtime default when unset. **Fix:** generate + persist a random
  secret on first boot; **refuse to start** if a known placeholder is present in prod.
- **No shared working default credentials.** Bootstrap can require the admin to set a
  password or generate a unique one-time credential; do not ship a universal
  `admin/admin`-style login.

## 4. Container & filesystem hardening

| Check | Risk | Detection / Fix |
|-------|------|-----------------|
| Runs as root | Context only | Do not report alone. Escalate only when a proven attacker primitive reaches the container and root materially expands file, device, namespace, or host-mount impact. Use an image-appropriate non-root user/UID and grant ownership only where the process must write. |
| `docker.sock` mounted into a container | High-impact capability | Docker documents that controlling the daemon can grant root-level host control. Report only when an attacker can execute requests through the socket (for example, after a proven app compromise). Avoid the mount; if unavoidable, expose only required operations through a separately authenticated and authorized proxy. |
| No read-only rootfs / caps not dropped | Context only | Do not report their absence alone. Use them only to establish added impact for a proven exploit; `--privileged` or dangerous added capabilities remain candidates when attacker reachability is shown |
| World-readable data dir / DB file | Candidate | `chmod -R 777` is strong evidence, but omission of a Node `mode` is not: the process umask and existing directory permissions apply. Determine effective ownership/mode and a local or co-tenant attacker path. |

## 5. Secrets management

- **`.env` tracked in git.** Inspect tracked files for real secrets and exposure; a
  tracked example/template with placeholders is not a finding. Keep secret-bearing
  files out of source control and build context.
- **Secrets baked into image metadata/layers.** `ENV` persists in the final image;
  secret values passed through `ARG` can appear in image history or provenance, and
  copied secret files can remain in layers/cache even after later deletion. Fix:
  BuildKit `--mount=type=secret` for build-time
  secrets; Compose `secrets:` (mounted at `/run/secrets/`) for runtime.
- **Client-bundle leakage.** Build tools expose referenced variables with public
  prefixes such as `NEXT_PUBLIC_*`, `VITE_*`, and `REACT_APP_*` to browser code. Treat
  them as public and never assign secrets.
- **Secrets logged.** Grep log calls for secret-shaped values; logging a live secret is
  a finding (see `false-positives.md` precedents).

## 6. CORS

- **Reflected `Origin` + `Access-Control-Allow-Credentials: true`.** Because every
  install has a different origin, developers sometimes reflect whatever `Origin` was
  sent. Prove that a victim credential is sent cross-site (for example, a cookie whose
  `SameSite` policy permits it) and that a sensitive response or operation is exposed;
  reflection plus `credentials: true` is a candidate, not proof by itself.
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
- **Fix:** prefer a destination allowlist. Where arbitrary hosts are required, parse and
  canonicalize the URL, resolve every address, reject disallowed ranges, ensure the
  connection uses the validated result (avoiding DNS-check/use races), and repeat the
  policy for every redirect. Fixed-host path control can still be SSRF if the server's
  network position or credentials expose privileged paths on that host.

## 8. Update mechanism

Do not report the absence of an in-app update notifier or use of a mutable image tag as
a vulnerability. If update code is in scope, review its signature/provenance checks,
authorization, rollback behavior, and whether an attacker can select the artifact.

## 9. Security headers (admin panels)

Do not report missing generic headers alone. Where a concrete browser attack exists,
evaluate whether `helmet()` (or equivalent) would mitigate it: CSP tuned to actual sources,
`X-Content-Type-Options: nosniff`, `frame-ancestors`/`X-Frame-Options` (clickjacking
admin actions), `Referrer-Policy`. These controls are defense-in-depth, not standalone
findings.

## 10. Backups

- **Backup dumps world-readable or on an unauth route.** A flat DB dump has **no
  query-layer access control**, so disclosure can reveal rows that application
  authorization would filter. **Detect:**
  static-file config (`express.static`, nginx `location`) over a web root that could
  hold `*.sql`/`*.dump`/`*.bak`/`.env*`; backup-export routes missing auth middleware.
  **Fix:** write backups outside any web-served dir and require explicit privileged
  authorization on download/restore endpoints. Consider recent reauthentication for
  high-impact operations according to the threat model.

## 11. "Expose without auth" / trusted-network flags

Many self-hosted apps ship an explicit escape hatch (e.g. `EXPOSE_NETWORK_WITHOUT_AUTH`,
`SKIP_AUTH`, `DISABLE_AUTH`, `TRUST_NETWORK`). An environment-controlled opt-out is not
itself attacker-controlled. Establish that it is enabled in the effective deployment,
which interfaces/routes become reachable, and what an unauthenticated network or CSRF
attacker can do. Bind loopback by default for local-only modes and make broader exposure
an explicit, visible operator choice.

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
rg -n '^\s*-\s*"?[0-9]+:[0-9]+' -g 'docker-compose*.yml'
rg -n "0\.0\.0\.0" -g 'docker-compose*.yml' -g 'Dockerfile*'
# Root container / socket mount / privileged
rg -ni "^\s*user:\s*root|--privileged|docker\.sock" -g 'Dockerfile*' -g 'docker-compose*.yml'
rg --files-without-match "^USER " -g 'Dockerfile*'  # Dockerfiles with NO USER directive
# Secrets in image / tracked env files
rg -ni "^(ENV|ARG)\s+\w*(SECRET|PASSWORD|KEY|TOKEN)" -g 'Dockerfile*'
git ls-files | rg '^\.env($|\.)'
# Express trust-proxy / host-header / CORS
rg -n "trust proxy" .
rg -n "req\.(hostname|get\(.host|headers\[.host|headers\.host)" .
rg -n "origin:\s*true|Access-Control-Allow-Origin" .
# Placeholder secret fallbacks
rg -n "process\.env\.\w*(SECRET|KEY|TOKEN)\w*\s*(\?\?|\|\|)\s*[\"']" .
# Auth-bypass flags
rg -ni "EXPOSE.*WITHOUT_AUTH|SKIP_AUTH|DISABLE_AUTH|TRUST_NETWORK" .
```

## Sources

- [OWASP Docker Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html)
- [OWASP Database Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Database_Security_Cheat_Sheet.html)
- [OWASP SSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
- [OWASP HTTP Headers Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html)
- [OWASP ASVS 5.0.0](https://github.com/OWASP/ASVS/tree/v5.0.0/5.0/en)
- [Express — Behind proxies](https://expressjs.com/en/guide/behind-proxies.html)
- [Docker port publishing and mapping](https://docs.docker.com/engine/network/port-publishing/) · [Docker packet filtering and UFW](https://docs.docker.com/engine/network/packet-filtering-firewalls/) · [Docker build secrets](https://docs.docker.com/build/building/secrets/)
- [Node.js `net.Server.listen()`](https://nodejs.org/api/net.html#serverlisten)
- [MDN — Strict-Transport-Security](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Strict-Transport-Security)
