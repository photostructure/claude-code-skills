<!-- Original synthesis. Adapted sources: cppreference (CC BY-SA 3.0/GFDL), SEI CERT standards prose (CC BY 4.0), and OpenSSF Compiler Hardening Guide (CC BY 4.0). The C++ Core Guidelines (custom license) were consulted, not relicensed. This file: CC BY-SA 4.0. See ../ATTRIBUTION.md. -->

# Build and Toolchain (node-gyp / binding.gyp)

## Contents

- [The three-file merge you actually compile](#the-three-file-merge-you-actually-compile)
- [binding.gyp anatomy](#bindinggyp-anatomy)
- [node-addon-api integration via node -p](#node-addon-api-integration-via-node--p)
- [NAPI_VERSION and ABI stability](#napi_version-and-abi-stability)
- [Exceptions: NAPI_CPP_EXCEPTIONS](#exceptions-napi_cpp_exceptions)
- [C++ standard selection per platform](#c-standard-selection-per-platform)
- [Symbol visibility](#symbol-visibility)
- [Artifact naming and symbol namespacing](#artifact-naming-and-symbol-namespacing)
- [Vendoring C sources](#vendoring-c-sources)
- [Conditions: OS and target_arch](#conditions-os-and-target_arch)
- [Cross-platform pitfalls](#cross-platform-pitfalls)
- [A complete, portable binding.gyp](#a-complete-portable-bindinggyp)
- [Primary sources](#primary-sources)

> Scope: *correct, portable* build wiring. Deep hardening flags live in `compiler-hardening.md`;
> sanitizer/analyzer wiring in `sanitizers-and-analysis.md`; prebuild/CI/release matrices in
> `ci-and-release.md`; language conventions in `modern-cpp-conventions.md`. Cross-link, don't duplicate.

## The three-file merge you actually compile

Your `binding.gyp` is **not** compiled in isolation. node-gyp's `lib/configure.js` injects two
more gyp files onto the command line, both populating `target_defaults`, so your target
**inherits** their settings unless you override:

1. **node-gyp's `addon.gypi`** — sets `type: 'loadable_module'`, `product_extension: 'node'`
   (output is `*.node`); defines `NODE_GYP_MODULE_NAME=<target_name>` (why
   `NODE_API_MODULE(NODE_GYP_MODULE_NAME, Init)` resolves); auto-adds Node/uv/V8 headers to
   `include_dirs` (**do not add Node headers yourself**); on Linux (non-`ia32`)/BSD/Android adds
   `cflags: ['-fPIC']`; on macOS sets `OTHER_LDFLAGS: ['-undefined dynamic_lookup']`; on Windows
   enables the delay-load hook so the `.node` loads under `node.exe`, `electron.exe`, etc.
2. **the target Node version's bundled `common.gypi`** (from the downloaded dev headers) —
   **version-sensitive.** Current `nodejs/node` `main` pins C++20, RTTI off, and exceptions off by
   default (`-fno-rtti -fno-exceptions -std=gnu++20` on Linux/BSD; `stdcpp20` /
   `ExceptionHandling: 0` on Windows; `GCC_ENABLE_CPP_EXCEPTIONS: 'NO'`, `CLANG_CXX_LIBRARY: 'libc++'`,
   `MACOSX_DEPLOYMENT_TARGET: '13.5'` on macOS). Node 18 headers pinned C++17.

**Consequences:** (a) by default your addon compiles with C++ exceptions and RTTI *disabled* — why
node-addon-api ships separate "except" targets; (b) the C++ standard is locked to the *target Node
version's* headers, so **pin it yourself** if you need a specific one; (c) macOS deployment target
and `libc++` come from here and vary by Node version — set them explicitly.

An addon is a `loadable_module` (shared object) resolved at `dlopen` time, so use `-fPIC` (already
added by addon.gypi), **not** `-pie`/`-fPIE`, which is wrong for a shared object. PIC/PIE hardening
reasoning lives in `compiler-hardening.md`.

## binding.gyp anatomy

Minimal shape — a `targets` array, each target with `target_name` and `sources`, placed next to
`package.json`:

```gyp
{ "targets": [ { "target_name": "my_addon", "sources": [ "src/addon.cc" ] } ] }
```

| Key | Meaning |
|---|---|
| `target_name` | Build/output name; addon.gypi also exposes it as `NODE_GYP_MODULE_NAME` for conventional use in `NODE_API_MODULE(...)` |
| `sources` | Files to compile |
| `include_dirs` | Header search paths (`-I`); Node/addon-api dirs are auto-added — don't repeat them |
| `defines` | Preprocessor macros → `-D` / `/D` |
| `cflags` / `cflags_c` / `cflags_cc` | Compiler flags: all langs / C only / **C++ only** |
| `ldflags` / `libraries` | Linker flags / libraries (`-`-prefixed entries pass through) |
| `dependencies` | Other gyp targets built/linked first (this is how node-addon-api is pulled in) |
| `conditions` | Conditional settings keyed on gyp variables (`OS`, `target_arch`, …) |
| `xcode_settings` / `msvs_settings` | Pass-through to Xcode/clang / MSBuild (`VCCLCompilerTool`, `VCLinkerTool`) |
| `configurations` | Per-`Debug`/`Release` settings |

**GYP syntax you must know:** `<!(cmd)` runs a shell command and substitutes stdout as a
**string**; `<!@(cmd)` splits stdout into a **list**; `<(var)` expands a string, `<@(var)` a list.
A key suffixed `!` **removes** matching inherited entries (e.g. `'cflags_cc!': ['-fno-exceptions']`);
a key suffixed `%` supplies a **default** only if unset; `+` prepends.

## node-addon-api integration via node -p

node-addon-api is a **header-only C++ wrapper** over the C Node-API. Include `"napi.h"`; **never**
include `node.h`, `v8.h`, `uv.h`, or `nan.h` — those carry no ABI-stability guarantee. Add
`"node-addon-api": "*"` to `package.json` dependencies, then depend on its modern gyp target:

```gyp
"dependencies": [
  "<!(node -p \"require('node-addon-api').targets\"):node_addon_api"
]
```

`node -p` runs Node **at configure time** and substitutes the result. The `.targets` mechanism
pulls in the include dir *and* the correct exception/define settings through the target's
`direct_dependent_settings` — you no longer hand-manage `include_dirs`. (Legacy `.include` is a
quoted path for `include_dirs`, `.include_dir` the raw path for CMake; prefer `.targets`.)
Straight-C addons (no C++) can build against **`node-api-headers`** instead, which exposes
`.include_dir`, the Windows `.def` files (`.def_paths`), and versioned `.symbols`.

## NAPI_VERSION and ABI stability

Node-API is **ABI-stable across Node.js major versions**: a module compiled against Node-API on
one major runs on later majors **without recompilation**, because it is insulated from V8/libuv
churn. This guarantee holds **only** while you use `napi.h` / `node_api.h` and avoid the V8/libuv
headers.

Pin the floor explicitly in `defines`:

```gyp
"defines": [ "NAPI_VERSION=9" ]
```

- `#define NAPI_VERSION N` restricts the surface to version N and earlier; on Node supporting
  Node-API 9+ it also **bakes the requested version into the addon at runtime**.
- The recommended `.targets` dependency resolves `node_addon_api.gyp`; that target does **not**
  import node-addon-api's separate `common.gypi`. With no explicit definition, the Node-API
  headers therefore use their default `NAPI_VERSION` of 8 rather than the build host's
  `process.versions.napi`. Pin it explicitly when the intended ABI floor is not 8 or when you
  want the contract visible in build configuration.
- Rule: **pick the lowest Node-API version that has the APIs you need.** One Node-API prebuild then
  covers every Node.js version at or above the matrix row (version-sensitive; matrix in the Node-API
  docs). That is the ABI-stability payoff for prebuilds — details in `ci-and-release.md`.

`fs-metadata` pins `NAPI_VERSION=9` (`fs-metadata: binding.gyp:17`); node-sqlite leaves it unpinned,
so its `.targets` integration compiles against the headers' implicit Node-API version 8 surface.
Both target Node >= 22 with node-addon-api 8.9.0.

## Exceptions: NAPI_CPP_EXCEPTIONS

Do **not** hand-set `-fno-exceptions` / `GCC_ENABLE_CPP_EXCEPTIONS` / MSVC `ExceptionHandling`.
Exception behavior is chosen **by which node-addon-api dependency target you name**, and it flips
both the preprocessor define and the per-platform compiler flag correctly:

| Dependency target | Define(s) added | Effect |
|---|---|---|
| `:node_addon_api` | `NODE_ADDON_API_DISABLE_CPP_EXCEPTIONS` | no-exceptions (matches inherited default) |
| `:node_addon_api_except` | `NAPI_CPP_EXCEPTIONS` | re-enables C++ exceptions (removes inherited `-fno-exceptions`) |
| `:node_addon_api_except_all` | `NAPI_CPP_EXCEPTIONS` + `NODE_ADDON_API_CPP_EXCEPTIONS_ALL` | as above, plus catch all native exceptions |
| `:node_addon_api_maybe` | `NODE_ADDON_API_ENABLE_MAYBE` | no-exceptions + type-safe `Maybe` API |

With `NAPI_CPP_EXCEPTIONS`, throwing `Napi::TypeError`/`Napi::Error` at a synchronous entry point
is caught by node-addon-api's wrapper and converted to a JS exception; a raw `std::runtime_error`
is **not** translated and aborts the process. node-sqlite builds with
`:node_addon_api_except` / `NAPI_CPP_EXCEPTIONS` (`node-sqlite: binding.gyp:19,24`); fs-metadata
instead hand-sets `NAPI_CPP_EXCEPTIONS` alongside the legacy `.gyp` dependency
(`fs-metadata: binding.gyp:13,16`). See
`napi-resource-model.md` (resource-review skill) for the exception-boundary discipline itself.

## C++ standard selection per platform

Because inheritance is version-dependent, pin the standard per compiler if you require one
(both reference projects target C++17):

```gyp
"cflags_cc": [ "-std=c++17" ],                                   # GCC/Clang (Linux/BSD)
"xcode_settings": {
  "CLANG_CXX_LANGUAGE_STANDARD": "c++17",                        # macOS; or "gnu++17"
  "CLANG_CXX_LIBRARY": "libc++"
},
"msvs_settings": {
  "VCCLCompilerTool": { "AdditionalOptions": [ "/std:c++17", "/Zc:__cplusplus" ] }
}
```

- MSVC uses `/std:c++17` (or the MSBuild `LanguageStandard: 'stdcpp17'`); add `/Zc:__cplusplus`
  so `__cplusplus` reports correctly (Node's `common.gypi` already sets it).
- Xcode standard values: `c++17`, `gnu++17`, `c++20`, `gnu++20`.
  (`fs-metadata: binding.gyp:158`, `node-sqlite: binding.gyp:76` both use
  `CLANG_CXX_LANGUAGE_STANDARD: c++17`.)
- If an inherited `-std=gnu++20` is present, the *last* `-std` on the GCC/Clang command line wins
  and gyp appends your target flags after `target_defaults`, so your explicit flag normally takes
  effect. To be certain, also remove the inherited one: `"cflags_cc!": ["-std=gnu++20"]`.

## Symbol visibility

Hiding non-exported symbols shrinks the addon, speeds load, and avoids symbol clashes /
interposition between multiple addons in one process. The Node-API registration symbol is exported
via its own macro attribute, so hidden-by-default visibility does **not** hide it.

```gyp
"cflags":    [ "-fvisibility=hidden" ],                                  # Linux/BSD, C and C++ TUs
"cflags_cc": [ "-fvisibility-inlines-hidden" ],                          # Linux/BSD, C++ only
"xcode_settings": {
  "GCC_SYMBOLS_PRIVATE_EXTERN": "YES"                                    # macOS == -fvisibility=hidden
}
# Windows: symbols are hidden by default (dllexport opt-in) — nothing to add.
```

GYP's `cflags` are common to both C and C++; `cflags_c` and `cflags_cc` add flags for only their
respective language. node-gyp's bundled `common.gypi` does **not** add a global
`-fvisibility=hidden` for addon `loadable_module` targets (the `visibility%: 'hidden'` variable is
V8's own build setting, not mapped onto addon `cflags`; version-sensitive — re-verify per Node
version). `node-sqlite` places `-fvisibility=hidden` in `cflags`, so it already reaches both its
vendored C and first-party C++ TUs on make-based POSIX builds (`node-sqlite: binding.gyp:65-73`);
its remaining C++-specific opportunity is `-fvisibility-inlines-hidden` in `cflags_cc`.

## Artifact naming and symbol namespacing

Two addons in one process can each statically link the *same* C library (e.g. `node:sqlite` and a
third-party SQLite addon, plus extensions like `sqlite-vec`) — a recipe for duplicate-symbol and
wrong-library-wins bugs. Defend on three axes:

- **Give the output a distinct `target_name`** to avoid artifact/package naming ambiguity, and
  conventionally register with `NODE_API_MODULE(NODE_GYP_MODULE_NAME, Init)` so source follows the
  build target. Current symbol-based Node-API registration does not require the macro's first
  argument to equal `target_name`, and prefixing that argument does not prevent native-library
  symbol collisions.
- **Namespace all C++** (`namespace photostructure::sqlite { … }` across every TU).
- **Hide the vendored library's symbols** so its `sqlite3_*` symbols are not exported to the
  process (the visibility section above) — this is *why* visibility matters here, not just size.

## Vendoring C sources

Compile a vendored C library (e.g. the SQLite amalgamation) **into the same target** as the addon,
and pin the version:

```gyp
"sources": [ "src/binding.cpp", "src/sqlite_impl.cpp", "src/upstream/sqlite3.c" ]
```

`node-sqlite` vendors `src/upstream/sqlite3.c` (~9.5 MB, SQLite 3.53.3) into the addon target
(`node-sqlite: binding.gyp:6-12`) and sets defensive compile-time defines on it —
`SQLITE_ENABLE_API_ARMOR` (validate C-API args, return `SQLITE_MISUSE` instead of UB;
`node-sqlite: binding.gyp:32-36`), `SQLITE_DQS=0`, `SQLITE_DEFAULT_FOREIGN_KEYS=1`,
`SQLITE_OMIT_DEPRECATED`, `SQLITE_OMIT_SHARED_CACHE` (`node-sqlite: binding.gyp:23-60`). Notes:
`cflags` apply to **both** C and C++, while `cflags_c` and `cflags_cc` add language-specific flags.
Put an intentional-fallthrough suppression in `cflags_c` if it is valid for all C TUs in the
target; if only the vendored source needs it, build that source as a separate target or use a
source-level suppression rather than weakening first-party files. **Pin the exact upstream
version** and record it. Hide the vendored symbols (visibility, above) so they don't leak into the
process.

## Conditions: OS and target_arch

`conditions` is a list of `['<expr>', {dict-if-true}, {dict-if-false}?]`. Gate on gyp variables,
not `process.*`:

- **`OS`** values are `"linux"`, `"mac"`, `"win"` (also `"freebsd"`, `"aix"`, `"android"`, …).
  Note **`"mac"` not `"darwin"`** and **`"win"` not `"win32"`** — the `darwin`/`win32` spellings are
  `process.platform` values used for prebuild folder names, not gyp `OS`.
- **`target_arch`** is what you build *for*: `"x64"`, `"arm64"`, `"ia32"`, `"arm"`. node-gyp sets it
  from `--arch` / `process.arch`.

```gyp
"conditions": [
  ["OS==\"mac\"",  { "xcode_settings": { "MACOSX_DEPLOYMENT_TARGET": "11.0" } }],
  ["OS==\"win\"",  { "defines": [ "WIN32_LEAN_AND_MEAN", "NOMINMAX" ] }],
  ["target_arch==\"arm64\"", { "defines": [ "ARM64_BUILD" ] }]
]
```

**Arch-specific compiler flags MUST be gated by `target_arch`** or the build fails with
"unknown argument" on the wrong arch. The canonical example: `-fcf-protection` (CET) is
**x86-only and hard-errors on arm64**, while `-mbranch-protection` (BTI/pac-ret) is
**arm64-only** — so each goes under its own `target_arch` condition
(`fs-metadata: binding.gyp:45-50` and `binding.gyp:51-57`). The actual hardening flag sets and the
per-arch MSVC split (`/guard:cf`, `/Qspectre`, `/HIGHENTROPYVA`, `/CETCOMPAT`, whose arch
applicability is version-sensitive — verify) live in `compiler-hardening.md`; this file only
establishes that the *mechanism* is `target_arch` conditions.

**Linker flag portability:** `-Wl,-z,relro`, `-Wl,-z,now`, `-Wl,-z,noexecstack` are **ELF/Linux-only**
(GNU ld / gold / lld on ELF). macOS `ld64` does not understand `-z` options — gate them under
`OS=="linux"`, never emit them on `mac`. (Details and full baseline in `compiler-hardening.md`.)

## Cross-platform pitfalls

**`target_arch is not defined` (gyp configure error).** A `conditions` expression references
`target_arch` where gyp hasn't defined the name. Guard with a defaulted variable so the name always
exists:

```gyp
{ "variables": { "target_arch%": "<(target_arch)" },
  "conditions": [ ["target_arch==\"x64\"", { /* … */ }] ] }
```

**MSVC `fatal error C1189: #error: "No Target Architecture"`.** Windows SDK `winnt.h` raises this
when no CPU-arch macro (`_AMD64_`, `_X86_`, `_ARM64_`, …) is defined at the point it's included —
typically because a header pulls in `<winnt.h>` **without `<windows.h>` first** (`windows.h` derives
the arch macro from the compiler's `_M_*` predefine). **Best fix: don't `#include <windows.h>`
directly in an addon.** `fs-metadata` includes it and pays for it — a `CL` env-var injection wrapper
plus a hand-rolled `windows_arch.h` re-deriving `_M_X64`/`_M_ARM64`/`_WIN64`
(`fs-metadata: src/windows/windows_arch.h:9-34`, `prebuildify-wrapper.ts:37-46`), whose own comment
concedes "if you don't include `<windows.h>` in your binding.gyp, this script is unnecessary"
(`fs-metadata: prebuildify-wrapper.ts:11-13`). `node-sqlite` sidesteps the whole class by not
including Windows headers directly. The global `CL` workaround is brittle (affects every compiler
invocation; duplicates arch logic in three places). If you *must* include `<windows.h>`, include it
first with `#define WIN32_LEAN_AND_MEAN` before it.

**`NOMINMAX` / `WIN32_LEAN_AND_MEAN`.** Node's `common.gypi` already defines `NOMINMAX` on Windows
(so `min`/`max` macros don't clobber `std::min`/`std::max`); define it yourself in any target built
*outside* that inheritance (a separate static-lib target, or CMake). `WIN32_LEAN_AND_MEAN` cuts
header bloat and avoids winsock include-ordering issues.

**macOS deployment target and libc++.** Set `MACOSX_DEPLOYMENT_TARGET` explicitly — don't rely on
the inherited default, which varies by Node version (currently `13.5`, historically much lower).
macOS/Clang uses **libc++** (`CLANG_CXX_LIBRARY: 'libc++'`), which Node's headers and node-addon-api
both select; `fs-metadata` pins `10.15` + libc++ (`fs-metadata: binding.gyp:159-161`). Linux/GCC
defaults to libstdc++; mixing standard libraries (or `_GLIBCXX_USE_CXX11_ABI` settings) across the
addon and its native deps causes link/runtime errors — keep one toolchain+stdlib per binary. A
glibc-built `.node` won't load on musl (Alpine); ship a `musl` prebuild variant (libc/arch prebuild
handling is in `ci-and-release.md`).

## A complete, portable binding.gyp

Uses `.targets`, pins C++17 (Node-version-independent), hides symbols on C++ TUs, sets the
deployment target, and stays no-exceptions by default (swap the dep target to
`:node_addon_api_except` to enable exceptions):

```gyp
{
  "variables": { "target_arch%": "<(target_arch)" },
  "targets": [
    {
      "target_name": "my_addon",
      "sources": [ "src/addon.cc" ],
      "dependencies": [
        "<!(node -p \"require('node-addon-api').targets\"):node_addon_api"
      ],
      "defines": [ "NAPI_VERSION=9" ],
      "cflags_cc": [ "-std=c++17", "-fvisibility=hidden", "-fvisibility-inlines-hidden" ],
      "conditions": [
        ["OS==\"mac\"", {
          "xcode_settings": {
            "CLANG_CXX_LANGUAGE_STANDARD": "c++17",
            "CLANG_CXX_LIBRARY": "libc++",
            "MACOSX_DEPLOYMENT_TARGET": "11.0",
            "GCC_SYMBOLS_PRIVATE_EXTERN": "YES"
          }
        }],
        ["OS==\"win\"", {
          "defines": [ "WIN32_LEAN_AND_MEAN", "NOMINMAX" ],
          "msvs_settings": {
            "VCCLCompilerTool": { "AdditionalOptions": [ "/std:c++17", "/Zc:__cplusplus" ] }
          }
        }]
      ]
    }
  ]
}
```

Layer `compiler-hardening.md`, `sanitizers-and-analysis.md`, and `ci-and-release.md` on top of this
skeleton. This skill runs as `/cpp:project-setup`; the resource-hygiene review runs as
`/cpp:resource-review`.

## Primary sources

- Node.js — Node-API (ABI stability, `NAPI_VERSION`, version matrix) — https://nodejs.org/api/n-api.html
- node-gyp — README, `addon.gypi`, `lib/configure.js` — https://github.com/nodejs/node-gyp
- nodejs/node bundled `common.gypi` (inherited C++ std / exceptions / RTTI / deployment target) — https://github.com/nodejs/node/blob/main/common.gypi
- node-addon-api — `doc/setup.md`, `doc/node-gyp.md`, `node_addon_api.gyp`, `noexcept.gypi`, `except.gypi`, `index.js` — https://github.com/nodejs/node-addon-api
- node-api-headers — README — https://github.com/nodejs/node-api-headers
- gyp-next — Input Format Reference (conditions, variables, expansion, `!`/`%` suffixes) — https://github.com/nodejs/gyp-next/blob/main/docs/InputFormatReference.md
- OpenSSF — Compiler Options Hardening Guide for C and C++ (arch-gated flags; ELF linker flags) — https://best.openssf.org/Compiler-Hardening-Guides/Compiler-Options-Hardening-Guide-for-C-and-C++.html
- SQLite — Compile-time options (`SQLITE_ENABLE_API_ARMOR`, `SQLITE_DQS`) — https://www.sqlite.org/compile.html
- Reference projects: `@photostructure/fs-metadata` (`/home/mrm/src/fs-metadata`) and `@photostructure/sqlite` (`/home/mrm/src/node-sqlite`) — cited inline by `file:line`.
