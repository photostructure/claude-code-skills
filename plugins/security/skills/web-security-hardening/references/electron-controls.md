# Electron Security Controls

Use this reference when an Electron application, Electron packaging configuration, or
packaged Electron resources are in scope. Apply OWASP ASVS to the application's web and
service surfaces; use Electron's current security checklist and official runtime,
packaging, and platform documentation for the desktop boundary.

## Contents

- [TL;DR](#tldr)
- [Profile the Electron application](#profile-the-electron-application)
- [Baseline and reporting](#baseline-and-reporting)
- [Content and process isolation](#content-and-process-isolation)
- [Preload and IPC capabilities](#preload-and-ipc-capabilities)
- [Navigation, windows, and embedded content](#navigation-windows-and-embedded-content)
- [Permissions, sessions, and downloads](#permissions-sessions-and-downloads)
- [Protocols, deep links, and shell integration](#protocols-deep-links-and-shell-integration)
- [Runtime versions and advisories](#runtime-versions-and-advisories)
- [Packaging, signing, updates, ASAR, and fuses](#packaging-signing-updates-asar-and-fuses)
- [Secrets, cookies, and local storage](#secrets-cookies-and-local-storage)
- [Common gotchas](#common-gotchas)
- [Priority calibration](#priority-calibration)
- [Primary sources](#primary-sources)

## TL;DR

1. Treat every renderer as potentially compromised, including renderers that normally
   load packaged local content.
2. Keep Node.js and OS capabilities in the main or a narrowly scoped utility process.
   Expose one validated operation per preload/IPC method, not general Electron APIs.
3. Keep context isolation and renderer sandboxing enabled; keep Node integration,
   insecure content, experimental features, and unnecessary webviews disabled.
4. Deny navigation, window creation, permissions, custom-protocol actions, downloads,
   deep links, and external URL schemes unless explicitly allowed.
5. Run a supported Electron major at the current patch/minor, ship a secure update path,
   sign release artifacts, and flip applicable package-time fuses.
6. Verify effective behavior for every window/view, child, session partition, target
   platform, and production package. One secure `BrowserWindow` proves only itself.

## Profile the Electron application

Establish this profile from code, lockfiles, and packager configuration:

- exact Electron version, bundled Chromium/Node versions, target operating systems,
  package formats, and whether source or a packaged artifact is under review;
- main, preload, renderer, worker, utility-process, extension, and native-addon entry
  points;
- every `BrowserWindow`, `WebContentsView`, `<webview>`, offscreen renderer, child
  window, and reusable window/view factory;
- packaged local, custom-protocol, remote, user-authored, third-party-frame, document,
  media, extension/plugin, and navigable content;
- all `contextBridge` and IPC operations and their native capabilities;
- default and custom sessions/partitions, permissions, downloads, cookies, certificate
  handling, proxy/network hooks, and custom protocols;
- deep links, file handlers, command-line/single-instance inputs, shell integration,
  update feeds, signing/notarization, fuses, ASAR integrity, crash reporting, and secret
  storage.

Record unresolved platform or packaged-behavior facts as Needs verification. Do not
assume a development run has the same fuses, signatures, resources, environment, or
session behavior as the distributed application.

## Baseline and reporting

For an Electron review, report two explicit baselines:

```text
Web/service baseline: OWASP ASVS 5.0.0 Level <1|2|3>, applicable web/API controls only
Desktop runtime baseline: Electron Security Checklist and official platform guidance,
verified on <date> against Electron <resolved version>
```

Call the result an **ASVS- and Electron-guided hardening review**. Never imply that ASVS
certifies the desktop runtime, installer, updater, OS entitlements, or code-signing
pipeline. Keep Electron controls in an **Electron Runtime** domain in the assessed-
control summary, using the normal Met / Gap / Not applicable / Needs verification
states and Essential / Recommended / Optional priorities.

Use live official Electron documentation for defaults and API semantics. Do not pin a
current version in this reference.

## Content and process isolation

Assess each renderer/window/view independently.

### Content trust

- Package executable application code locally where practical. Load remote resources
  only over authenticated secure transports and never grant remote content Node.js
  integration.
- Treat user-authored HTML/Markdown, remote responses, third-party frames, navigable
  links, extensions/plugins, and rendered media/documents as untrusted content even
  when the containing application is local.
- Apply the existing browser/XSS controls to renderer content. Electron raises the
  impact of renderer script execution when a native capability is reachable.

### Effective web preferences

Require or verify the equivalent effective behavior for all renderers:

```js
const win = new BrowserWindow({
  webPreferences: {
    preload: trustedPreloadPath,
    nodeIntegration: false,
    nodeIntegrationInWorker: false,
    nodeIntegrationInSubFrames: false,
    contextIsolation: true,
    sandbox: true,
    webSecurity: true,
    allowRunningInsecureContent: false,
    experimentalFeatures: false,
    webviewTag: false,
  },
})
```

Credit safe version defaults when verified, but prefer explicit settings for
security-critical factories where that prevents regression and makes intent testable.
Trace wrapper objects, spreads, environment branches, `webPreferences` mutation, child
window overrides, and production-only configuration before marking a control Met.

- Do not enable arbitrary Blink features. If a named feature is required, document its
  risk, constrain the affected renderer, and verify it against the installed version.
- Enforce a restrictive CSP for local/custom-protocol and remote pages. Avoid broad
  `unsafe-eval`, `unsafe-inline`, wildcard, `data:`, and remote script allowances unless
  narrowly justified. Do not set a custom scheme's `bypassCSP` privilege by default.
- Do not disable TLS or certificate validation globally. Review `certificate-error`,
  `setCertificateVerifyProc`, imported certificates, command-line switches, and proxy
  hooks for fail-open behavior and production leakage.

## Preload and IPC capabilities

Treat preload APIs and IPC handlers as a local privileged API surface, not plumbing.

### Preload bridge

- Expose one named method per operation through `contextBridge.exposeInMainWorld`.
- Do not expose `ipcRenderer`, `send`, `invoke`, `on`, Electron modules, Node globals,
  `require`, general channel selection, or arbitrary callback event objects.
- Wrap renderer callbacks so the `IpcRendererEvent` is removed before data crosses the
  bridge. Freeze/copy semantics do not make an overpowered API safe.
- Keep preload code small, packaged, reviewable, and free of remote/dynamic code. Bundle
  dependencies when sandboxed-preload constraints require it; do not disable sandboxing
  merely to regain broad Node module access.

Example narrow bridge:

```js
contextBridge.exposeInMainWorld('preferences', {
  read: () => ipcRenderer.invoke('preferences:read'),
  updateTheme: (theme) => ipcRenderer.invoke('preferences:update-theme', { theme }),
  onChanged: (callback) =>
    ipcRenderer.on('preferences:changed', (_event, value) => callback(value)),
})
```

### Privileged handlers

For every `ipcMain.on` and `ipcMain.handle`:

1. Validate `event.senderFrame` (or the installed version's equivalent) against the
   intended parsed protocol/origin and frame type. Do not rely on the top-level
   `WebContents` URL for subframe messages.
2. Validate payload shape, scalar types, lengths, allowed fields, identifiers, paths,
   URLs, and state transitions in the privileged process. TypeScript types disappear at
   runtime.
3. Apply user/tenant/object/action authorization where the operation touches remote or
   shared application data.
4. Translate renderer choices into fixed operations. Do not accept arbitrary commands,
   IPC channel names, filesystem roots, executables, shell arguments, SQL, or URLs.
5. Return only required data; redact secrets and internal errors. Verify replies go to
   the intended frame.
6. Bound expensive operations and repeated subscriptions. Clean up handlers/listeners
   when window lifecycles make stale privilege or cross-window delivery possible.

Sender validation does not replace payload validation. Sandboxing does not constrain a
main-process handler that intentionally performs the requested native operation.

## Navigation, windows, and embedded content

- Register `will-navigate` handlers on every navigable `WebContents`; deny by default or
  compare a parsed URL's exact protocol/origin/host and any required path.
- Register `setWindowOpenHandler` and deny unexpected windows. Avoid giving children
  more permissive preferences or preload capabilities than their opener.
- Treat redirects and reused/named windows as navigation. Test alternate mouse buttons,
  keyboard shortcuts, target names, child frames, and login/OAuth flows where applicable.
- Prefer an architecture without embedded third-party content. Electron currently
  recommends avoiding `<webview>` where possible; prefer `WebContentsView`, an `iframe`
  when its browser isolation is sufficient, or an external browser.
- If `<webview>` is required, leave `allowpopups` and Node integration disabled. Use
  `will-attach-webview` to validate the parsed `src`/partition, delete attacker-selected
  preload values, and force safe preferences before attachment.

Never use string prefixes as origin checks. For example,
`https://example.com.attacker.invalid` passes a naive
`startsWith("https://example.com")` test.

## Permissions, sessions, and downloads

- Configure both `setPermissionCheckHandler` and `setPermissionRequestHandler` for every
  session that can load content. Electron's session documentation requires both for
  complete permission handling.
- Deny by default; allow a named permission only for the exact requesting and embedding
  origins, frame type, user gesture, device/resource, and application workflow that need
  it. Use `details.requestingUrl`, `requestingOrigin`, `embeddingOrigin`, and related
  version-appropriate fields rather than only `webContents.getURL()`.
- Cover custom partitions. Protocol, webRequest, cookie, proxy, permission, certificate,
  and download configuration is session-specific.
- Review media, fullscreen, pointer/keyboard lock, clipboard, geolocation, notifications,
  HID/USB/serial/Bluetooth, filesystem, display capture, and open-external permissions
  according to the actual application surface.
- Control `will-download` for remote/untrusted content. Validate source/redirect chain,
  require an intended user gesture/workflow, avoid attacker-selected save paths, and do
  not automatically execute or shell-open completed downloads.

Mark controls Not applicable only after proving the application has no corresponding
content, session, or device surface.

## Protocols, deep links, and shell integration

### Custom application protocols

- Prefer a narrowly scoped custom protocol over privileged `file://` pages. Register only
  the privileges required: commonly `standard` and `secure`; avoid `bypassCSP`, broad
  service-worker, extension, or universal file privileges without a concrete need.
- Register a protocol on every session/partition that uses it.
- In `protocol.handle`, parse and decode the request once, map logical resource names to
  an allowlisted packaged root, and verify normalized path containment. Do not join an
  arbitrary URL path to the filesystem and assume `path.join` prevents traversal.
- Reject control characters and attacker-shaped response header names/values. Constrain
  redirects, MIME types, cache behavior, CORS, and CSP according to the served resource.
- Avoid `file://` for application pages. When it is unused, disable the fuse granting
  extra file-protocol privileges.

### Deep links and file handlers

Treat `open-url`, `open-file`, cold-start `process.argv`, and `second-instance` command
lines as untrusted OS-delivered input. Parse the complete URL/file, require the expected
scheme and named action, validate every parameter, and translate it to a fixed internal
operation. Do not pass it directly to `loadURL`, IPC, filesystem, updater, authentication,
or shell/process APIs.

### External URLs and shell APIs

- Send ordinary web links to `shell.openExternal` only after parsing and allowing exact
  `https:` origins/hosts required by the product. Reject credentials, unexpected ports,
  confusing hostnames, and non-web schemes unless a documented workflow requires them.
- Apply equivalent allowlists and user-intent checks to `openPath`, `showItemInFolder`,
  shortcuts, login items, notification actions, and platform scripts.
- Do not allow renderer input to select an executable, shell command, arbitrary file, or
  command-line switch.

## Runtime versions and advisories

- Resolve the installed Electron version from the lockfile or installed dependency.
  Record the bundled Chromium and Node versions where relevant.
- Require a supported stable major and the latest minor/patch on that line. Electron's
  normal policy supports the latest three stable major versions; support status changes
  on the published schedule.
- Check official Electron advisories and release notes during every review. Also account
  for applicable Chromium, Node.js, V8, image/media parser, and native-addon advisories.
- Include regression checks when the application uses advisory-sensitive boundaries,
  including rich Chromium/DOM values transferred through `contextBridge`, named-window
  reuse across trust levels, custom-protocol or `webRequest` response headers, subframe
  permission origins, and embedded-ASAR integrity validation.
- Prioritize an unsupported or known-affected runtime based on content exposure and the
  advisory's affected platform/feature. Do not import a package-audit severity without
  establishing applicability.
- Maintain an update cadence that can deliver urgent Electron/Chromium fixes quickly.
  Sandboxing limits blast radius but does not replace updating.

## Packaging, signing, updates, ASAR, and fuses

### Signing and updates

- Code-sign distributed Windows and macOS artifacts; notarize macOS releases where the
  distribution model requires it. Protect signing identities/tokens with scoped CI
  access and review release provenance.
- Use a fixed trusted HTTPS update origin and supported updater flow. Keep feed/channel
  selection out of renderer, deep-link, environment, and command-line control in
  production. Verify the platform/tooling's signature and downgrade behavior for every
  target package format.
- Separate development update behavior from packaged production behavior. Handle update
  failures without falling back to unsigned, insecure, or user-selected content.

### ASAR integrity

ASAR packaging does not encrypt code and does not by itself prevent modification. On
supported macOS and Windows builds, assess `EnableEmbeddedAsarIntegrityValidation`
together with `OnlyLoadAppFromAsar`, correct integrity metadata, and OS code signing.
Verify the exact Electron version against current advisories; these fuses are additional
integrity controls, not a reason to stop patching.

### Fuses

Read the packaged fuse state, not only source configuration. Decide each current fuse
against actual application behavior:

| Fuse | Normal hardening decision | Caveat |
| --- | --- | --- |
| `RunAsNode` | Disable when unused | Disabling breaks `child_process.fork`; prefer utility processes |
| `EnableNodeOptionsEnvironmentVariable` | Disable when production does not require it | Also affects `NODE_EXTRA_CA_CERTS`; verify enterprise TLS needs |
| `EnableNodeCliInspectArguments` | Disable in production | Include `SIGUSR1`/inspector workflows in compatibility tests |
| `EnableEmbeddedAsarIntegrityValidation` | Enable on supported packaged platforms | Requires compatible ASAR metadata and current Electron |
| `OnlyLoadAppFromAsar` | Enable with embedded ASAR validation | Ensure unpacked/native resources still work as designed |
| `EnableCookieEncryption` | Normally enable for sensitive cookies | One-way migration; test existing profiles and rollback behavior |
| `GrantFileProtocolExtraPrivileges` | Disable when application pages do not use `file://` | Migrate to a constrained custom protocol first |
| `LoadBrowserProcessSpecificV8Snapshot` | Evaluate for packaged builds | Verify packager/runtime compatibility and current guidance |
| `WasmTrapHandlers` | Keep the supported default absent a measured need | Disabling changes WebAssembly bounds-checking performance |

Use the current `@electron/fuses`/packager documentation because available fuses and
defaults evolve.

## Secrets, cookies, and local storage

- Keep high-value long-lived credentials out of renderer-owned `localStorage`,
  IndexedDB, caches, logs, crash metadata, and broadly readable files. Renderer XSS can
  read renderer-accessible storage.
- Store only the minimum secret material needed. Prefer OS-backed credential storage or
  Electron `safeStorage` from the main process, and keep decryption behind narrow IPC.
- Verify `safeStorage` semantics per platform. On Linux, detect unavailable or weak
  backends such as `basic_text`; do not label fallback ciphertext protected.
- Prefer the asynchronous `safeStorage` APIs when supported by the resolved Electron
  version; handle temporary unavailability and key rotation without insecure fallback.
- Enable the cookie-encryption fuse where applicable, but do not confuse at-rest cookie
  encryption with protection from a compromised renderer or same-user process.
- Redact tokens, paths, personal data, and renderer-supplied values from logs, crash
  annotations, telemetry, update logs, and diagnostic IPC replies.

## Common gotchas

- **Defaults are versioned.** An omitted preference may be safe on a modern release and
  unsafe on an old one. Resolve the version and every wrapper override.
- **Local is not automatically trusted.** Packaged code can render remote/user data or
  contain an XSS that reaches a preload capability.
- **Context isolation is not capability isolation.** A raw or overpowered bridge defeats
  the boundary while leaving `contextIsolation: true`.
- **Sandboxing stops at IPC.** The main process performs whatever privileged operation
  its handler authorizes.
- **Every `WebContents` and session counts.** Child windows, OAuth popups, views,
  webviews, offscreen renderers, custom partitions, and extensions often bypass the
  configuration shown on the primary window.
- **Frame identity matters.** `event.sender` identifies a `WebContents`; use the actual
  sender frame/origin for cross-frame authorization.
- **URL prefixes are not origins.** Parse and compare exact components.
- **`file://` is unusually privileged.** Prefer a constrained custom scheme and avoid
  granting custom schemes privileges they do not require.
- **Fuses are defense in depth.** An enabled `runAsNode` fuse is not remote RCE when the
  attacker must already execute arbitrary local commands.
- **ASAR is not encryption or signing.** Combine integrity validation with code signing
  and current patched Electron versions.
- **Developer security warnings are not a production control.** They depend on runtime
  naming/environment and do not replace tests or static review.
- **Electronegativity is a lead generator only.** Its open-source defaults and checks are
  no longer actively maintained; independently verify every hit against current Electron
  APIs and this skill's evidence/state model.

## Priority calibration

Normally treat these as **Essential** when applicable:

- remote/untrusted renderer content with Node integration, context isolation disabled,
  or sandboxing disabled;
- a raw/general preload bridge or privileged IPC operation without sender, payload, and
  authorization controls;
- unrestricted navigation/window/webview privilege inheritance or attacker-controlled
  shell/process execution;
- fail-open TLS validation or a production updater accepting an attacker-controlled,
  insecure, or unsigned source;
- an unsupported/known-affected runtime exposed to attacker-supplied active content.

Normally treat current-runtime adoption, restrictive permissions, custom-protocol
containment, CSP, signing, safe deep links, and secure updates as Essential or
Recommended based on exposure. Treat fuse tightening, ASAR integrity, cookie encryption,
diagnostic redaction, and optional platform defenses as Recommended/Optional unless the
threat model makes them boundary-critical.

Do not translate these priorities into vulnerability severities. If a complete exploit
path is found, move it to a separate vulnerability review.

## Primary sources

- [Electron Security](https://www.electronjs.org/docs/latest/tutorial/security)
- [Context Isolation](https://www.electronjs.org/docs/latest/tutorial/context-isolation)
- [Process Sandboxing](https://www.electronjs.org/docs/latest/tutorial/sandbox)
- [Inter-Process Communication](https://www.electronjs.org/docs/latest/tutorial/ipc)
- [`contextBridge`](https://www.electronjs.org/docs/latest/api/context-bridge)
- [`BrowserWindow`](https://www.electronjs.org/docs/latest/api/browser-window)
- [`<webview>`](https://www.electronjs.org/docs/latest/api/webview-tag)
- [`session`](https://www.electronjs.org/docs/latest/api/session)
- [`protocol`](https://www.electronjs.org/docs/latest/api/protocol)
- [Electron Fuses](https://www.electronjs.org/docs/latest/tutorial/fuses)
- [ASAR Integrity](https://www.electronjs.org/docs/latest/tutorial/asar-integrity)
- [`safeStorage`](https://www.electronjs.org/docs/latest/api/safe-storage)
- [Code Signing](https://www.electronjs.org/docs/latest/tutorial/code-signing)
- [Updating Applications](https://www.electronjs.org/docs/latest/tutorial/updates)
- [Electron release timelines](https://www.electronjs.org/docs/latest/tutorial/electron-timelines)
- [Electron security advisories](https://github.com/electron/electron/security/advisories)

<!-- Original synthesis of official Electron guidance and advisories. See ../ATTRIBUTION.md. -->
