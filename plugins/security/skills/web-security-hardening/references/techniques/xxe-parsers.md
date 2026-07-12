<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# XXE by XML Parser

XXE risk is per-parser: the same untrusted XML is inert in one library and a file-read/SSRF
primitive in another. Identify the parser, then verify its entity/DTD behavior against the
installed version — defaults drift across majors and CVEs.

## Per-parser defaults (VERIFY for the installed version)

Durable principle: never assume a Node XML library is XXE-safe or XXE-unsafe by reputation.
Grep the imports, then confirm the option semantics of the pinned version.

- **fast-xml-parser** (`new XMLParser(...)`, `parse(`): does NOT fetch external system
  entities (no `file://`/`http://` resolution); it only expands internal DOCTYPE/document
  entities, and `processEntities` (default `true`) applies expansion limits. Anti-pattern:
  relying on it for entity expansion of untrusted XML. Fix: pass `processEntities: false`
  for untrusted input. Verify against the installed version — entity handling and limits
  have changed across 4.x/5.x; use the pinned package's entity documentation and current
  advisories rather than a version-independent claim.
- For **xml2js**, **sax**, and wrappers, verify the pinned parser and configuration rather
  than inheriting a blanket “safe” label from the package name; wrappers may preprocess or
  hand data to another parser.
- **libxmljs / libxmljs2** (`parseXml`, `parseXmlString`; also transitively via
  wrappers): `noent: true` enables entity substitution and can load external entities
  according to the bundled libxml2 loader/options. Anti-pattern:
  `parseXml(untrusted, { noent: true })` or a DTD-loading option on attacker-controlled
  XML. Fix below.

## libxmljs / libxmljs2 hardening

Anti-pattern (greppable): entity replacement or DTD loading/validation on request-derived
XML. Check both library aliases and underlying flags: `replaceEntities: true` / `noent:
true`, `validateEntities: true` / `dtdvalid: true`, `validateAttributes: true` / `dtdattr:
true`, and direct `XML_PARSE_DTDLOAD` / `XML_PARSE_DTDATTR`. `DTDATTR` implies DTD loading.
Missing options are a verification question, not automatically a gap; check the pinned
binding's defaults and option mapping.

- Keep entity replacement and DTD load/validation options false. Determine the libxml2
  version bundled by the Node binding, not the system CLI version. If the binding exposes
  libxml2 2.13+'s `XML_PARSE_NO_XXE`, prefer it; otherwise reject DOCTYPE/external
  identifiers and prevent resource loading through the binding's documented resolver
  controls.
- Reject DOCTYPE when the input contract does not require it, but do not rely on a raw-byte
  substring scan as the primary control; decoding and parser behavior are authoritative.
- Version-gate `nonet: true`. In older libxml2 it disables the built-in HTTP/FTP clients
  but not local-file reads. Libxml2 2.15 removed its last built-in network client, so
  `XML_PARSE_NONET` then has no effect except being passed to custom resource loaders.
  It is therefore only defense-in-depth, never the load-bearing XXE control. Verify the
  binding's option mapping, bundled libxml2, and any custom loader.

## Real ingestion vectors

XXE rarely arrives as an obvious `text/xml` body. Trace these surfaces from the upload/
webhook boundary (see ../input-output-and-files.md) to whichever XML parser consumes them:

- **SVG uploads** — parsed/rasterized/sanitized server-side; a DOCTYPE rides in the image.
- **DOCX/XLSX/PPTX (OOXML)** — ZIP containers of XML parts; extraction feeds a parser.
- **SOAP / XML-RPC** endpoints and their WSDL/schema handling.
- **SAML assertions** — signed XML from an IdP is still parser input before signature check.
- **RSS/Atom feed imports** and other partner/federated XML.

## Impact

XXE via a fetching parser can yield SSRF, local-file disclosure, and entity-expansion DoS.
Prevent external resource loading and entity substitution with controls supported by the
binding's bundled parser; `nonet` alone is not sufficient and is ineffective against local
files (and largely inert in libxml2 2.15+). See ../input-output-and-files.md
for the SSRF egress-allowlist and upload-validation controls that compound this defense.

## Primary sources

- [OWASP XML External Entity Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/XML_External_Entity_Prevention_Cheat_Sheet.html)
- [fast-xml-parser — Entities docs](https://github.com/NaturalIntelligence/fast-xml-parser/blob/master/docs/v4%2C%20v5/5.Entities.md)
- [libxmljs](https://github.com/libxmljs/libxmljs)
- [libxml2 `parser.h` options (`XML_PARSE_NO_XXE`, `XML_PARSE_NONET`)](https://gnome.pages.gitlab.gnome.org/libxml2/html/parser_8h.html)
