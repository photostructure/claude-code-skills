# JavaScript and TypeScript Framework Evidence

Use this reference to translate a generic control into evidence about the application's
actual framework, adapter, middleware order, and installed version. A framework name or
package dependency is never enough by itself.

## Contents

- [Version and runtime first](#version-and-runtime-first)
- [Express and Node HTTP servers](#express-and-node-http-servers)
- [NestJS](#nestjs)
- [Next.js](#nextjs)
- [React, Vue, and Angular](#react-vue-and-angular)
- [Runtime validation libraries](#runtime-validation-libraries)
- [Evidence patterns](#evidence-patterns)
- [Primary sources](#primary-sources)

## Version and runtime first

Before crediting a default or recommending an API:

1. Read `package.json` and the lockfile for the resolved framework and adapter versions.
2. Identify the production entry point and build target. Test/dev servers may have
   different middleware, headers, and error behavior.
3. Trace wrappers, platform adapters, edge middleware, reverse proxies, and serverless
   configuration that can add, remove, or override a control.
4. Check official documentation for that installed major version when behavior is
   version-sensitive.

Record **Needs verification**, not Gap, when a CDN or hosting platform is expected to
provide a control but its deployed configuration is outside the repository.

## Express and Node HTTP servers

### Middleware coverage and order

- Follow each router mount from the production entry point. Security middleware mounted
  after a route does not protect that route.
- Check whether alternate listeners, health/admin ports, WebSocket upgrades, static-file
  mounts, and error handlers bypass the main stack.
- Confirm request-size limits on every enabled body parser, including JSON, URL-encoded,
  text, raw, multipart, and framework-specific parsers.
- Treat `app.disable("x-powered-by")` as a small information-exposure control, not proof
  of broader response hardening.

### Helmet and headers

- Credit `helmet()` only for headers enabled by the effective configuration and only on
  routes it precedes. Individual headers can be disabled or overwritten later.
- Inspect the generated CSP directives. Helmet's defaults are a starting point, not
  evidence that the policy permits the application to work securely without broad
  sources, inline exceptions, or environment-specific weakening.
- Development exceptions such as disabling `upgrade-insecure-requests` may be reasonable;
  verify that they cannot reach production.
- Avoid duplicating a header at the CDN and application unless ownership and override
  behavior are clear.

### Proxy, origin, sessions, and errors

- `trust proxy` affects client IP, secure-cookie decisions, protocol, and hostname.
  Verify the exact trusted hop/subnet model; unconditional trust is not correct merely
  because a proxy exists.
- Derive security-sensitive public URLs from a configured canonical origin where host
  header trust is not guaranteed.
- For `express-session`, inspect cookie attributes, store durability, secret handling,
  regeneration at privilege changes, idle/absolute expiry, and logout invalidation.
- Ensure production error handling does not return stack traces, SQL/driver errors,
  tokens, secrets, or internal paths. Preserve useful server-side logging with redaction.

## NestJS

- Determine whether the application uses the Express or Fastify adapter before applying
  adapter-specific guidance.
- Inspect global and route-scoped pipes. A `ValidationPipe` only protects parameters with
  usable runtime metadata and DTO rules; TypeScript interfaces disappear at runtime.
- With Nest's `class-validator` integration, `whitelist: true` strips properties that
  have no validation decorator; `forbidNonWhitelisted: true` rejects them. A TypeScript
  declaration alone is not enough. Neither option substitutes for authorization or
  field-level ownership rules.
- `transform: true` can coerce values. Confirm that coercion matches business semantics
  and does not turn malformed input into an accepted authorization-sensitive value.
- Trace guards, interceptors, middleware, pipes, and exception filters across global,
  controller, and method scopes. A decorator's presence on one controller proves only
  that controller is covered.
- Verify Helmet, CORS, parser limits, and cookie/session plugins against the selected
  adapter and that they are registered before listening.
- Review Swagger/OpenAPI or GraphQL explorer exposure separately for production.

## Next.js

Assess the Pages Router, App Router, Route Handlers, Server Actions, Middleware, and any
custom server as separate execution surfaces when present.

### Server/client boundary

- Only intentional public values should enter browser bundles. Inspect `NEXT_PUBLIC_*`
  variables and `next.config.js` `env` entries—the latter are always bundled even without
  the prefix—plus values serialized into pages, React Server Component payloads, initial
  state, and build artifacts.
- A server-only module is useful evidence only if all import paths preserve the boundary.
- Treat Server Actions and Route Handlers as remotely callable endpoints: validate their
  inputs and repeat authentication and object/action authorization inside the server
  boundary. UI visibility is not authorization.

### Headers, CSP, redirects, and caching

- Trace `next.config` headers, Middleware matchers, platform config, and custom-server
  middleware. Excluded static/API routes and alternate deployments can change coverage.
- Nonce-based CSP in Next.js can affect static optimization and caching. Recommend it
  with a rollout design that accounts for rendering mode; do not paste a generic policy.
- Inspect remote image allowlists/patterns narrowly and review user-controlled redirect
  destinations and rewrites.
- Check that authenticated or user-specific responses are not placed in shared caches,
  and that public caching cannot preserve authorization-dependent content.
- Verify production source-map, debug, and error-page exposure from build and hosting
  settings rather than development behavior.

## React, Vue, and Angular

These frameworks normally escape values in ordinary template/text bindings. Credit that
protection for those contexts, then look for deliberate escape hatches and browser APIs:

| Framework | Raw HTML escape hatch examples |
| --- | --- |
| React | `dangerouslySetInnerHTML` |
| Vue | `v-html` |
| Angular | direct DOM APIs and `DomSanitizer` `bypassSecurityTrust*` methods; normal `[innerHTML]` is sanitized |

- Raw HTML is not automatically a Gap: establish whether the value is trusted, safely
  sanitized by the framework or a maintained HTML sanitizer under an appropriate policy,
  or attacker-shaped. Angular sanitizes untrusted values in HTML and URL template
  contexts, but not resource URLs; trusting bypass APIs and direct DOM calls bypass that
  boundary.
- Do not extrapolate text escaping to every URL, style, JavaScript, resource-URL, or DOM
  API context. Credit the detected framework's documented contextual protections, then
  review `href`/`src`, navigation, `postMessage`, storage, DOM insertion, and dynamic code.
- Client-side validation improves user experience but never satisfies a server trust-
  boundary control by itself.
- When Trusted Types is applicable, treat it as CSP-aligned defense in depth with a
  migration plan; do not report its absence as a universal gap.

## Runtime validation libraries

Zod, Joi, Ajv, Yup, `class-validator`, and similar dependencies count only when their
schemas execute on the relevant trust boundary and the application uses the validated
result.

Check for these common failures:

- calling a permissive or partial schema where a strict create/update schema is needed;
- validating but later using the original request object;
- allowing unknown fields into ORM update/create calls;
- validating shape but not business semantics, ownership, state transitions, length,
  ranges, or resource limits;
- coercion that accepts surprising values;
- applying validation to JSON while query strings, headers, files, WebSockets, or jobs
  take alternate paths;
- relying only on TypeScript types at an external boundary.

Mark a validation control Met only for the boundary and operation actually evidenced.

## Evidence patterns

Good evidence connects configuration to coverage:

```text
Met: src/server.ts:24 mounts helmet() before /api and /app; src/server.ts:61 adds the
same header policy to the separately mounted static router.

Gap: src/server.ts:18 mounts /uploads before helmet() at line 31, so upload download
responses do not receive the stated response-header baseline.

Needs verification: deploy/platform.json delegates HSTS to the edge, but the repository
does not contain the production edge configuration. Confirm the deployed HTTPS response.
```

Do not infer a repository-wide absence from a single entry point until alternate servers,
tests/examples, framework config, and deployment adapters are distinguished.

## Primary sources

- [Helmet documentation](https://helmetjs.github.io/)
- [Express security best practices](https://expressjs.com/en/advanced/best-practice-security.html)
- [Express behind proxies](https://expressjs.com/en/guide/behind-proxies.html)
- [NestJS validation](https://docs.nestjs.com/techniques/validation)
- [NestJS security](https://docs.nestjs.com/security/helmet)
- [Next.js security headers](https://nextjs.org/docs/app/api-reference/config/next-config-js/headers)
- [Next.js data security](https://nextjs.org/docs/app/guides/data-security)
- [Next.js environment variables](https://nextjs.org/docs/app/guides/environment-variables)
- [Next.js `next.config.js` `env`](https://nextjs.org/docs/pages/api-reference/config/next-config-js/env)
- [React `dangerouslySetInnerHTML`](https://react.dev/reference/react-dom/components/common#dangerously-setting-the-inner-html)
- [Vue `v-html` security guidance](https://vuejs.org/guide/best-practices/security.html)
- [Angular security](https://angular.dev/best-practices/security)
- [OWASP Input Validation Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html)

<!-- Adapted from OWASP guidance under CC BY-SA 4.0; see ../ATTRIBUTION.md. -->
