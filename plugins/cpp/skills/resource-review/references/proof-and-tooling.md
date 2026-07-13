<!-- Original synthesis. Adapted sources: cppreference (CC BY-SA 3.0/GFDL), SEI CERT standards prose (CC BY 4.0), and OpenSSF Compiler Hardening Guide (CC BY 4.0). The C++ Core Guidelines (custom license) were consulted, not relicensed. This file: CC BY-SA 4.0. See ../ATTRIBUTION.md. -->

# Proof and Tooling

How to turn a *suspected* native defect into *proof*, and the false-positive
discipline that keeps a resource review signal-dense. A sanitizer fault is the
strongest evidence, but an exhaustive source trace can also prove an unconditional
lifetime violation. Read this before reporting anything, and again during self-verification.

## Contents

- [The proof hierarchy](#the-proof-hierarchy)
- [Building the addon under a sanitizer](#building-the-addon-under-a-sanitizer)
- [Loading a sanitized addon into unsanitized Node](#loading-a-sanitized-addon-into-unsanitized-node)
- [Runtime options and the zero-exit trap](#runtime-options-and-the-zero-exit-trap)
- [What each sanitizer does NOT catch](#what-each-sanitizer-does-not-catch)
- [Valgrind: the no-rebuild alternative](#valgrind-the-no-rebuild-alternative)
- [The deterministic reproducer](#the-deterministic-reproducer)
- [Static analysis is a lead, never proof](#static-analysis-is-a-lead-never-proof)
- [Suppressions: legitimate vs. bug-masking](#suppressions-legitimate-vs-bug-masking)
- [The reporting gate: Proven / Lead / Theoretical](#the-reporting-gate-proven--lead--theoretical)

## The proof hierarchy

Rank evidence by how directly it demonstrates the defect. Prefer the strongest
proof you can obtain; do not report below the "Lead" line as if it were a finding.

| Rank | Evidence | Proves |
|---|---|---|
| **1 — strongest** | Sanitizer report **with a symbolized stack trace into first-party code**: ASan use-after-free / heap-buffer-overflow / double-free, LSan direct leak, UBSan signed-integer-overflow / misaligned / null, TSan data race (two stacks) | The exact defect, at the exact line, on a real execution |
| **2** | Valgrind Memcheck (heap OOB, UAF, leak, uninitialized read) or Helgrind/DRD (race, lock-order) report — no rebuild required | Same class of defect via a different engine; corroborates or substitutes for 1 |
| **3** | A **deterministic reproducer**, or a **complete traced lifetime** with `file:line` for acquisition, every ownership transfer/branch, the reachable trigger, and the missing/invalid release or use | A reproducible failure, or an unconditional defect established directly from the full code path |
| **4 — lead only** | Static-analyzer diagnostic (clang-analyzer / Cppcheck / MSVC `/analyze`) or an incomplete/conditional lifetime trace | A *path worth checking*. Over-approximating; missing facts must be resolved before reporting |

A defect-class review reports rank 1–3. For a traced-lifetime proof, explicitly show why
RAII, cleanup hooks, callers, error paths, and teardown ordering do not refute it. A rank-4
lead goes in "Needs verification" as a question — never as a finding. See [`defect-classes.md`](./defect-classes.md)
for what each sanitizer report maps to, and [`report-format.md`](./report-format.md)
for how to write it up.

## Building the addon under a sanitizer

Sanitizers are **compile-time instrumentation**: you must rebuild the `.node`
with `-fsanitize=…` on **both** the compile and link steps. The flag combinations
that share a binary are `address,undefined,leak` (LSan is bundled in ASan); `thread`
must be a **separate** build (`address` + `thread` are mutually exclusive), and MSan
is impractical here (it needs Node and V8 themselves instrumented — Linux-only, skip
it). See [`napi-resource-model.md`](./napi-resource-model.md) for what to exercise.

```bash
# ASan + UBSan + LSan, one binary. -fno-sanitize-recover makes UBSan FAIL, not warn.
clang++ -fsanitize=address,undefined -fno-sanitize-recover=undefined \
        -fno-omit-frame-pointer -g -O1 ...   # compile AND link
```

`fs-metadata: scripts/sanitizers-test.sh` sets exactly this: `CC/CXX=clang`,
`CFLAGS/CXXFLAGS="-fsanitize=address -fno-omit-frame-pointer -g -O1"`,
`LDFLAGS=-fsanitize=address` (`sanitizers-test.sh:42-45`). Wire the flag into
`binding.gyp` on the right per-OS key (`cflags_cc`/`ldflags` on Linux,
`xcode_settings.OTHER_CPLUSPLUSFLAGS`/`OTHER_LDFLAGS` on macOS — plain `cflags`
is ignored by the Xcode generator).

Two build-time corrections that matter for a *valid* sanitizer run:

- **`_FORTIFY_SOURCE` must be OFF under AddressSanitizer.** The OpenSSF guide is
  explicit: do not enable `_FORTIFY_SOURCE` for instrumented builds — it produces
  false positives/negatives against ASan's own allocator. Prepend
  `-U_FORTIFY_SOURCE` (or `-U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0`) in the sanitizer
  build. This is a real gap in `fs-metadata: binding.gyp` (fortify is added
  unconditionally, including under the ASan recompile) and in `node-sqlite`'s
  single-profile sanitizer script — a corrected version gates fortify off the
  sanitizer profile.
- **Keep `-fPIC`; do not add `-pie`/`-fPIE`.** A Node addon is a **shared object**
  `dlopen`ed into the host — `-fPIC` is already required and correct. ASan does not
  need PIE for a shared library. (MSan and TSan want PIE for a main executable, but
  you are not building one.) **ASan static linking is unsupported.** Hardening-flag
  portability (arch-gated `-fcf-protection`/`-mbranch-protection`, ELF-only
  `-Wl,-z,*`) belongs to the `project-setup` skill's `compiler-hardening.md`, not here.

## Loading a sanitized addon into unsanitized Node

This is the step that trips everyone. **The `node` binary is not built with a
sanitizer**, so the ASan runtime loads *late* (the addon is `dlopen`ed into an
already-running process) and ASan aborts:

```
==NNN==ASan runtime does not come first in initial library list; you should
either link runtime to your application or manually preload it with LD_PRELOAD.
```

Fix: preload the runtime so it is the first library, then run your **JS test
suite** (that is what exercises the addon):

```bash
# Linux (clang). Resolve the exact runtime path — arch/version-sensitive: verify.
LD_PRELOAD="$(clang++ -print-file-name=libclang_rt.asan-x86_64.so)" \
ASAN_OPTIONS=detect_leaks=1:abort_on_error=1 \
UBSAN_OPTIONS=print_stacktrace=1:halt_on_error=1 \
LSAN_OPTIONS=suppressions=./.lsan-suppressions.txt \
  node --expose-gc test/run.js
```

- GCC's runtime is `libasan.so` (`gcc -print-file-name=libasan.so`). Never
  hard-code the filename — resolve it with `-print-file-name` (`fs-metadata:
  scripts/sanitizers-test.sh:56-71`).
- **macOS:** use `DYLD_INSERT_LIBRARIES=<libclang_rt.asan_osx_dynamic.dylib>`
  instead of `LD_PRELOAD` (`fs-metadata: scripts/macos-asan.sh`). **SIP strips
  `DYLD_INSERT_LIBRARIES`** from system binaries and from Jest/worker child
  processes — run a **self-built/Homebrew `node`** and a **single-process** harness
  (no worker fork), or ASan interceptors are silently never installed and the run
  proves nothing.
- **LeakSanitizer is unsupported on macOS arm64** — set `detect_leaks=0` there or
  ASan aborts at startup (`fs-metadata: scripts/macos-asan.sh:34-38`); fall back to
  the Xcode `leaks` tool.
- TSan is a separate run: `TSAN_OPTIONS=halt_on_error=1:suppressions=./tsan.supp`.

## Runtime options and the zero-exit trap

A sanitizer that prints a report but **exits 0** will pass CI and hide the defect.
Two independent causes, two fixes:

- **UBSan is recoverable by default** — it prints and keeps going. Force failure at
  build time (`-fno-sanitize-recover=undefined`) *and/or* runtime
  (`UBSAN_OPTIONS=halt_on_error=1`). `print_stacktrace=1` is off by default; you
  almost always want it.
- **ASan/LSan** can also report-and-continue depending on `halt_on_error`/`exitcode`
  and how the JS runner swallows output. The robust move: **post-process the
  combined output and fail on any sanitizer banner even when the exit code is 0**
  (`fs-metadata: scripts/analyze-sanitizer-output.ts`, `sanitizers-test.sh:97-101`).

| Var | Key options |
|---|---|
| `ASAN_OPTIONS` | `detect_leaks=1`, `abort_on_error=1`, `halt_on_error=1`, `verify_asan_link_order=0` (for the `dlopen` case) |
| `LSAN_OPTIONS` | `suppressions=<file>`, `print_suppressions=1` (LSan options do **not** go in `ASAN_OPTIONS`) |
| `UBSAN_OPTIONS` | `print_stacktrace=1`, `halt_on_error=1`, `suppressions=<file>` |
| `TSAN_OPTIONS` | `halt_on_error=1`, `history_size=2..7` (for the second race stack), `suppressions=<file>` |

## What each sanitizer does NOT catch

A clean run under one sanitizer is **not** proof the others would be clean. Do not
generalize a green ASan run into "no memory bugs."

| Tool | Catches | Does **not** catch |
|---|---|---|
| **ASan** | heap/stack/global OOB, use-after-free/return/scope, double/invalid free | uninitialized reads; data races; integer/UB; *reachable* leaks |
| **LSan** | allocations with **no remaining pointer** at exit | "still reachable" objects (singletons, caches) — not reported |
| **UBSan** | signed overflow, misalignment, null deref, bad shift/enum/bool, OOB *index* | unsigned overflow (unless explicitly enabled); heap/stack overflow (ASan's job); leaks; races; uninit reads |
| **TSan** | data races, lock-order deadlocks | memory errors; leaks; UB; **races in code not built with `-fsanitize=thread`** — i.e. inside V8/Node → missed races |
| **Valgrind Memcheck** | heap OOB/UAF, uninitialized reads, leaks, mismatched free | **stack and global** overflows (unreliable — ASan is better here); races |

Consequence: to claim a resource is clean you run **`address,undefined,leak`** in
one job and **`thread`** in a second. UBSan is the only tool that proves an
integer-overflow (CWE-190) or misalignment claim; ASan is the only one that proves
a stack/global overflow; LSan proves a direct leak (CWE-401) but is silent on the
reachable-but-unfreed case. Valgrind's "still reachable" class can identify such allocations
for investigation, but is not itself proof of a defect: report only a violated lifetime contract
or demonstrated harmful growth.

## Valgrind: the no-rebuild alternative

Memcheck needs **no recompilation** — it runs stock `node`, which is exactly why it
is the fallback when the LD_PRELOAD/DYLD dance fails. It is ~10x–50x slower but often
the fastest path to a first repro.

```bash
valgrind --tool=memcheck --leak-check=full \
  --show-leak-kinds=definite,indirect,possible --track-origins=yes \
  --error-exitcode=1 --suppressions=./.valgrind.supp --gen-suppressions=all \
  node test/run.js
```

- `--error-exitcode=1` is **essential** — Valgrind's default exit is 0 even on
  errors (the same zero-exit trap).
- Leak classes: **definitely lost** (no pointer), **indirectly lost** (only via a
  lost parent), **possibly lost** (interior pointer only), **still reachable**
  (alive at exit — often a benign singleton). A practical gate is grepping the
  summary for `definitely lost: 0 … indirectly lost: 0` (`fs-metadata:
  scripts/valgrind-test.sh:63-76`).
- **Helgrind** (`--tool=helgrind`) / **DRD** (`--tool=drd`) find races and
  lock-order deadlocks without a TSan rebuild — the alternative when you cannot
  produce a clean all-instrumented TSan binary.
- `--gen-suppressions=all` emits ready-to-paste stanzas for V8/Node/ICU/OpenSSL
  one-time-init noise you cannot fix — the seed for a *narrow* suppression file.

## The deterministic reproducer

A sanitizer report is strongest when it rides on a test that faults **every time**.
To get there:

- **Drive it from JS under GC pressure.** Many addon lifetime bugs (finalizer order,
  `ObjectWrap` teardown, reference use-after-free) only surface when V8 collects at an
  awkward moment. Run with `--expose-gc` and force `global.gc()` between operations
  (`fs-metadata: scripts/check-memory.ts` uses a JS GC-based memory test on every
  platform before the native sanitizers run).
- **Reproduce teardown bugs with Worker threads / `process.exit()`.** Env-cleanup
  and instance-data finalizer defects (see [`napi-resource-model.md`](./napi-resource-model.md))
  need a real env teardown to fire; a single `require()` never exercises them.
- **Minimize.** Strip the repro to the smallest JS that still faults under ASan/
  Valgrind. A one-screen repro that reliably crashes is stronger proof than a 500-line
  suite that crashes "sometimes."
- A repro that faults **only under a sanitizer** (not in a normal run) is still
  rank-3 proof — the sanitizer is revealing UB the optimizer otherwise hides.

## Static analysis is a lead, never proof

clang-tidy's `clang-analyzer-*` group, `scan-build`, Cppcheck, and MSVC `/analyze`
do path-sensitive or heuristic analysis without running the code. They surface real
bugs — `clang-analyzer-cplusplus.NewDeleteLeaks`, `clang-analyzer-core.NullDereference`,
`unix.Malloc`, `bugprone-use-after-move` — but they **over-approximate**: a diagnostic
is a hypothesis about a path that may be infeasible. Confirm every one with a
sanitizer, reproducer, or complete traced lifetime before it becomes a finding.

Sources of static-analysis **false positives** in this domain:

- **Toolchain header mismatch.** Running Homebrew-LLVM clang-tidy against Apple SDK
  headers, or clang-tidy against an MSVC `compile_commands.json`, yields parse errors
  and phantom diagnostics that are artifacts of the wrong headers, not bugs in your
  code (`R04` §6.1). The robust fix is a matching toolchain (`-isysroot`, a matching
  LLVM), **not** deleting the output.
- **Missing / wrong `compile_commands.json`.** node-gyp does not emit one; without a
  correct DB (via `bear -- npx node-gyp build` or CMake.js) clang-tidy guesses flags,
  misses include paths and the C++ standard, and emits garbage.
- **Unscoped analysis.** Without a `HeaderFilterRegex` limited to `src/`, you drown in
  `cppcoreguidelines-*` findings inside `napi.h` / `node_api.h` / the STL that you
  cannot fix and that are not your defect.

**Do not silently regex-filter real diagnostics.** `fs-metadata: scripts/clang-tidy.ts`
drops output lines matching broad patterns like `no member named '\w+' in namespace
'std'` and `'…' file not found` to paper over the macOS/Windows header mismatch — but
a *genuine* "you used a `std::` name that doesn't exist" or a real missing-include in
first-party code is then filtered away as "known toolchain noise." Filtering is the
opposite of proof: it manufactures false negatives. Fix the toolchain instead. If you
inherit such a filter, treat any suppressed-looking diagnostic as unverified, not
absent. Tuning which checks run at all is a `project-setup` concern
(`sanitizers-and-analysis.md`), not a defect to report here.

## Suppressions: legitimate vs. bug-masking

A suppression that hides third-party noise is hygiene. A suppression broad enough to
swallow *your* code's defects is a bug-masking anti-pattern — and the single most
common way a real leak escapes a review.

**Legitimate (narrow, third-party, documented):**

- Errors/leaks inside code you cannot rebuild — V8, libc/pthread startup, ICU,
  OpenSSL one-time init. `fs-metadata: .lsan-suppressions.txt` is the good model: it
  suppresses `leak:v8::internal::…`, `leak:node::…`, `leak:uv_…`, and the build-tool
  leaks — **everything not owned by the addon** — and nothing that passes through
  first-party frames. `.valgrind.supp` similarly targets named V8/Node/ICU/OpenSSL
  init blocks with a rationale comment each.
- One-time intentional allocations (interned strings, global caches): bracket with
  `__lsan_disable()`/`__lsan_enable()` or `__lsan_ignore_object(ptr)`, not a wildcard.

**Bug-masking (avoid, and flag if you see it):**

- `node-sqlite: .lsan-suppressions.txt` suppresses `leak:napi_`, `leak:Napi::`,
  `leak:node::`, and even `leak:node_modules/`. Because **essentially every addon
  allocation touches an `napi_*`/`Napi::` frame**, a genuine first-party reference or
  handle leak is silenced along with the noise — the suppression is wide enough to
  hide the exact bug class the review exists to find. Its `.asan-suppressions.txt`
  blanket-suppresses `interceptor_via_fun:pthread_*`/`dlopen`/`dlsym` similarly. The
  corrected form narrows to specific library objects / known-benign init routines
  (`leak:v8::`, `leak:icu_`) and **drops the `napi_`/`Napi::`/`node_modules/`
  wildcards** so the sanitizer keeps signal on first-party code.

Rules: a suppression is **as specific as possible** (function/file, not library-wide),
**carries a comment** linking the reason, and is periodically pruned with
`print_suppressions=1` (dead suppressions that never fire are removed). If a finding
disappears only because a suppression matched an addon-owned frame, you have not
proven the code is clean — you have proven the suppression is too broad.

## The reporting gate: Proven / Lead / Theoretical

Every candidate is in exactly one state. This is a **defect** review — report only
what dynamic evidence, a reproducer, or a complete source-level lifetime trace demonstrates.

| State | You have… | Action |
|---|---|---|
| **Proven** | A rank 1–3 artifact: a sanitizer/Valgrind report with a stack trace into first-party code, a deterministic reproducer, or a complete traced lifetime proving an unconditional violation | **Report**, with the trace, repro, or full code path embedded as the proof |
| **Lead** | A static-analyzer diagnostic or an incomplete/conditional lifetime trace whose guards, callers, ownership, or reachability remain unresolved | List under **"Needs verification"** as a question — not a finding |
| **Theoretical** | A pattern match or best-practice gap (missing `-fstack-protector`, no UBSan in CI, an over-broad suppression, no `_FORTIFY_SOURCE`) with **no observed defect** | **Drop** it from a defect review. Configuration/hardening posture belongs to the `project-setup` skill |

Signal over noise: better to omit a theoretical nit than to bury one proven
use-after-free in ten "consider adding" remarks. And note what is **not** evidence —
reviewer confidence and eloquence are not proof, and **neither is a second tool
agreeing with you**: two analyzers converge on the same infeasible path all the time.
A stack trace is preferred evidence. Without one or a reproducer, the source trace must be
complete enough to establish the violation without assumptions; otherwise it is a lead.

## Primary sources

- AddressSanitizer — Clang docs: https://clang.llvm.org/docs/AddressSanitizer.html
- LeakSanitizer — Clang docs: https://clang.llvm.org/docs/LeakSanitizer.html
- UndefinedBehaviorSanitizer — Clang docs: https://clang.llvm.org/docs/UndefinedBehaviorSanitizer.html
- ThreadSanitizer — Clang docs: https://clang.llvm.org/docs/ThreadSanitizer.html
- Valgrind Memcheck manual: https://valgrind.org/docs/manual/mc-manual.html
- Valgrind Helgrind manual: https://valgrind.org/docs/manual/hg-manual.html
- Valgrind core manual (suppressions): https://valgrind.org/docs/manual/manual-core.html
- google/sanitizers wiki — ASan LeakSanitizer & flags: https://github.com/google/sanitizers/wiki/AddressSanitizerLeakSanitizer
- google/sanitizers issue #796 (ASan link-order / LD_PRELOAD): https://github.com/google/sanitizers/issues/796
- Node.js BUILDING.md (ASan build, Linux-only): https://github.com/nodejs/node/blob/main/BUILDING.md
- Clang-Tidy (checks, `-p`, `--header-filter`, NOLINT): https://clang.llvm.org/extra/clang-tidy/
- Clang Static Analyzer checkers (`scan-build`, checker names): https://clang.llvm.org/docs/analyzer/checkers.html
- Cppcheck manual (`--error-exitcode`, `--enable`): https://cppcheck.sourceforge.io/manual.html
- MSVC `/analyze` reference: https://learn.microsoft.com/en-us/cpp/build/reference/analyze-code-analysis
- OpenSSF Compiler Options Hardening Guide (`_FORTIFY_SOURCE` incompatible with sanitizers): https://best.openssf.org/Compiler-Hardening-Guides/Compiler-Options-Hardening-Guide-for-C-and-C++.html
- Node.js Node-API reference (instance data, env cleanup hooks, finalizers): https://nodejs.org/api/n-api.html
