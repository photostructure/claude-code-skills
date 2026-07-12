<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# Server-Side Template Injection

Untrusted data reaching template *compilation* executes as template code — RCE, not
merely XSS. Decide severity by where the user data lands, then keep template source
server-controlled.

## Recognize SSTI-prone engines

Node engines that compile template source to executable JS are all SSTI-prone when the
source is attacker-influenced:

- Pug/Jade, EJS, Nunjucks, doT, and lodash `_.template` compile to JS and reach RCE.
- Handlebars and Mustache are logic-less, but Handlebars still reaches RCE through
  prototype/helper access (see the sandbox note below); Mustache has no code context.
- Grep for the compile/render surfaces: `pug.compile(`, `pug.render(`, `ejs.compile(`,
  `ejs.render(`, `new Function(` from a template body, `nunjucks.renderString(`,
  `nunjucks.compile(`, `Handlebars.compile(`, `Handlebars.precompile(`, `_.template(`,
  `doT.template(`. Confirm engine and version against `package.json`; behavior and
  escaping defaults are version-sensitive — verify against the installed version.

## The severity-deciding distinction

The same engine is safe or catastrophic depending on which argument the user controls:

- **Unsafe (SSTI/RCE):** user input is the template *source* —
  `ejs.compile(userInput)`, `nunjucks.renderString(userInput)`,
  `pug.render(userInput)`, `_.template(userInput)`, or any template string built by
  concatenating/interpolating request data (`` `Hello ${userInput}` `` passed to
  `compile`). Grep: a variable derived from `req.*` flowing into the *first* argument of
  any compile/render call.
- **Safe (XSS at most):** user input is *data* rendered by a fixed template —
  `render(fixedTemplate, { name: userInput })`, `template({ name: userInput })`. The
  template literal is a server-owned constant; the user value is a context field. Residual
  risk is output encoding (raw sinks `<%- %>`, `{{{ }}}`, `!{ }`) — see
  [../input-output-and-files.md](../input-output-and-files.md).
- Fix for the unsafe pattern: move the user value out of the source and into the data
  context; the template body must be a literal or a server-side file, never a request
  value.

## Keep template source server-controlled

- Do not select or load the template path from request/config data without an allowlist;
  a user-chosen filename that resolves to an attacker-writable file is equivalent to
  compiling user input. See path handling in
  [../input-output-and-files.md](../input-output-and-files.md).
- If user-authored templates are a genuine product requirement, use a logic-less engine
  (Mustache) that has no expression/code context — not a full engine in "sandbox" mode.
- Do **not** rely on engine sandboxes as the boundary. Handlebars, Nunjucks, and Pug
  sandbox/restriction modes are routinely bypassed (prototype-chain and helper escapes);
  Handlebars' own docs warn options such as `allowProtoPropertiesByDefault`,
  `allowProtoMethodsByDefault`, and `allowCallsToHelperMissing` enable RCE and that even
  restricted templates can crash the process. Treat any "run untrusted templates safely"
  claim as unverified — confirm the exact sandbox option semantics against the installed
  version before trusting them, and prefer isolation (separate process/container with
  dropped privileges) over in-process sandboxing.
- Mark a template boundary Met only after tracing every dynamic template source and the
  installed engine's compile semantics.

## Primary sources

- [OWASP WSTG — Testing for Server-Side Template Injection](https://owasp.org/www-project-web-security-testing-guide/v41/4-Web_Application_Security_Testing/07-Input_Validation_Testing/18-Testing_for_Server_Side_Template_Injection)
- [PortSwigger — Server-side template injection](https://portswigger.net/web-security/server-side-template-injection)
- [Handlebars — runtime options / prototype access security](https://handlebarsjs.com/api-reference/runtime-options.html)
