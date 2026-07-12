<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# SQL Injection in ORMs / Query Builders

ORMs do not make SQL injection impossible; they add "raw" escape hatches whose safety depends on which API and syntax you use. Review every raw fragment and every dynamically built clause.

## Raw does not mean unbound

The common misconception is that a "raw" API disables parameterization, so people concatenate. Wrong: the raw APIs below **still parameterize** — they accept bindings and emit a prepared statement. The vulnerability is bypassing the binding slot with string interpolation, not using the raw API at all.

- Anti-pattern: any request value reaching a query through `` `...${x}...` ``, `'... ' + x`, or `.concat()` inside a query string.
- Fix: keep the value in a binding placeholder; pass it through the API's parameter channel. Never build the SQL text from user data.

## Knex

- Anti-pattern: `knex.raw('... ' + col + ' = ' + id)`; `knex.whereRaw(\`${col} = ${id}\`)`.
- Fix: bind through placeholders — `?` is a **value**, `??` is an **identifier**: `knex.raw('?? = ?', [col, id])`. `whereRaw` takes the same bindings: `knex.whereRaw('?? = ?', [col, id])`. Identifiers still route through the allowlist below (`??` quotes but does not validate). Verify `?`/`??` semantics against the installed Knex version.

## Prisma

- Anti-pattern: `$queryRawUnsafe(\`... ${x}\`)` / `$executeRawUnsafe(...)` with interpolated input; `Prisma.raw(userInput)`.
- Fix: use the tagged-template form — `$queryRaw\`SELECT ... WHERE id = ${v}\`` — which builds a prepared statement with `${...}` as bound parameters. Compose with `Prisma.sql\`...\`` and `Prisma.join(values)` for `IN` lists. Grep specifically for the `Unsafe` suffix and `Prisma.raw`; those do not parameterize interpolated text. Confirm method names against the installed Prisma version.

## Sequelize

- Anti-pattern: `sequelize.query('... ' + x)`; interpolating request data into `sequelize.literal(userInput)` — `literal()` is inserted verbatim and is **not** escaped.
- Fix: pass `replacements` (`?` / `:name`, escaped client-side before send) or `bind` (`$1` / `$name`, sent to the driver out-of-band): `sequelize.query('... WHERE id = :id', { replacements: { id } })`. Reserve `literal()` for server-controlled constants only. `bind` values cannot be identifiers/keywords — use the allowlist below for those.

## TypeORM

- Anti-pattern: `.where('name = ' + name)` or `.where(\`name = '${name}'\`)` in the query builder; identifiers spliced into `orderBy(userInput)`.
- Fix: named parameters — `.where('user.name = :name', { name })`, or the equivalent `.setParameter('name', value)` / `.setParameters({...})`. Parameters are escaped per driver. Verify parameter binding behavior against the installed TypeORM version.

## Unbindable identifiers

Table names, column names, `ORDER BY` targets, and sort direction cannot be bound as parameters in any of the above.

- Anti-pattern: quote-escaping or `??`-wrapping attacker-supplied identifiers/sort fields and treating that as safe; `ORDER BY ${req.query.sort} ${req.query.dir}`.
- Fix: map request input through a **fixed allowlist** to known-good literals: `const col = ({ name: 'name', created: 'created_at' })[req.query.sort] ?? 'id'` and `dir === 'desc' ? 'DESC' : 'ASC'`. Do not escape-and-pass-through; only emit values you control.

See ../input-output-and-files.md for the broader database/command/template boundary and ../../ATTRIBUTION.md.

## Primary sources

- [OWASP SQL Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html)
- [Prisma — Raw queries](https://www.prisma.io/docs/orm/prisma-client/using-raw-sql/raw-queries)
- [Knex — Raw](https://knexjs.org/guide/raw.html)
- [Sequelize v6 — Raw Queries](https://sequelize.org/docs/v6/core-concepts/raw-queries/)
- [TypeORM — Select using Query Builder](https://typeorm.io/docs/query-builder/select-query-builder/)
