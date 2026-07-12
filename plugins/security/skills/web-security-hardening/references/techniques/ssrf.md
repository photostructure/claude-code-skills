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

- Prefer an allowlist of destinations when the business function permits it. Otherwise,
  resolve and reject every address that is not globally routable for the intended service,
  including loopback, private, link-local/metadata, unspecified, multicast, reserved, and
  IPv4-mapped IPv6 forms. A hand-maintained list containing only RFC1918 and
  `169.254.169.254` is incomplete; use a maintained parser/classifier and test IPv4, IPv6,
  compressed, mapped, and alternate textual forms.
- Cloud metadata uses the same `169.254.169.254` on AWS / GCP / Azure; GCP also serves
  `metadata.google.internal`. Prefer an outbound egress firewall / NAT policy as the
  authoritative control — app-layer checks are defense-in-depth, not a substitute.
  Verify current metadata addresses and any provider-specific hostnames against the
  installed cloud's live docs.
- Use a maintained IP parser/classifier rather than hand-rolled string/CIDR math. Test the
  pinned library against mapped/compressed IPv6 and alternate IPv4 notations; package names
  and a passing `isPrivate()` call are not proof of complete classification.

## Validate the address used by the connection

Anti-pattern to grep: validation runs on the URL/hostname string, then a separate
`fetch`/`axios`/`got` call re-resolves DNS. Between the two lookups the attacker's DNS
can flip to `169.254.169.254` (TOCTOU / DNS rebinding), so the connection reaches an
internal address the check never saw.

- Validate at the actual connection boundary so the address checked is the address used.
  A custom `lookup` can do this for Node `http`/`https`, but its callback may select one
  address rather than expose every A/AAAA record, and third-party clients/Undici use
  different dispatcher/agent hooks. Verify the exact client and retry behavior.
- If pre-resolving and pinning manually, validate all candidate A/AAAA answers, connect to
  an approved address, and preserve the original hostname for the HTTP `Host` header and
  TLS SNI/certificate verification. Replacing the URL hostname with an IP without doing so
  can break virtual hosting or tempt code to disable certificate verification.
- Reused keep-alive sockets do not perform another lookup; ensure they were created through
  the validated connection path. Apply the same validation to each new connection/retry.

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
- [Node.js HTTP `lookup` option](https://nodejs.org/api/http.html#httprequestoptions-callback)
- [Node.js TLS `servername` option](https://nodejs.org/api/tls.html#tlsconnectoptions-callback)
