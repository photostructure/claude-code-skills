<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# Unsafe deserialization (Node)

Reviving objects from untrusted bytes with an eval-capable library or a function/prototype-restoring
reviver is arbitrary code execution, not parsing. Keep untrusted input as inert data.

## Dangerous libraries that revive functions

- Confirmed anti-pattern: `node-serialize` `unserialize(...)` on attacker-controlled input.
  GHSA-q4v7-4rhw-9hqm / CVE-2017-5941 affects all published versions through 0.0.4 and has
  no patched release; an immediately invoked serialized function can execute code. Review
  any other function/prototype-restoring package from its pinned source and advisories
  rather than inferring identical marker or gadget behavior from the word “deserialize.”
- Greppable indicator: `_$$ND_FUNC$$_` in values that reach `node-serialize` deserves
  investigation and rejection. The marker in unrelated text is not by itself proof of an
  exploit attempt; confirm the data flow.
- Fix: remove eval/function-restoring libraries from any untrusted path. Transfer plain data as JSON and reconstruct
  behavior server-side from an allowlist (below). If a legitimate internal use exists, gate it behind
  an authenticity check (signed/MAC'd payload from a trusted producer) and document the trust boundary.
- Verify against the installed version: confirm which function names the package exposes and whether a
  given version still evals the marker before marking anything Met — do not assume an "unserialize"
  helper is safe because it is renamed.

## Data-only parsing is the safe default

- Anti-pattern: passing a second argument (reviver) to `JSON.parse(text, reviver)` that reconstructs
  functions, class instances, or prototypes from type tags in the data; or any custom "revive"/"hydrate"
  step driven by an attacker-supplied `type`/`$type`/`__class__` field.
- Fix: parse untrusted input with plain `JSON.parse(text)` and no reviver, then validate the resulting
  plain object against a runtime schema (see ../input-output-and-files.md, "Runtime schemas") before use.
  A reviver, if used at all, must only transform scalar values (e.g. ISO strings to `Date`) and never
  resolve a name into a callable or a prototype.
- Reject `__proto__` / `constructor` / `prototype` keys before any merge or assignment onto the parsed
  object (prototype pollution — see ../input-output-and-files.md, "Structured input and assignment").

## Safe class rehydration = validate-then-construct

- Anti-pattern: turning parsed data back into a typed instance via `eval`, `new Function(...)`,
  `Object.assign(new Target(), data)`, `Object.setPrototypeOf(data, ...)`, or a dynamic
  `registry[data.type]` lookup where `type` is attacker-controlled and unvalidated. Blind
  `Object.assign` onto a prototype-bearing target also carries injected `__proto__`/getters.
- Fix: dispatch through an explicit allowlist. Map a validated discriminator to a known factory, then
  construct from validated fields only:
  a `switch`/`Map` of permitted type names → constructor, each copying an explicit field list after
  schema validation. Never derive the constructor or a property name directly from the payload, and
  never funnel payload text through `eval`/`Function`/`vm`.
- Verify against the installed version: ORM/ODM and class-transformer style libraries may auto-instantiate
  classes or run setters during hydration. Confirm the installed version's instantiation behavior and
  whether it exposes an unsafe "raw"/"excludeExtraneous" toggle before relying on it.

## Primary sources

- [OWASP Deserialization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Deserialization_Cheat_Sheet.html)
- [NVD — CVE-2017-5941 (node-serialize unserialize RCE)](https://nvd.nist.gov/vuln/detail/CVE-2017-5941)
- [GitHub Advisory GHSA-q4v7-4rhw-9hqm](https://github.com/advisories/GHSA-q4v7-4rhw-9hqm)
