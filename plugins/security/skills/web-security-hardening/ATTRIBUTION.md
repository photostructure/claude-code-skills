# Attribution

`web-security-hardening` is an original, JavaScript/TypeScript-focused synthesis of
security verification standards and primary implementation guidance. It is not
affiliated with or endorsed by the organizations listed below.

## Adapted sources

| Source | License | Use in this skill |
| --- | --- | --- |
| [OWASP Application Security Verification Standard 5.0.0](https://owasp.org/www-project-application-security-verification-standard/) | CC BY-SA 4.0 | The assurance-level backbone, control domains, and verification-oriented framing. |
| [OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/) | CC BY-SA 4.0 | Implementation guidance for browser controls, validation/encoding, identity, sessions, secrets, files, databases, deployment, and operations. |

The source material was narrowed to JavaScript/TypeScript web applications, rewritten,
combined, and reorganized into an applicability-aware review workflow and progressive
reference set. The skill adds the Met / Gap / Not applicable / Needs verification state
model, separates hardening priority from vulnerability severity, credits effective
framework defaults, and requires repository evidence for both satisfied controls and
gaps.

## Consulted primary sources

Official NIST, MDN, Node.js, framework, database, and library documentation is cited
next to the relevant reference sections. These sources were used to verify factual and
version-sensitive behavior; the surrounding expression is original. In particular:

- NIST SP 800-63B-4 informs current password and authenticator guidance.
- MDN documents browser behavior and deployment considerations for CSP and HTTP headers.
- Helmet and framework documentation inform library- and adapter-specific evidence.
- Redis, LevelDB, database, container, and platform documentation inform deployment
  checks without treating every missing defense-in-depth setting as a vulnerability.
- The `references/techniques/` cards synthesize official framework, library, and vendor
  documentation and public CVE advisories alongside OWASP guidance. Version-sensitive
  details are linked to primary sources so reviewers can re-check them against the
  installed version; only the facts needed to explain the control are summarized.

## Licensing

Because this skill adapts OWASP material licensed under **CC BY-SA 4.0**, the combined
skill is distributed under **CC BY-SA 4.0**. See [`LICENSE`](./LICENSE).

Composite adaptation Copyright (c) 2026 Matthew McEachen.
