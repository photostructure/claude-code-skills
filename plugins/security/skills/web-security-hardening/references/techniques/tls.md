<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# TLS for Self-Terminating Origins

Hardening for Node processes that terminate TLS themselves, plus the page-level and
client-side rules that survive TLS delegation to a managed edge.

## Contents

- [TLS floor and cipher config](#tls-floor-and-cipher-config)
- [Mixed content](#mixed-content)
- [Verification and HSTS](#verification-and-hsts)

## TLS floor and cipher config

When a Node process terminates TLS (`https.createServer`, `tls.createServer`,
`http2.createSecureServer`, or a `tls.createSecureContext`), pin a modern floor and a
vetted cipher set:

- Anti-pattern: `minVersion` absent, or `secureProtocol: 'TLSv1_method'`/`'TLSv1_1_method'`/
  `'SSLv3_method'`, or `minVersion: 'TLSv1'`/`'TLSv1.1'`, or a `secureOptions` bitmask that
  re-enables old protocols. Fix: set `minVersion: 'TLSv1.2'` (prefer `'TLSv1.3'` where the
  client base allows) and never lower `maxVersion` below it. RFC 8996 deprecates TLS 1.0/1.1;
  SSLv2/SSLv3 must always be off.
- Anti-pattern: hand-rolled `ciphers` string containing `RC4`, `3DES`/`DES-CBC3`, `EXPORT`,
  `NULL`, `aNULL`, or `@SECLEVEL=0`. Fix: adopt a platform-recommended list — take the
  cipher list from the Mozilla SSL Configuration Generator (intermediate profile for broad
  reach, modern for TLS 1.3-only; the generator does not emit a Node.js profile, so apply the
  recommended list via the `ciphers`/`minVersion` options yourself), preferring AEAD suites
  (AES-GCM, ChaCha20-Poly1305) and forward-secret key exchange. In Node, the legacy cipher
  specification format in `ciphers` applies only to TLS 1.2 and below; TLS 1.3 offers a small
  fixed set of suites defined by the protocol, selectable only by their full `TLS_...` names
  in the same `ciphers` list — verify the exact behavior against the installed Node/OpenSSL
  version.
- Node's default `minVersion` (`tls.DEFAULT_MIN_VERSION`) and default `ciphers`
  (`tls.DEFAULT_CIPHERS`) track a sane baseline in current releases, but both are
  version-sensitive — verify the exact default against the installed Node version rather than
  assuming it, and set `minVersion` explicitly so the floor does not drift with the runtime.
- Delegating termination to a managed edge (ALB/CloudFront/nginx/Cloudflare) is a legitimate
  fix — but then say so: the origin app carries no TLS floor, so record where termination
  happens and that the edge enforces the version/cipher policy, and confirm the origin hop is
  not plaintext on an untrusted network.

## Mixed content

An HTTPS page must load every subresource over HTTPS:

- Anti-pattern: `http://` in `<script src>`, `<link href>`, `fetch()`/`XMLHttpRequest` URLs,
  `<img>`/`<iframe>`/`<video>` sources, CSS `url(...)`, or web-font/`WebSocket` (`ws://`) URLs
  emitted by templates or built assets. Browsers block active mixed content (scripts, XHR,
  frames) and may block or upgrade passive content, so the page breaks or silently degrades.
- Fix: emit protocol-relative-free absolute HTTPS URLs or same-origin relative paths; derive
  public base URLs from trusted deployment config, not request headers. As a backstop, ship a
  `Content-Security-Policy: upgrade-insecure-requests` directive — but fix the emitting code;
  the header is defense-in-depth, not the primary control. See ../browser-and-http.md.

## Verification and HSTS

- Anti-pattern: `rejectUnauthorized: false` on any outbound `https`/`tls`/`fetch` client, a
  custom `checkServerIdentity` that returns without throwing, or the process-wide
  `NODE_TLS_REJECT_UNAUTHORIZED=0`. This disables certificate/hostname verification and makes
  every outbound TLS call MITM-able. Fix: keep verification on; for a genuinely private CA,
  pass that CA via the `ca` option (or `NODE_EXTRA_CA_CERTS`) instead of disabling checks.
  Never globally disable verification to silence a cert error.
- Anti-pattern: `Strict-Transport-Security` sent (especially with `includeSubDomains`/
  `preload`) before HTTPS is reliable on the apex and all subdomains. HSTS is a commitment —
  premature `preload` can hard-break hosts that still need HTTP. Fix: enable HSTS only after
  TLS serves all pages reliably; roll out with a short `max-age` first, then raise it and add
  `preload`. See ../browser-and-http.md for the header details.

## Primary sources

- [OWASP Transport Layer Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Transport_Layer_Security_Cheat_Sheet.html)
- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/)
- [Node.js TLS/SSL documentation](https://nodejs.org/api/tls.html)
