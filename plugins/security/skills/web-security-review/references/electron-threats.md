# Electron Vulnerability Review

Use this reference when the requested scope contains an Electron application,
packaged Electron resources, or Electron-specific APIs. Treat Electron renderers as
browser attack surfaces connected to native capabilities through preload scripts,
IPC, the main process, utility processes, and operating-system integration.

## Contents

- [Review posture](#review-posture)
- [Resolve the trust topology](#resolve-the-trust-topology)
- [Electron proof patterns](#electron-proof-patterns)
- [Version and advisory analysis](#version-and-advisory-analysis)
- [False-positive controls](#false-positive-controls)
- [Search starters](#search-starters)
- [Severity calibration](#severity-calibration)
- [Primary sources](#primary-sources)

## Review posture

Assume JavaScript execution in a renderer is possible only after proving an XSS,
compromised remote-content path, malicious navigation, untrusted extension/plugin, or
equivalent execution source. Then trace which native capability that renderer can reach.
Do not turn a missing hardening control into a vulnerability by itself.

Map these boundaries before judging a candidate:

```text
remote/user/deep-link/protocol input
        -> renderer or WebContents
        -> preload/contextBridge/IPC
        -> main or utility process
        -> filesystem, shell, process, secrets, devices, updater, or OS API
```

An Electron finding needs the same complete proof shape as any other finding:

- **Data-flow:** attacker-controlled input or code execution, the renderer/IPC/native
  route it follows, the privileged sink, and the resulting impact.
- **Exposure:** the real secret, file, device, or resource, how an attacker can observe
  it through Electron, and why it is sensitive.
- **Configuration:** the effective Electron/version/platform setting, the reachable
  attacker operation it affects, the boundary it removes, and the concrete impact.

## Resolve the trust topology

Establish all of the following from code and resolved dependencies:

1. The exact Electron version from the lockfile or installed package, not only a range
   in `package.json`; the target operating systems and packaging toolchain.
2. Main, preload, renderer, worker, utility-process, and extension entry points.
3. Every `BrowserWindow`, `WebContentsView`, `<webview>`, child window, offscreen
   renderer, and custom/session partition, including effective `webPreferences`.
4. Which contents are packaged local code, remote code, user-authored content, rendered
   documents/media, third-party frames, or navigable URLs.
5. Every capability exposed through `contextBridge`, `ipcRenderer`, `ipcMain`,
   `postMessage`, message ports, or custom protocols.
6. Deep-link, command-line, `open-url`, `second-instance`, file-open, drag/drop,
   clipboard, download, and custom-protocol inputs.
7. Signing, update, fuse, ASAR-integrity, secret-storage, and permission configuration
   when the claimed issue depends on packaged behavior.

Research beyond the report scope when a window factory, preload, shared IPC handler, or
packager config determines effective behavior. Report only locations within the user's
requested scope.

## Electron proof patterns

### Renderer-to-native capability escalation

Investigate these combinations, then prove the complete chain:

- attacker-controlled/remote content with `nodeIntegration`,
  `nodeIntegrationInWorker`, or `nodeIntegrationInSubFrames` enabled;
- renderer script execution with `contextIsolation` disabled and a privileged preload
  or Node/Electron object reachable in the main world;
- an unsandboxed renderer plus a reachable native capability or a version-specific
  Chromium/Electron exploit;
- a preload that exposes `require`, `process`, `Buffer`, `ipcRenderer`, `shell`, `fs`,
  `child_process`, a general RPC surface, or a function accepting unconstrained
  commands, paths, URLs, or channel names;
- `executeJavaScript`, `eval`, `Function`, or string-form timers fed by data an attacker
  controls.

`contextIsolation: true` is not proof that the bridge is safe. Trace every exposed
function. `sandbox: true` limits a compromised renderer, but an IPC method that asks the
main process to perform an unsafe operation crosses that sandbox intentionally.

### IPC authorization and data flow

Treat each `ipcMain.on` or `ipcMain.handle` registration as a privileged endpoint:

1. Identify every renderer/frame that can reach the channel.
2. Check `event.senderFrame` or equivalent frame identity against the intended parsed
   URL/origin and reject unexpected or destroyed frames.
3. Validate the structured-cloned payload's type, size, fields, paths, URLs, identifiers,
   and business authorization in the privileged process.
4. Trace validated values into filesystem, database, shell, network, device, credential,
   window, and application-state operations.
5. Check the reply path. `event.reply` returns to the sending frame, while
   `event.sender.send` targets the `WebContents` main frame; prove any cross-frame data
   exposure rather than assuming it.

Sender validation and argument validation solve different problems. A trusted renderer
can still be compromised, and an allowed operation can still accept an unsafe path or
object identifier.

### Navigation, child windows, and embedded contents

Trace attacker-shaped links, frame content, `window.open` arguments, and webview
attributes through:

- `will-navigate`, redirects, `loadURL`, `loadFile`, and window/view reuse;
- `setWindowOpenHandler`, especially `overrideBrowserWindowOptions` and any child with
  more permissive preferences or preload capabilities than its opener;
- `will-attach-webview`, including attacker-selected `src`, `preload`, `partition`,
  `allowpopups`, and web preferences;
- named windows and multiple top-level windows with different trust levels.

Use `new URL()` and exact allowed protocols/origins/hosts. A prefix test such as
`url.startsWith("https://example.com")` also accepts attacker hosts such as
`https://example.com.attacker.invalid`.

Report only when attacker-controlled content can navigate into a privileged context,
inherit a capability, disclose data, or cause another concrete boundary violation.

### Shell and operating-system integration

Investigate attacker-controlled values reaching `shell.openExternal`, `shell.openPath`,
`shell.showItemInFolder`, `child_process`, login-item configuration, native dialogs,
notifications, shortcuts, or platform scripts. Prove which URL scheme, file type,
executable, argument, or handler is selected on an affected platform.

A variable passed to `openExternal` is a lead, not a finding. Constants and values
restricted to an exact safe `https:` allowlist are normally safe. A generic allowlist
that admits `file:`, custom schemes, or OS command handlers can cross into native code.

### Custom protocols and deep links

Treat these as external request boundaries:

- `protocol.handle()` and privileged custom schemes receive attacker-shaped request
  URLs when untrusted content can request or navigate to them. Trace decoded path,
  query, and header data into filesystem paths, redirects, response headers, CSP, or
  cross-origin behavior. Prove path containment after decoding and normalization.
- `open-url`, `second-instance` command-line arrays, cold-start arguments, `open-file`,
  and registered protocol-client URLs can be supplied by another local application or
  a clicked link. Parse the complete URL and allow only named actions and parameter
  shapes before it reaches navigation, IPC, shell, filesystem, or authentication state.
- `registerSchemesAsPrivileged` options such as `bypassCSP`, service-worker support, or
  extra privileges are configuration candidates only when an attacker-reachable
  request gains a concrete capability.

### Permissions, sessions, downloads, and storage

- Verify both permission-check and permission-request paths for every session/partition.
  For subframes, use the requesting and embedding origin details appropriate to the
  installed version; top-level `webContents.getURL()` alone may identify the wrong
  principal.
- Trace device selectors, media/fullscreen/clipboard/filesystem permissions, downloads,
  and save paths from the requesting frame through the resulting native access.
- Treat cookies, renderer storage, crash annotations, logs, and `safeStorage` output as
  exposures only after identifying a real sensitive value and an attacker-observable
  path. On Linux, establish the selected storage backend before claiming encryption.

### Package, updater, and integrity boundaries

Investigate update feed construction, transport, signature verification, downgrade or
channel selection, signing configuration, writable installation paths, and Electron
fuses only when the attacker prerequisites and packaged behavior are known.

ASAR archives are packaging, not secrecy. ASAR integrity and code signing are separate
controls. A claimed ASAR-integrity bypass needs an affected Electron version, the
relevant fuses/platform, attacker write access to the installation, and a concrete code
loading result.

## Version and advisory analysis

Electron ships Chromium, Node.js, V8, and platform integration as part of the app. For
each version candidate:

1. Resolve the exact installed/package version and target platform.
2. Check whether its major line is supported and whether it is the latest patch/minor
   on that line.
3. Check official Electron advisories and release notes, plus applicable upstream
   Chromium/Node advisories.
4. Match the advisory's affected range, API/feature, platform, content source, and
   attacker prerequisites to the application.
5. Report only a reachable match. Otherwise put the missing reachability fact under
   Needs verification or record the version gap in a hardening review.

Give extra scrutiny to advisory-sensitive boundaries that have changed in recent
Electron releases: rich Chromium/DOM values transferred through `contextBridge`, named
`window.open` targets reused across different trust levels, attacker-shaped headers in
custom protocols or `webRequest`, subframe-origin attribution in permission handlers,
and embedded-ASAR integrity validation. These are search categories, not timeless
vulnerabilities; match the current advisory, affected version/platform, and reachable
application behavior before reporting them.

Do not pin a "current" Electron version in this reference. Electron supports the latest
three stable major lines, and both releases and advisories change frequently.

## False-positive controls

- An omitted explicit preference is not unsafe when the resolved Electron version's
  effective default is safe and no wrapper overrides it. Conversely, do not credit a
  modern default to an older version.
- `nodeIntegration: true`, `sandbox: false`, or `contextIsolation: false` on packaged,
  fixed local content is not automatically exploitable. Prove how attacker-controlled
  code reaches the renderer and what capability becomes available.
- Missing IPC sender validation is a hardening gap until an untrusted/compromised frame
  can reach a meaningful operation or sensitive reply.
- Disabled `runAsNode`/inspector fuses reduce post-compromise living-off-the-land risk.
  Their default state is not remote code execution when the claimed attacker must
  already run arbitrary local commands.
- Missing code signing, ASAR integrity, cookie encryption, or security warnings is not
  by itself an application vulnerability. Apply the applicable proof shape.
- Development windows, test fixtures, and dead/example configuration remain excluded.

If Electronegativity is installed, use it only as an optional search lead. Its open-source
rules and version defaults are no longer actively maintained and do not cover modern
IPC, `contextBridge`, `WebContentsView`, fuses, or current protocol APIs. Never import
its severity/confidence labels; vet every hit against this skill's proof gate and the
resolved Electron version.

## Search starters

Use these as discovery queries, never as report generators:

```bash
rg -n "BrowserWindow|BrowserView|WebContentsView|<webview|webPreferences|preload" .
rg -n "nodeIntegration|contextIsolation|sandbox|webSecurity|allowRunningInsecureContent" .
rg -n "contextBridge|ipcRenderer|ipcMain|senderFrame|MessageChannelMain|postMessage" .
rg -n "will-navigate|setWindowOpenHandler|will-attach-webview|loadURL|window.open" .
rg -n "openExternal|openPath|showItemInFolder|protocol.handle|registerSchemesAsPrivileged" .
rg -n "setPermission(Request|Check)Handler|will-download|second-instance|open-url|open-file" .
rg -n "@electron/fuses|FuseV1Options|asar|autoUpdater|setFeedURL|safeStorage" .
```

Also inspect indirect window factories, wrapper defaults, generated packager config,
lockfiles, and compiled preload bundles that text searches can miss.

## Severity calibration

- **Critical:** proven pre-auth renderer-to-host code execution or systemic compromise.
- **High:** host command/file access, credential theft, signing/update compromise, or a
  major native capability reached by a realistic compromised renderer.
- **Medium:** meaningful but constrained cross-window, origin, permission, file, or
  application-state boundary violation.
- **Low:** narrow demonstrable exposure or integrity effect with strong prerequisites.

Do not call ordinary renderer XSS host RCE unless the native-capability chain is proven.
State the target platform, content trust, user interaction, and local prerequisites that
drive severity.

## Primary sources

- [Electron Security](https://www.electronjs.org/docs/latest/tutorial/security)
- [Context Isolation](https://www.electronjs.org/docs/latest/tutorial/context-isolation)
- [Process Sandboxing](https://www.electronjs.org/docs/latest/tutorial/sandbox)
- [Inter-Process Communication](https://www.electronjs.org/docs/latest/tutorial/ipc)
- [`contextBridge`](https://www.electronjs.org/docs/latest/api/context-bridge)
- [`session`](https://www.electronjs.org/docs/latest/api/session)
- [`protocol`](https://www.electronjs.org/docs/latest/api/protocol)
- [Electron Fuses](https://www.electronjs.org/docs/latest/tutorial/fuses)
- [Electron release timelines](https://www.electronjs.org/docs/latest/tutorial/electron-timelines)
- [Electron security advisories](https://github.com/electron/electron/security/advisories)

<!-- Original synthesis of official Electron guidance and advisories. See ../ATTRIBUTION.md. -->
