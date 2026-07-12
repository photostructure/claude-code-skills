<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# XSS Sinks and Sanitizers

Recognize raw-HTML sinks in code, then neutralize them with a maintained sanitizer and correct per-context encoding.

## Sanitizer of record

- Use a maintained, actively patched sanitizer for user-authored HTML/SVG. DOMPurify is the
  common choice; do not hand-roll regex/denylist "sanitizers" (`replace(/<script>/…)`),
  which are bypassable and are not a primary control.
- In Node/SSR, DOMPurify requires a DOM implementation such as a current supported jsdom;
  follow DOMPurify's server-side setup and version guidance. The sanitizer need not use the
  browser page's identical `window`, but security depends on the sanitizer/DOM combination
  parsing the content as expected and on not mutating sanitized markup afterward.
- Sanitize on the **server** when multiple clients consume the same rich content; keep
  client-side sanitization as an additional boundary immediately before DOM insertion.
- Where Trusted Types are enforced, integrate DOMPurify according to the policy design.
  Direct sanitization can request `TrustedHTML` with `RETURN_TRUSTED_TYPE: true`; inside a
  `trustedTypes.createPolicy(...).createHTML` callback DOMPurify documents using `false`
  because the callback must return a string.

## Worked fix (React)

Grep target: `dangerouslySetInnerHTML={{ __html: <untrusted> }}` with no sanitize call on
the value. Fix — sanitize the value first, then pass only the clean result:

```jsx
const clean = DOMPurify.sanitize(dirty);
<div dangerouslySetInnerHTML={{ __html: clean }} />
```

## Per-framework raw sinks

Each of these bypasses the framework's automatic escaping. Treat any of them fed
request/DB/user data as a finding; fix by feeding sanitizer output (or trusted static
content) instead of raw values.

- React: `dangerouslySetInnerHTML={{ __html: … }}` — sanitize the `__html` value.
- Vue: `v-html="…"` — sanitize the bound value; prefer `{{ }}` (text-escaped) where possible.
- Angular: `[innerHTML]="…"` is **auto-sanitized** by Angular's built-in sanitizer, so the
  real finding is a `DomSanitizer.bypassSecurityTrust*` call on untrusted data —
  `bypassSecurityTrustHtml`, `bypassSecurityTrustScript`, `bypassSecurityTrustStyle`,
  `bypassSecurityTrustUrl`, `bypassSecurityTrustResourceUrl`. Remove the bypass; if a trust
  wrapper is genuinely required, validate/sanitize for that exact HTML/URL/resource context
  before marking the value trusted. Verify behavior for the installed Angular binding.
- EJS: `<%- … %>` (raw) vs. `<%= … %>` (escaped) — sanitize raw output.
- Handlebars: `{{{ … }}}` (triple-brace, unescaped) vs. `{{ … }}` — sanitize triple-brace.
- Pug: `!= …` (unescaped) vs. `= …` (escaped) — sanitize unescaped interpolation.

## Contexts auto-escaping does not cover

- Do not summarize every framework as “HTML text only.” React, Vue, Angular, and template
  engines have different property/attribute escaping and URL sanitization behavior. Verify
  the installed framework and exact binding. Still apply context-specific controls:
  allowlist URL schemes, avoid building script/style source from data, and avoid DOM sinks
  (`innerHTML`, `insertAdjacentHTML`, `document.write`, `eval`) fed untrusted input.
- CSP is **defense-in-depth, not a fix for the sink**. Do not mark a raw-HTML sink resolved
  because a Content-Security-Policy exists — fix the sink and keep CSP as a second layer.

See ../input-output-and-files.md for output-context encoding and ../../ATTRIBUTION.md.

## Primary sources

- [DOMPurify README](https://github.com/cure53/DOMPurify)
- [OWASP XSS Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html)
- [OWASP DOM-based XSS Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/DOM_based_XSS_Prevention_Cheat_Sheet.html)
- [Angular Security guide](https://angular.dev/best-practices/security)
- [Vue Security guide](https://vuejs.org/guide/best-practices/security.html)
- [React DOM: dangerouslySetInnerHTML](https://react.dev/reference/react-dom/components/common)
