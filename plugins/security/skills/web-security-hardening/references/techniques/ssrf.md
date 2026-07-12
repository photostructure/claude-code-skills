<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# SSRF Address Validation

Hardening for features that fetch attacker-influenced URLs (webhooks, link previews,
avatar/image import, PDF/HTML render, OIDC/JWKS/metadata fetch). See also
[URLs, redirects, and outbound requests](../input-output-and-files.md#urls-redirects-and-outbound-requests).

## Block internal and metadata destinations

Anti-pattern to grep: `fetch(req.body.url)`, `axios.get(userUrl)`, `http.get(target)`,
`got(url)`, `request(url)` where the host is user-supplied and no IP check runs. A
hostname allowlist alone is not enough — an attacker-controlled host can resolve into
any range.

- Fix: after resolving (see next section), reject the request if the resolved IP falls in
  any blocked range. Deny at minimum: cloud metadata `169.254.169.254` and all
  link-local `169.254.0.0/16` (and `fe80::/10`); loopback `127.0.0.0/8` and `::1/128`;
  `0.0.0.0/8`; RFC1918 `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`; unique-local
  `fc00::/7`; and IPv4-mapped IPv6 (`::ffff:0:0/96`, e.g. `::ffff:169.254.169.254`).
  Normalize mapped/compressed IPv6 before the range test so a mapped form cannot smuggle
  a blocked v4 address past a v4-only check.
- Cloud metadata uses the same `169.254.169.254` on AWS / GCP / Azure; GCP also serves
  `metadata.google.internal`. Prefer an outbound egress firewall / NAT policy as the
  authoritative control — app-layer checks are defense-in-depth, not a substitute.
  Verify current metadata addresses and any provider-specific hostnames against the
  installed cloud's live docs.
- Use a well-maintained IP-range library (e.g. `ipaddr.js`) rather than hand-rolled
  string/CIDR math, and verify it classifies IPv4-mapped and compressed IPv6 as you
  expect. Do not rely on the `ip` (node-ip) package for SSRF decisions: its
  `isPrivate`/`isPublic` have documented classification bypasses for non-decimal and
  otherwise unusual IP notations (CVE-2023-42282 and related unresolved issues), and the
  package is effectively unmaintained — confirm the current status of any library before
  trusting it.

## Resolve once, pin, connect to the pinned IP (DNS rebinding)

Anti-pattern to grep: validation runs on the URL/hostname string, then a separate
`fetch`/`axios`/`got` call re-resolves DNS. Between the two lookups the attacker's DNS
can flip to `169.254.169.254` (TOCTOU / DNS rebinding), so the connection reaches an
internal address the check never saw.

- Fix: resolve the hostname yourself once (all A + AAAA records), validate every returned
  IP against the block ranges, then connect to that pinned IP — do not let the HTTP client
  resolve again. Validate at socket/connection time, not only at URL-parse time.
- Named lever in Node: supply a custom `lookup` function (the `dns.lookup` signature,
  accepted by the core `http`/`https` agent and by `got`/`axios` via a custom agent) that
  performs the check and returns the validated address; or validate in the socket
  `lookup`/`connect` event and destroy the socket on a blocked IP. Confirm the exact
  option name and that it fires per-connection in your installed client version.
- Keep the IP pinned for the whole request (including keep-alive reuse); short/zeroed
  DNS TTLs are an attacker signal, not a reason to re-resolve mid-request.

## Re-validate every redirect hop; allowlist schemes and hosts

Anti-pattern to grep: a client with default redirect following (`maxRedirects` > 0,
`follow`/`redirect: 'follow'`) where only the original URL was validated; also
`new URL(userUrl)` with no scheme check, or a URL carrying `user:pass@`.

- Fix: either disable redirect following and handle each hop manually, or install a
  per-redirect hook that re-runs the full scheme/host/IP validation on the new location.
  A validated first hop can 3xx-redirect straight to metadata. Verify your client's
  redirect-hook / `beforeRedirect` name and semantics against its installed version.
- Allowlist required schemes (`https:`, and `http:` only if genuinely needed); reject
  `file:`, `gopher:`, `data:`, `ftp:`, `blob:`, and other non-http(s) schemes.
- Reject credential-bearing URLs (`url.username`/`url.password` non-empty) and
  protocol-relative (`//host`) forms. Compare normalized scheme/host/port with a real URL
  parser, never string prefix/suffix matches.

## Primary sources

- [OWASP SSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
- [AWS EC2 Instance Metadata Service (IMDS)](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instancedata-data-retrieval.html)
- [GCP metadata server](https://cloud.google.com/compute/docs/metadata/overview)
- [Azure Instance Metadata Service](https://learn.microsoft.com/en-us/azure/virtual-machines/instance-metadata-service)
