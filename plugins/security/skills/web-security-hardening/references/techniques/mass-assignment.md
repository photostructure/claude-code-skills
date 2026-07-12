<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# Mass Assignment / Over-Posting by ORM

Binding a request body straight into a model lets a caller set fields the form never
exposed (role, owner, tenant, billing, verified). Also called autobinding, over-posting,
or object injection. Fix with a server-derived allowlist, not a blocklist.

## Server-derived privileged fields

Security-relevant attributes must come from the authenticated server context, never the
request body.

- Anti-pattern: `Model.create(req.body)`, `Object.assign(user, req.body)`, `{ ...req.body }`
  spread into a model, or `new Model(req.body)` where the model carries `role`, `isAdmin`,
  `ownerId`, `userId`, `tenantId`, `orgId`, `accountId`, `billingPlan`, `credits`,
  `balance`, `emailVerified`, `status`, or `approved`.
- Fix: set these explicitly from the session/token after authorization, e.g.
  `data.ownerId = req.user.id`, and exclude them from the DTO the client can populate.
  A field the server owns must be overwritten server-side even if the client omits it —
  do not merely trust that it is absent.
- Blocklisting sensitive fields is fragile: new privileged columns silently become
  writable. Prefer an explicit allowlist of the bindable, non-sensitive fields (OWASP).

## Per-ORM allowlist enforcement

Pass an explicit field allowlist to the write call; do not hand the ORM the raw body.
Confirm exact option names/behavior against the installed major version — these differ
across versions and some are silent-drop vs. throw.

- **Sequelize:** `Model.create(values, { fields: ['name', 'email'] })` and
  `instance.update(values, { fields: [...] })` / `instance.save({ fields: [...] })` write
  only listed attributes; anything else in `values` is ignored. Anti-pattern: `create`/
  `update`/`bulkCreate` called with request data and no `fields` option. Verify `fields`
  semantics in the installed v6/v7.
- **Mongoose:** `strict` mode (on by default) drops schema-undeclared keys on save; set
  `strict: 'throw'` to reject them instead. Anti-pattern: `new Model(req.body).save()`
  relying on strict alone — strict does NOT stop over-posting of *declared* privileged
  fields, and `findOneAndUpdate`/`$set` from raw body still sets them. Fix: also select an
  explicit set of writable fields (build the update object by hand or pick allowed keys).
  Confirm the default is still enabled in the installed version.
- **Prisma:** pass a hand-built `data: { name, email }` object; Prisma rejects unknown
  keys, but only relative to your object — spreading the body in (`data: { ...req.body }`)
  reintroduces every attacker key that maps to a real column. Anti-pattern: `...req.body`
  or a raw body variable inside `data`. Fix: destructure the allowed fields explicitly.
- **NestJS:** register `ValidationPipe({ whitelist: true, forbidNonWhitelisted: true })`
  with class-validator DTOs — `whitelist` strips properties that have no validation
  decorator; `forbidNonWhitelisted` rejects the request instead. Anti-pattern: no global/
  route ValidationPipe, a DTO with undecorated privileged fields, or `@Body()` bound to the
  entity. Caveat: this is an input-shape filter, NOT authorization — a decorated but
  privileged field still passes; keep such fields out of the DTO and set them server-side.

See ../input-output-and-files.md ("Structured input and assignment") for DTO mapping and
../identity-sessions-and-secrets.md for the ownership/authorization checks these fields feed.

## Primary sources

- [OWASP Mass Assignment Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Mass_Assignment_Cheat_Sheet.html)
- [Sequelize Model Basics (`fields` allowlist)](https://sequelize.org/docs/v6/core-concepts/model-basics/)
- [Sequelize Model Instances (`save`/`update` `fields`)](https://sequelize.org/docs/v6/core-concepts/model-instances/)
- [Mongoose Schema Guide (`strict` mode)](https://mongoosejs.com/docs/guide.html)
- [Prisma CRUD (`data` argument)](https://www.prisma.io/docs/orm/prisma-client/queries/crud)
- [NestJS Validation (`whitelist` / `forbidNonWhitelisted`)](https://docs.nestjs.com/techniques/validation)
