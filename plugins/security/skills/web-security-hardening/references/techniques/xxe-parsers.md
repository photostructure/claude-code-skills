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
  have changed across 4.x/5.x (e.g. CVE-2026-25896 encoding-bypass).
- **xml2js**, **sax**: do not resolve external entities; internal-only. Grep confirms the
  parser, but do not mark "safe" without checking the pinned version's changelog.
- **libxmljs / libxmljs2** (`parseXml`, `parseXmlString`; also transitively via
  `xml2json`): WILL fetch and expand external entities — file read and SSRF — when
  `noent: true` is set. Anti-pattern: `parseXml(untrusted, { noent: true })` or any
  DTD-loading option on attacker-controlled XML. Fix below.

## libxmljs / libxmljs2 hardening

Anti-pattern (greppable): `noent: true`, `dtdload: true`, `dtdvalid: true`, or a missing/
default options object on request-derived XML.

- Parse with `{ noent: false, dtdload: false, nonet: true }` (and `dtdvalid: false`) so
  entities are not substituted, external DTDs are not loaded, and the parser makes no
  network requests even if another flag re-enables entities.
- Reject or hard-limit `<!DOCTYPE` in untrusted payloads before parsing; treat any DOCTYPE
  in an upload/webhook body as suspicious.
- `nonet: true` blocks the network leg only: `XML_PARSE_NONET` forbids `http://`/`ftp://`
  fetches (SSRF, remote-DTD retrieval, out-of-band exfil) but does NOT stop `file://`
  local reads — it gates network protocols, not the filesystem. The load-bearing control
  against local file read is `noent: false` plus rejecting DOCTYPE; keep `nonet: true` as
  defense-in-depth for the network paths. Verify these option names/defaults against the
  installed libxmljs version.

## Real ingestion vectors

XXE rarely arrives as an obvious `text/xml` body. Trace these surfaces from the upload/
webhook boundary (see ../input-output-and-files.md) to whichever XML parser consumes them:

- **SVG uploads** — parsed/rasterized/sanitized server-side; a DOCTYPE rides in the image.
- **DOCX/XLSX/PPTX (OOXML)** — ZIP containers of XML parts; extraction feeds a parser.
- **SOAP / XML-RPC** endpoints and their WSDL/schema handling.
- **SAML assertions** — signed XML from an IdP is still parser input before signature check.
- **RSS/Atom feed imports** and other partner/federated XML.

## Impact

XXE via a fetching parser yields SSRF (internal `http://`, cloud metadata) and local file
read (`file:///etc/passwd`, app secrets), plus DoS via entity expansion. `nonet` shuts the
network paths (SSRF and out-of-band exfil of read data) but not the local `file://` read
itself — stop that with `noent: false` and DOCTYPE rejection. See ../input-output-and-files.md
for the SSRF egress-allowlist and upload-validation controls that compound this defense.

## Primary sources

- [OWASP XML External Entity Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/XML_External_Entity_Prevention_Cheat_Sheet.html)
- [fast-xml-parser — Entities docs](https://github.com/NaturalIntelligence/fast-xml-parser/blob/master/docs/v4%2C%20v5/5.Entities.md)
- [libxmljs](https://github.com/libxmljs/libxmljs)
- [libxml2 parser options (`XML_PARSE_NONET` — "Forbid network access")](https://gnome.pages.gitlab.gnome.org/libxml2/devhelp/libxml2-parser.html)
