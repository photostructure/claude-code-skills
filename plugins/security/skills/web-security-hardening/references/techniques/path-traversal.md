<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# Path traversal decoding & containment

Serving a request-derived filename safely requires decoding first, then canonicalizing,
then a segment-aware containment check. Order matters: each step defeats a different bypass.

## Decode before you canonicalize

Containment checked against a still-encoded string is bypassable — `%2e%2e%2f`,
double-encoded `%252e`, overlong UTF-8, and null bytes all pass a naive `includes('../')`
denylist and only become `../` after the platform decodes them downstream.

- Anti-pattern: `if (name.includes('..')) reject()` / `path.join(base, req.query.file)`
  applied to a raw or single-pass value; a denylist scan run before any decode.
- Fix: fully URL-decode the untrusted segment before comparing (`decodeURIComponent`),
  and reject rather than re-loop if the value still contains a `%` after one decode
  (defeats double-encoding like `%252e`) — do not silently decode repeatedly.
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
  `const rel = path.relative(base, target)` to be non-empty and **not** start with `..`
  and **not** be absolute (`!rel.startsWith('..') && !path.isAbsolute(rel)`). Equivalently,
  compare against `base + path.sep`. `path.resolve` normalizes away `..`/`.` and
  `path.relative` yields a `../`-leading string precisely when `target` escapes `base`.
- This is a lexical check. It does not stop symlink or TOCTOU escapes where an attacker
  controls intermediate directories — pair with `O_NOFOLLOW`/`fs.realpath` and
  least-privilege modes (see ../deployment-and-operations.md). Verify `path.relative`/
  `path.resolve` semantics against your installed Node version.

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
