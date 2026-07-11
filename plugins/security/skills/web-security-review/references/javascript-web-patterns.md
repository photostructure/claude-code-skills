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

**Flag these:**

```jsx
<div dangerouslySetInnerHTML={{__html: userInput}} />  // XSS — Critical
                                                       //   unless DOMPurify-sanitized
<a href={userInput}>          // check for javascript: protocol
<iframe src={userInput} />    // check for javascript: protocol
eval(userInput)               // Critical
new Function(userInput)       // Critical
setTimeout(userInput, ms)     // Critical if string argument
```

**Safe remediations to recognize:**

```jsx
import DOMPurify from "dompurify";
<div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(html) }} />;

const ok = url.startsWith("https://") || url.startsWith("/"); // href allowlist
```

---

## Vue

**Auto-escaped — do NOT flag:**

```vue
<div>{{ userInput }}</div>     <!-- mustache escapes -->
<div :class="userInput">       <!-- attribute binding -->
<input :value="userInput" />
```

**Flag these:**

```vue
<div v-html="userInput"></div>   <!-- XSS — Critical -->
<a :href="userInput">            <!-- check protocol -->
<component :is="userInput" />    <!-- arbitrary component load -->
Vue.compile(userTemplate)        <!-- server-side template injection -->
new Vue({ template: userInput })
```

---

## Angular

**Auto-escaped — do NOT flag:** `{{ userInput }}` interpolation, `[innerHTML]="value"`
(sanitized by `DomSanitizer`).

**Flag these — sanitization bypass with user input:**

```ts
this.sanitizer.bypassSecurityTrustHtml(userInput); // FLAG
this.sanitizer.bypassSecurityTrustScript(userInput); // FLAG
this.sanitizer.bypassSecurityTrustUrl(userInput); // FLAG
this.sanitizer.bypassSecurityTrustResourceUrl(userInput); // FLAG
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

**Flag these:**

```js
db.query(`SELECT * FROM users WHERE id = ${userId}`); // SQL injection
db.collection("u").find({ $where: userInput }); // NoSQL code injection
exec(userInput);
execSync(userInput); // command injection — Critical
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

// FLAG: attacker chooses the Redis command and arguments
await redis.sendCommand([req.body.command, ...req.body.args]);

// FLAG: attacker supplies executable Lua source
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

new ClassicLevel(req.query.location); // FLAG if reachable: filesystem path control
await ClassicLevel.destroy(req.query.location); // FLAG: destructive path control
await ClassicLevel.repair(req.query.location); // FLAG: destructive path control
```

Use server-selected `sublevel()` namespaces to separate tenants/data classes, but do
not treat a prefix as authorization. Use atomic batches for multi-key security
invariants and a consistent snapshot for multi-read authorization decisions.

### Object / where-clause injection (looks safe, isn't)

Express's `qs` parser turns `?id[$gt]=` into an **object**, so a "parameterized" ORM
or ODM call can silently change meaning (for example, Knex CVE-2016-20018 dropped the
WHERE clause; MongoDB interprets operator objects). A scalar type-check is the fix.

```js
// VULNERABLE: req.query.id may be an object, not a string
knex("users").where({ id: req.query.id }); // ?id[$gt]= → returns all rows
User.findOne({ where: req.query }); // whole query object attacker-shaped

// SAFE: reject non-scalars first (also collapse HPP with the `hpp` middleware)
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

**Watch:** `NEXT_PUBLIC_*` env vars are shipped to the client — never put secrets there.

---

## DOM XSS sinks (vanilla / any framework escape hatch)

**Always dangerous with user input:**

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
// FLAG: untrusted keys merged into an object
function merge(t, s) {
  for (const k in s) t[k] = s[k];
} // __proto__ / constructor
_.merge(target, userInput); // lodash < 4.17.12
$.extend(true, target, userInput); // jQuery deep extend

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

`function f(data: any)` bypasses type safety entirely — treat `any` on a request path
as unvalidated input.

---

## Grep starters

Confirm hits by reading the code — these locate candidates, they don't prove bugs.

```bash
# DOM XSS sinks
grep -rn "innerHTML\|outerHTML\|document\.write\|insertAdjacentHTML" --include="*.{js,jsx,ts,tsx}"
# React / Vue / Angular escape hatches
grep -rn "dangerouslySetInnerHTML" --include="*.{jsx,tsx}"
grep -rn "v-html" --include="*.vue"
grep -rn "bypassSecurityTrust" --include="*.ts"
# code execution
grep -rn "eval(\|new Function(" --include="*.{js,ts}"
# command injection
grep -rn "child_process\|\bexec(\|execSync(\|spawn(" --include="*.{js,ts}"
# SQL / NoSQL injection, SSRF, prototype pollution
grep -rn "\.raw(\|\.query(\`" --include="*.{js,ts}"
grep -rn '\$where\|\$regex\|findOne(req\.\|find(req\.' --include="*.{js,ts}"
grep -rn "sendCommand\|\.eval(\|new ClassicLevel\|ClassicLevel\.destroy\|ClassicLevel\.repair" --include="*.{js,ts}"
grep -rn "fetch(\|http\.get(\|axios(" --include="*.{js,ts}"
grep -rn "__proto__\|constructor\[" --include="*.{js,ts}"
```
