<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# Prototype Pollution

Attacker-controlled keys (`__proto__`, `constructor`, `prototype`) can alter a target's
prototype—or, through vulnerable recursive/path assignment, `Object.prototype`—and change
security-relevant defaults elsewhere in the process.

## Safe structures

- Anti-pattern: accumulator objects built as `{}` or `Object.assign({}, req.body)` that then
  receive attacker-controlled keys, plus code that reads inherited config via `obj[key]`.
- Fix: hold untrusted-keyed maps in `new Map()`/`new Set()`, or when a plain object is required
  build it with `Object.create(null)` (or the `{ __proto__: null }` literal) so there is no
  prototype to pollute. Access with `Map.get`/`Object.hasOwn`, not bracket lookups that walk the chain.
- Backstop: `Object.freeze(Object.prototype)` blocks writes
  process-wide. This is defense-in-depth, not a primary control — it throws or silently no-ops when
  a dependency legitimately extends built-in prototypes, so verify your dependency tree tolerates it.

## Reject dangerous keys at every level

- Anti-pattern: a guard that only checks top-level request keys (`if (key in req.body)`), or a
  recursive merge/`set(obj, path, val)` that never inspects the key it is about to assign. Nested
  payloads like `{"a":{"__proto__":{"polluted":1}}}` and dotted paths `a.__proto__.polluted` slip past.
- Fix: reject `__proto__`, `constructor`, and `prototype` at every segment before a generic
  recursive merge/path assignment. For an explicit schema that legitimately contains such
  a name, map it without a generic path setter. Use `Object.hasOwn` and an allowlist before writing.

## Classic vulnerable sinks

- Review uses of `_.merge`, `_.mergeWith`, `_.defaultsDeep`, `_.set`, `_.setWith`,
  `_.zipObjectDeep`, `_.unset`, `_.omit`, and `qs.parse` / Express `extended` query parsing fed
  request data. These APIs have had multiple prototype-pollution advisories; determine
  exposure from the exact function and installed version using the package's current
  advisory record rather than copying a single “safe floor.”
- Keep dependencies patched, but do not rely on version alone. Avoid deep-merging or
  path-assigning untrusted objects; map request DTOs to explicit fields (see
  ../input-output-and-files.md, "Structured input and assignment"). If a deep merge is unavoidable,
  gate it behind the per-level key rejection above.

## Drop `__proto__` during JSON ingestion

- Anti-pattern: parsed JSON passed to merge/path-assignment without schema/key validation;
  `JSON.parse` preserves a literal own `"__proto__"` data property, which becomes dangerous
  only when a later sink interprets it.
- Fix: validate parsed objects against an allowlisted schema before any merge/assignment.
  Where arbitrary keys are not part of the contract, a `JSON.parse` reviver may reject
  dangerous keys at every depth; do not globally reject legitimate `constructor` or
  `prototype` data without considering the schema. As a runtime backstop,
  start Node with `--disable-proto=delete` (or `=throw`, `ERR_PROTO_ACCESS`) to remove the
  `Object.prototype.__proto__` accessor — added in Node v13.12.0 / v12.17.0, so verify the flag exists
  in your runtime. Note it does not stop `constructor.prototype` pollution; it is defense-in-depth only.

## Primary sources

- [OWASP Prototype Pollution Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Prototype_Pollution_Prevention_Cheat_Sheet.html)
- [Node.js CLI documentation — `--disable-proto`](https://nodejs.org/api/cli.html#--disable-protomode)
- [GitHub Advisory Database — lodash](https://github.com/advisories?query=ecosystem%3Anpm+affects%3Alodash)
