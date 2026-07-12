<!-- Original synthesis. Adapted sources: cppreference (CC BY-SA 3.0/GFDL), SEI CERT standards prose (CC BY 4.0), and OpenSSF Compiler Hardening Guide (CC BY 4.0). The C++ Core Guidelines (custom license) were consulted, not relicensed. This file: CC BY-SA 4.0. See ../ATTRIBUTION.md. -->

# Baseline Selection and Reporting

The applicability model and reporting contract for `/cpp:project-setup`. This file
decides *which* build, toolchain, and convention controls apply to *this* project,
what counts as evidence, and how to report gaps without inventing flags.

## Contents

- [Standards backbone](#standards-backbone)
- [Establish the project profile](#establish-the-project-profile)
- [Profile-driven applicability](#profile-driven-applicability)
- [Not applicable — architecture and platform gating](#not-applicable--architecture-and-platform-gating)
- [Evidence rules](#evidence-rules)
- [State calibration](#state-calibration)
- [Priority calibration](#priority-calibration)
- [Hardening gap vs. exploitable defect](#hardening-gap-vs-exploitable-defect)
- [Report template](#report-template)
- [Source and version policy](#source-and-version-policy)
- [Primary sources](#primary-sources)

## Standards backbone

Pin these as the coverage index. None is a mandate to apply every control to every
target — select applicable domains from the profile first, then assess.

| Backbone | Owns | Notes |
| --- | --- | --- |
| **OpenSSF Compiler Options Hardening Guide for C and C++** | GCC/Clang compiler + linker baseline; per-flag minimum toolchain versions | The recommended-options set is the compiler/linker checklist. Quote its version floors; do not raise them from memory. |
| **Microsoft Learn (MSVC/link.exe reference)** | Windows compiler + linker hardening (`/guard:cf`, `/Qspectre`, `/sdl`, `/CETCOMPAT`, `/guard:signret`, `/DYNAMICBASE`, `/HIGHENTROPYVA`, `/NXCOMPAT`, `/GS`) | Authoritative for arch applicability of each switch. |
| **C++ Core Guidelines** | Code conventions (RAII, special members, `noexcept`, ownership) | R.1, R.11, C.21, E.6, P.8, F.6 are the load-bearing rules for addon resource code. See `modern-cpp-conventions.md`. |
| **SEI CERT C/C++ Coding Standard** | Language-level defect rules cited in review (e.g. `FIO02-C` path canonicalization, integer rules) | Cite an exact rule id only when you have verified it exists. |
| **Sanitizer / tool docs** (Clang ASan/UBSan/TSan, clang-tidy, node-gyp, node-addon-api, Node-API, prebuildify/node-gyp-build) | Test-build instrumentation and analysis wiring | See `sanitizers-and-analysis.md`, `build-and-toolchain.md`, `ci-and-release.md`. |

**Never fabricate** a compiler flag, linker flag, clang-tidy check name, Node-API
function name, define, CWE id, or CERT rule id. If a name is uncertain, omit it or mark
it *version-sensitive: verify*. A wrong flag is worse than a missing one — several
hard-error the build (see gating below).

## Establish the project profile

Before assessing anything, read the profile off the repository. The profile determines
the entire applicable-domain set.

| Profile axis | Determine from | Why it matters |
| --- | --- | --- |
| Addon vs. general C++ | `binding.gyp` + `package.json` (a `.node` `loadable_module`) vs. a plain library/CLI | Addons are **shared libraries** → `-fPIC`, not `-pie`/`-fPIE`; exception/RTTI/std defaults are inherited from Node. |
| Target OS matrix | CI matrix, prebuild scripts, `conditions` in `binding.gyp` | Gates the entire `-Wl,-z,*` (Linux) vs. `ld64` (macOS) vs. MSVC (Windows) split. |
| Target arch matrix | `target_arch` conditions, prebuild `--arch` | Gates `-fcf-protection` (x86) vs. `-mbranch-protection` (arm64) and the x64-only MSVC switches. |
| Ships prebuilt binaries | `prebuildify`/`node-gyp-build` (or deprecated `prebuild-install`) in `package.json` scripts, a `prebuilds/` layout | Pulls in the multi-libc/arch matrix + oldest-glibc build + Node-API version pinning. |
| Vendors C/C++ sources | Amalgamations/upstream trees compiled into the target (e.g. `src/upstream/sqlite3.c`) | Pulls in defensive defines, visibility, upstream-version pinning, warning scoping. |
| Threading / async work | `Napi::AsyncWorker`, threadsafe functions, worker threads, `std::thread`, mutexes/atomics | Pulls in TSan, context-aware instance data, env cleanup hooks. |
| Exceptions across N-API | `NAPI_CPP_EXCEPTIONS` / the `node_addon_api_except` dependency target | Pulls in the exception-boundary translation requirement. |
| Effective build inheritance | `binding.gyp` **plus** node-gyp's `addon.gypi` **plus** the target Node's bundled `common.gypi` | The C++ standard, `-fno-exceptions`, and `-fno-rtti` come from `common.gypi` and are **Node-version-locked** — do not read them off `binding.gyp` alone. |

## Profile-driven applicability

Apply controls to real surfaces:

| Profile fact | Normally applicable domains |
| --- | --- |
| Native addon (any) | `-fPIC` (already applied by node-gyp on Linux non-ia32), OpenSSF GCC/Clang baseline on POSIX, symbol visibility, ABI-safe headers only (`napi.h`/`node_api.h`; never `v8.h`/`node.h`/`uv.h`) |
| Ships prebuilt binaries | multi-arch + multi-libc (glibc/musl) matrix, **oldest-glibc build** in an old container, `NAPI_VERSION` pinned to the lowest version with the APIs you need, libc/arch tagging via `prebuildify` |
| Vendors C sources | defensive compile defines, `-fvisibility=hidden` on the vendored TUs, warning scoping for intentional upstream constructs (e.g. `-Wno-implicit-fallthrough` only on the vendored file), upstream-version pinning |
| Spawns worker threads / async work | **TSan** in CI, context-aware **instance data** (`napi_set_instance_data`) instead of mutable globals, `napi_add_env_cleanup_hook` for reference teardown, `std::atomic` shutdown flag polled on the worker |
| Uses C++ exceptions across N-API | single exception-translation boundary (catch at every entry point, convert to a pending JS error), the `node_addon_api_except` target — never let a raw `std::exception` escape into libuv/V8 |
| Raw buffer ops / integer size math | `-fstack-protector-strong`, `-D_FORTIFY_SOURCE` (`=3` where the toolchain supports it), `-D_GLIBCXX_ASSERTIONS` / `-D_LIBCPP_HARDENING_MODE`, UBSan |
| Linux target | `-Wl,-z,relro -Wl,-z,now` (full RELRO), `-Wl,-z,noexecstack`, `-fstack-clash-protection`, `-fcf-protection=full` (x86 only) / `-mbranch-protection=standard` (arm64 only) |
| macOS target | pin `MACOSX_DEPLOYMENT_TARGET`, `GCC_SYMBOLS_PRIVATE_EXTERN: YES` (= `-fvisibility=hidden`); **no** `-Wl,-z,*` (ld64 rejects them); PIE/ASLR are default |
| Windows target | MSVC `/guard:cf`+`/GUARD:CF`, `/sdl`, `/Qspectre`, `/ZH:SHA_256`; arch-gated `/CETCOMPAT`+`/guard:ehcont` (x64) or `/guard:signret` (arm64); `/GS`, `/DYNAMICBASE`, `/HIGHENTROPYVA`, `/NXCOMPAT` are on by default |
| CI / published package | sanitizer + clang-tidy jobs that **gate** (fail the build), SHA-pinned actions, `ignore-scripts` posture, provenance/OIDC publishing |
| General modern C++17 (non-addon) | Core Guidelines RAII conventions, explicit standard selection, the OpenSSF baseline adapted for the binary type (executables *do* use `-fPIE -pie`) |

## Not applicable — architecture and platform gating

Mark **Not applicable** (not Gap) when the profile excludes the surface. Getting this
wrong produces recommendations that hard-error the build.

- `-Wl,-z,relro/now/noexecstack` on a **macOS-only** build — these are GNU ld / ELF only; Apple `ld64` does not understand them. macOS gets ASLR/PIE and W^X by default.
- `-Wl,-z,nodlopen` on a **Node.js addon or any other dynamically loaded plugin** — it marks the ELF object unavailable to `dlopen()`, which is the mechanism Node uses to load `.node` files.
- `-mbranch-protection=…` on **x64** — unknown option → build error. It is AArch64-only.
- `-fcf-protection=full` on **arm64** — GCC/Clang **hard-error** (`not supported for this target`). It is x86/x86-64 only.
- `-fstack-clash-protection` on a target that lacks an implementation — errors; treat as version/target-sensitive, not a universal.
- **TSan** on a strictly single-threaded, fully synchronous addon with no worker threads, no async work, and no shared mutable state — nothing for it to observe.
- `/CETCOMPAT` and `/guard:ehcont` on **ARM64** (or any non-Windows target) — both are x64-only. `/guard:signret` is the ARM64 counterpart.
- `_FORTIFY_SOURCE` inside an **AddressSanitizer** build — OpenSSF states sanitizers are incompatible with FORTIFY; it must be `-U_FORTIFY_SOURCE`/`=0` in that profile. Its absence there is *correct*, not a gap.

Do **not** mark a domain Not applicable merely because the relevant code sits outside
the requested diff. Read the whole build config and CI matrix first.

Corrections to common myths (preserve these):

- `/Qspectre` and `/HIGHENTROPYVA` are **not** x64-only. `/Qspectre` covers ARM/ARM64 since VS 2017 15.7; `/HIGHENTROPYVA` applies to any 64-bit image (x64 *and* arm64) and is merely ignored for 32-bit.
- `/CETCOMPAT` and `/guard:ehcont` **are** x64-only; `/guard:signret` is arm64-only.
- Addons are shared libraries → use `-fPIC`, never `-pie`/`-fPIE`.

## Evidence rules

Weigh the **effective** build over stated intentions.

Accept as evidence:

- the effective `binding.gyp` **after** the `addon.gypi` + `common.gypi` merge (remember inheritance — the standard/exceptions/RTTI come from Node's `common.gypi`);
- actual compiler/linker command lines from a verbose build (`node-gyp rebuild --verbose`), or the emitted `.node` inspected for the protection (e.g. RELRO/NX/CFG markings);
- CI workflow config that **runs and gates on** sanitizers, clang-tidy, Valgrind, or leak checks (an exit-code that fails the job);
- prebuild scripts and the resulting artifact matrix (arch × libc);
- tests that assert the behavior (memory tests, worker-thread/thread-safety suites).

Treat as weak — investigate before crediting:

- a flag named in a README/`doc/` but absent from the effective gyp;
- a `.clang-tidy` with `WarningsAsErrors: ''` (advisory only — findings never fail CI);
- suppressions files not wired into the run (e.g. an `.asan-options` file whose own header says it "is not loaded automatically");
- a flag present but **ungated** by `OS`/`target_arch` (it may hard-error or be silently dropped on another target in the matrix);
- a sanitizer script that runs but whose report is ignored on a zero exit;
- clang-tidy that never runs on the platform where the code lives (e.g. the `src/darwin/*` tree excluded from every lint job) — coverage claimed, coverage absent;
- a control on one target when equivalent targets in the matrix remain uncovered.

For **Met** and **Gap**, cite `binding.gyp:line`, the CI file, or observed build output.
For **Needs verification**, state the missing fact and a safe way to confirm it. Do not
assume Gap just because static inspection cannot show what a particular toolchain
version does — that is Needs verification.

## State calibration

| Observation | State |
| --- | --- |
| Effective gyp/CI applies the control under the correct `OS`/`target_arch` condition, confirmed in build output or artifact | **Met** |
| Applicable domain, control absent from the effective build (or present but disabled/overridden) | **Gap** |
| Control present but **ungated** so it hard-errors or is stripped on another target in the matrix | **Gap** (correctness) or **Needs verification** if the matrix is unclear |
| Named in docs/README but not found in the effective gyp/CI | **Needs verification** |
| CI references the tool but the run does not gate (advisory `WarningsAsErrors: ''`, ignored exit code) | **Needs verification**, escalating to **Gap** after confirmation |
| No relevant surface (single-platform, single-arch, single-threaded, no vendored C, executable not library) | **Not applicable** |

Partial implementation is normally **Gap** when the missing portion is materially
relevant — e.g. `-fvisibility=hidden` on the C (vendored) TUs but not the C++ addon TUs
on Linux leaves the addon's own symbols exported. Describe what is covered and what
remains rather than marking the whole domain absent.

## Priority calibration

Prioritize remediation, not fear. These are defaults; exposure, binary type, and
operational cost can move them.

- **Essential:**
  - No `-fstack-protector-strong` **and** no `_FORTIFY_SOURCE` on a security-sensitive addon that does raw buffer ops / pointer size math (the exact mitigations for that code class).
  - C++ exceptions able to cross the C ABI — a raw `std::exception`/`std::runtime_error` thrown from an N-API entry point or worker callback with no catch, aborting the process instead of translating to a JS error.
  - Mutable global/static state in a **worker-capable** addon instead of per-`napi_env` instance data — cross-Worker corruption.
  - Over-broad sanitizer/Valgrind suppressions that mask **first-party** leaks (e.g. `leak:napi_`, `leak:Napi::`, `leak:node_modules/` — these swallow essentially every addon allocation).

- **Recommended:**
  - Full RELRO (`-Wl,-z,relro -Wl,-z,now`) and `-Wl,-z,noexecstack` on Linux.
  - **UBSan and TSan** in CI (UBSan for the cast/narrowing/`union` code; TSan for any threaded/async addon).
  - `-fvisibility=hidden` (+ `-fvisibility-inlines-hidden`) on the **C++** TUs, not just the vendored C.
  - Oldest-glibc prebuild in an old container so binaries load on older distros; libc-tagged musl variant.
  - `-D_GLIBCXX_ASSERTIONS` / `-D_LIBCPP_HARDENING_MODE=_LIBCPP_HARDENING_MODE_FAST`; `-Werror=format-security`; `-fstack-clash-protection`.
  - Promote RAII/ownership clang-tidy checks (`cppcoreguidelines-special-member-functions`, `cppcoreguidelines-owning-memory`, `bugprone-use-after-move`) to gating on first-party headers.

- **Optional:**
  - `-fstrict-flex-arrays=3`, `-ftrivial-auto-var-init=zero`, `-fhardened` (GCC 14+).
  - Higher-assurance MSVC source hashing (`/ZH:SHA_256` or stronger), extra security telemetry, additional sanitizer/fuzz coverage.

Never translate **Essential** directly to "Critical" or imply exploitability — that is a
severity claim, and severity belongs to a concrete defect, not a missing defense.

## Hardening gap vs. exploitable defect

Keep the two lanes separate.

- A **hardening gap** is a missing defense-in-depth control in the build/toolchain/convention baseline — e.g. no `-fstack-protector-strong`, no full RELRO, visibility not applied, no TSan job. It has no proof-of-exploit; it raises the cost of *some* future bug. This skill (`/cpp:project-setup`) owns these.
- An **exploitable defect** is a concrete first-party bug with a data-flow: use-after-free across GC/teardown order, TOCTOU on a path, an unbounded/mis-sized `memcpy`, integer overflow feeding an allocation (CWE-190), a raw exception crossing the ABI, silent truncation of data. These are **not** baseline gaps — escalate them to **`/cpp:resource-review`** (`defect-classes.md`, `napi-resource-model.md`, `proof-and-tooling.md`, `report-format.md`), which requires a reproduction or a proof path.

When project-setup work surfaces a probable defect, note it and hand it off; do not
launder it into a "missing flag." When a review finds that a defect is only reachable
because a mitigation is absent, both apply — report the defect in resource-review and the
missing mitigation here.

## Report template

```
# C++ / node-gyp Project Setup Review — <project>

## Profile
- Type: <native addon | general C++17 library/CLI>
- Target matrix: <OS × arch>, libc: <glibc/musl>
- Node-API: NAPI_VERSION=<n> | node-addon-api <version> | exceptions: <NAPI_CPP_EXCEPTIONS?>
- Vendored C/C++: <yes: which upstream @ pinned version | no>
- Concurrency: <worker threads / async work / synchronous only>
- Prebuilds: <prebuildify+node-gyp-build | prebuild-install (deprecated) | source-only>

## Baseline
- OpenSSF Compiler Options Hardening Guide for C and C++ (GCC/Clang)
- Microsoft Learn MSVC reference (Windows)
- C++ Core Guidelines (conventions); SEI CERT C/C++ (defect rules)
- Toolchains observed: GCC <v> / Clang <v> / MSVC <v>; Node <v> headers (common.gypi std=<...>)

## Coverage summary
| Domain | State | Priority |
| --- | --- | --- |
| Stack protection / FORTIFY | Met/Gap/N.A./Needs-verif | ... |
| Linker hardening (RELRO/NX) | ... | ... |
| Arch-gated CFI (cf-protection / branch-protection / MSVC guards) | ... | ... |
| Symbol visibility | ... | ... |
| Exception boundary | ... | ... |
| Context-awareness / instance data | ... | ... |
| Sanitizers (ASan/UBSan/TSan) + gating | ... | ... |
| Static analysis (clang-tidy) + gating | ... | ... |
| Prebuild matrix / oldest-glibc / Node-API pin | ... | ... |

## Findings
### Essential
- <title>
  - Applicability: <which profile fact makes this apply>
  - Evidence: <binding.gyp:line | CI file | build output>
  - Recommendation: <exact flag / gyp fragment, arch/OS-gated>
  - Tradeoffs: <e.g. -Wl,-z,now adds startup cost; =3 needs GCC 12+>
  - Source: <OpenSSF section | MSVC doc | Core Guideline id>
### Recommended
  <same shape>
### Optional
  <same shape>

## Needs verification
- <missing fact + safe confirmation method (e.g. run `node-gyp rebuild --verbose`)>

## Controls already met
- <control @ evidence>  (credit real coverage, including inherited common.gypi defaults)

## Not applicable
- <control> — <reason: e.g. macOS-only build, ld64 rejects -Wl,-z,*>

## Probable defects (→ /cpp:resource-review)
- <defect + why it is a bug, not a baseline gap>

## Remediation roadmap
1. Essential …  2. Recommended …  3. Optional …
```

Every recommended flag in the report must be **arch/OS-gated** in the fragment you give,
so it can never hard-error on another target in the matrix (see
`compiler-hardening.md` for the gated `conditions` blocks).

## Source and version policy

- Pin the baseline as **OpenSSF Compiler Options Hardening Guide for C and C++** (plus the MSVC reference for Windows) in every report, and quote the guide's per-flag minimum toolchain versions rather than inventing floors.
- Every flag is toolchain-version-sensitive — verify against the *observed* GCC/Clang/MSVC version. Examples that shift: `_FORTIFY_SOURCE=3` (GCC 12+/Clang 9+, needs `-O1`+), `-fstrict-flex-arrays=3` (GCC 13+/Clang 16+), `-ftrivial-auto-var-init` (GCC 12+/Clang 8+), `_LIBCPP_HARDENING_MODE` (libc++ 18+; the older `_LIBCPP_ENABLE_ASSERTIONS` is deprecated), `-fhardened` (GCC 14+), `/ZH:SHA_256` default (VS 2022 17.0+), `/Qspectre` ARM64 (VS 2017 15.7+).
- Account for the three-file merge: the effective build is `binding.gyp` + node-gyp `addon.gypi` + the **target Node version's** `common.gypi`. The C++ standard, `-fno-exceptions`, `-fno-rtti`, and macOS deployment target are inherited and Node-version-locked; re-verify per target Node version rather than assuming C++17/C++20.
- Never fabricate a flag, linker option, clang-tidy check, Node-API/`napi_*` name, compile define, CWE id, or CERT rule id. Confirm against the primary source or omit it.
- Prefer normative/official docs; use blog posts and issue threads only as discovery leads, and confirm the behavior against the vendor doc before asserting it.

## Primary sources

- [OpenSSF Compiler Options Hardening Guide for C and C++](https://best.openssf.org/Compiler-Hardening-Guides/Compiler-Options-Hardening-Guide-for-C-and-C++.html) — CC BY 4.0
- [C++ Core Guidelines](https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines) — consulted under its [custom license](https://github.com/isocpp/CppCoreGuidelines/blob/master/LICENSE)
- [SEI CERT C Coding Standard](https://cmu-sei.github.io/secure-coding-standards/) — CC BY 4.0 standards prose; MIT code examples
- [GCC Instrumentation Options](https://gcc.gnu.org/onlinedocs/gcc/Instrumentation-Options.html) and [AArch64 Options](https://gcc.gnu.org/onlinedocs/gcc/AArch64-Options.html)
- [Microsoft Learn — MSVC compiler/linker security options](https://learn.microsoft.com/en-us/cpp/build/reference/c-cpp-prop-page) (`/guard:cf`, `/Qspectre`, `/CETCOMPAT`, `/guard:ehcont`, `/guard:signret`, `/HIGHENTROPYVA`, `/DYNAMICBASE`, `/NXCOMPAT`, `/GS`, `/sdl`, `/ZH`)
- [Clang AddressSanitizer](https://clang.llvm.org/docs/AddressSanitizer.html) and [clang-tidy](https://clang.llvm.org/extra/clang-tidy/)
- [Node.js Node-API reference](https://nodejs.org/api/n-api.html) (`napi_set_instance_data`, `napi_add_env_cleanup_hook`, `NAPI_VERSION`, ABI stability)
- [node-gyp](https://github.com/nodejs/node-gyp) and [node-addon-api](https://github.com/nodejs/node-addon-api) (the `addon.gypi` + `common.gypi` merge, exception dependency targets)
- [prebuildify](https://github.com/prebuild/prebuildify) and [node-gyp-build](https://github.com/prebuild/node-gyp-build) (prebuild matrix, libc/arch tagging)
