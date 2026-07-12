<!--
Adapted from getsentry/skills — security-review/languages/javascript.md.
Reference material derived from the OWASP Cheat Sheet Series.
Licensed CC BY-SA 4.0. See ../ATTRIBUTION.md. Changes: trimmed to web
frameworks, reorganized, added TypeScript/validation notes.
-->

# JavaScript / TypeScript Web Patterns

Framework-specific "safe vs. dangerous" catalog. Use it to decide whether a candidate
finding is actually exploitable or is already neutralized by the framework. **A safe
pattern here means "do not flag."**

## Framework detection

| Indicator                                           | Framework |
| --------------------------------------------------- | --------- |
| `import React`, `.jsx`/`.tsx`, `useState`           | React     |
| `import Vue`, `.vue`, `v-bind`, `v-model`           | Vue       |
| `@Component`, `import ... @angular`                 | Angular   |
| `import express`, `app.get/post`                    | Express   |
| `@Controller`, `@nestjs/*`                          | NestJS    |
| `next`, `getServerSideProps`, `app/` route handlers | Next.js   |

---

## React

**Auto-escaped — do NOT flag:**

```jsx
<div>{userInput}</div>          // JSX escapes interpolated values
<input value={userInput} />     // attribute binding (except href/src)
<div className={userInput}>
```

**Investigate these escape hatches and executable/URL contexts.** Report only after
tracing untrusted data and proving browser-executable or security-boundary impact;
the API name does not determine severity.

```jsx
<div dangerouslySetInnerHTML={{__html: userInput}} />  // raw HTML; require trusted or sanitized input
<a href={userInput}>          // check for javascript: protocol
<iframe src={userInput} />    // check for javascript: protocol
eval(userInput)               // script execution if attacker-controlled
new Function(userInput)       // script execution if attacker-controlled
setTimeout(userInput, ms)     // browser string form evaluates code
```

**Safe remediations to recognize:**

```jsx
import DOMPurify from "dompurify";
<div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(html) }} />;

const parsed = new URL(url, window.location.origin);
const safeForExternalLink = parsed.protocol === "https:";
const safeForLocalRedirect = parsed.origin === window.location.origin;
```

---

## Vue

**Auto-escaped — do NOT flag:**

```vue
<div>{{ userInput }}</div>     <!-- mustache escapes -->
<div :class="userInput">       <!-- attribute binding -->
<input :value="userInput" />
```

**Investigate these:**

```vue
<div v-html="userInput"></div>   <!-- raw HTML; require trusted or sanitized input -->
<a :href="userInput">            <!-- check protocol -->
<component :is="userInput" />    <!-- only security-relevant if it selects a privileged component/capability -->
Vue.compile(userTemplate)        <!-- server-side template injection -->
new Vue({ template: userInput })
```

---

## Angular

**Auto-escaped — do NOT flag:** `{{ userInput }}` interpolation, `[innerHTML]="value"`
(sanitized by `DomSanitizer`).

**Investigate these sanitization bypasses when their argument is untrusted:**

```ts
this.sanitizer.bypassSecurityTrustHtml(userInput); // CANDIDATE
this.sanitizer.bypassSecurityTrustScript(userInput); // CANDIDATE
this.sanitizer.bypassSecurityTrustUrl(userInput); // CANDIDATE
this.sanitizer.bypassSecurityTrustResourceUrl(userInput); // CANDIDATE
```

Only safe with server-validated, non-user content.

---

## Express / Node.js

**Safe — do NOT flag:**

```js
User.findOne({ where: { id: userId } }); // Sequelize — parameterized
res.json({ data: userInput }); // auto-serialized
```

For MongoDB, a structured filter is safe only after every request-derived equality
value is validated as the expected scalar type:

```js
if (typeof id !== "string") throw new BadRequest();
db.collection("users").findOne({ _id: id }); // safe after scalar validation
```

**Inspect the template before deciding:** `res.render()` is safe only when the value
reaches an escaped directive. EJS `<%= value %>`, Handlebars `{{value}}`, and Pug
`= value` escape HTML. EJS `<%- value %>`, Handlebars `{{{value}}}` / `{{& value}}`,
and Pug `!= value` / `!{value}` emit raw HTML; flag them when the value is attacker-
controlled and unsanitized.

**Investigate these:**

```js
db.query(`SELECT * FROM users WHERE id = ${userId}`); // SQL injection if userId is tainted
db.collection("u").find({ $where: userInput }); // NoSQL code injection if tainted
exec(userInput);
execSync(userInput); // command injection candidate; severity follows reachable impact
spawn(cmd, { shell: true }); // command injection if cmd tainted
res.sendFile(userPath);
fs.readFile(userPath); // path traversal — check validation
path.join(base, userInput); // ../../../ escape possible
fetch(userUrl);
http.get(userUrl); // SSRF — check URL validation
```

### NoSQL operator injection (MongoDB)

MongoDB/BSON APIs preserve structure rather than treating every value as an inert
parameter. A JSON body or parsed query value can therefore introduce `$ne`, `$gt`,
`$regex`, or another operator when code expects a scalar.

```js
// VULNERABLE: either value can be an operator object such as { $ne: null }
db.users.findOne({ username: req.body.username, password: req.body.password });

// SAFE: validate the expected scalar type before building the filter
if (typeof req.body.username !== "string" ||
    typeof req.body.password !== "string") throw new BadRequest();
db.users.findOne({ username: req.body.username, password: req.body.password });
```

Also flag request-shaped filters passed wholesale to `find`, `findOne`, aggregation
stages, Mongoose query helpers, or `$where`. Treat `$regex` as injection when it enables
data extraction; do not report regex performance alone under this skill's DoS exclusion.

### Redis

Normal Redis clients encode commands as binary-safe argument arrays. A caller-derived
value is not protocol injection, though a caller-derived **key** may still cross an
authorization boundary.

```js
await redis.get(`profile:${req.params.id}`); // not injection; still check ownership

// CANDIDATE: attacker chooses the Redis command and arguments
await redis.sendCommand([req.body.command, ...req.body.args]);

// CANDIDATE: attacker supplies executable Lua source
await redis.eval(req.body.script, { keys: [key], arguments: [value] });

// SAFE from script injection: source is fixed; data is passed separately
const script = "return redis.call('GET', KEYS[1])";
await redis.eval(script, { keys: [serverDerivedKey], arguments: [] });
```

For one-time reset/session tokens, separate `GET` then `DEL` calls are replayable under
concurrency; use atomic `GETDEL` (Redis 6.2+) or a fixed Lua/transaction equivalent.
For expiring security state, remember that plain `SET` discards an existing TTL; supply
`EX`/`PX` or intentionally use `KEEPTTL`.

### LevelDB / classic-level

LevelDB keys are byte strings, not query syntax. Treat caller-derived keys as an
authorization question, not injection.

```js
await db.get(req.params.id); // not injection; still check tenant/owner scope

new ClassicLevel(req.query.location); // CANDIDATE: filesystem path/cross-store control
await ClassicLevel.destroy(req.query.location); // CANDIDATE: destructive path control
await ClassicLevel.repair(req.query.location); // CANDIDATE: destructive path control
```

Use server-selected `sublevel()` namespaces to separate tenants/data classes, but do
not treat a prefix as authorization. Use atomic batches for multi-key security
invariants and a consistent snapshot for multi-read authorization decisions.

### Object / where-clause injection (looks safe, isn't)

Depending on the Express version and configured query parser, nested query syntax such
as `?id[$gt]=` can become an **object**. JSON bodies can always carry objects. ODMs such
as MongoDB may interpret operator objects; SQL ORM behavior varies by library and
version. Validate the expected scalar type, then confirm the installed library's
generated query before calling this injection.

```js
// CANDIDATE: req.query.id may be structured; inspect parser and ORM/ODM semantics
knex("users").where({ id: req.query.id }); // behavior varies; inspect installed version/query
User.findOne({ where: req.query }); // whole query object attacker-shaped

// SAFE: reject non-scalars before constructing the filter
if (typeof req.query.id !== "string") throw new BadRequest();
```

### Mass assignment (privilege escalation)

```js
// VULNERABLE: schema has role/isAdmin/ownerId → attacker sets them
User.create(req.body);
Object.assign(user, req.body);
new User(req.body); // Mongoose schema may expose privileged fields

// SAFE: allowlist writable fields
User.create(req.body, { fields: ["name", "email"] }); // Sequelize
// NestJS: ValidationPipe({ whitelist: true, forbidNonWhitelisted: true }) + DTO
```

---

## Next.js

**Flag these:**

```jsx
export async function getServerSideProps({ query }) {
  const data = await fetch(query.url); // SSRF — attacker controls URL
}
<div dangerouslySetInnerHTML={{ __html: props.content }} />; // XSS
```

**Watch:** Next.js inlines referenced `NEXT_PUBLIC_*` values into browser bundles at
build time. Treat those references as public and never assign secrets to them.

---

## DOM XSS sinks (vanilla / any framework escape hatch)

**Candidate sinks with untrusted input** (prove the resulting execution, navigation,
or other impact before reporting):

```js
element.innerHTML = userInput;
element.outerHTML = userInput;
element.insertAdjacentHTML(pos, userInput);
document.write(userInput);
document.writeln(userInput);
location = userInput;
location.href = userInput; // open redirect / javascript:
window.open(userInput);
eval(userInput);
new Function(userInput)();
```

**Safe — text only, do NOT flag:**

```js
element.textContent = userInput;
element.innerText = userInput;
element.setAttribute("data-x", userInput); // non-event, non-url attribute
document.createTextNode(userInput);
```

Common DOM XSS **sources** to trace: `location.hash`, `location.search`,
`document.referrer`, `window.name`, `postMessage` data.

---

## Prototype pollution

```js
// CANDIDATE: untrusted keys merged into an ordinary object
function merge(t, s) {
  for (const k in s) t[k] = s[k];
} // keys such as __proto__ / constructor may affect prototypes, depending on semantics
_.merge(target, userInput); // version-gate against the installed package's advisories
$.extend(true, target, userInput); // version-gate; prove a polluted property reaches a sink

// SAFE
const obj = Object.create(null); // no prototype chain
const m = new Map(); // keys can't touch the prototype
// or skip __proto__/constructor/prototype keys explicitly
```

---

## TypeScript: types are not runtime validation

```ts
// VULNERABLE: a cast validates nothing at runtime
const input = req.body as UserInput;
db.query(`SELECT * FROM users WHERE id = ${input.id}`); // still SQL injection

// SAFE: validate at the boundary
import { z } from "zod";
const UserInput = z.object({ id: z.number(), name: z.string() });
const input = UserInput.parse(req.body); // throws on bad input
```

`function f(data: any)` supplies no compile-time guarantee. Treat request data as
untrusted until a runtime validator or equivalent guard is found; `any` alone is not a
vulnerability.

---

## Search starters

Confirm hits by reading the code — these locate candidates, they don't prove bugs.

```bash
# DOM XSS sinks
rg -n -g '*.{js,jsx,ts,tsx}' 'innerHTML|outerHTML|document\.write|insertAdjacentHTML'
# React / Vue / Angular escape hatches
rg -n -g '*.{jsx,tsx}' 'dangerouslySetInnerHTML'
rg -n -g '*.vue' 'v-html'
rg -n -g '*.ts' 'bypassSecurityTrust'
# code execution
rg -n -g '*.{js,ts}' 'eval\(|new Function\('
# command injection
rg -n -g '*.{js,ts}' 'child_process|\bexec\(|execSync\(|spawn\('
# SQL / NoSQL injection, SSRF, prototype pollution
rg -n -g '*.{js,ts}' '\.raw\(|\.query\(`'
rg -n -g '*.{js,ts}' '\$where|\$regex|findOne\(req\.|find\(req\.'
rg -n -g '*.{js,ts}' 'sendCommand|\.eval\(|new ClassicLevel|ClassicLevel\.destroy|ClassicLevel\.repair'
rg -n -g '*.{js,ts}' 'fetch\(|http\.get\(|axios\('
rg -n -g '*.{js,ts}' '__proto__|constructor\['
```

## Authoritative references

- [React DOM: `dangerouslySetInnerHTML`](https://react.dev/reference/react-dom/components/common#dangerously-setting-the-inner-html)
- [Vue security guidance](https://vuejs.org/guide/best-practices/security)
- [Angular security guidance](https://angular.dev/best-practices/security)
- [OWASP Cross-Site Scripting Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html)
- [Express query parser setting](https://expressjs.com/en/api.html#app.settings.table)
- [Redis security](https://redis.io/docs/latest/operate/oss_and_stack/management/security/)
- [Node.js `child_process`](https://nodejs.org/api/child_process.html)
- [Node.js URL API](https://nodejs.org/api/url.html)
- [Next.js environment variables](https://nextjs.org/docs/app/guides/environment-variables)
