<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# NoSQL / Operator Injection (MongoDB)

Attacker-controlled objects that reach a query become operators, not values — turning a lookup into a filter bypass or, via server-side JS, RCE.

## Query strings deserialize into operators

- With the `qs`/"extended" query parser, `?age[$gt]=0` (and `?user[$ne]=`) parses into
  `{ age: { $gt: 0 } }`. This is Express 4's default parser; Express 5 defaults to "simple"
  (Node `querystring`, no nesting) — verify the `query parser` setting against your version.
  A JSON body (`{"pass":{"$ne":null}}`) yields the same nested operators regardless of the
  query parser. So `collection.find(req.query)` or `find({ user: req.query.user })` silently
  becomes operator injection — an authentication check like `find({ user, pass })` matches
  with `pass[$ne]=` or `pass[$gt]=`.
- Anti-pattern to grep: `find(req.query`, `find(req.body`, `findOne({ ... req.body })`,
  `{ $where:`, request values spread into a filter, or any filter field assigned directly
  from `req.query`/`req.params`/`req.body` without a type check.
- Fix: validate **query and params, not just body** — the injection vector is often in the
  query string. Treat every request-derived source as a trust boundary
  (see ../input-output-and-files.md).

## Validate scalars; build allowlisted filters

- Expected equality values must be primitives. Reject `typeof value === "object"` (which
  also catches arrays) before building the filter, or coerce with a runtime schema
  (`zod`, `joi`, `ajv`) that pins the type to string/number.
- Construct the filter from named, allowlisted fields — `{ email: String(email) }` — never
  pass a whole request object as a filter, projection, sort, update, or aggregation stage.
- Anti-pattern to grep: `find(`/`updateOne(`/`aggregate([`/`sort(` whose argument is a
  request object or an un-narrowed value; `$in`/`$or` arrays sourced straight from input.

## `$where` / `$function` execute JavaScript (RCE)

- `$where` and `$function` (and `$accumulator`) run arbitrary JavaScript against each
  document — this is code execution, not just filter bypass. Never build these from input,
  and never accept them from a request-supplied filter.
- Fix: disable server-side JS on the server where the feature is unused —
  `security.javascriptEnabled: false` (or `mongod --noscripting`). Prefer `$expr` with
  aggregation operators over `$where`. Note: server-side JS (`$where`, `$function`,
  `$accumulator`) is deprecated as of MongoDB 8.0 — verify the deprecation/availability
  state against your installed server version.

## "We use Mongoose" is not automatic safety

- Mongoose casts query values to schema types, which neutralizes many operator payloads —
  but casting is bypassed by `Schema.Types.Mixed` fields, `strict: false`, and `$where`,
  and it does not sanitize raw operator keys you pass through yourself.
- `strict` (default on) drops undeclared fields on **save**; it does not vet query filters.
  Query-side filtering of unknown keys is governed by `strictQuery`, whose default has
  changed across major versions — verify the `strict`/`strictQuery` defaults against your
  installed Mongoose version rather than assuming.
- Anti-pattern to grep: `Schema.Types.Mixed`, `type: Object`, `strict: false`,
  `{ strict: false }`, `.find(req.` on a Mongoose model. Fix: keep strict schemas, avoid
  `Mixed` for request-populated fields, and still validate scalars at the boundary — the
  ODM is defense-in-depth, not the primary control.

## Primary sources

- [OWASP WSTG — Testing for NoSQL Injection](https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/05.6-Testing_for_NoSQL_Injection)
- [MongoDB Manual — `$where` operator](https://www.mongodb.com/docs/manual/reference/operator/query/where/)
- [MongoDB Manual — `security.javascriptEnabled` / server-side JavaScript](https://www.mongodb.com/docs/manual/reference/configuration-options/#mongodb-setting-security.javascriptEnabled)
- [Mongoose — Schemas Guide (`strict`, `strictQuery`, Mixed)](https://mongoosejs.com/docs/guide.html)
- [Express — Migrating to v5 (`query parser` default changes to "simple")](https://expressjs.com/en/guide/migrating-5/)
