<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# Regular-expression DoS (ReDoS)

A single attacker-influenced string matched against a backtracking regex can pin a CPU
core and stall the Node event loop. Treat every regex over untrusted input as a
resource-consumption surface. See also `../input-output-and-files.md` (parsers and
deserialization) and `../deployment-and-operations.md` (timeouts, resource limits).

## Catastrophic backtracking

- Anti-pattern: nested or overlapping quantifiers, especially anchored to `$`. Grep
  literals and dynamic `new RegExp(...)` for a repetition inside a repeated group
  (`(a+)+`, `(a*)*`, `([a-zA-Z]+)*`, `(.*a){10,}`), overlapping alternation under a
  quantifier (`(a|aa)+`, `(a|a?)+`, `(\d+|\w+)*`), and adjacent unbounded quantifiers
  (`\s+.*$`, `.*.*=.*`). Depending on the expression, a near-match can cause polynomial
  or exponential backtracking; confirm with analysis rather than classifying every example
  as exponential.
- Fix: rewrite to remove ambiguity — make inner quantifiers possessive/atomic where the
  engine supports it, replace overlapping alternatives with a single character class,
  and anchor both ends where full-string matching is intended. Test suspected expressions
  in an isolated worker/process with a strict external timeout and gradually increasing
  input; do not paste a potentially catastrophic 50,000-character case into the main test
  process. Node's built-in `RegExp` has no per-match timeout — verify against
  the installed Node version rather than assuming one exists.

## Bound the input and the engine

- Anti-pattern: matching an unbounded body/query/header value directly, e.g.
  `pattern.test(req.body.field)` or `str.match(userPattern)` with no length guard.
- Fix: cap length before matching (reject or truncate to a documented maximum via schema
  `maxLength`) so worst-case work stays bounded. When the pattern is attacker-controlled or
  analysis cannot establish an acceptable bound, use a linear-time engine such as `node-re2`
  (`const RE2 = require("re2")`); it exposes a RegExp-like API backed by RE2's linear-time
  engine. The named ESM export requires `re2` 1.24.0 or newer, so version-gate that import.
  RE2 is not fully syntax- or behavior-compatible with JavaScript `RegExp` and rejects
  features such as backreferences and lookaround. Compile and behavior-test every migrated
  pattern against the installed binding; do not silently fall back to native `RegExp` for
  attacker-controlled patterns.

## Keep untrusted patterns out of backtracking engines; audit dependencies

- Anti-pattern: `new RegExp(userInput)` or `new RegExp(\`^${userInput}$\`)` — the user
  controls the program the engine runs, so they can supply their own evil regex. Also
  flag search/filter features that pass raw input into a query engine's regex operator.
- Fix: do not build a `RegExp` from unescaped user input. If a substring must be matched
  literally, escape metacharacters first (`RegExp.escape` is built in since Node 24 /
  V8 13.6 — verify against the installed version, and on older runtimes use a maintained
  polyfill such as `core-js` or `es-shims`) or use plain-string operations
  (`String.includes`/`indexOf`) instead. Compile against a
  linear-time engine when a user-supplied pattern is genuinely required.
- Anti-pattern: pulling in a dependency with a known-vulnerable regex (validators,
  parsers, slugifiers, `marked`/markdown, `moment`, path-to-regexp, etc.).
- Fix: run `npm audit` / your SCA tool and triage ReDoS advisories; upgrade or replace
  the offending package. Confirm the fix version in the advisory against your installed
  lockfile — do not assume `latest` is patched.

## Primary sources

- [OWASP: Regular expression Denial of Service (ReDoS)](https://owasp.org/www-community/attacks/Regular_expression_Denial_of_Service_-_ReDoS)
- [MDN: Regular expressions](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Regular_expressions)
- [node-re2 (RE2 bindings for Node.js)](https://github.com/uhop/node-re2)
