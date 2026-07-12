<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# Framework Production Misconfiguration

Hardening for defaults that are safe in development but leak internals or expose tooling
once the same code runs in production. See also [Deployment and operations](../deployment-and-operations.md).

## Set NODE_ENV=production so error output stops leaking stack traces

Express's built-in error handler writes `err.stack` to the client response for any error
reaching `next(err)` without a custom handler; it sends only the status-code HTML instead
when `NODE_ENV === 'production'`. Many frameworks (and view engines, ORMs, template
compilers) key error verbosity, template caching, and debug pages off the same variable.

- Anti-pattern to grep: no `NODE_ENV=production` in the deploy env (`printenv NODE_ENV`
  empty, `env`/`.env`/Dockerfile/compose/k8s manifest missing it), `NODE_ENV=development`
  shipped to prod, or a stack trace visible in a live 500 response body.
- Fix: set `NODE_ENV=production` in the runtime environment (not just at build time), and
  do not rely on it alone — add an explicit custom error-handling middleware
  (`app.use((err, req, res, next) => …)`, four args) that returns a generic body and logs
  the detail server-side. Confirm no route hands `err.stack`, `err.message`, or SQL/driver
  text to the client. Verify the exact NODE_ENV-gated behavior against the installed
  Express/framework version — the gate and what it suppresses shift across majors.

## Directory listing: remove the opt-in that produces it, do not "add a control"

Express serves no directory index by default — for a directory with no matching index
file `express.static` (serve-static) calls `next()`, which yields Express's default 404
in a bare app; it never lists the directory. Listings appear only because someone opted in: the
`serve-index` middleware, or a reverse proxy autoindex (`autoindex on;` in nginx, or
Apache `Options +Indexes`).

- Anti-pattern to grep: `require('serve-index')` / `serveIndex(...)` mounted on any path;
  `autoindex on` in nginx config; `Options +Indexes` in Apache config; a live directory
  URL returning an HTML file listing.
- Fix: delete the `serve-index` mount (or scope it to an authenticated admin route with a
  documented reason); set `autoindex off` / remove `+Indexes`. There is no header or flag
  to "harden" a listing into safety — the fix is disabling the feature. Keep application
  data, backups, and dotfiles outside any static/web-served root regardless.

## Decide production exposure for explorers, introspection, and setup routes

Swagger/OpenAPI UIs, GraphQL explorers, and one-time bootstrap/install routes require an
explicit production exposure decision. Documentation and introspection can be intentional
for a public API; setup routes are different because they can change trust state.

- Anti-pattern to grep: `swaggerUi.serve` / `SwaggerModule.setup(...)` mounted
  unconditionally; a GraphQL server with introspection/explorer enabled in prod
  (`introspection: true`, or Apollo's landing page / GraphQL Playground left on); a
  `/setup`, `/install`, `/seed-admin`, or first-run bootstrap route with no permanent
  disable after completion.
- Fix: disable explorers in production unless they are an intentional, access-controlled
  product surface. Disable or restrict GraphQL introspection based on the API's consumers
  and threat model; it is not an authorization control, and public schemas may intentionally
  expose it. Verify exact server/version options. Make setup routes fail closed once
  initialized: gate on persisted state and remove public access after setup. If recovery or
  reinitialization is required, expose it through a separately authenticated operational
  procedure—not an in-memory boolean that resets on restart.

## Primary sources

- [Express: error handling (built-in handler and production stack traces)](https://expressjs.com/en/guide/error-handling.html)
- [Express: production best practices — performance and reliability (NODE_ENV)](https://expressjs.com/en/advanced/best-practice-performance.html)
- [serve-index middleware](https://github.com/expressjs/serve-index)
- [nginx ngx_http_autoindex_module](https://nginx.org/en/docs/http/ngx_http_autoindex_module.html)
- [OWASP Top 10 A05:2021 — Security Misconfiguration](https://owasp.org/Top10/A05_2021-Security_Misconfiguration/)
- [Apollo Server: introspection and landing page configuration](https://www.apollographql.com/docs/apollo-server/api/apollo-server/)
