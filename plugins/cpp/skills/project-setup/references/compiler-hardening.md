<!-- Original synthesis. Adapted sources: cppreference (CC BY-SA 3.0/GFDL), SEI CERT standards prose (CC BY 4.0), and OpenSSF Compiler Hardening Guide (CC BY 4.0). The C++ Core Guidelines (custom license) were consulted, not relicensed. This file: CC BY-SA 4.0. See ../ATTRIBUTION.md. -->

# Compiler and Linker Hardening for Native Addons

Per-OS, per-arch hardening flag matrix for `.node` addon builds and general C++17.
This is the crown-jewel reference: the flags here are accurate as written, but several
are **version-sensitive** or **hard-error if misapplied to the wrong arch** — those are
marked. Anchored on the OpenSSF *Compiler Options Hardening Guide* (GCC/Clang) and
Microsoft Learn (MSVC). Cross-link: [`build-and-toolchain.md`](./build-and-toolchain.md)
for the toolchain floors, [`sanitizers-and-analysis.md`](./sanitizers-and-analysis.md)
for the sanitizer builds these flags must be disabled in,
[`ci-and-release.md`](./ci-and-release.md) for the prebuild matrix.

## Contents

- [The addon is a shared library: -fPIC, never -pie](#the-addon-is-a-shared-library)
- [GCC/Clang baseline (Linux, mostly macOS)](#gccclang-baseline)
- [FORTIFY_SOURCE specifics](#fortify_source-specifics)
- [Standard-library hardening](#standard-library-hardening)
- [ELF linker hardening — Linux only](#elf-linker-hardening)
- [macOS and ld64 caveats](#macos-and-ld64-caveats)
- [Architecture-gated CFI (hard-errors if misapplied)](#architecture-gated-cfi)
- [MSVC compiler and linker (Windows)](#msvc-compiler-and-linker)
- [Sanitizer builds: what to turn OFF](#sanitizer-builds-what-to-turn-off)
- [Complete arch-gated binding.gyp](#complete-arch-gated-bindinggyp)
- [Reference projects: right and wrong](#reference-projects)
- [Myth corrections](#myth-corrections)

## The addon is a shared library

A Node.js native addon is a **shared library** — an ELF `.so` on Linux, a Mach-O bundle
on macOS, a DLL on Windows, all named `.node`. Consequences that trip people up:

- Use **`-fPIC`** (position-independent *code*), **never** `-fPIE`/`-pie`. The
  executable-only PIE flags do not apply to shared objects; node-gyp/GYP already compiles
  addon targets with `-fPIC`. Reserve `-fPIE -pie` for standalone executables.
- ASLR of the addon image follows from `-fPIC` on ELF; on macOS and Windows the loader
  randomizes shared images by default (see the per-platform sections).
- Symbol visibility matters: a loadable module coexists in the host process with V8,
  libuv, and other addons. Add `-fvisibility=hidden` (and `-fvisibility-inlines-hidden`
  for C++) so internal symbols don't bloat the dynamic symbol table or permit
  interposition. node-gyp's bundled `common.gypi` does **not** add this for addon targets
  (version-sensitive: verify).

## GCC/Clang baseline

OpenSSF-recommended "safe to ship" set. Per-flag minimum toolchain versions are the
guide's; anything below your prebuild's floor is a no-op or an error, so gate accordingly.

| Flag | Purpose | Min. toolchain | Notes |
|---|---|---|---|
| `-O2` | Optimization; **required** for FORTIFY and several protections | GCC 2.95.3, Clang 4.0 | Without `-O1`+ there is no fortification |
| `-Wall -Wextra` | Warn on defect-prone constructs | GCC 2.95.3, Clang 4.0 | |
| `-Wformat -Wformat=2` | Format-string checking (`=2` adds security checks) | GCC 2.95.3, Clang 4.0 | |
| `-Werror=format-security` | Promote unsafe format strings to **errors** | GCC 2.95.3, Clang 4.0 | Selective `-Werror=` is safe to distribute |
| `-Wconversion` | Warn on value-changing implicit conversions | GCC 2.95.3, Clang 4.0 | Noisy; opt in per project |
| `-Wimplicit-fallthrough` | Warn on unannotated `switch` fallthrough | GCC 7.0, Clang 4.0 | Suppress only over vendored C (e.g. SQLite) |
| `-U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=3` | Compile+run-time buffer/libc misuse checks | level 3: GCC 12, Clang 9 (glibc) | `-U` first; requires `-O1`+; see below |
| `-fstack-protector-strong` | Stack-smashing canary, strong heuristic | GCC 4.9, Clang 6.0 | Broadly portable; recommended default |
| `-fstack-clash-protection` | Probe each stack page vs. stack-clash | GCC 8.0, Clang 11.0 | **Not on every target** — can hard-error; see CFI section |
| `-ftrivial-auto-var-init=zero` | Zero-init otherwise-uninitialized automatics | GCC 12, Clang 8.0 | Defends against uninitialized-read info leaks |
| `-fstrict-flex-arrays=3` | Only `[]` counts as a flexible array member | GCC 13, Clang 16 | Tightens FORTIFY bounds |
| `-fPIC` | Position-independent code → ASLR | Binutils 2.16 | Required for shared objects anyway |

**Production "codegen" set** (OpenSSF): `-fno-strict-aliasing`, `-fno-strict-overflow`,
`-fno-delete-null-pointer-checks` — each stops the optimizer from exploiting UB in ways
that delete safety checks. No version floor.

**GCC-only extras:** `-Wtrampolines` (GCC 4.3), `-fzero-init-padding-bits=all` (GCC 15),
`-Wbidi-chars=any` (Trojan-Source detection, GCC 12). **GCC 14+ shortcut:** `-fhardened`
bundles a curated set in one flag but ties behavior to the GCC version. Add `-fexceptions`
whenever the addon is built with `NAPI_CPP_EXCEPTIONS` (and for multithreaded C using
pthreads, so cancellation cleanup can unwind through C frames).

Do **not** use blanket `-Werror` in distributed source: a newer compiler can add warnings
that break downstream builds. Use selective `-Werror=<name>` (e.g. `format-security`) in
source, and reserve blanket `-Werror` for your own CI.

## FORTIFY_SOURCE specifics

`_FORTIFY_SOURCE` is a **glibc** feature living in glibc headers. It silently does nothing
without the optimizer (`-O1` minimum, `-O2` recommended). Levels: `=1` (conforming
checks), `=2` (standard), `=3` (GCC 12+/Clang 9+, adds dynamic object-size checks at low
overhead). Always prefix `-U_FORTIFY_SOURCE` because many distros predefine `=2` and you
otherwise get a "redefined" warning.

- **musl (Alpine)** has limited/no `_FORTIFY_SOURCE` support; **macOS** SDK headers support
  it but coverage differs from glibc. Treat cross-libc behavior as version-sensitive.
- **Must be OFF under AddressSanitizer** — see [Sanitizer builds](#sanitizer-builds-what-to-turn-off).

## Standard-library hardening

Bounds/precondition assertions inside the C++ standard library. Pick by which libc++/libstdc++
you link — these belong in **`cflags_cc`** (C++ only), not `cflags`:

| Define | Library | Min. version | Notes |
|---|---|---|---|
| `-D_GLIBCXX_ASSERTIONS` | libstdc++ (GCC) | libstdc++ 6.0 | Bounds/precondition checks on containers, `string`, etc. |
| `-D_LIBCPP_HARDENING_MODE=_LIBCPP_HARDENING_MODE_FAST` | libc++ (Clang/macOS) | libc++ 18.1 | Supersedes deprecated `_LIBCPP_ENABLE_ASSERTIONS` |

macOS addons typically link libc++, Linux glibc builds link libstdc++, so a portable
`binding.gyp` sets the libstdc++ macro under the Linux branch and the libc++ macro under
the mac branch. These precondition checks are independent of FORTIFY and can remain enabled
under AddressSanitizer unless testing identifies a conflict in the exact standard-library and
sanitizer versions in use.

## ELF linker hardening

The `-Wl,-z,*` family is **GNU ld / ELF-specific** (the OpenSSF guide says as much: these
"may not be valid options for other linkers"). Put them **only** under the Linux branch —
they are not macOS ld64 flags. These go in **`ldflags`**:

| Linker flag | Effect | Min. binutils | Notes |
|---|---|---|---|
| `-Wl,-z,relro` | Map relocations read-only after load | 2.15 | Partial RELRO on its own |
| `-Wl,-z,now` | Resolve all symbols at load → full RELRO (GOT read-only) | 2.15 | Adds startup cost; pair with `relro` |
| `-Wl,-z,noexecstack` | Mark stack non-executable (W^X) | 2.14 | |
| `-Wl,-z,nodlopen` | Disallow `dlopen()` of this object | 2.10 | **Not applicable to `.node` addons or other plugins loaded with `dlopen()`** |
| `-Wl,--as-needed -Wl,--no-copy-dt-needed-entries` | Drop unused `DT_NEEDED` deps | 2.20 | Trims the dependency surface |

## macOS and ld64 caveats

Apple's `ld64` does **not** understand `-z relro/now/noexecstack`; passing them
yields linker warnings or errors, not RELRO. macOS provides the equivalent protections a
different way:

- **PIE is the default** for executables since OS X 10.7; **ASLR is on by default**, and
  shared images (including `.node` bundles) are randomized by the loader.
- W^X / non-executable data and the stronger runtime protections come from the platform
  and the **Hardened Runtime** code-signing capability, not from linker flags.
- Apple Silicon's `arm64e` slice uses pointer authentication (PAC) as an ABI feature, but
  the generic `arm64` slice that third-party Node addons ship is **not** `arm64e`, so
  PAC-ABI hardening is not generally available. Treat `-mbranch-protection` on Apple
  targets as nuanced (version-sensitive: verify) rather than a drop-in.
- Practical rule: on mac, keep the GCC/Clang *compiler* baseline (stack protector, format
  security, FORTIFY where supported, std-lib hardening) but **omit every `-Wl,-z,*`**.

## Architecture-gated CFI

Two hardware control-flow-integrity features target different ISAs. Applying the wrong one
to the wrong arch is a **build failure**, so they must live under `target_arch` conditions —
never in a shared flag list.

| Flag | Arch | Effect | Misapplication |
|---|---|---|---|
| `-fcf-protection=full` (also `=branch`, `=return`) | **x86 / x86-64 only** (Intel CET, i686+) | Emits `endbr` + shadow-stack marking → CET-compatible binary | On AArch64, GCC **hard-errors**: `error: '-fcf-protection=full' is not supported for this target`. Gate to x86. |
| `-mbranch-protection=standard` (also `pac-ret`, `bti`, `none`) | **AArch64 only** | `standard` = PAC return-signing + BTI at their standard level | On x86 it is an **unknown option → error**. Gate to arm64. |

- `-fcf-protection`'s backward-edge (shadow-stack) protection only takes effect at run time
  on CET-capable CPUs/OSes; the flag primarily makes the binary CET-compatible.
- `-mbranch-protection=standard` turns on all AArch64 branch-protection features; PAC needs
  Armv8.3-A, BTI needs Armv8.5-A hardware to be enforced.
- **`-fstack-clash-protection` is also target-limited:** on unsupported targets the compiler
  errors (`not supported on this target`). Supported on x86/x86-64 and, in recent toolchains,
  AArch64 Linux — but do not assume it everywhere (version-sensitive: verify).

GYP arch values: `target_arch=='x64'` / `'ia32'` (x86) vs `'arm64'`.

## MSVC compiler and linker

All statements below are Microsoft Learn. "Default on" = MSVC's own default; node-gyp
inherits MSVC/link.exe defaults, so you only opt into the ones that are **off** by default.

### Compiler options (`VCCLCompilerTool`)

| Option | Default | Effect | Arch | Notes |
|---|---|---|---|---|
| `/GS` | **On** | Stack security cookie (return address, EH, vulnerable params) | All | `/GS-` disables — don't |
| `/sdl` | Off | Superset of `/GS`; promotes a set of security warnings to errors, zero-inits some pointers | All | Overrides `/GS-`; recommended for new code |
| `/guard:cf` | Off | Forward-edge CFI (validates indirect-call targets) | **All** (x86/x64/ARM/ARM64) | **Must also pass linker `/GUARD:CF`**; needs `/DYNAMICBASE` (default on); incompatible with `/ZI`, `/clr` |
| `/Qspectre` | Off | Spectre v1 (CVE-2017-5753) speculation barriers | **x86, x64, ARM/ARM64** (ARM since VS 2017 15.7) | Available since VS 2017 15.5.5 |
| `/ZH:SHA_256` | SHA-256 default in VS 2022 (MD5 in VS 2019) | Source-file hash in PDB (source↔binary integrity) | All | `/ZH` since VS 2019 16.4; avoid MD5/SHA-1 |
| `/guard:ehcont` | Off | EH continuation metadata (complements CET shadow stack) | **x64 only** | Compiler **and** linker; needs `/Gy`; can hard-fail link (LNK2046/2047) |
| `/guard:signret` | Off | ARM64 return-address signing (PAC) | **ARM64 only** | The ARM64 analog of x64 EHCONT/CET return protection |

### Linker options (`VCLinkerTool`)

| Option | Default | Effect | Arch | Notes |
|---|---|---|---|---|
| `/DYNAMICBASE` | **On** | ASLR (rebaseable image) | 32/64-bit | `/DYNAMICBASE:NO` unsupported on ARM/ARM64/ARM64EC; required for `/HIGHENTROPYVA` and `/GUARD:CF` |
| `/HIGHENTROPYVA` | **On for 64-bit** | 64-bit ASLR (full VA entropy) | **any 64-bit image** (x64 *and* ARM64); ignored for 32-bit | Needs `/LARGEADDRESSAWARE` (default 64-bit) + `/DYNAMICBASE` |
| `/NXCOMPAT` | **On** | DEP / W^X compatible | All | `/NXCOMPAT:NO` opts out |
| `/GUARD:CF` | Off | Writes CFG target metadata into the image | All | Pair with compiler `/guard:cf`; compiling with `/guard:cf` but not linking `/GUARD:CF` pays the cost with **no** protection |
| `/CETCOMPAT` | Off | Marks binary CET-shadow-stack compatible (backward-edge CFI) | **x64 only** | Since VS 2019; inapplicable on ARM64 |

**Protection-to-flag by arch:**

| Protection | x64 | ARM64 |
|---|---|---|
| Forward-edge CFI | `/guard:cf` + `/GUARD:CF` | `/guard:cf` + `/GUARD:CF` (same flag) |
| Backward-edge CFI (ROP) | `/CETCOMPAT` + `/guard:ehcont` | `/guard:signret` (hardware PAC) |
| Spectre v1 | `/Qspectre` | `/Qspectre` |
| ASLR | `/DYNAMICBASE` + `/HIGHENTROPYVA` (both default on) | `/DYNAMICBASE` + `/HIGHENTROPYVA` (default on) |
| DEP / stack canary | `/NXCOMPAT`, `/GS` (default) | `/NXCOMPAT`, `/GS` (default) |

x64-only: `/CETCOMPAT`, `/guard:ehcont`. ARM64-only: `/guard:signret`. 64-bit
(both): `/HIGHENTROPYVA`. All arches: `/GS`, `/sdl`, `/guard:cf`+`/GUARD:CF`, `/Qspectre`,
`/DYNAMICBASE`, `/NXCOMPAT`, `/ZH:SHA_256`.

MSVC AddressSanitizer (`/fsanitize=address`) is **x86/x64 only** — a testing tool, not a
production hardening flag.

## Sanitizer builds: what to turn OFF

**Critical.** `_FORTIFY_SOURCE` must be **disabled** under AddressSanitizer. OpenSSF: "we do
not recommend enabling `_FORTIFY_SOURCE` for instrumented test builds where sanitizers are
used" — FORTIFY's interceptors collide with ASan's, producing false positives/negatives. The
sanitizer build is a *separate profile*: it recompiles with `-fsanitize=address
-fno-omit-frame-pointer -g -O1` and should also pass `-U_FORTIFY_SOURCE
-D_FORTIFY_SOURCE=0`. Standard-library hardening assertions can remain enabled unless the
specific toolchain demonstrates a conflict. See
[`sanitizers-and-analysis.md`](./sanitizers-and-analysis.md) for the full ASan/UBSan/TSan
wiring.

## Complete arch-gated binding.gyp

Release-profile fragment. Every arch-specific flag is under a `target_arch` condition so it
never hard-fails on the other arch; `-Wl,-z,*` and the CFI flags are OS/arch-gated per the
rules above. (Sanitizer builds are a separate profile — do **not** add ASan here.)

```python
{
  "conditions": [
    ["OS=='linux'", {
      "cflags": [
        "-O2", "-Wall", "-Wextra", "-Wformat", "-Wformat=2",
        "-Werror=format-security",
        "-U_FORTIFY_SOURCE", "-D_FORTIFY_SOURCE=3",
        "-fstack-protector-strong", "-fstack-clash-protection",
        "-ftrivial-auto-var-init=zero", "-fstrict-flex-arrays=3",
        "-fvisibility=hidden", "-fPIC"
      ],
      "cflags_cc": [ "-D_GLIBCXX_ASSERTIONS", "-fvisibility-inlines-hidden", "-fexceptions" ],
      "ldflags": [
        "-Wl,-z,relro", "-Wl,-z,now",
        "-Wl,-z,noexecstack"
      ],
      "conditions": [
        ["target_arch=='x64' or target_arch=='ia32'",
          { "cflags": [ "-fcf-protection=full" ] }],
        ["target_arch=='arm64'",
          { "cflags": [ "-mbranch-protection=standard" ] }]
      ]
    }],
    ["OS=='mac'", {
      "xcode_settings": {
        "OTHER_CFLAGS": [
          "-O2", "-Wall", "-Wextra", "-Wformat=2",
          "-Werror=format-security",
          "-U_FORTIFY_SOURCE", "-D_FORTIFY_SOURCE=2",
          "-fstack-protector-strong", "-fvisibility=hidden"
        ],
        "OTHER_CPLUSPLUSFLAGS": [
          "-D_LIBCPP_HARDENING_MODE=_LIBCPP_HARDENING_MODE_FAST"
        ],
        "GCC_SYMBOLS_PRIVATE_EXTERN": "YES"
        # NOTE: no -Wl,-z,* — ld64 doesn't support them; PIE/ASLR are default.
      }
    }],
    ["OS=='win'", {
      "msvs_settings": {
        "VCCLCompilerTool": {
          "AdditionalOptions": [ "/guard:cf", "/Qspectre", "/sdl", "/ZH:SHA_256" ]
          # /GS is on by default
        },
        "VCLinkerTool": {
          "AdditionalOptions": [ "/GUARD:CF" ]
          # /DYNAMICBASE /HIGHENTROPYVA /NXCOMPAT are on by default
        }
      },
      "conditions": [
        ["target_arch=='x64'",
          { "msvs_settings": {
              "VCLinkerTool": { "AdditionalOptions": [ "/CETCOMPAT" ] },
              "VCCLCompilerTool": { "AdditionalOptions": [ "/guard:ehcont" ] } } }],
        ["target_arch=='arm64'",
          { "msvs_settings": {
              "VCCLCompilerTool": { "AdditionalOptions": [ "/guard:signret" ] } } }]
      ]
    }]
  ]
}
```

GYP field mapping: Linux (make) uses `cflags` (all languages) / `cflags_c` (C only) /
`cflags_cc` (C++ only) / `ldflags`; macOS
(Xcode/ninja) uses `xcode_settings.OTHER_CFLAGS` / `OTHER_CPLUSPLUSFLAGS` /
`OTHER_LDFLAGS` (never `-z` here); Windows (MSBuild) uses
`msvs_settings.VCCLCompilerTool.AdditionalOptions` and `VCLinkerTool.AdditionalOptions`.
`_FORTIFY_SOURCE=3` needs GCC 12+/Clang 9+, so on an older prebuild floor drop to `=2` or
bump the toolchain (see [`build-and-toolchain.md`](./build-and-toolchain.md)). GYP semantics
(e.g. `cflags!` to *remove* an inherited flag) are node-gyp-version-sensitive: verify.

## Reference projects

**`fs-metadata: binding.gyp` gets the arch split right.** It gates `-fcf-protection=full`
under `target_arch=='x64'` (`binding.gyp:45-50`) and `-mbranch-protection=standard` under
`target_arch=='arm64'` (`binding.gyp:51-57`) — exactly the discipline that avoids the
hard errors above. Its Windows layer (`binding.gyp:79-144`) likewise splits per-arch:
x64 gets `/Qspectre`, `/HIGHENTROPYVA`, `/CETCOMPAT`; ARM64 omits them with inline
rationale (ARM64 relies on hardware PAC/BTI). Copy this structure.

Where it **falls short of the OpenSSF baseline**:

- Applies `-D_FORTIFY_SOURCE=2` unconditionally, **including under the ASan build**
  (`binding.gyp:33,41,166,172`; the sanitizer run at `sanitizers-test.sh:44-45` recompiles
  with `-fsanitize=address` but never undefines it) — contrary to OpenSSF guidance. Move
  FORTIFY out of the sanitizer profile.
- Missing the ELF linker set (`-Wl,-z,relro -Wl,-z,now -Wl,-z,noexecstack`),
  `-fstack-clash-protection`, `-D_GLIBCXX_ASSERTIONS` (and the libc++ analogue on macOS),
  and `_FORTIFY_SOURCE=3`. Uses advisory `-Wformat-security` rather than
  `-Werror=format-security`.

**`node-sqlite: binding.gyp` gets Windows right but has an incomplete POSIX baseline.** Its
per-arch MSVC split (`binding.gyp:104-150`) is a good model. On make-based POSIX builds its
`cflags` entries (`-fvisibility=hidden`, `-fPIC`, and `-Wno-implicit-fallthrough`) reach both C
and C++ TUs; `cflags_cc` then adds `-fexceptions` and Linux `-fno-plt`
(`binding.gyp:65-73,88-90`). It therefore already hides both vendored-C and first-party-C++
symbols, but still lacks the rest of the OpenSSF GCC/Clang baseline
(`-fstack-protector-strong`, FORTIFY, `-fstack-clash-protection`, the CFI pair, format
hardening, standard-library assertions, `-fvisibility-inlines-hidden`, and the applicable
ELF linker flags). Its fallthrough suppression is also common to the C++ TUs; move it to
`cflags_c` if it is intended for all C files, or isolate the vendored source if it alone needs
the suppression.

## Myth corrections

- **`/Qspectre` is NOT x64-only.** ARM/ARM64 support was added in VS 2017 15.7.
- **`/HIGHENTROPYVA` is NOT x64-only.** It applies to any **64-bit** image (x64 *and*
  ARM64) and is simply ignored for 32-bit.
- **`/CETCOMPAT` IS x64-only**, and **`/guard:ehcont` IS x64-only**; the ARM64 backward-edge
  counterpart is **`/guard:signret`**.
- **`-fcf-protection=full` is x86-only and hard-errors on AArch64**; **`-mbranch-protection`
  is arm64-only** and errors on x86. Always arch-gate both.
- **`-Wl,-z,relro/now/noexecstack` are Linux/ELF only** — macOS ld64 rejects them;
  never put them in `xcode_settings`.
- **`-Wl,-z,nodlopen` must not be used for a `.node` addon** — Node loads the shared object
  with `dlopen()`, and the flag makes the loader reject it.
- **A `.node` is a shared library** — use `-fPIC`, not `-fPIE -pie`.
- **`_FORTIFY_SOURCE` must be OFF under AddressSanitizer; standard-library assertions need
  not be disabled absent a demonstrated toolchain conflict.**

## Primary sources

- OpenSSF — *Compiler Options Hardening Guide for C and C++* (CC BY 4.0):
  https://best.openssf.org/Compiler-Hardening-Guides/Compiler-Options-Hardening-Guide-for-C-and-C++.html
- GCC — *Instrumentation Options* (`-fcf-protection`, `-fstack-protector-strong`,
  `-fstack-clash-protection`, `-ftrivial-auto-var-init`):
  https://gcc.gnu.org/onlinedocs/gcc/Instrumentation-Options.html
- GCC — *AArch64 Options* (`-mbranch-protection`):
  https://gcc.gnu.org/onlinedocs/gcc/AArch64-Options.html
- Clang — *AddressSanitizer* (flags, sanitizer build): https://clang.llvm.org/docs/AddressSanitizer.html
- Microsoft Learn — `/Qspectre`: https://learn.microsoft.com/en-us/cpp/build/reference/qspectre
- Microsoft C++ Team Blog — *Spectre mitigations in MSVC* (ARM/ARM64 since 15.7):
  https://devblogs.microsoft.com/cppblog/spectre-mitigations-in-msvc/
- Microsoft Learn — `/guard:cf` (compiler): https://learn.microsoft.com/en-us/cpp/build/reference/guard-enable-control-flow-guard
- Microsoft Learn — `/GUARD` (linker): https://learn.microsoft.com/en-us/cpp/build/reference/guard-enable-guard-checks
- Microsoft Learn — `/guard:ehcont` (x64): https://learn.microsoft.com/en-us/cpp/build/reference/guard-enable-eh-continuation-metadata
- Microsoft Learn — `/CETCOMPAT` (x64): https://learn.microsoft.com/en-us/cpp/build/reference/cetcompat
- Microsoft Learn — `/HIGHENTROPYVA` (64-bit): https://learn.microsoft.com/en-us/cpp/build/reference/highentropyva-support-64-bit-aslr
- Microsoft Learn — `/DYNAMICBASE`, `/NXCOMPAT`, `/GS`, `/sdl`, `/ZH`, and the
  C/C++ project property pages (`/guard:signret` = ARM64, ASan = x86/x64):
  https://learn.microsoft.com/en-us/cpp/build/reference/c-cpp-prop-page
- node-gyp — GYP field reference / `common.gypi` behavior: https://github.com/nodejs/node-gyp
- Node.js — Node-API and C++ addons: https://nodejs.org/api/n-api.html
