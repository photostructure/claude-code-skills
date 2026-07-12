<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# Open Redirect

Attacker-controlled redirect/forward targets that send authenticated users to an external
origin (phishing, token/OAuth-code theft, filter evasion).

## Anti-patterns to grep

- Any sink that navigates to request-derived data: `res.redirect(req.query...)`,
  `res.redirect(req.body.returnTo)`, `res.location(...)`, `window.location =`,
  `location.assign/replace`, `next`/`returnTo`/`redirect_uri`/`continue`/`url`/`dest`
  parameters flowing into a redirect.
- Prefix/substring "validation" instead of parsing: `startsWith('/')`,
  `startsWith('https://mysite.com')`, `!url.includes('//')`, `endsWith('mysite.com')`,
  regexes anchored on the raw string. All are bypassable and are not primary controls.

## Backslash and slash normalization bypass

- A check that only rejects protocol-relative `//host` still lets `/\evil.com`,
  `\/\/evil.com`, `/\/evil.com`, and `https:/\evil.com` escape the origin. Per the WHATWG
  URL Standard, for special schemes (`http`/`https`/`ws`/`wss`/`ftp`/`file`) a backslash
  is handled the same as a forward slash in the authority-slashes and path-start states;
  the mismatch only records an `invalid-reverse-solidus` **validation error**, which the
  spec defines as **non-fatal** — parsing continues and `\` becomes `/`. So `/\evil.com`
  resolves to authority `evil.com`.
- Do not grow a separator denylist. WHATWG parsing trims or ignores certain leading
  controls, while percent-encoded separators normally remain path data unless another
  component decodes them. Define one parser/decoding boundary and redirect using the
  validated parsed result so a downstream parser cannot reinterpret the raw candidate.
- Verify normalization against the installed runtime: browsers, Node's WHATWG `URL`, and
  the legacy `url.parse()` differ. `url.parse()` is deprecated (legacy API) and normalizes
  differently from `new URL()`; use the WHATWG `URL` parser and confirm behavior on the
  version you ship.

## Safe construction

- Resolve the candidate against the app's own origin and compare parsed origins — never
  string-inspect the raw input:
  `const u = new URL(candidate, appOrigin); if (u.origin !== appOrigin) reject();`
  Passing `appOrigin` as the base makes a genuine relative path (`/dashboard`) resolve to
  your origin while `//evil.com`, `/\evil.com`, `https://evil.com`, and
  `https://mysite.com.evil.com` all resolve to a different `origin` and are rejected.
- After validation, pass the canonical parsed URL (or its validated relative path) to the
  redirect API—not the original raw string—so validation and navigation use one parse.
- Compare `.origin` (scheme+host+port), not `.hostname` alone (misses scheme downgrade and
  port), and not `.host` as a substring. Reject credential-bearing (`user:pass@`) and
  non-`http(s)` schemes (`javascript:`, `data:`) explicitly.

## Prefer mapping or a relative-path allowlist

- Best: have the client send a short identifier/token that the server maps to a known-good
  URL (`{ home: '/', invoice: '/invoices' }[key]`). The raw URL never leaves the server, so
  there is nothing to tamper with (OWASP's highest-protection recommendation).
- Otherwise enforce a strict same-origin **relative-path** allowlist: require the value to
  begin with a single `/` (not `//` or `/\`), reject after normalization, and prepend your
  own origin. Do not maintain an allowlist of external hosts unless the feature genuinely
  requires off-site redirects.
- For OAuth authorization requests, follow the current OAuth security BCP: match
  `redirect_uri` against pre-registered values using exact string comparison (subject to
  the narrow native-app rules). If application `state` data contains a post-login return
  target, authenticate/bind the state and validate that target separately; `state` is not
  itself a redirect-URI registration mechanism.

See ../input-output-and-files.md (URLs, redirects, and outbound requests) and
../../ATTRIBUTION.md.

## Primary sources

- [OWASP Unvalidated Redirects and Forwards Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Unvalidated_Redirects_and_Forwards_Cheat_Sheet.html)
- [WHATWG URL Standard](https://url.spec.whatwg.org/)
- [RFC 9700 — OAuth 2.0 Security Best Current Practice](https://www.rfc-editor.org/rfc/rfc9700.html)
