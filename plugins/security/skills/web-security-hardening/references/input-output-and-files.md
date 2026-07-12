<!-- OWASP-derived guidance. CC BY-SA 4.0. See ../ATTRIBUTION.md. -->

# Input, Output, and File Handling

## Contents

- [Trust boundaries](#trust-boundaries)
- [Runtime schemas](#runtime-schemas)
- [Validation, encoding, and sanitization](#validation-encoding-and-sanitization)
- [Structured input and assignment](#structured-input-and-assignment)
- [Output contexts](#output-contexts)
- [Database, command, and template boundaries](#database-command-and-template-boundaries)
- [URLs, redirects, and outbound requests](#urls-redirects-and-outbound-requests)
- [Paths and files](#paths-and-files)
- [Uploads and downloads](#uploads-and-downloads)
- [Parsers and deserialization](#parsers-and-deserialization)

> **Technique cards** (concrete Node/JS anti-patterns and fixes; load per control):
> [`sql-injection`](./techniques/sql-injection.md), [`nosql-injection`](./techniques/nosql-injection.md),
> [`command-injection`](./techniques/command-injection.md), [`xss-sinks`](./techniques/xss-sinks.md),
> [`ssti`](./techniques/ssti.md), [`prototype-pollution`](./techniques/prototype-pollution.md),
> [`ssrf`](./techniques/ssrf.md), [`open-redirect`](./techniques/open-redirect.md),
> [`path-traversal`](./techniques/path-traversal.md), [`deserialization`](./techniques/deserialization.md),
> [`xxe-parsers`](./techniques/xxe-parsers.md), [`redos`](./techniques/redos.md),
> [`mass-assignment`](./techniques/mass-assignment.md).

## Trust boundaries

Inventory every external or lower-trust source, not only `req.body`:

- query/path/form/body values and duplicate parameters;
- headers, cookies, multipart metadata, filenames, and uploaded content;
- WebSocket messages, `postMessage`, URL fragments, and browser storage;
- webhooks, partner feeds, queues, imported files, and federated claims;
- database/cache values originally written by another user;
- environment/admin-config values that cross into executable or path contexts.

Validate as close as practical to the boundary and preserve a typed/normalized internal
representation afterward. Revalidate when data crosses a new trust boundary or changes
meaning; “already in the database” is not a security guarantee.

## Runtime schemas

TypeScript types disappear at runtime. For each externally callable operation:

- validate the complete request shape with a maintained runtime schema;
- reject unknown fields for privileged create/update operations unless explicitly
  supported;
- validate scalar vs. object/array distinctions before ORM/ODM filters;
- constrain string lengths, numeric ranges, collection sizes, enums, and dates;
- distinguish absent, null, empty, zero, and false according to business semantics;
- validate discriminated unions and nested objects completely;
- apply canonicalization once, before comparisons and authorization decisions;
- return stable, non-sensitive validation errors.

Client validation improves UX but never satisfies the server-side control. Generated
OpenAPI/GraphQL schemas count only when enforcement occurs on the receiving boundary.

## Validation, encoding, and sanitization

Use the right control for the job:

| Control | Purpose | Typical use |
| --- | --- | --- |
| **Syntactic validation** | Ensure data has the expected shape/format | UUID, date, enum, email syntax, scalar type |
| **Semantic validation** | Ensure values are allowed in business context | date order, quantity, ownership-compatible transition |
| **Output encoding** | Make data inert in a specific sink | HTML text/attribute, JavaScript, CSS, URL component |
| **Sanitization** | Remove unsafe active constructs while retaining permitted rich content | User-authored HTML/SVG under a strict policy |

Prefer allowlists for structured values. Denylist filters for strings such as `<script>`,
`../`, or `1=1` are bypassable and are not primary controls.

Do not mutate ordinary names, addresses, passwords, or prose with a generic sanitizer.
That corrupts data and still does not make it safe for every output context. Store the
intended canonical value; encode at each sink.

## Structured input and assignment

- Map request DTOs to explicit writable fields; do not spread or assign whole request
  objects into models with role, owner, tenant, billing, or workflow fields.
- Derive identity/tenant/owner fields from the authenticated server context.
- Collapse or reject HTTP parameter pollution according to route semantics.
- Validate object keys when they influence queries, sort/order identifiers, projections,
  merge targets, or prototype-bearing objects.
- Reject `__proto__`, `prototype`, and `constructor` keys before unsafe recursive merge;
  prefer libraries/data structures that do not traverse inherited properties.
- Treat GraphQL field selection, JSON Patch paths, and generic filter languages as
  capability surfaces with explicit allowlists and depth/shape bounds.

## Output contexts

Verify the final sink, including framework escape hatches:

- HTML text and normal framework interpolation should use automatic contextual escaping;
- HTML attributes, URLs, CSS, and JavaScript strings need their own context handling;
- avoid composing script/style blocks from data;
- raw HTML APIs (`dangerouslySetInnerHTML`, `v-html`, EJS `<%-`, Handlebars triple
  braces, Pug raw output, direct DOM `innerHTML`) require trusted static content or an
  allowlist sanitizer suitable for the runtime; account for framework sanitization such
  as Angular's normal `[innerHTML]` binding before reporting a gap;
- sanitize on the server when multiple clients consume rich content; client-side
  sanitization may remain an additional boundary before DOM insertion;
- do not mark a raw sink Met because CSP exists—fix the sink and keep CSP as defense-in-depth;
- JSON serialization is normally safe for JSON responses, but embedding JSON inside HTML
  or scripts needs safe serialization for that containing context.

For links and media, validate permitted schemes. Reject `javascript:` and other active
schemes where navigation/resource execution is possible.

## Database, command, and template boundaries

- Use bound/parameterized values for SQL and allowlist identifiers (table/column/sort
  direction) that cannot be bound. Keep values in each ORM/query builder's documented
  binding or escaping channel:
  bind through `knex.raw('?? = ?', [col, id])` (`?` value, `??` identifier), Prisma's
  tagged-template `$queryRaw` (never `$queryRawUnsafe`/`$executeRawUnsafe`), Sequelize
  `replacements`/`bind` (never interpolation into `literal`), or TypeORM query-builder
  `:name` parameters—never string-concatenate request data into them.
- For Mongo/document stores, validate request-derived equality values as scalars and
  construct allowlisted filters; never pass whole request objects as filters/stages.
- Normal Redis client arguments are binary-safe; focus on key authorization, dynamic
  command dispatch, manual RESP, and attacker-composed Lua/functions. Do not recommend
  SQL-style escaping for ordinary client arguments.
- LevelDB keys are not query syntax; focus on authorization namespaces, bounded range
  scans, unambiguous key encoding, destructive range operations, and dynamic filesystem
  locations.
- Use `execFile`/`spawn` with an argument array and `shell:false`; keep command names
  server-selected. Constrain user-derived arguments to the command's intended grammar.
  Guard against option injection with `--` only when that utility documents support for
  it; otherwise reject flag-like values or use a safer API.
- Keep template source server-controlled. Escaped interpolation is preferred; compiling
  attacker-authored templates is an execution boundary.

Mark parameterization/safe APIs Met only after tracing every dynamic fragment and the
installed library semantics.

## URLs, redirects, and outbound requests

- Parse URLs with a real URL parser and compare normalized scheme/host/port, not string
  prefixes or suffixes.
- For redirects, prefer server-side route identifiers or a same-origin relative-path
  policy; reject protocol-relative and credential-bearing URLs.
- For SSRF-prone features, allowlist required schemes/hosts, resolve and validate every
  target IP, and re-check redirects. Prevent a second, unchecked DNS resolution between
  validation and connection (for example by pinning the validated address where the
  client safely supports it) and use egress controls when practical. Account for DNS
  rebinding and IPv4/IPv6 forms.
- Derive public absolute URLs from trusted deployment config, not Host or forwarded
  headers, unless a correctly configured trusted proxy overwrites them.
- Keep webhook callback registration separate from invocation authorization and protect
  test-fire endpoints.

## Paths and files

- Keep base directories server-controlled and canonicalize the base and candidate.
- Use segment-aware containment (`path.relative` or equality/`base + path.sep`), not
  raw string-prefix checks.
- Generate server-side filenames; retain original names only as metadata after validation.
- Do not let request/config paths select databases, templates, modules, backups, or
  executable/plugin directories without an explicit allowlist.
- Apply least-privilege filesystem modes and prevent symlink/race escapes where an
  attacker can modify intermediate directories.
- Keep application data, secrets, databases, and backups outside static/web-served roots.

## Uploads and downloads

For uploads:

- allow only business-required types/extensions;
- validate content rather than trusting `Content-Type` or filename;
- generate a storage name and enforce filename/size/count limits;
- validate archive members, paths, nesting, and expanded size before extraction;
- store outside the webroot or behind an authorized download handler;
- set safe served `Content-Type` and `Content-Disposition`;
- authorize both upload and later read/delete/replace operations;
- consider malware scanning or content disarm for document workflows when the threat
  model and operations support it;
- isolate processing of complex formats and remove unnecessary metadata when required.

For downloads, prevent IDOR, path traversal, MIME confusion, inline execution, shared-
cache leakage, and disclosure through guessable object-storage URLs. Signed URLs need
short, purpose-appropriate expiry and should not be logged with their full signature.

## Parsers and deserialization

- Pin/inspect parser versions and disable executable/custom types for untrusted data.
- In js-yaml 4.x, `load()` excludes executable JavaScript tags by default; do not
  recommend `safeLoad()`, and verify the resolved release and advisories. In js-yaml
  5.x, `load()` defaults to `CORE_SCHEMA`. Check version-specific limits: 5.0/5.1 expose
  `maxDepth` and `maxMergeSeqLength`; 5.2+ exposes `maxDepth`, `maxTotalMergeKeys`, and
  `maxAliases`. In every version, investigate custom schemas/tags and known issues.
- Disable XML external entities/DTD processing unless explicitly required and safely
  constrained.
- Do not deserialize attacker data with eval-capable libraries or restore prototypes/
  functions from untrusted representations.
- Apply depth/size/entity limits as resilience controls; prioritize them according to
  actual exposure and the review's DoS scope.
- Treat regular expressions over untrusted input as a resource-consumption surface: avoid
  nested or overlapping quantifiers, cap input length before matching, and prefer a
  linear-time engine (for example RE2) for attacker-influenced patterns. Escape input
  that is meant to be literal. If accepting regex syntax is an intentional feature,
  constrain its syntax and execution rather than pretending escaping preserves that API.

## Primary sources

- [OWASP Input Validation Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html)
- [OWASP XSS Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html)
- [OWASP File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html)
- [OWASP SQL Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html)
- [OWASP SSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
- [OWASP Mass Assignment Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Mass_Assignment_Cheat_Sheet.html)
- [OWASP Deserialization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Deserialization_Cheat_Sheet.html)
- [Node.js child-process documentation](https://nodejs.org/api/child_process.html)
- [Knex raw parameter binding](https://knexjs.org/guide/raw.html#raw-parameter-binding)
- [Prisma raw database access](https://www.prisma.io/docs/orm/prisma-client/using-raw-sql/raw-queries)
- [Sequelize raw queries](https://sequelize.org/docs/v6/core-concepts/raw-queries/)
- [TypeORM query builder](https://typeorm.io/docs/query-builder/select-query-builder)
- [`js-yaml` documentation](https://github.com/nodeca/js-yaml)
- [`js-yaml` 4.0 migration changes](https://github.com/nodeca/js-yaml/blob/4.1.0/CHANGELOG.md#400---2021-01-03)
