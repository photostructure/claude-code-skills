<!-- Original synthesis. Adapted sources: cppreference (CC BY-SA 3.0/GFDL), SEI CERT standards prose (CC BY 4.0), and OpenSSF Compiler Hardening Guide (CC BY 4.0). The C++ Core Guidelines (custom license) were consulted, not relicensed. This file: CC BY-SA 4.0. See ../ATTRIBUTION.md. -->

# Report Format

Output template for the `resource-review` skill. Summary table first, findings grouped
by **defect class** (not by file), every finding backed by a concrete PROOF, patches
proposed but **never** auto-applied. A finding without a named tool + exact diagnostic
(or a traced lifetime/reproducer) is a lead, not a finding — put it under *Needs
verification*.

## Contents
- [Severity rubric](#severity-rubric)
- [Report skeleton](#report-skeleton)
- [Anatomy of a finding card](#anatomy-of-a-finding-card)
- [What counts as PROOF, per class](#what-counts-as-proof-per-class)
- [Worked finding cards](#worked-finding-cards)
- [Needs verification](#needs-verification)
- [Proposed patches](#proposed-patches)
- [Clean result](#clean-result)
- [Rules](#rules)
- [Primary sources](#primary-sources)

## Severity rubric

Severity = **reachability × consequence**. Reachability: can attacker-influenced JS
input (a length, offset, string, buffer, or call ordering) steer the defect? Consequence:
memory corruption > exhaustion/DoS > info leak > benign cleanup. Native memory corruption
outranks the equivalent logic bug because it is UB — the optimizer may already have deleted
a nearby check (CWE-758).

| Severity | Shape | Native examples |
|----------|-------|-----------------|
| **Critical** | Attacker-influenced memory corruption reachable from JS | Heap-buffer-overflow WRITE sized from a JS number (CWE-787); use-after-free of a `napi_value`/native handle a JS caller can trigger (CWE-416); integer-overflow → under-allocation → overflow chain from a JS length (CWE-680); double-free on an attacker-reachable path (CWE-415). |
| **High** | Corruption needing a race/edge, or resource exhaustion on a hot path | UAF on a teardown/finalizer race (env exit vs. async callback); fd/handle leak on a per-request error path → descriptor exhaustion (CWE-775); `napi_ref` leak on a hot path pinning a large JS graph (CWE-401); OOB **write** reachable only via an uncommon-but-valid input. |
| **Medium** | Bounded impact, or gated by validation that currently holds | Bounded OOB **read** of a few bytes (CWE-125); integer truncation/sign-change that is currently range-checked upstream (CWE-197); uninitialized read of a non-pointer scalar; leak reachable only under an error branch that is hard to hit. |
| **Low** | Demonstrable but limited | A violated cleanup/lifetime contract with bounded exit-only impact. Process-lifetime singletons and Valgrind "still reachable" blocks are not findings unless the intended lifetime is violated or harmful growth is demonstrated. |

**Overall risk** = the highest single finding's severity (Clean if none).

## Report skeleton

````markdown
## Resource Review: <scope reviewed>

### Summary
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High     | 0 |
| Medium   | 0 |
| Low      | 0 |

**Scope:** <files / diff / addon path reviewed>
**Build under test:** <compiler + version, C++ std, Debug/Release, sanitizers enabled>
**Overall risk:** Critical / High / Medium / Low / Clean

### Findings

#### [UAF-001] Use-after-free of native handle on teardown race — `src/db_wrap.cpp:214` (Critical — CWE-416, MEM30-C)
- **Proof (ASan):** `heap-use-after-free READ of size 8` in `DbWrap::OnComplete`; the
  *freed-by* stack is the env-cleanup hook, the *use* stack is the libuv completion
  callback. Reproducer: `test/teardown-race.js` (close the handle while a query is
  in flight), 3/50 runs trip ASan.
  ```
  ==12==ERROR: AddressSanitizer: heap-use-after-free on address 0x60700000dfb0
  READ of size 8 at 0x60700000dfb0 thread T7
      #0 DbWrap::OnComplete(uv_work_t*) src/db_wrap.cpp:214
    freed by thread T0 here:
      #1 DbWrap::Cleanup(void*)       src/db_wrap.cpp:180
  ```
- **Trigger:** JS calls `db.closeSync()` (or the process exits) while an async
  `db.query()` is still running; cleanup frees `this->handle_`, then the worker
  completion dereferences it.
- **Impact:** Read/write of freed heap → crash or, with heap grooming from JS-sized
  allocations, exploitable corruption.
- **Evidence:**
  ```cpp
  void DbWrap::OnComplete(uv_work_t* w) {
    auto* self = static_cast<DbWrap*>(w->data);
    self->handle_->flush();          // handle_ freed by Cleanup() on another path
  }
  ```
- **Fix:** Order teardown so in-flight work is drained/cancelled before the owner is
  freed, and give the resource an RAII owner instead of a raw `delete`.
  ```cpp
  // WRONG: cleanup deletes while a worker may still run
  void DbWrap::Cleanup(void* p) { delete static_cast<DbWrap*>(p); }

  // RIGHT: cancel/join outstanding work first; keep-alive ref until it drains
  void DbWrap::Cleanup(void* p) {
    auto* self = static_cast<DbWrap*>(p);
    self->CancelPending();     // stop async jobs before releasing the handle
    self->handle_.reset();     // std::unique_ptr owner, ordered release
    delete self;
  }
  ```
  Pattern reference: `node-sqlite: src/sqlite_impl.h:253-267` (RAII depth guards) and
  its documented teardown ordering — finalize all statements/backups *before* closing
  the connection to avoid UAF of async jobs.

### Needs verification
Leads whose PROOF is incomplete. Phrase as a question; do not count them.

#### [VERIFY-001] Possible OOB write — `src/codec.cpp:88`
- **Question:** Is `len` (from `info[1].As<Napi::Number>()`) bounds-checked against the
  destination `ArrayBuffer` byte length before the `memcpy`, on every path? Trace the
  caller and re-run the codec test under ASan before treating as OOBW.

### Proposed patches
For each Critical/High finding, a minimal before→after diff. **Review each patch before
applying — nothing has been changed.**
````

## Anatomy of a finding card

Header: `[<CLASS>-NNN] <one-line defect> — file:line (<Severity> — CWE-###, <CERT rule>)`.
IDs are `<CLASS>-NNN` so findings are referenceable — reuse the class slugs below.

| Field | Content |
|-------|---------|
| **Proof** | The named detector + the **exact** diagnostic it emitted (ASan/UBSan/MSan/LSan report string, Valgrind category), or a traced object lifetime, or a runnable reproducer. Paste the load-bearing lines of the trace, not the whole dump. This is the field that makes it a finding. |
| **Trigger** | Plain-English scenario in terms a JS caller understands: which API, which argument, what ordering. For addon code, name the JS entry point. |
| **Impact** | Consequence class (corruption / exhaustion / info leak / benign) and why the severity. |
| **Evidence** | The minimal source snippet at `file:line` that contains the defect. |
| **Fix** | `// WRONG` → `// RIGHT`, smallest change that removes the defect (prefer RAII / bounds check / ordered teardown over a band-aid null-check). Cite a reference-project pattern when one applies. |

Class slugs (map each finding to one — see `defect-classes.md` for the full table):
`UAF` use-after-free · `DFREE` double-free · `MISMATCH` mismatched/invalid free ·
`LEAK` memory leak · `FDLEAK` fd/handle/resource leak · `OOBW` out-of-bounds write ·
`OOBR` out-of-bounds read · `UNINIT` uninitialized read · `INTOVF` integer overflow ·
`TRUNC` truncation/sign-change · `INTCHAIN` overflow→under-alloc→overflow ·
`NPD` null-pointer deref · `PTRUB` pointer-arithmetic UB · `TOCTOU` filesystem race.

## What counts as PROOF, per class

For dynamic proof, name the tool **and** the diagnostic it prints. For a source-level
proof, trace the complete path required by `proof-and-tooling.md`. "Looks like a leak"
is not proof. See that reference for how to run each tool and reduce a reproducer.

| Class (CWE) | Typical dynamic proof = tool + exact diagnostic |
|-------------|--------------------------------|
| `UAF` (416) | ASan `heap-use-after-free` (with alloc + free stacks); Valgrind "Invalid read/write … N bytes inside a block … free'd"; scope variants need ASan `stack-use-after-scope` / `stack-use-after-return`. |
| `DFREE` (415) | ASan `attempting double-free`; Valgrind "Invalid free() / delete / delete[]". |
| `MISMATCH` (762/590) | ASan `alloc-dealloc-mismatch`, `new-delete-type-mismatch`; Valgrind "Mismatched free() / delete / delete []"; non-heap free → Valgrind "Invalid free()". |
| `LEAK` (401) | LeakSanitizer leak report (`ASAN_OPTIONS=detect_leaks=1` or `-fsanitize=leak`); Valgrind `--leak-check=full` **"definitely lost"** or "indirectly lost". "Still reachable" is investigation context, not proof absent a violated lifetime contract or harmful growth. |
| `FDLEAK` (775/772) | Valgrind `--track-fds=yes` lists the still-open descriptor + its open stack **at exit**. LSan does **not** catch the fd, only the `FILE*` memory. |
| `OOBW` (787) | ASan `heap-buffer-overflow` / `stack-buffer-overflow` / `global-buffer-overflow` **WRITE**; Valgrind "Invalid write" (heap only — Valgrind does **not** reliably catch stack/global overflows: no redzones). |
| `OOBR` (125) | ASan `*-buffer-overflow` **READ**; Valgrind "Invalid read" (heap); UBSan `bounds`/`local-bounds` for arrays of known size. |
| `UNINIT` (457) | **MSan** `use-of-uninitialized-value` (Linux/x86-64, whole-program instrumented, **mutually exclusive with ASan**); or Valgrind "Conditional jump or move depends on uninitialised value(s)". |
| `INTOVF` (190) | UBSan `signed-integer-overflow` (in `-fsanitize=undefined`); `unsigned-integer-overflow` is **not** in the default `undefined` group — enable it explicitly. UBSan default is **log-and-continue**; note whether `-fno-sanitize-recover` was set. |
| `TRUNC` (197/195) | UBSan `implicit-signed/unsigned-integer-truncation`, `implicit-integer-sign-change` (via `-fsanitize=implicit-conversion`; not in `undefined`). |
| `INTCHAIN` (680) | ASan overflow on the **undersized** buffer, plus the UBSan/`-Wconversion` evidence for the size math that wrapped. |
| `NPD` (476) | ASan SEGV with symbolized stack; UBSan `null` / `nonnull-attribute`. |
| `TOCTOU` (367) | **Not** sanitizer-detectable (it is a race). Proof = the traced check→use window (e.g. `access()` then `fopen()` on the same path) + a reproducer that swaps the file. TSan finds data races, **not** filesystem TOCTOU. |

Reporting caveats to respect when writing PROOF:
- `_FORTIFY_SOURCE` must be **OFF** under AddressSanitizer — do not cite a FORTIFY abort as your proof in an ASan build; they conflict.
- MSan and ASan cannot be combined; a `UNINIT` finding needs a separate MSan (or Valgrind) run.
- Valgrind reliably catches heap corruption but **misses stack and global overflows** — an ASan-only reproducer is expected for those; don't downgrade a finding because Valgrind stayed quiet.
- For CERT rules: cite **MEM30-C** for double-free (freeing freed memory is a prohibited *access*); MEM31-C is the *leak* rule. Both are version-sensitive: verify against the live SEI CERT wiki.

## Worked finding cards

#### [INTCHAIN-001] Integer overflow → under-allocation → heap overflow — `src/buf.cpp:43` (Critical — CWE-680, MEM35-C)
- **Proof (ASan, corroborated by UBSan):** ASan `heap-buffer-overflow WRITE of size N`
  in the copy at `buf.cpp:46`, writing past the 8-byte block allocated at `buf.cpp:44`.
  Built with `-fsanitize=unsigned-integer-overflow` (which is **not** in the default
  `undefined` group), UBSan also reports the wrap of `count * width` at `buf.cpp:43` for
  `count = 0x20000001, width = 8`. Reproducer: `Buf.pack(0x20000001, 8)` from JS.
- **Trigger:** JS passes a large `count`. The size math `count * width` is evaluated in
  32-bit `unsigned int` and wraps to 8, so `malloc` returns an 8-byte block; the copy then
  writes the real length, computed in 64-bit (~4 GB), past it.
- **Impact:** Attacker-sized heap overflow write from JS input — memory corruption.
- **Evidence:**
  ```cpp
  uint32_t count = info[0].As<Napi::Number>().Uint32Value();  // from JS
  const uint32_t width = 8;
  size_t n = count * width;                             // 32-bit multiply wraps → n == 8
  auto* p = static_cast<uint8_t*>(malloc(n));
  memcpy(p, src, static_cast<size_t>(count) * width);   // 64-bit real length → overflow
  ```
  The two multiplies differ: the size is computed in 32-bit `unsigned` (wraps), the copy
  length is widened to 64-bit first (does not). Making both 32-bit hides the bug; making
  both 64-bit still overflows for `count ≥ 2^61` — the point is to guard, not to widen.
- **Fix:** Do the size math in a width that cannot wrap and reject before allocating.
  ```cpp
  // WRONG: 32-bit multiply feeds the size; the copy uses the widened real length
  size_t n = count * width;
  // RIGHT: 64-bit throughout, guard the overflow, then allocate a container
  if (width != 0 && count > SIZE_MAX / width)
    throw Napi::RangeError::New(env, "size overflow");
  std::vector<uint8_t> buf(static_cast<size_t>(count) * width);   // RAII, one length
  ```
  Pattern reference: `fs-metadata` ships a `WouldOverflow(a, b)` guard
  (`b > 0 && a > UINT64_MAX / b`) applied before size math for exactly this class.

#### [FDLEAK-001] File descriptor leak on error path — `src/fs_read.cpp:57` (High — CWE-775, FIO42-C)
- **Proof (Valgrind):** `valgrind --track-fds=yes` reports at exit
  `Open file descriptor 27:` with the open stack at `fs_read.cpp:57`; count grows by one
  per failed call. Reproducer: call `readTagged(path)` on a file that fails validation 1000×.
- **Trigger:** JS calls the reader on inputs that hit the post-`open` validation failure;
  the early `throw`/return skips `close(fd)`.
- **Impact:** Descriptor exhaustion → `EMFILE`, denial of service on a hot path.
- **Evidence:**
  ```cpp
  int fd = open(path, O_RDONLY);
  if (!validate(fd)) throw Napi::Error::New(env, "bad header"); // fd leaks
  // ... close(fd) only on the success path
  ```
- **Fix:** Wrap the fd in an RAII guard so unwinding (thrown `Napi::Error`) closes it.
  ```cpp
  // WRONG: manual close skipped on throw
  int fd = open(path, O_RDONLY);
  // RIGHT: RAII owner closes on every exit, including exceptions
  FdGuard fd{open(path, O_RDONLY)};
  if (!validate(fd.get())) throw Napi::Error::New(env, "bad header");
  ```
  Pattern reference: `fs-metadata: src/common/fd_guard.h:26-69` (explicit ctor, `noexcept`
  move, `release()` for ownership handoff; move-assign closes the current fd first, `:56-65`).

#### [LEAK-001] `napi_ref` never deleted — `src/emitter.cpp:33` (Medium — CWE-401, MEM31-C)
- **Proof (LSan):** LeakSanitizer reports a definite leak whose allocation stack is
  `napi_create_reference` at `emitter.cpp:33`; one leaked ref per `Emitter` created,
  none freed. Grows monotonically across the create/discard loop in `test/emitter.js`.
- **Trigger:** JS constructs and discards many `Emitter`s; each stores a strong
  `napi_ref` to a callback and never calls `napi_delete_reference`.
- **Impact:** Native memory leak **and** the strong ref pins the JS callback graph,
  blocking GC of everything it retains. High if on a hot path; Medium here.
- **Fix:** Give the reference a single RAII owner that releases it exactly once while its
  environment is valid.
  ```cpp
  // WRONG: strong ref created, never released — leaks and pins the JS callback graph
  napi_create_reference(env, cb, 1, &cb_ref_);
  // RIGHT: node-addon-api RAII releases the reference with the owning ObjectWrap.
  cb_ref_ = Napi::Persistent(cb);
  // For raw napi_ref, call napi_delete_reference exactly once while env is valid.
  ```
  When distinguishing your addon's leaks from V8/Node/libuv noise, an LSan suppression
  file must **not** blanket-suppress `napi_*` / `Napi::` frames, or it will hide exactly
  this finding (see `proof-and-tooling.md`).

## Needs verification

A lead goes here — never in Findings — when any of these is unresolved: the input source
is unclear (is the length actually attacker-controlled?), the exposure boundary is unknown
(is the path reachable from JS or only from trusted C++ callers?), or the effective build
config is uncertain (was the sanitizer that would prove it even enabled?). Phrase as a
question, name the one thing to check, and do not count it in the summary table.

## Proposed patches

Collect the Critical/High before→after diffs in one section for easy review. Every patch
is a **proposal**. The reviewer never edits source as part of the review — no auto-apply,
no "I went ahead and fixed it." Prefer fixes that remove the defect class (RAII owner,
bounds check on the JS-supplied size, ordered teardown) over local patches (a lone
null-check, a `try/catch` that swallows the error) that leave the hazard latent.

## Clean result

When nothing survived proof:

> **No proven memory/resource defects identified in `<scope>`.**
> Scanned: `<files/diff>`. Build under test: `<compiler, std, sanitizers>`.
> Unresolved leads are listed under *Needs verification*.

State what was actually exercised (which sanitizers, which reproducers). "Clean" means
"no proven defect under the tools that were run," not "provably defect-free."

## Rules

- Lead with the summary table; group findings by **class**, not by file.
- Every finding needs `file:line`, an evidence snippet, a **PROOF** (named tool + exact
  diagnostic, or traced lifetime, or reproducer), a plain-English trigger, an impact, and
  a wrong→right fix. No confidence scores — if it is reported, it is proven; if it is a
  hunch, it goes under *Needs verification*.
- Tag each finding with its CWE and the applicable CERT C/C++ rule; use `<CLASS>-NNN` IDs.
- Severity is reachability × consequence: attacker-influenced corruption from JS input is
  Critical. Do not report process-lifetime or "still reachable" memory without a violated
  lifetime contract or demonstrated harmful growth.
- Respect the tool caveats: FORTIFY off under ASan; MSan/ASan mutually exclusive; Valgrind
  misses stack/global overflows; TOCTOU is not sanitizer-detectable; MEM30-C (not MEM31-C)
  for double-free. Mark any version-sensitive flag or rule id "verify."
- **Never edit files as part of the review.** Patches are proposals for human approval.

## Primary sources

- MITRE CWE — 416, 415, 762, 590, 401, 772/775, 787, 121/122, 125, 457, 190/191, 131, 680, 197/195/196, 476, 367, 758: https://cwe.mitre.org/data/definitions/ (append `<id>.html`).
- SEI CERT C Coding Standard (MEM/INT/ARR/FIO/EXP/STR rules): https://cmu-sei.github.io/secure-coding-standards/sei-cert-c-coding-standard/rules/
- SEI CERT C++ Coding Standard (MEM50-57-CPP, EXP53/54-CPP, CTR50-53-CPP): https://cmu-sei.github.io/secure-coding-standards/sei-cert-cpp-coding-standard/rules/
- Clang sanitizer docs — AddressSanitizer https://clang.llvm.org/docs/AddressSanitizer.html, UBSan https://clang.llvm.org/docs/UndefinedBehaviorSanitizer.html, MSan https://clang.llvm.org/docs/MemorySanitizer.html, LSan https://clang.llvm.org/docs/LeakSanitizer.html
- Valgrind Memcheck manual (leak classes, `--track-fds`, error categories): https://valgrind.org/docs/manual/mc-manual.html
- Node.js Node-API "Object lifetime management" (handle scopes, `napi_ref`, finalizers): https://nodejs.org/api/n-api.html#object-lifetime-management
- ISO C++ Core Guidelines (R — resource management): https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines
