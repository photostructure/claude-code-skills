<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# Server-Side Template Injection

Untrusted data used as template *source* is SSTI. Impact ranges from output manipulation
and resource exhaustion to server-side code execution, depending on the engine, enabled
helpers/extensions, and exposed context. Keep template source server-controlled.

## Recognize SSTI-prone engines

Template engines need engine- and version-specific analysis when source is attacker-controlled:

- Pug/Jade, EJS, Nunjucks, doT, and lodash `_.template` expose expressions or compilation
  paths that can have severe impact; confirm the exact API and context before labeling RCE.
- Handlebars and Mustache are more constrained, but helpers/lambdas, partial loaders,
  prototype-access options, and application-provided capabilities still determine impact.
- Grep for the compile/render surfaces: `pug.compile(`, `pug.render(`, `ejs.compile(`,
  `ejs.render(`, `new Function(` from a template body, `nunjucks.renderString(`,
  `nunjucks.compile(`, `Handlebars.compile(`, `Handlebars.precompile(`, `_.template(`,
  `doT.template(`. Confirm engine and version against `package.json`; behavior and
  escaping defaults are version-sensitive — verify against the installed version.

## The severity-deciding distinction

First determine whether the user controls template source or only data:

- **SSTI (impact is engine-specific):** user input is the template *source* —
  `ejs.compile(userInput)`, `nunjucks.renderString(userInput)`,
  `pug.render(userInput)`, `_.template(userInput)`, or any template string built by
  concatenating/interpolating request data (`` `Hello ${userInput}` `` passed to
  `compile`). Grep: a variable derived from `req.*` flowing into the *first* argument of
  any compile/render call.
- **Not SSTI by itself:** user input is *data* rendered by a fixed template —
  `render(fixedTemplate, { name: userInput })`, `template({ name: userInput })`. The
  template literal is a server-owned constant; the user value is a context field. Still
  assess output encoding, getters/helpers, and prototype pollution. Raw sinks include
  `<%- %>`, `{{{ }}}`, and `!{ }`—see
  [../input-output-and-files.md](../input-output-and-files.md).
- Fix for the unsafe pattern: move the user value out of the source and into the data
  context; the template body must be a literal or a server-side file, never a request
  value.

## Keep template source server-controlled

- Do not select or load the template path from request/config data without an allowlist;
  a user-chosen filename that resolves to an attacker-writable file is equivalent to
  compiling user input. See path handling in
  [../input-output-and-files.md](../input-output-and-files.md).
- If user-authored templates are a genuine product requirement, select a deliberately
  constrained language and expose only inert data/capabilities. “Logic-less” is not a
  complete security boundary: extensions, lambdas/helpers, partial loading, output sinks,
  and resource consumption still need review.
- Do **not** assume in-process template restrictions form a security sandbox. Handlebars'
  own docs warn that options such as `allowProtoPropertiesByDefault`,
  `allowProtoMethodsByDefault`, and `allowCallsToHelperMissing` enable RCE and that even
  restricted templates can crash the process. Treat any "run untrusted templates safely"
  claim as unverified — confirm the exact sandbox option semantics against the installed
  version before trusting them, and prefer isolation (separate process/container with
  dropped privileges) over in-process sandboxing.
- Mark a template boundary Met only after tracing every dynamic template source and the
  installed engine's compile semantics.

## Primary sources

- [OWASP WSTG — Testing for Server-Side Template Injection](https://owasp.org/www-project-web-security-testing-guide/v41/4-Web_Application_Security_Testing/07-Input_Validation_Testing/18-Testing_for_Server_Side_Template_Injection)
- [Handlebars — runtime options / prototype access security](https://handlebarsjs.com/api-reference/runtime-options.html)
