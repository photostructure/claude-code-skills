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
  (`\s+.*$`, `.*.*=.*`). A run of matching characters followed by one non-matching
  character forces exponential path exploration.
- Fix: rewrite to remove ambiguity — make inner quantifiers possessive/atomic where the
  engine supports it, replace overlapping alternatives with a single character class,
  and anchor both ends so the engine cannot re-seed the match. Add a unit test that feeds
  a long adversarial string (e.g. `"a".repeat(50_000) + "!"`) and asserts the match
  returns promptly. Node's built-in `RegExp` has no per-match timeout — verify against
  the installed Node version rather than assuming one exists.

## Bound the input and the engine

- Anti-pattern: matching an unbounded body/query/header value directly, e.g.
  `pattern.test(req.body.field)` or `str.match(userPattern)` with no length guard.
- Fix: cap length before matching (reject or truncate to a documented maximum via schema
  `maxLength`) so worst-case work stays bounded. For any attacker-influenced pattern or
  input, run it on a linear-time engine: `node-re2` (`import { RE2 } from "re2"`, or
  `const RE2 = require("re2")`) is a drop-in for the `RegExp` API
  (`test`/`exec`/`match`/`replace`) and cannot backtrack. RE2 rejects features that need
  exponential time — backreferences (`\1`) and lookaround (`(?=)`, `(?!)`) — and throws
  `SyntaxError` on them. Standard Unicode property escapes (`\p{...}`) are supported; only
  the `v`-flag "properties of strings" (e.g. `\p{Basic_Emoji}`) are not. Verify your
  patterns compile under the installed `re2` version and keep a native `RegExp` fallback
  only for trusted, backtracking-free patterns.

## Never compile untrusted patterns; audit dependencies

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
