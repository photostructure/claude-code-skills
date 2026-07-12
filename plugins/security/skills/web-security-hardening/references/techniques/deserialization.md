<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# Unsafe deserialization (Node)

Reviving objects from untrusted bytes with an eval-capable library or a function/prototype-restoring
reviver is arbitrary code execution, not parsing. Keep untrusted input as inert data.

## Dangerous libraries that revive functions

- Anti-pattern: an import of `node-serialize`, `serialize-to-js`, `funcster`, or `cryo`, then
  `unserialize(...)` / `deserialize(...)` called on a request-derived value (body, cookie, query,
  header, queue message). `node-serialize.unserialize` is CVE-2017-5941: any property whose string
  value begins with the marker `_$$ND_FUNC$$_` is passed to `eval`, and an appended IIFE (`}()`)
  runs on deserialize. `funcster` revives functions similarly (marker `__js_function`). `cryo`
  differs: it restores object prototypes, and RCE fires when a gadget method (`toString`/`valueOf`)
  is later called on the restored object, not on deserialize itself.
- Greppable payload marker: `_$$ND_FUNC$$_` in stored/logged/transmitted values — treat its presence
  as an active exploit attempt, not a benign string.
- Fix: remove these libraries from any untrusted path. Transfer plain data as JSON and reconstruct
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
- [OpsecX — Exploiting Node.js deserialization bug for Remote Code Execution](https://opsecx.com/index.php/2017/02/08/exploiting-node-js-deserialization-bug-for-remote-code-execution/)
