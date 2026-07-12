<!-- Original synthesis. Adapted sources: cppreference (CC BY-SA 3.0/GFDL), SEI CERT standards prose (CC BY 4.0), and OpenSSF Compiler Hardening Guide (CC BY 4.0). The C++ Core Guidelines (custom license) were consulted, not relicensed. This file: CC BY-SA 4.0. See ../ATTRIBUTION.md. -->

# Sanitizers and Static Analysis

Wiring dynamic and static analysis into a node-gyp native addon (and general C++17). Dynamic
analysis (sanitizers, Valgrind) proves defects at runtime with a stack trace; static analysis
(clang-tidy, the Clang analyzer, Cppcheck, MSVC `/analyze`) finds them without running. Both are
required — they catch overlapping but distinct bug classes. For reading a sanitizer trace as *proof*
of a specific defect see the resource-review skill's `proof-and-tooling.md` and `defect-classes.md`;
for the hardening flags these builds must disable see `compiler-hardening.md`.

## Contents

- [Mental model: instrumentation vs binary translation](#mental-model-instrumentation-vs-binary-translation)
- [The sanitizer matrix](#the-sanitizer-matrix)
- [Legal combinations](#legal-combinations)
- [Building a sanitized .node and loading it under Node](#building-a-sanitized-node-and-loading-it-under-node)
- [Per-tool runtime options](#per-tool-runtime-options)
- [Valgrind (no rebuild)](#valgrind-no-rebuild)
- [macOS: SIP, single-process harness, LSan on arm64](#macos-sip-single-process-harness-lsan-on-arm64)
- [Suppression discipline](#suppression-discipline)
- [clang-tidy](#clang-tidy)
- [compile_commands.json for node-gyp](#compile_commandsjson-for-node-gyp)
- [Clang Static Analyzer and Cppcheck](#clang-static-analyzer-and-cppcheck)
- [MSVC /analyze and the Core Guidelines checker](#msvc-analyze-and-the-core-guidelines-checker)
- [CI wiring](#ci-wiring)

## Mental model: instrumentation vs binary translation

Sanitizers are **compile-time instrumentation** (rebuild with `-fsanitize=…`): fast and precise.
Valgrind is a **binary-translation VM** (no recompile) but 10x–50x slower and catches a different,
overlapping set. Use both. A clean exit-0 run is meaningless if the build never linked the runtime or
the code was never exercised — always confirm the runtime loaded and that a *known* defect is caught
before trusting silence.

## The sanitizer matrix

| Tool | Flag | Finds | Slowdown | Recompile? | Platforms |
|---|---|---|---|---|---|
| **ASan** | `-fsanitize=address` | heap/stack/global overflow, use-after-free/-return/-scope, double/invalid free; leaks (bundled LSan) | ~2x | Yes | Linux, macOS, *BSD, Windows |
| **LSan** | `-fsanitize=leak` or bundled in ASan | leaks at process exit | ~0 until exit | Yes (or none via ASan) | Linux, macOS, Android, NetBSD |
| **UBSan** | `-fsanitize=undefined` | signed overflow, misalignment, null deref, bad shifts, OOB array index, bad enum/bool, `vptr` | small | Yes | Linux, macOS, Windows, *BSD |
| **TSan** | `-fsanitize=thread` | data races, lock-order deadlocks, pthread misuse | 5x–15x | Yes (**all** code incl. libs) | Linux/Darwin x86_64+arm64; **64-bit only** |
| **MSan** | `-fsanitize=memory` | reads of uninitialized memory | ~3x | Yes (**all** code incl. libc++) | **Linux/NetBSD/FreeBSD only** |
| **Valgrind Memcheck** | `valgrind --tool=memcheck` | uninit reads, heap OOB, use-after-free, leaks, mismatched/double free, bad `memcpy` overlap | 10x–50x | **No** | Linux, macOS (dated), *BSD |
| **Valgrind Helgrind** | `valgrind --tool=helgrind` | data races, pthread misuse, lock-order deadlocks | ~100x | No | same as Valgrind |

ASan does **not** find uninitialized reads (that is MSan/Memcheck), data races (TSan), or integer
overflow/UB (UBSan). Memcheck mainly instruments the heap and is weak on stack/global overflows —
ASan is better there. LSan reports allocations with *no remaining pointer* at exit; objects still
reachable at exit are not reported (contrast Valgrind's "still reachable" leak class).

**Node-addon reality:** ASan + UBSan is the high-value pair for addons. Reach for TSan only if the
addon actually spawns threads (libuv workers, `AsyncWorker`/`AsyncProgressWorker`) — `node-sqlite`'s
`BackupJob` runs `sqlite3_backup_step` on a worker thread and reads a `std::atomic<bool>` set from
the main thread, exactly the shape TSan is for. MSan is usually impractical: Node and V8 themselves
would need MSan-instrumented builds or you get false positives.

## Legal combinations

`address,undefined,leak` share one binary (recommended default). `thread` and `memory` are each
exclusive with `address` and with each other. Practical partition: **one job with
`-fsanitize=address,undefined` (LSan is part of ASan), a second with `-fsanitize=thread`, and — only
with a fully sanitized toolchain — a third with `-fsanitize=memory`.**

| Combination | Allowed? |
|---|---|
| `address,undefined` / `address` + `leak` / `undefined` + `leak` / `thread,undefined` | Yes |
| `address` + `thread` / `address` + `memory` / `thread` + `memory` / `leak` + `thread` | **No** |

MSVC supports **ASan only** (`/fsanitize=address`) — no UBSan, LSan, TSan, or MSan. TSan and MSan
are 64-bit only.

## Building a sanitized .node and loading it under Node

Two problems compound for addons. First, gyp needs the flag on **both compile and link**, and the
keys differ per platform (`cflags`/`cflags_cc` are ignored on macOS — mac uses `xcode_settings`):

```python
{
  "target_name": "addon",
  "cflags_cc": ["-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-g", "-O1"],
  "ldflags":  ["-fsanitize=address,undefined"],
  "conditions": [
    ["OS=='mac'", { "xcode_settings": {
      "OTHER_CPLUSPLUSFLAGS": ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"],
      "OTHER_LDFLAGS":        ["-fsanitize=address,undefined"] }}],
    ["OS=='win'", { "msvs_settings": {
      "VCCLCompilerTool": { "AdditionalOptions": ["/fsanitize=address"] }}}]  # ASan only on MSVC
  ]
}
```
(Keys are standard gyp; behavior is version-sensitive — verify against your node-gyp version.)

Second, the **load-order problem**: ASan must be first in the initial shared-library list so it can
intercept `malloc`/`free` before anything allocates. A `.node` is `dlopen`ed into an
already-running `node` that was **not** built with ASan, so on Linux you get
`ASan runtime does not come first in initial library list …`; on Windows/MSVC the same "ASan must be
the first DLL" rule fails **silently** as corruption. Two fixes:

- **Build Node with ASan** (`./configure --debug --enable-asan; make`) — cleanest, but **Linux
  only** today; use a Linux container for macOS/Windows. Your addon must use the same toolchain and
  `-fsanitize=address`.
- **Keep stock Node, preload the runtime** (Linux):
  ```bash
  LD_PRELOAD="$(clang++ -print-file-name=libclang_rt.asan-x86_64.so)" \
    ASAN_OPTIONS=detect_leaks=0:verify_asan_link_order=0 \
    node test/run.js
  ```
  The runtime filename is version/arch-specific — always resolve it with `-print-file-name`
  (`libasan.so` for GCC; `libclang_rt.asan_osx_dynamic.dylib` on macOS via `DYLD_INSERT_LIBRARIES`).
  `verify_asan_link_order=0` silences the link-order check for the `dlopen` case. `detect_leaks=0` is
  common because a non-ASan V8/Node reports benign "leaks"; better is to keep leaks on with a narrow
  `LSAN_OPTIONS=suppressions=` file for V8/Node internals (see
  [Suppression discipline](#suppression-discipline)).

`fs-metadata: scripts/sanitizers-test.sh` is a working model: `CXXFLAGS="-fsanitize=address
-fno-omit-frame-pointer -g -O1"`, `LDFLAGS=-fsanitize=address` (:45-46),
`LSAN_OPTIONS=suppressions=$(pwd)/.lsan-suppressions.txt` (:50), preloads the detected
`libclang_rt.asan` (:56-71), and post-processes output so a report that still exits 0 fails the run
(:97-101). That last step matters: **UBSan is recoverable by default** — it prints and keeps going
(exit 0). To fail CI, build `-fno-sanitize-recover=undefined` (or `-fsanitize-trap=undefined`) **and**
set `UBSAN_OPTIONS=halt_on_error=1`.

> **`_FORTIFY_SOURCE` must be OFF under ASan.** The OpenSSF guide is explicit: do not enable
> `_FORTIFY_SOURCE` for sanitizer builds (false positives/negatives). If your base `cflags` define it
> (as hardened addon builds do), the sanitizer profile must prepend `-U_FORTIFY_SOURCE`. See
> `compiler-hardening.md` for the full hardening set and the `-fPIC`-vs-`-pie` and `-fcf-protection`
> (x86-only) vs `-mbranch-protection` (arm64-only) arch splits — those belong to the production build,
> not the sanitizer build. The MSan `-fPIE -pie` example in Clang's docs is for executables; addons
> are shared objects and use `-fPIC`.

## Per-tool runtime options

Colon-separated `key=value`; `ASAN_OPTIONS=help=1 ./x` prints all. LSan options for an ASan build go
in **`LSAN_OPTIONS`, not `ASAN_OPTIONS`.**

| Var | Key options |
|---|---|
| `ASAN_OPTIONS` | `detect_leaks=1` (Linux default), `halt_on_error=true`, `abort_on_error`, `detect_stack_use_after_return`, `suppressions=<file>`, `verify_asan_link_order=0` (dlopen), `log_path` |
| `LSAN_OPTIONS` | `suppressions=<file>`, `exitcode=23`, `max_leaks`, `print_suppressions=1` (shows which fired — prune dead ones) |
| `UBSAN_OPTIONS` | `print_stacktrace=1` (off by default — almost always want it), `halt_on_error=1`, `suppressions=<file>` |
| `TSAN_OPTIONS` | `halt_on_error=1`, `exitcode=66`, `history_size=0..7` (raise to recover the 2nd stack of a race), `suppressions=<file>` |

## Valgrind (no rebuild)

Memcheck (default tool) catches uninitialized-value use, heap OOB, use-after-free, mismatched/double
free, `memcpy` overlap, and leaks — but is weak on stack/global overflows. Essential flags:

```bash
valgrind --leak-check=full --show-leak-kinds=definite,indirect,possible \
  --track-origins=yes --error-exitcode=1 --suppressions=node.supp \
  --gen-suppressions=all node test/run.js
```

`--error-exitcode` is **mandatory for CI** — Valgrind exits 0 on errors by default. Leak classes:
*definitely lost* (no pointer), *indirectly lost* (only via a lost parent), *possibly lost* (interior
pointer only), *still reachable* (reachable at exit — often fine, e.g. singletons, V8/ICU one-time
init). `fs-metadata: scripts/valgrind-test.sh` greps for `definitely lost: 0 … indirectly lost: 0`
as its pass gate (:63-76) and ships `.valgrind.supp` for V8/Node/ICU/OpenSSL one-time-init blocks
with per-entry rationale. Suppression stanza format uses `tool:kind` (e.g. `Memcheck:Leak`) then
`fun:`/`obj:`/`src:` frames — **C++ names must be mangled**; `...` is a frame-count wildcard.
Helgrind/DRD detect races and lock-order deadlocks without a rebuild but run ~100x.

## macOS: SIP, single-process harness, LSan on arm64

- **SIP strips `DYLD_INSERT_LIBRARIES`** (the macOS `LD_PRELOAD`) when launching protected/system
  binaries and, critically, from **forked worker child processes**. A Jest/worker-based test runner
  therefore loses the ASan interceptors in its workers, so the sanitizer silently does nothing.
  `fs-metadata` treats that case as non-fatal and falls back to the Xcode `leaks` tool
  (`scripts/macos-asan.sh:63-106`), but the consequence is that the trickiest CoreFoundation/IOKit
  RAII code gets the *least* sanitizer coverage. **Fix:** run a small **single-process harness**
  directly under `DYLD_INSERT_LIBRARIES` (no worker fork), so interceptors survive — a tiny
  `node -e`/script that exercises the addon, not the full worker-forking test framework. Use a
  self-built/Homebrew `node`, never the SIP-protected system one.
- **LSan is unsupported on macOS arm64.** Enabling it aborts ASan at startup. `macos-asan.sh`
  disables `detect_leaks` on arm64 (:34-38); on macOS x64 leak detection works via
  `ASAN_OPTIONS=detect_leaks=1`. Plan leak coverage for arm64 through the `leaks` tool or a Linux
  ASan/LSan job instead.

## Suppression discipline

A suppression file trades coverage for quiet. The rule: **suppress only third-party or known-init
noise you cannot rebuild (V8, libc, ICU, OpenSSL, pthread startup); never wildcard first-party
frames.** `print_suppressions=1` shows which fired so dead rules can be pruned.

- **Good (narrow):** `fs-metadata: .lsan-suppressions.txt` suppresses `leak:v8::internal::…`,
  `leak:node::…`, `leak:uv_…`, libc/pthread startup, and specific build-tool/`@unrs/resolver`
  leaks — everything *not* owned by the addon.
- **Bad (over-broad):** `node-sqlite: .lsan-suppressions.txt` suppresses whole frames like
  `leak:napi_`, `leak:Napi::`, `leak:node::`, `leak:napi_register_module`, and even
  `leak:node_modules/`. Because essentially every addon allocation passes through an `napi_*`/`Napi::`
  frame, this silences the addon's *own* reference/handle leaks — the exact defects LSan exists to
  find. Narrow to specific library objects/init routines (`leak:v8::`, `leak:icu_`) and drop the
  `napi_`/`Napi::`/`node_modules/` wildcards.
- **Wire the file you actually load.** `fs-metadata`'s `.asan-suppressions.txt` and `.asan-options`
  are **dead config** relative to CI: `sanitizers-test.sh` sets `ASAN_OPTIONS=` inline with no
  `suppressions=` and only loads the *LSan* file; `.asan-options` even says so in its header
  ("this file is not loaded automatically", :2-3). Either wire it
  (`ASAN_OPTIONS=suppressions=./.asan-suppressions.txt:…`) or delete it, so no one edits a
  suppression and wonders why nothing changed.

A suppression must be as specific as possible (function/file, not library-wide) and carry a comment
linking a tracking issue. Prefer fixing, or `__attribute__((no_sanitize("…")))` on one reviewed
function, over a broad rule that makes CI green by hiding the bug. TSan's `called_from_lib:<lib>` and
LSan's `leak:<lib>` exist specifically for non-instrumented third-party `.so`s.

## clang-tidy

clang-tidy runs AST-matcher "checks" **and** can drive the Clang Static Analyzer (`clang-analyzer-*`
is literally the same symbolic-execution checkers `scan-build` runs; everything else is fast
syntactic matching). Check groups relevant to an addon:

| Prefix | Purpose | Enable on first-party code? |
|---|---|---|
| `bugprone-*` | likely-bug constructs (`bugprone-use-after-move`, `bugprone-dangling-handle`, `bugprone-unchecked-optional-access`) | Yes — high signal |
| `clang-analyzer-*` | surfaces the static analyzer (`clang-analyzer-cplusplus.NewDelete`, `clang-analyzer-unix.Malloc`) | Yes (slower) |
| `cppcoreguidelines-*` | Core Guidelines (`cppcoreguidelines-special-member-functions`, `cppcoreguidelines-owning-memory`) | Selectively — see below |
| `cert-*` | SEI CERT rules (mostly aliases) | Selectively |
| `performance-*` | perf pitfalls (`performance-unnecessary-copy-initialization`, `performance-for-range-copy`) | Yes |
| `modernize-*` | C++11+ (`modernize-use-nullptr`, `modernize-use-override`, `modernize-make-unique`) | Yes |
| `misc-*` | (`misc-const-correctness`, `misc-unused-parameters`) | Yes |
| `concurrency-*` | (`concurrency-mt-unsafe`) | If threaded |
| `readability-*` / `hicpp-*` | clarity/style; `hicpp-*` is mostly aliases of the canonical names | Trim heavily |

Prefer the canonical (`modernize-`/`cppcoreguidelines-`/`performance-`) name; don't *also* enable the
`hicpp-*`/`cert-*` alias of the same rule or you double-report. Check names drift across LLVM
majors — confirm with `clang-tidy --list-checks -checks=*`, never from memory.

**Commonly disabled because they bury C-interop/Node-API code** (the reason is what each check
*does*, not a defect):

| Check | Why disabled |
|---|---|
| `readability-magic-numbers` / `cppcoreguidelines-avoid-magic-numbers` | flags nearly every numeric literal |
| `cppcoreguidelines-pro-type-vararg` | fires on `printf` **and every Node-API varargs call** |
| `cppcoreguidelines-pro-bounds-pointer-arithmetic` / `-pro-bounds-array-to-pointer-decay` | pervasive in buffer/FFI code |
| `cppcoreguidelines-owning-memory` | requires `gsl::owner<>` annotations you likely don't use |
| `misc-non-private-member-variables-in-classes` | flags plain structs / public data members |
| `modernize-use-trailing-return-type`, `readability-identifier-length` | pure style, huge volume |

**Enable the RAII/ownership checks on first-party code even when they're off globally.** The three
worth their noise for addon lifetime code are `cppcoreguidelines-special-member-functions` (rule of
five — the hand-written move-only guards), `cppcoreguidelines-owning-memory` (raw owning pointers like
`DatabaseSync*`, `sqlite3_stmt*`), and `bugprone-use-after-move`. `node-sqlite` disables the two `cppcoreguidelines-`
checks globally (`cppcoreguidelines-owning-memory` at `.clang-tidy:15`,
`cppcoreguidelines-special-member-functions` at `:19`, plus the `hicpp-special-member-functions` alias
at `:26`) while keeping `bugprone-use-after-move` on — reasonable for its vendored SQLite/Node shims, but its own guards
and `ObjectWrap` subclasses are exactly what those checks protect; scope them back on with a nested
`.clang-tidy` (its `HeaderFilterRegex` already excludes `upstream|shims|node_modules|vendored`).
`fs-metadata` keeps a strict set only in `src/windows/.clang-tidy` (`InheritParentConfig: true`),
leaving `src/darwin/*.cpp` — its most RAII-dense CoreFoundation/IOKit code — ungated. Promote the RAII
checks to the root and set them as `WarningsAsErrors`; an empty `WarningsAsErrors` plus a
fail-only-on-errors runner makes clang-tidy purely advisory.

```yaml
Checks: >
  -*, bugprone-*, clang-analyzer-*, cppcoreguidelines-*, performance-*, modernize-*, misc-*,
  -cppcoreguidelines-pro-type-vararg, -cppcoreguidelines-pro-bounds-pointer-arithmetic,
  -cppcoreguidelines-avoid-magic-numbers
WarningsAsErrors: 'bugprone-*,clang-analyzer-*,cppcoreguidelines-special-member-functions'
HeaderFilterRegex: '.*/src/.*'   # your code only — not napi.h / node headers / STL
```

Set `HeaderFilterRegex` to match **only your `src/`**. `napi.h` and `node_api.h`/`js_native_api.h`
live under `node-addon-api/` and the node-gyp header cache; without scoping you drown in
`cppcoreguidelines-*` findings inside headers you cannot fix. Suppress in source with
`// NOLINT(check-name)` / `NOLINTNEXTLINE(...)` / `NOLINTBEGIN … NOLINTEND` (each applies to its own
line only).

**Do not silently regex-filter real diagnostics.** A common hack when clang-tidy can't parse the
platform's system headers (Homebrew-LLVM vs Apple headers; MSVC vs clang) is to drop output lines
matching broad patterns like `no member named '\w+' in namespace 'std'` or `'…' file not found`. That
also swallows a genuine "you used a `std::` name that doesn't exist" or a real missing-include in
*your* code (`fs-metadata: scripts/clang-tidy.ts` does exactly this). The robust fix is to install a
matching LLVM and point `--extra-arg`/`-isysroot` at the right sysroot, not to filter the analyzer's
errors.

## compile_commands.json for node-gyp

clang-tidy, Cppcheck, and the Clang analyzer all want a **`compile_commands.json`** (via `-p
<dir>`), and **node-gyp does not emit one** — it drives `make` (Linux/macOS) or MSBuild (Windows).
Produce the DB out-of-band:

- **Linux/macOS:** intercept the build with Bear — `bear -- npx node-gyp build` — or `compiledb`.
- **Any platform:** build with CMake.js instead of node-gyp and pass
  `-DCMAKE_EXPORT_COMPILE_COMMANDS=ON`.
- **Windows/MSVC:** Bear relies on POSIX exec interception and does **not** work. Use CMake.js/Ninja
  to emit the DB, or skip the DB entirely and run MSVC `/analyze` in the MSBuild step (it *is* the
  compiler; no DB needed).

clang-tidy on a `cl.exe`-produced DB is fragile: newer MSVC flags like `/external:I` are unknown to
the Clang driver, and MSVC precompiled headers make it fail with *"unable to handle compilation,
expected exactly one compiler job"* — disable PCH for the clang-tidy pass. The common cross-platform
split is **clang-tidy + Clang analyzer on Linux/macOS, MSVC `/analyze` + CppCoreCheck on Windows**,
rather than forcing clang-tidy to consume an MSVC compilation database.

## Clang Static Analyzer and Cppcheck

**Clang Static Analyzer** (`scan-build`, `clang --analyze`) is path-sensitive symbolic execution —
deeper than clang-tidy's syntactic checks, per-TU, and slower. Run it as a **separate** CI pass from
the fast clang-tidy lint:

```bash
scan-build --status-bugs -o out/ npx node-gyp build   # --status-bugs = nonzero exit on findings
```

Default checker packages (`core`, `cplusplus`, `deadcode`, `nullability`, `security`, `unix`) cover
null deref, `cplusplus.NewDelete`, `unix.Malloc`, etc.; `alpha.*` checkers are experimental and never
default-on. The Node-API **C** surface (`node_api.h`) is a good target for `unix.Malloc`-style
checkers.

**Cppcheck** aims for a near-zero false-positive rate and uniquely checks **all** `#if`
configurations. It needs no rebuild and consumes the DB optionally:

```bash
cppcheck --enable=warning,style,performance,portability --std=c++17 \
  --project=compile_commands.json --check-level=exhaustive \
  --error-exitcode=1 --inline-suppr
```

Default run reports `error` severity only; add categories with `--enable`. `--error-exitcode` is the
CI gate. Do not append a positional source path when using `--project`; to narrow the compilation
database, use `--file-filter='src/*'` instead. Inline-suppress with
`// cppcheck-suppress <id>` on the line before the finding (needs `--inline-suppr`). Addons
(`--addon=cert`, `--addon=misra`) post-process a dump against secure-coding standards; MISRA rule
texts are proprietary and must be supplied via `--rule-texts=`.

## MSVC /analyze and the Core Guidelines checker

`/analyze` (PREfast) runs **inside `cl.exe`** at compile time (no DB), emitting classic `C6xxx` and
Core Guidelines `C26xxx` warnings. The Core Guidelines checker ships as the **EspXEngine** plugin
plus `CppCoreCheck.dll`:

```cmd
set esp.extensions=cppcorecheck.dll
set caexcludepath=%include%
cl /analyze /analyze:plugin EspXEngine.dll ... foo.cpp
```

Or via MSBuild (set before importing `Microsoft.Cpp.targets`):

```xml
<EnableCppCoreCheck>true</EnableCppCoreCheck>
<CodeAnalysisRuleSet>CppCoreCheckRules.ruleset</CodeAnalysisRuleSet>
<RunCodeAnalysis>true</RunCodeAnalysis>
```

Representative warnings map to Core Guidelines: `C26494` (Type.5, always initialize), `C26485`
(Bounds.3, no array-to-pointer decay), `C26481` (Bounds.1, no pointer arithmetic), `C26400`
(owner/resource), `C6262` (excessive stack, tunable via `/analyze:stacksize`). Use
`ConcurrencyCheck.dll` (`C26100–C26167`) for the threaded probe/worker code. Exclude system headers
via `CAExcludePath` or `/analyze:external-` (VS2019 16.10+). Suppress with
`[[gsl::suppress("bounds.1")]]` or `[[gsl::suppress("26400")]]` — **plain numbers, no macros** (macros
aren't expanded inside attributes). Two gotchas: **disable precompiled headers** for files analyzed
with EspXEngine (it may fail reading a PCH built with default options), and since VS2019 do **not**
set `esp.annotationbuildlevel` (it causes false positives).

## CI wiring

Partition into independent jobs (sanitizers cannot share a binary; see
[Legal combinations](#legal-combinations)):

- **ASan+UBSan+LSan (Linux):** build `-fsanitize=address,undefined -fno-sanitize-recover=undefined`;
  run the suite with the runtime `LD_PRELOAD`ed and
  `ASAN_OPTIONS=abort_on_error=1 UBSAN_OPTIONS=print_stacktrace=1:halt_on_error=1
  LSAN_OPTIONS=suppressions=lsan.supp`. Post-process output so a zero-exit report still fails.
- **TSan (Linux):** only if threaded; separate binary `-fsanitize=thread`,
  `TSAN_OPTIONS=halt_on_error=1:suppressions=tsan.supp`.
- **Valgrind Memcheck (no rebuild):** `--leak-check=full --error-exitcode=1 --suppressions=node.supp`
  with a V8/Node suppression file.
- **Static (Linux/macOS):** fast clang-tidy lint (fail via `WarningsAsErrors`) plus a separate
  `scan-build --status-bugs` and/or Cppcheck `--error-exitcode=1` pass.
- **Windows:** MSVC ASan (`/fsanitize=address`) and `/analyze` + CppCoreCheck; run ASan for other
  tools via a Linux container. Run clang-tidy on **all** platforms' source, not just the host's —
  per-OS file exclusion plus a Linux-only lint matrix means a platform's RAII-dense code is never
  analyzed.

Cross-links: `ci-and-release.md` (matrix, prebuilds, provenance), `compiler-hardening.md` (the
production flags these builds disable), `build-and-toolchain.md` (gyp mechanics), and the
resource-review skill's `proof-and-tooling.md` for turning a sanitizer trace into a proven finding.

## Primary sources

- AddressSanitizer / LeakSanitizer / UBSan / ThreadSanitizer / MemorySanitizer — Clang docs: https://clang.llvm.org/docs/AddressSanitizer.html , https://clang.llvm.org/docs/LeakSanitizer.html , https://clang.llvm.org/docs/UndefinedBehaviorSanitizer.html , https://clang.llvm.org/docs/ThreadSanitizer.html , https://clang.llvm.org/docs/MemorySanitizer.html
- GCC Instrumentation Options: https://gcc.gnu.org/onlinedocs/gcc/Instrumentation-Options.html
- google/sanitizers wiki (flags, LSan, link-order): https://github.com/google/sanitizers/wiki
- Node.js BUILDING.md (`--enable-asan`): https://github.com/nodejs/node/blob/main/BUILDING.md
- Valgrind Memcheck / Helgrind / core (suppressions): https://valgrind.org/docs/manual/mc-manual.html , https://valgrind.org/docs/manual/hg-manual.html , https://valgrind.org/docs/manual/manual-core.html
- Clang-Tidy (options, checks list, aliases, config, NOLINT, `-p`): https://clang.llvm.org/extra/clang-tidy/ , https://clang.llvm.org/extra/clang-tidy/checks/list.html
- Clang Static Analyzer checkers / scan-build: https://clang.llvm.org/docs/analyzer/checkers.html , https://clang.llvm.org/docs/analyzer/user-docs/CommandLineUsage.html
- Cppcheck manual and addons: https://cppcheck.sourceforge.io/manual.html , https://github.com/danmar/cppcheck/blob/main/addons/README.md
- MSVC `/analyze` and C++ Core Guidelines checkers: https://learn.microsoft.com/en-us/cpp/build/reference/analyze-code-analysis , https://learn.microsoft.com/en-us/cpp/code-quality/using-the-cpp-core-guidelines-checkers
- OpenSSF Compiler Options Hardening Guide (`_FORTIFY_SOURCE` incompatible with sanitizers): https://best.openssf.org/Compiler-Hardening-Guides/Compiler-Options-Hardening-Guide-for-C-and-C++.html
