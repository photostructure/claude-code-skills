<!-- OWASP-derived baseline guidance. CC BY-SA 4.0. See ../ATTRIBUTION.md. -->

# Baseline Selection and Reporting

## Contents

- [Standards backbone](#standards-backbone)
- [Select an assurance level](#select-an-assurance-level)
- [Profile-driven applicability](#profile-driven-applicability)
- [Evidence rules](#evidence-rules)
- [State calibration](#state-calibration)
- [Priority calibration](#priority-calibration)
- [Source and version policy](#source-and-version-policy)

## Standards backbone

Use **OWASP ASVS 5.0.0** as the coverage index. ASVS is a verification standard,
not a vulnerability severity system and not a mandate to implement every control in
every application. Select a level and applicable domains before assessing controls.

Describe a review based on these condensed references as **ASVS-guided**. Claim ASVS
conformance only after enumerating every requirement at the selected level, recording
applicability, and obtaining the required code, configuration, architecture, and
operational evidence. A clean selected-control review is not certification.

Use the OWASP Cheat Sheet Series to interpret and implement requirements. Use NIST,
RFCs, MDN, and official framework/library documentation when those sources define the
relevant behavior more precisely.

Do not use the OWASP Top 10 as the checklist. It is an awareness/risk document; ASVS is
the stronger basis for design, coding standards, review, and verification.

## Select an assurance level

| Level | Use for | Review posture |
| --- | --- | --- |
| **ASVS Level 1** | Lightweight review, low-risk public content, portfolio screening, early development | Broad minimum controls; identify obvious baseline omissions |
| **ASVS Level 2** | Most production applications, especially authenticated or data-bearing apps | Default; cover normal application and platform security boundaries |
| **ASVS Level 3** | Systems whose risk analysis, contracts, or regulatory requirements call for the highest assurance | Deep architecture, operational, cryptographic, and verification rigor |

Choose Level 2 when any of these are present unless the user specifies otherwise:

- login, accounts, private data, administration, or multi-tenancy;
- payments, health/financial data, consequential workflows, or secrets;
- internet exposure with meaningful state-changing behavior;
- APIs relied on by other privileged systems.

Level 3 is not “more findings.” It is a stricter assurance target that may require
architecture/process evidence beyond source code. Mark such controls Needs verification
when their evidence lives outside the repository.

ASVS requirement `v5.0.0-6.3.3` makes MFA part of Level 2 and adds stronger hardware-
based requirements at Level 3. Do not select Level 2 while treating MFA as optional. If
the user wants a tailored hardening review rather than ASVS conformance, state the
deviation instead of relabeling the result as a lower or passing ASVS assessment.

## Profile-driven applicability

Apply controls based on real surfaces:

| Profile fact | Normally applicable domains |
| --- | --- |
| Browser-rendered HTML/SSR | CSP, framing, MIME, referrer/cache, output encoding, DOM sinks |
| Cookie-authenticated state changes | CSRF, cookie attributes, origin/Fetch Metadata, session lifecycle |
| Bearer/API-key-only API | token lifecycle, authorization, CORS if browser-called; not cookie CSRF |
| Password login/recovery | password policy/storage, throttling, enumeration, reset-token lifecycle |
| OAuth/OIDC | state/nonce, redirect/callback, token validation, account linking, PKCE applicability |
| File uploads/downloads | type/size/name/storage/access controls, active content, archive handling |
| User-authored rich HTML | allowlist sanitizer plus contextual output controls and CSP |
| Application-encrypted data/tokens | AEAD/mode choice, key/IV/nonce management, CSPRNG, weak-algorithm avoidance |
| Multi-user/multi-tenant | object/function authorization, server-derived namespaces, auditability |
| Reverse proxy/CDN | trusted proxy hops, forwarded-header overwrite, TLS/public-origin config |
| Self-hosted/container | bind defaults, bootstrap, filesystem/DB exposure, secrets/backups, updates |
| CI/CD and published packages/images | dependency integrity, secret handling, artifact provenance |

Examples of Not applicable:

- CSP and clickjacking headers on a service that only returns JSON to non-browser clients;
- password composition/storage controls when the app delegates all identity to an IdP;
- CSRF for a route authenticated solely by a caller-set bearer header;
- HSTS for a non-HTTP local IPC service.

Do not mark a domain Not applicable merely because relevant code is outside the requested
diff. Research the repository and deployment shape first.

## Evidence rules

Accept evidence from:

- executed middleware and route composition;
- effective production configuration and IaC;
- framework/library behavior verified for the installed version;
- tests that assert security behavior;
- deployment/platform policy that demonstrably covers the app;
- documented architecture decisions with observable compensating controls.

Weak evidence that requires more investigation:

- dependency presence without middleware/route use;
- `.env.example` without runtime enforcement;
- comments, TODOs, README claims, or unused helpers;
- client-side validation/authorization without a server boundary;
- a control on one route when equivalent routes remain uncovered;
- platform assumptions without deploy config or an explicit user confirmation.

For Met and Gap, cite `file:line` or effective platform evidence. For Needs verification,
state the missing fact and a safe verification method. Do not assume Gap simply because
static code cannot reveal a CDN, WAF, IdP, or managed-secret setting.

## State calibration

| Observation | State |
| --- | --- |
| Global middleware enforces a suitable control on every applicable route | Met |
| Applicable route explicitly disables or bypasses the control | Gap |
| Control is absent from repo but may be provided by a named CDN with no config available | Needs verification |
| App has no relevant browser/identity/upload/etc. surface | Not applicable |
| Package is installed but wiring is not found | Needs verification or Gap after repository-wide confirmation |

Partial implementation is normally Gap when the missing portion is materially relevant.
Describe what is covered and what remains rather than marking the whole domain absent.

## Priority calibration

Prioritize remediation, not fear:

- **Essential:** missing server-side authorization; exposed default credentials;
  plaintext/reversibly encrypted passwords; session cookies sent without Secure on an
  HTTPS production app; no CSRF boundary for cookie-authenticated mutations; secrets in
  public bundles; no runtime validation on privileged structured input.
- **Recommended:** CSP rollout for a browser app; tighter CORS; absolute session timeout;
  rate limiting on authentication and other expensive or enumerable endpoints, with
  request-size and result-set bounds; restrictive referrer/cache policy; secret
  rotation and scoped service identities; upload content verification.
- **Optional:** Permissions-Policy for unused capabilities; cross-origin isolation when
  the app benefits; higher-assurance key custody; additional security telemetry.

These examples are defaults, not immutable labels. Existing controls, exposure, user
impact, and operational cost can move priority. Never translate Essential directly to
Critical or imply exploitability.

## Source and version policy

- Pin the baseline as `OWASP ASVS 5.0.0` in every report.
- When using an exact ASVS identifier, cite it as `v5.0.0-x.y.z` and verify it against
  the official release. If exact lookup is unavailable, cite the ASVS chapter/domain and
  the implementation source instead of guessing an ID.
- Verify framework and library defaults against the installed version. Helmet, Next.js,
  authentication libraries, browsers, and standards evolve.
- Prefer normative/official sources; use community listicles only as discovery leads.
- Include the date of any live source verification when the user requests an auditable
  or compliance-oriented report.
- State whether the report assessed a selected control set or every applicable
  requirement at the chosen level.

## Primary sources

- [OWASP ASVS project and 5.0.0 release](https://owasp.org/www-project-application-security-verification-standard/)
- [OWASP ASVS 5.0.0 source](https://github.com/OWASP/ASVS/tree/v5.0.0)
- [OWASP Cheat Sheet Series — ASVS index](https://cheatsheetseries.owasp.org/IndexASVS.html)
- [OWASP guidance on ASVS vs. Top 10](https://owasp.org/Top10/2025/0x03_2025-Establishing_a_Modern_Application_Security_Program/)
