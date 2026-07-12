<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# Prototype Pollution

Attacker-controlled keys (`__proto__`, `constructor`, `prototype`) that mutate `Object.prototype`
during recursive merge, assignment-by-path, or key-parsing, poisoning every object at runtime.

## Safe structures

- Anti-pattern: accumulator objects built as `{}` or `Object.assign({}, req.body)` that then
  receive attacker-controlled keys, plus code that reads inherited config via `obj[key]`.
- Fix: hold untrusted-keyed maps in `new Map()`/`new Set()`, or when a plain object is required
  build it with `Object.create(null)` (or the `{ __proto__: null }` literal) so there is no
  prototype to pollute. Access with `Map.get`/`Object.hasOwn`, not bracket lookups that walk the chain.
- Backstop: `Object.freeze(Object.prototype)` (and `Object.prototype.constructor`) blocks writes
  process-wide. This is defense-in-depth, not a primary control — it throws or silently no-ops when
  a dependency legitimately extends built-in prototypes, so verify your dependency tree tolerates it.

## Reject dangerous keys at every level

- Anti-pattern: a guard that only checks top-level request keys (`if (key in req.body)`), or a
  recursive merge/`set(obj, path, val)` that never inspects the key it is about to assign. Nested
  payloads like `{"a":{"__proto__":{"polluted":1}}}` and dotted paths `a.__proto__.polluted` slip past.
- Fix: reject or skip `__proto__`, `constructor`, and `prototype` inside the recursion/loop itself —
  at each key and each path segment, not just the root. Use `Object.hasOwn(obj, key)` to iterate own
  properties and validate keys against an allowlist before writing.

## Classic vulnerable sinks

- Anti-pattern (grep): `_.merge`, `_.mergeWith`, `_.defaultsDeep`, `_.set`, `_.setWith`,
  `_.zipObjectDeep`, `_.unset`, `_.omit`, and `qs.parse` / Express `extended` query parsing fed
  request data. Historical CVEs: lodash `defaultsDeep` (CVE-2019-10744, fixed 4.17.12),
  `merge`/`mergeWith`/`defaultsDeep` (CVE-2018-16487, fixed 4.17.11), `set`/`setWith`/`zipObjectDeep`
  (CVE-2020-8203, fixed 4.17.19 per the GitHub advisory), and `unset`/`omit` path deletion
  (CVE-2025-13465, CVE-2026-2950) — verify the installed version against each advisory, not the name.
- Fix: keep these libraries patched (`npm audit`) — note 4.17.21 is *not* a safe floor: CVE-2025-13465
  and CVE-2026-2950 affect it, so pin to the version named in the current advisory. Do not deep-merge or
  path-assign untrusted objects at all — map request DTOs to explicit fields (see
  ../input-output-and-files.md, "Structured input and assignment"). If a deep merge is unavoidable,
  gate it behind the per-level key rejection above.

## Drop `__proto__` during JSON ingestion

- Anti-pattern: `JSON.parse(body)` (or a body-parser feeding merge/assignment) with no reviver, so a
  literal `"__proto__"` key survives into a downstream sink.
- Fix: pass a reviver to `JSON.parse` that deletes/rejects `__proto__` (and `constructor`/`prototype`)
  keys before they reach any object graph, or parse into null-prototype objects. As a runtime backstop,
  start Node with `--disable-proto=delete` (or `=throw`, `ERR_PROTO_ACCESS`) to remove the
  `Object.prototype.__proto__` accessor — added in Node v13.12.0 / v12.17.0, so verify the flag exists
  in your runtime. Note it does not stop `constructor.prototype` pollution; it is defense-in-depth only.

## Primary sources

- [OWASP Prototype Pollution Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Prototype_Pollution_Prevention_Cheat_Sheet.html)
- [Node.js CLI documentation — `--disable-proto`](https://nodejs.org/api/cli.html#--disable-protomode)
- [lodash security advisories (GitHub / npm audit; CVE-2019-10744, CVE-2018-16487, CVE-2020-8203, CVE-2025-13465, CVE-2026-2950)](https://github.com/lodash/lodash/security)
