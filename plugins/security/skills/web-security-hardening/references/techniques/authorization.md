<!-- OWASP/vendor-derived guidance. CC BY-SA 4.0. See ../../ATTRIBUTION.md. -->

# Object- and Function-Level Authorization

Enforce that the authenticated principal may act on *this* object and *this* operation — not merely that they are logged in.

## Object-level authorization (BOLA/IDOR)

The greppable tell is a handler that takes a client-supplied id and loads the record without any owner/tenant predicate: `findById(req.params.id)`, `WHERE id = :id` alone, `getObject({ id })`, or a route that returns another user's data when the id is swapped. Derive the principal from the session, never from the request body (see [../identity-sessions-and-secrets.md](../identity-sessions-and-secrets.md)).

- **Scope the query itself.** Constrain the data-access call by the authenticated principal in the same statement: `WHERE id = :id AND owner_id = :sessionUserId` (or tenant/org column), so a mismatched id returns zero rows instead of another user's record. Prefer deriving objects from identity where possible (e.g. account details from `sessionUserId`, no id exposed). Verify the ownership column and session accessor against the installed schema/framework — do not assume an ORM scopes by tenant implicitly.
- **Choose disclosure behavior deliberately.** `403` is the normal response when valid
  credentials are insufficient. RFC 9110 permits `404` when the service intends to conceal
  a forbidden resource's existence. In that threat model, keep the observable response
  consistent for missing and forbidden objects and avoid identifiers in the body; do not
  require byte-identical `404`s for every application.
- **Check every function that receives a client id.** Access to one object of a type does not grant access to all objects of that type. Audit every endpoint reading, updating, or deleting by id — not just the obvious GET. Unpredictable ids (random GUIDs) reduce enumeration but are not an authorization control on their own.

## Function/verb-level authorization (BFLA)

The greppable tell is a role/permission check attached to a path or the read handler while a sibling handler for another method omits it: `router.get('/x', requireAdmin, ...)` next to `router.post('/x', handler)` with no guard, or middleware mounted on `GET` routes only. Attackers pivot from an authorized `GET /api/invites/{id}` to an unguarded `POST /api/invites/new`.

- **Authorize per method, not per path.** Verify the role/permission inside (or on) each verb's handler — `GET`, `POST`, `PUT`, `PATCH`, `DELETE`. Do not assume an endpoint is "regular" or "admin" from its URL; privileged and public routes commonly share a base path. Confirm which methods your router's path-level middleware actually covers against the installed router version.
- **Consolidate privileged endpoints under one enforced control.** Route admin/privileged operations through a single authorization module (or a base admin controller/guard that all privileged controllers inherit) invoked from every business function, rather than ad-hoc checks scattered per handler. Centralization makes coverage auditable and closes copy-paste gaps.

## Deny-by-default policy gateway

The greppable tell is authorization expressed as scattered `if (user.role === 'admin')` conditionals with no catch-all, so a newly added route ships with no policy and is silently open.

- **Fail closed for any route lacking an explicit policy.** The enforcement mechanism should deny all access by default and require an explicit grant per function; a route with no attached policy must be rejected, not permitted. Prefer a framework/global control applied application-wide over per-method opt-in. Validate permissions on every request regardless of origin (AJAX, server-side, internal) — "already authenticated" is not authorization. Verify the deny-by-default behavior of your policy layer against its installed version; some middlewares default to allow when no matching rule is found.

See ../../ATTRIBUTION.md for licensing.

## Primary sources

- [OWASP Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html)
- [OWASP API1:2023 Broken Object Level Authorization](https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/)
- [OWASP API5:2023 Broken Function Level Authorization](https://owasp.org/API-Security/editions/2023/en/0xa5-broken-function-level-authorization/)
- [OWASP WSTG: Testing for Bypassing Authorization Schema](https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/05-Authorization_Testing/02-Testing_for_Bypassing_Authorization_Schema)
- [RFC 9110 §15.5.4 — 403 Forbidden](https://www.rfc-editor.org/rfc/rfc9110.html#section-15.5.4)
