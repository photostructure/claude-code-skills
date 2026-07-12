<!-- Original synthesis. Adapted sources: cppreference (CC BY-SA 3.0/GFDL), SEI CERT standards prose (CC BY 4.0), and OpenSSF Compiler Hardening Guide (CC BY 4.0). The C++ Core Guidelines (custom license) were consulted, not relicensed. This file: CC BY-SA 4.0. See ../ATTRIBUTION.md. -->

# CI and Release for Native Addons

Cross-platform CI, prebuilt binaries, and supply chain for Node.js native addons
(node-addon-api / Node-API + node-gyp) and general C++17. Applicability-aware: an addon
is a **shared/loadable module**, not an executable, which changes several release choices
below. See `compiler-hardening.md` for flag rationale, `sanitizers-and-analysis.md` for
sanitizer invocation, and the resource-review skill's `napi-resource-model.md` for the
N-API teardown model CI must exercise.

## Contents

- [The build and test matrix](#the-build-and-test-matrix)
- [Node-API and ABI stability](#node-api-and-abi-stability)
- [Shipping prebuilt binaries](#shipping-prebuilt-binaries)
- [glibc floor and musl prebuilds](#glibc-floor-and-musl-prebuilds)
- [arm64: native runners vs emulation](#arm64-native-runners-vs-emulation)
- [macOS universal binaries and deployment target](#macos-universal-binaries-and-deployment-target)
- [Windows architecture specifics](#windows-architecture-specifics)
- [Sanitizer, Valgrind, and analysis jobs that gate](#sanitizer-valgrind-and-analysis-jobs-that-gate)
- [Native code coverage](#native-code-coverage)
- [Release-build hardening and its platform applicability](#release-build-hardening-and-its-platform-applicability)
- [Publishing with OIDC and provenance](#publishing-with-oidc-and-provenance)
- [Supply chain for vendored C](#supply-chain-for-vendored-c)
- [CI gaps to check for](#ci-gaps-to-check-for)

## The build and test matrix

The addon target space is a cross-product, not a list. Enumerate it explicitly:

| Dimension | Values |
|---|---|
| OS | `linux` (glibc), `linux` (musl/Alpine), `darwin`, `win32` |
| CPU | `x64`, `arm64` (also `ia32`/`armv7` for some projects) |
| libc (Linux only) | glibc and musl are **distinct, non-ABI-compatible targets** |
| Runtime/ABI | Node-API version (stable across Node majors) **or** per-major `NODE_MODULE_VERSION` |

Node-API collapses the runtime dimension: one prebuild per `(os, arch, libc)` serves
every supported Node major (see next section). For a V8/NAN addon you instead need one
binary per Node major. The Node-version axis then becomes a **test** axis — does the
prebuild load and pass on each Node major — not a build axis.

GitHub Actions matrix skeleton:

```yaml
strategy:
  fail-fast: false          # a release matrix must not cancel siblings when one leg fails
  matrix:
    os: [ubuntu-24.04, ubuntu-24.04-arm, macos-15, windows-2022, windows-11-arm]
    node: [22, 24, 26]
```

- `fail-fast: false` is mandatory for release matrices; the default (`true`) cancels
  in-progress legs and hides which platforms actually broke.
- `include` adds/annotates combinations and is processed **after** `exclude`.
- Runner labels and hosted-arch availability change over time `[verify current runners]`.

Reference matrix: `fs-metadata: .github/workflows/build.yml` builds macOS x64
(`macos-15-intel`) + arm64, Windows x64 + arm64 (`windows-11-arm`), Linux glibc x64/arm64,
and Linux musl x64/arm64 (Alpine via Docker `--platform`), then fans tests over those
OSes x Node {22,24,26}.

## Node-API and ABI stability

A Node-API addon compiled against Node-API version *n* loads on every Node.js release
supporting version *n* and all later releases, including future majors, with no recompile.
This is the single highest-leverage release decision: **prefer Node-API** so release
complexity is `(os x arch x libc)`, not `(os x arch x libc x Node-major)`.

- Bake the requested version at compile time with `NAPI_VERSION=X` (a.k.a.
  `NODE_API_VERSION`). If unset it **defaults to 8**. `fs-metadata` explicitly pins
  `NAPI_VERSION=9`; node-sqlite relies on the headers' implicit version 8 surface because its
  `.targets` dependency does not import node-addon-api's separate `common.gypi`.
- Node-API versions are additive, but moving e.g. v9->v10 may require source changes
  `[version-sensitive: verify per target]`.
- Build `NAPI_CPP_EXCEPTIONS` if entry points throw `Napi::` errors; a raw `std::exception`
  crossing the C ABI is not translated and aborts the process (see `napi-resource-model.md`).

## Shipping prebuilt binaries

npm has no built-in binary distribution; the ecosystem layers conventions on top. Two are
current; the third is legacy.

**1. Bundle-all — `prebuildify` + `node-gyp-build` (recommended by the tooling).**
`prebuildify` writes every platform binary into `prebuilds/<platform>-<arch>/` inside the
published tarball; `node-gyp-build` is both the `install` script and the runtime loader that
selects the matching `.node`, falling back to a source build.

```json
{ "scripts": { "install": "node-gyp-build" } }
```
```js
const binding = require('node-gyp-build')(__dirname)
```

Key `prebuildify` flags: `--napi` (one binary across Node/Electron versions), `--strip`
(strip symbols), `--tag-libc` (encode glibc/musl in the filename), `--arch x64+arm64`
(request a macOS fat build). Loader resolution reads `prebuilds/<platform>-<arch>/<tags>.node`;
libc is detected as `process.env.LIBC` if set, else `musl` when `/etc/alpine-release` exists,
else `glibc`. Publish must include `prebuilds/`; force a source build with
`npm install --build-from-source`. Reference: `fs-metadata: scripts/prebuildify-wrapper.ts`
runs `prebuildify --napi --tag-libc --strip`.

**2. optionalDependencies platform packages (esbuild/sharp/SWC pattern).** Publish each
binary as its own scoped package and list them as `optionalDependencies` of a thin wrapper.
Each platform package filters install with `package.json` fields `os`, `cpu`, and `libc`
(the `libc` field is honored **only when `os` is `linux`**). npm installs an optional dep
only when host `os`/`cpu`/`libc` match and does not fail the install when one is skipped.
`node-gyp-build-optional-packages` automates the runtime resolution. Smaller per-user
download; more sub-packages to manage. Caveat: `--no-optional` or a stale lockfile can omit
the platform package, producing a runtime "cannot find module" — smoke-test a clean install
on each target.

**3. Download-on-install — `prebuild`/`prebuild-install`, `node-pre-gyp` (legacy).** Fetch a
single matching binary from a release host at install time. Adds a network dependency and a
supply-chain surface; `node-pre-gyp` does **not** distinguish musl from glibc by default and
can fetch a non-working binary on Alpine. Prefer 1 or 2.

## glibc floor and musl prebuilds

glibc and musl are different libc implementations and are **not ABI-compatible**; a
glibc-linked `.node` may fail to load on Alpine and vice-versa. Two consequences:

- **Ship separate prebuilds per libc**: at minimum glibc + musl for each of x64 and arm64.
  Tag them (`--tag-libc`) or set the `libc` package.json field so the loader/npm picks
  correctly at install time.
- **Build glibc prebuilds on the OLDEST glibc you support**, inside a container, so the binary
  runs forward on newer glibc. Building on a newer glibc silently pulls in newer versioned
  symbols (e.g. `GLIBC_2.34`) that hard-fail on older hosts. Reference:
  `fs-metadata: scripts/prebuild-linux-glibc.sh` builds in a **Debian 11 (Bullseye, glibc 2.31)**
  container so binaries load on Ubuntu 20.04+ and modern Node Docker images, with an in-file
  table of glibc-per-distro documenting why.
- Build **musl prebuilds on Alpine** (native or emulated container) — a separate leg, not a
  flag on the glibc leg.
- Static-linking `libstdc++`/`libgcc` reduces libc-version coupling but does not erase a
  syscall/ABI assumption; validate, don't assume it makes one binary serve both families.

## arm64: native runners vs emulation

Prefer, in order: **native arm64 runner -> cross-compile -> QEMU emulation**.

- Native hosted arm64 runners for Linux and Windows became generally available for public
  repos (2025-08-07); macOS hosted runners are arm64 by default `[verify current runners]`.
  With native runners you build each `(os, arch)` leg natively and avoid emulation for common
  desktop/server targets.
- **Cross-compile** with node-gyp `--arch <arch>` (sets `target_arch`; `binding.gyp` branches
  on `target_arch`/`OS`). node-gyp downloads the target's Node headers. A cross **toolchain**
  additionally needs the target compiler (`CC`/`CXX`, e.g. `aarch64-linux-gnu-g++`) and
  arch flags on the target cflags only.
- **QEMU + binfmt_misc** (Docker Buildx) remains the fallback for arches without a native
  runner — notably **musl arm64** and niche arches: `docker/setup-qemu-action`, then
  `docker buildx build --platform linux/amd64,linux/arm64`. Emulation is much slower than
  native, especially for compile-heavy work; use it as a fallback, not the default.

## macOS universal binaries and deployment target

- A universal binary is one Mach-O with multiple arch slices. Produce it by compiling with
  both `-arch x86_64 -arch arm64` in one clang invocation, or per-arch then
  `lipo -create a b -output universal`. In `prebuildify`, `--arch x64+arm64` requests the fat
  build but only forwards the first arch to node-gyp — ensure `binding.gyp` actually passes
  both `-arch` values via `xcode_settings`/`OTHER_CFLAGS`, or clang emits a single-arch binary.
- `MACOSX_DEPLOYMENT_TARGET` sets the **minimum** macOS version. Pin it to the oldest OS you
  support so the binary loads on older systems; too-new a value raises the floor.
  `fs-metadata` pins `MACOSX_DEPLOYMENT_TARGET: "10.15"` and `CLANG_CXX_LIBRARY: libc++` in
  `binding.gyp`.
- On an arm64 macOS runner clang cross-targets `x86_64` natively, so one runner emits a
  universal or an arm64+x64 pair with no separate Intel runner.

## Windows architecture specifics

- Use MSVC predefined macros for arch detection, not GCC's: `_M_X64`, `_M_ARM64`, `_M_IX86`,
  `_M_ARM64EC`; `_WIN32` is defined on all Windows targets, `_WIN64` on 64-bit.
- The node-gyp **delay-load hook** (`win_delay_load_hook.cc`) is enabled by default so a `.node`
  resolves imported symbols against the running process image regardless of the host exe's name;
  needed because Windows addons link against the host executable's exports, not a shared libnode.
- MSVC per-arch hardening (both reference projects split this correctly in `binding.gyp`
  `conditions`): x64 adds `/Qspectre`, `/HIGHENTROPYVA`, `/CETCOMPAT`; ARM64 omits them.
  Two of those three omissions rest on a **myth** — verify before copying:
  - `/CETCOMPAT` **is** correctly x64-only (Microsoft: "only applicable to the x64
    architecture"): CET shadow-stack is an Intel/AMD hardware feature; ARM64 relies on
    hardware PAC/BTI instead. Omit it on ARM64.
  - `/Qspectre` is **not** x64-only. Microsoft documents it for processors from "Intel, AMD,
    and ARM," and Spectre-mitigated libraries ship for x86/x64, ARM, and ARM64. It is a valid
    (and advisable) ARM64 flag; omitting it there under-hardens the ARM64 build.
  - `/HIGHENTROPYVA` is **not** x64-only. It is "enabled by default for 64-bit executable
    images" and is only ignored for 32-bit images — so it already applies to ARM64. Explicitly
    passing it on ARM64 is harmless; claiming it is Intel-specific is wrong.
  - `/guard:cf` (CFG), `/sdl`, `/DYNAMICBASE` (ASLR), `/NXCOMPAT` (DEP) apply to both arches.
- Windows builds need Visual Studio / VC++ Build Tools and a compatible Python; Python >= 3.12
  requires node-gyp >= v10 `[version-sensitive]`.

## Sanitizer, Valgrind, and analysis jobs that gate

These are debugging tools run in CI, **not shipped artifacts**; run them primarily on
Linux glibc x64. The recurring failure is a job that runs but never gates. Three rules:

**1. Make a zero-exit report still fail the run.** Sanitizers and Valgrind can print findings
while the process exits 0 (e.g. Node swallows the exit code, or a leak is only "reachable").
- ASan/UBSan: compile+link with `-fsanitize=address` (`-O1 -g -fno-omit-frame-pointer`
  `-fno-optimize-sibling-calls` for readable stacks); add `-fsanitize=undefined` with
  `-fno-sanitize-recover=all` so UB **aborts** instead of logging. LeakSanitizer is part of
  ASan and on by default on **Linux**; opt-in via `ASAN_OPTIONS=detect_leaks=1` on macOS x64;
  **unsupported on macOS arm64** — `fs-metadata: scripts/macos-asan.sh:34-38` disables it there
  to avoid an ASan startup abort.
- Valgrind Memcheck (no recompile): `--leak-check=full` **plus `--error-exitcode=<n>`** so any
  error yields a nonzero exit — without it Valgrind preserves the program's own exit code.
- Node itself isn't built with ASan, so `LD_PRELOAD` the ASan runtime to initialize before
  Node `dlopen`s the addon (`fs-metadata: scripts/sanitizers-test.sh:56-71`), then
  **post-process the output** and fail on any first-party finding even at exit 0
  (`fs-metadata: scripts/sanitizers-test.sh:97-101` -> `analyze-sanitizer-output.ts`;
  Valgrind pass-gate greps in `valgrind-test.sh:63-76`).

**2. `_FORTIFY_SOURCE` must be OFF under AddressSanitizer.** OpenSSF explicitly advises against
`_FORTIFY_SOURCE` in sanitizer builds (false positives/negatives). If the release cflags define
it, the sanitizer job must strip it: prepend `-U_FORTIFY_SOURCE` (also fixes the
distro-predefined redefinition warning) and rebuild with `-D_FORTIFY_SOURCE=0`. This is a real
gap in `fs-metadata` (fortify is added unconditionally, including under ASan) — do not copy it.

**3. Suppress only third-party noise, narrowly.** You need V8/Node/ICU suppressions
(LSan `suppressions=`, UBSan `-fsanitize-ignorelist=`, Valgrind `--suppressions=`). Keep them
specific: blanket wildcards like `leak:napi_*` / `leak:Napi::` silence essentially all addon
allocations that touch N-API and can mask a genuine first-party leak (a node-sqlite gap).
Prefer object-file/`v8::`/`icu_` scoped patterns.

**clang-tidy / static analysis must gate too.** Run it on **every** OS whose sources ship —
per-OS file exclusion means a POSIX-only lint matrix never analyzes `src/darwin/*`
(`fs-metadata: build.yml:25-26`, `clang-tidy.ts:324-341` leaves the darwin tree, its most
RAII-dense code, unlinted). Set `WarningsAsErrors` on the high-signal ownership checks
(`bugprone-use-after-move`, `cppcoreguidelines-special-member-functions`,
`clang-analyzer-cplusplus.NewDeleteLeaks`) so findings fail CI; a config with
`WarningsAsErrors: ''` reports but never blocks (both reference projects ship advisory-only
POSIX configs). Do not fabricate check names — verify each against the clang-tidy check list.

## Native code coverage

Pick one toolchain and stay consistent; compile with `-O0 -g` so counters map to source.

- **gcov / gcovr**: compile+link with `--coverage` (= `-fprofile-arcs -ftest-coverage`); running
  the instrumented binary emits `.gcda`; aggregate with `gcovr` or `lcov`+`genhtml`.
- **Clang source-based**: compile with `-fprofile-instr-generate -fcoverage-mapping` (pass
  `-fprofile-instr-generate` at link too); run produces `default.profraw` (`LLVM_PROFILE_FILE`);
  merge with `llvm-profdata merge -sparse`, report with `llvm-cov show|report|export`.

Addon wrinkle: coverage counters live in the `.node`; flushing happens at process `exit`. A
test runner that calls hard `process.exit()` can skip atexit handlers and drop counts — prefer
a clean runner exit.

## Release-build hardening and its platform applicability

Full flag rationale is in `compiler-hardening.md`; here only the applicability rules that bite
in a **cross-platform release matrix**. A wrong flag on the wrong target is a build break, not
a warning.

- **A `.node` is a shared/loadable module.** Use `-fPIC` (`-shared`), **not** `-fPIE`/`-pie` —
  the PIE flags are for main executables and do not apply to an addon. (Both reference projects
  correctly use `-fPIC`.)
- **`-fcf-protection` is x86-only**; it hard-errors ("unknown argument"/unsupported) on arm64.
  **`-mbranch-protection=standard` (PAC/BTI) is arm64-only.** Gate each under its `target_arch`
  condition so the other arch does not fail to build (`fs-metadata: binding.gyp:45-50` for x64
  cf-protection, `:51-57` for arm64 branch-protection).
- **`-Wl,-z,relro`, `-Wl,-z,now`, `-Wl,-z,noexecstack` are ELF/GNU-ld (Linux) only.** macOS's
  ld64 does not understand `-z` and errors on them — scope these linker flags to a Linux
  condition, not "POSIX." (`-fstack-protector-strong`, `-fstack-clash-protection`,
  `-D_FORTIFY_SOURCE`, `-D_GLIBCXX_ASSERTIONS`/`-D_LIBCPP_HARDENING_MODE=...` apply to both
  Linux and macOS.)
- **`_FORTIFY_SOURCE` needs `-O1`+**; level 3 needs GCC 12 / Clang 9. An old glibc-floor image
  (e.g. GCC 10 on Bullseye) may only support `=2` — `[version-sensitive: verify toolchain]`.
- **Symbol visibility on a coexisting addon**: an addon can share a process with other addons
  (e.g. this SQLite addon plus `node:sqlite`), so hide internal symbols. Apply
  `-fvisibility=hidden` in `cflags` on Linux, where it reaches both C and C++ TUs, and add
  `-fvisibility-inlines-hidden` in `cflags_cc`; node-gyp's `common.gypi` does not add these for
  addon `loadable_module` targets. node-sqlite already supplies the common visibility flag
  (`binding.gyp:65-73`). macOS uses `GCC_SYMBOLS_PRIVATE_EXTERN: YES`; Windows hides by default.
  Also give the artifact a distinct target name and namespace all C++ code. Target naming keeps
  package artifacts unambiguous; hiding/namespacing native symbols is what prevents clashes with
  other SQLite addons in one process.

## Publishing with OIDC and provenance

Publish from CI with short-lived identity, not a long-lived npm token.

- Grant the job `permissions: { id-token: write }` and use npm's **OIDC trusted publishing**
  so the runner mints a short-lived credential instead of storing an `NPM_TOKEN`
  `[version-sensitive: verify current npm trusted-publishing support]`.
- Add `npm publish --provenance` to attach a signed provenance attestation (Sigstore) tying the
  package to the source commit and CI run; supported when publishing from a recognized CI
  (GitHub Actions/GitLab). Reference: `fs-metadata: .github/workflows/build.yml:268-327` uses
  `id-token: write` + `--provenance`.
- Ensure the published tarball actually contains `prebuilds/` (or that all platform sub-packages
  publish) — a missing prebuild silently degrades users to a source build or a load failure.
- Separate build/test from the release/publish job; do not expose publishing credentials to
  fork PRs or contributor-controlled build steps.
- **Smoke-test a clean `npm install` on each OS/arch/libc** after publish — the classic failures
  (optional-dep skipped, wrong libc prebuild, missing folder) only appear on a fresh install.

## Supply chain for vendored C

Many addons vendor a C dependency as a single-file **amalgamation** (canonical example:
SQLite's `sqlite3.c`, which node-sqlite vendors at `src/upstream/sqlite3.c`, SQLite 3.53.3,
compiled into the same target — `binding.gyp:6-12`). Single-TU builds let the compiler optimize
across the whole library (SQLite reports 5-10% over separate files), which is why vendoring
beats linking an unknown system version. Hygiene rules, applicable to any vendored native dep:

- **Pin an exact version.** SQLite's filenames encode it: `3.X.Y` -> `3XXYY00`
  (e.g. `sqlite-amalgamation-3530300.zip` = 3.53.3).
- **Verify a strong checksum against a value stored in your repo**, not just size. SQLite's
  download page publishes a per-product CSV whose hash column is **SHA3-256** (FIPS-202); record
  the pinned version + expected SHA3-256 in-tree and fail the build on mismatch.
- **Vendor in-tree (or fetch reproducibly with the pinned hash)** so builds are hermetic and do
  not trust an external host at build time.
- **Gate updates behind review + full CI.** Do not auto-update vendored C at build time; bump
  version + hash in one reviewable commit and re-run the whole sanitizer/coverage matrix.
- **Record each dependency's license.** SQLite is public domain; other vendored C may carry
  attribution/copyleft obligations.
- **Harden the install/CI surface**: set `ignore-scripts=true` in `.npmrc` (contributors opt in
  once for the native build), SHA-pin third-party GitHub Actions by commit digest (e.g. via
  `pinact`), and run advisory/code scanning (CodeQL `c-cpp` manual build). Reference:
  `fs-metadata: CONTRIBUTING.md:11-22` (ignore-scripts rationale) and its SHA-pinned workflows.

## CI gaps to check for

Audit an existing addon's CI for these real, recurring holes (all observed in the reference
projects and applicability-aware — flag only what applies to the platforms actually shipped):

- **Static analysis that never gates**: `WarningsAsErrors: ''` and/or a job that reports but
  passes; findings accumulate with no enforcement.
- **A whole OS's source never linted**: per-OS file exclusion + a lint matrix missing that OS
  (darwin in `fs-metadata`) means its most delicate resource code is never analyzed.
- **`_FORTIFY_SOURCE` left on under ASan**, producing false results in the sanitizer job.
- **Over-broad suppressions** (`leak:napi_*`, `leak:node_modules/`) that mask first-party leaks.
- **Tests skipped on the platform where they matter**: Windows handle/thread and resource-leak
  suites skipped on Windows CI (`fs-metadata`: `worker_threads.test.ts`, `thread_safety.test.ts`,
  `windows-memory-check.test.ts`, `windows-resource-security.test.ts`, with `maxWorkers: 1`) —
  exactly where `HANDLE`/`FindClose` leaks and thread-pool DLL pinning need verification. Port
  such suites to a standalone runner rather than silently dropping coverage.
- **Under-hardened ARM64 Windows** from copying the `/Qspectre`/`/HIGHENTROPYVA` "x64-only" myth
  (see [Windows architecture specifics](#windows-architecture-specifics)).
- **No clean-install smoke test**, so prebuild-packaging and libc-selection bugs ship to users.

## Primary sources

- Node.js — Node-API: <https://nodejs.org/api/n-api.html>
- Node.js — ABI Stability: <https://nodejs.org/en/learn/modules/abi-stability>
- prebuildify: <https://github.com/prebuild/prebuildify>
- node-gyp-build: <https://github.com/prebuild/node-gyp-build>
- node-gyp: <https://github.com/nodejs/node-gyp>
- npm Docs — package.json (`os`/`cpu`/`libc`, `optionalDependencies`): <https://docs.npmjs.com/cli/v11/configuring-npm/package-json>
- npm Docs — generating provenance / trusted publishing: <https://docs.npmjs.com/generating-provenance-statements>
- GitHub Docs — Workflow syntax (`strategy.matrix`/`include`/`exclude`/`fail-fast`): <https://docs.github.com/en/actions/reference/workflow-syntax-for-github-actions>
- GitHub Docs — GitHub-hosted runners reference: <https://docs.github.com/en/actions/reference/runners/github-hosted-runners>
- GitHub Changelog — arm64 hosted runners GA (2025-08-07): <https://github.blog/changelog/2025-08-07-arm64-hosted-runners-for-public-repositories-are-now-generally-available/>
- Docker Docs — Multi-platform builds (buildx/QEMU/binfmt): <https://docs.docker.com/build/building/multi-platform/>
- Apple Developer — Building a universal macOS binary: <https://developer.apple.com/documentation/apple-silicon/building-a-universal-macos-binary>
- Microsoft Learn — Predefined macros (`_M_X64`, `_M_ARM64`, `_M_ARM64EC`, `_WIN32`/`_WIN64`): <https://learn.microsoft.com/en-us/cpp/preprocessor/predefined-macros>
- Microsoft Learn — `/Qspectre` (Intel/AMD/ARM; ARM64 libs): <https://learn.microsoft.com/en-us/cpp/build/reference/qspectre>
- Microsoft Learn — `/HIGHENTROPYVA` (default-on for 64-bit images): <https://learn.microsoft.com/en-us/cpp/build/reference/highentropyva-support-64-bit-aslr>
- Microsoft Learn — `/guard` (Control Flow Guard): <https://learn.microsoft.com/en-us/cpp/build/reference/guard-enable-control-flow-guard>
- Clang — AddressSanitizer: <https://clang.llvm.org/docs/AddressSanitizer.html>
- Clang — LeakSanitizer: <https://clang.llvm.org/docs/LeakSanitizer.html>
- LLVM — llvm-cov command guide: <https://llvm.org/docs/CommandGuide/llvm-cov.html>
- gcovr — Compiling for coverage: <https://gcovr.com/en/stable/guide/compiling.html>
- Valgrind — Memcheck manual (`--leak-check`, `--error-exitcode`, suppressions): <https://valgrind.org/docs/manual/mc-manual.html>
- OpenSSF — Compiler Options Hardening Guide for C and C++: <https://best.openssf.org/Compiler-Hardening-Guides/Compiler-Options-Hardening-Guide-for-C-and-C++.html>
- SQLite — The Amalgamation: <https://sqlite.org/amalgamation.html>
- SQLite — Download page (SHA3-256, version encoding, CSV metadata): <https://sqlite.org/download.html>
- cibuildwheel (PyPA) — build-the-matrix prior art: <https://cibuildwheel.pypa.io/en/stable/>
- Chainguard Academy — glibc vs musl: <https://edu.chainguard.dev/chainguard/chainguard-images/about/images-compiled-programs/glibc-vs-musl/>
