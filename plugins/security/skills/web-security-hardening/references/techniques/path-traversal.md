<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# Path traversal decoding & containment

Serving a request-derived filename safely requires decoding first, then canonicalizing,
then a segment-aware containment check. Order matters: each step defeats a different bypass.

## Decode before you canonicalize

Containment checked before a later decoding step is bypassable: an encoded separator can
become traversal after the check. Define one canonical decoding boundary and ensure no
downstream component decodes the path again.

- Anti-pattern: `if (name.includes('..')) reject()` / `path.join(base, req.query.file)`
  applied to a raw or single-pass value; a denylist scan run before any decode.
- If the handler receives a raw URL component, decode it exactly once with the protocol-
  appropriate decoder and reject malformed encoding. Do **not** reject every remaining `%`:
  it may be legitimate data. Instead, prevent a second decode downstream. If a router has
  already decoded the value, do not call `decodeURIComponent` again.
- Reject null bytes explicitly (`name.includes('\0')`). Node `fs`/`path` calls throw on a
  poison-null-byte path (`ERR_INVALID_ARG_VALUE`), but reject at the boundary so the value
  never reaches a sink — verify the throw behavior against your installed Node version.
- Denylist string filters for `../` are a bypassable secondary control, never the primary
  one (see ../input-output-and-files.md). Prefer indexed/allowlisted identifiers that map
  to server-side paths when the design allows it.

## Resolve, then enforce segment-aware containment

Once decoded, canonicalize and verify the target stays inside the base by path segments —
not by string prefix. A prefix test (`resolved.startsWith(base)`) lets a sibling like
`/srv/data-evil` pass containment for base `/srv/data`.

- Anti-pattern: `resolved.startsWith(baseDir)` without a trailing separator; comparing
  before `path.resolve`; trusting `path.isAbsolute` alone (docs: "not safe for mitigating
  path traversals").
- Fix: `const target = path.resolve(base, candidate)` then require
  `const rel = path.relative(base, target)` and reject when `rel === '..'`,
  `rel.startsWith('..' + path.sep)`, or `path.isAbsolute(rel)`. An empty `rel` means the
  target equals the base; allow or reject that according to whether the operation may use
  the directory itself. Do not use `rel.startsWith('..')`, which also rejects a valid name
  such as `..notes`.
- This is a lexical check. It does not stop symlink or TOCTOU escapes where an attacker
  controls directories. `O_NOFOLLOW` commonly protects only the final path component;
  `realpath` followed by a later open can race. Prefer an OS/runtime facility that resolves
  relative to an already-open directory while forbidding symlinks beneath it, where
  available; otherwise remove attacker write access to path components and apply least
  privilege. Verify platform and Node support rather than presenting `O_NOFOLLOW` plus
  `realpath` as a complete generic fix.

## Framework decoding is already done for you

- Express populates `req.params` and `req.query` with values already URL-decoded to
  literal `../` before your handler runs — do not assume the raw wire encoding survives,
  and do not "decode again" expecting to catch encoded payloads. Canonicalize + contain
  the literal value. Confirm decoding behavior against your installed Express/router
  version; matched-param decoding has changed across major versions.
- The same applies to any router that pre-decodes: treat the handler-visible value as the
  post-decode literal and run resolve + `path.relative` containment on it.

## Primary sources

- [OWASP Path Traversal](https://owasp.org/www-community/attacks/Path_Traversal)
- [OWASP Input Validation Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html)
- [Node.js path module](https://nodejs.org/api/path.html)
- [Linux `openat2(2)` — `RESOLVE_BENEATH` / `RESOLVE_NO_SYMLINKS`](https://man7.org/linux/man-pages/man2/openat2.2.html)
