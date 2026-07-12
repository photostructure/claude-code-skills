<!-- Original synthesis. Adapted sources: cppreference (CC BY-SA 3.0/GFDL), SEI CERT standards prose (CC BY 4.0), and OpenSSF Compiler Hardening Guide (CC BY 4.0). The C++ Core Guidelines (custom license) were consulted, not relicensed. This file: CC BY-SA 4.0. See ../ATTRIBUTION.md. -->

# Memory and Resource Defect Classes

The bug taxonomy behind a *proof-based* native review. For every finding, name four things: the
**defect class**, the **CWE** (and CERT rule where one exists), the **concrete detector** that
would prove it — an ASan report string, a Valgrind category, a UBSan check, or a static-analyzer
warning — and the **safe pattern** the code should use instead. "Proof-based" means: cite the tool
plus the exact diagnostic it emits, not a hunch. Reason about data flow and ownership first; grep
only to find candidates (see [Recognition grep starters](#recognition-grep-starters)). Tooling
detail lives in `proof-and-tooling.md`; addon lifetime rules (`napi_value`, handle scopes,
`napi_ref`, finalizers) live in `napi-resource-model.md`; build/flag detail lives in the
`/cpp:project-setup` skill's `compiler-hardening.md` and `sanitizers-and-analysis.md`.

## Contents

- [Master defect-class map](#master-defect-class-map)
- [Use-after-free and dangling references (CWE-416)](#use-after-free-and-dangling-references-cwe-416)
- [Double, invalid, and mismatched free (CWE-415, CWE-762, CWE-590)](#double-invalid-and-mismatched-free-cwe-415-cwe-762-cwe-590)
- [Memory, resource, and descriptor leaks (CWE-401, CWE-772)](#memory-resource-and-descriptor-leaks-cwe-401-cwe-772)
- [Buffer overflow and out-of-bounds access (CWE-787, CWE-125, CWE-121, CWE-122)](#buffer-overflow-and-out-of-bounds-access-cwe-787-cwe-125-cwe-121-cwe-122)
- [Uninitialized reads (CWE-457, CWE-908)](#uninitialized-reads-cwe-457-cwe-908)
- [Integer overflow, truncation, and signedness (CWE-190, CWE-191, CWE-681)](#integer-overflow-truncation-and-signedness-cwe-190-cwe-191-cwe-681)
- [Pointer-arithmetic UB and null dereference (CWE-469, CWE-476)](#pointer-arithmetic-ub-and-null-dereference-cwe-469-cwe-476)
- [TOCTOU filesystem races (CWE-367)](#toctou-filesystem-races-cwe-367)
- [Data races (CWE-362)](#data-races-cwe-362)
- [Detection-tool matrix](#detection-tool-matrix)
- [Hardening is defense-in-depth, not detection](#hardening-is-defense-in-depth-not-detection)
- [Recognition grep starters](#recognition-grep-starters)
- [Primary sources](#primary-sources)

---

## Master defect-class map

| Defect class | CWE | CERT C / C++ | Proves it (dynamic) | Proves it (static) |
|---|---|---|---|---|
| Use-after-free / dangling | CWE-416 | MEM30-C; MEM50-CPP, EXP54-CPP, CTR51-CPP | ASan `heap-use-after-free`; Valgrind "Invalid read/write" | `-Wanalyzer-use-after-free`; `clang-analyzer-cplusplus.NewDelete`; `bugprone-use-after-move` |
| Double-free | CWE-415 | MEM30-C; MEM51-CPP | ASan `double-free`; Valgrind "Invalid free() / delete" | `-Wanalyzer-double-free` |
| Mismatched alloc/dealloc | CWE-762 | MEM34-C (partial); MEM51-CPP | ASan `alloc-dealloc-mismatch`, `new-delete-type-mismatch`; Valgrind "Mismatched free() / delete" | `-Wanalyzer-mismatching-deallocation` |
| Free of non-heap pointer | CWE-590 | MEM34-C; MEM51-CPP | ASan bad-free; Valgrind "Invalid free()" | `-Wanalyzer-free-of-non-heap` |
| Memory leak | CWE-401 | MEM31-C; MEM51-CPP | LSan (`detect_leaks`); Valgrind "definitely/indirectly lost" | `-Wanalyzer-malloc-leak`; `clang-analyzer-cplusplus.NewDeleteLeaks` |
| Resource / fd / handle leak | CWE-772 (fd → CWE-775) | FIO42-C | Valgrind `--track-fds=yes` | `-Wanalyzer-fd-leak`, `-Wanalyzer-file-leak` |
| OOB write (heap/stack/global) | CWE-787 (CWE-121/122) | ARR30-C, STR31-C; CTR50-CPP | ASan `heap/stack/global-buffer-overflow`; Valgrind "Invalid write" (heap only) | `-Wanalyzer-out-of-bounds`; `_FORTIFY_SOURCE` (runtime) |
| OOB read | CWE-125 | ARR30-C, ARR38-C, STR32-C | ASan (any region); Valgrind "Invalid read" (heap only) | UBSan `bounds`/`local-bounds` |
| Uninitialized read | CWE-457, CWE-908 (ptr CWE-824) | EXP33-C; EXP53-CPP | **MSan** `use-of-uninitialized-value`; Valgrind "Conditional jump … uninitialised value(s)" | `-Wmaybe-uninitialized`; `cppcoreguidelines-init-variables` |
| Signed integer overflow (UB) | CWE-190 | INT32-C | UBSan `signed-integer-overflow` | `-fwrapv` (hardening) |
| Unsigned wraparound | CWE-190 | INT30-C | UBSan `unsigned-integer-overflow` (opt-in) | — |
| Truncation / sign change | CWE-197, CWE-681 | INT31-C | UBSan `implicit-*-integer-truncation`, `implicit-integer-sign-change` | `-Wconversion`, `-Wsign-conversion`; `bugprone-narrowing-conversions` |
| Overflow → under-alloc → overflow | CWE-680 (CWE-190→CWE-131) | INT30-C, MEM35-C | ASan overflow on the undersized buffer | `-Wanalyzer-tainted-allocation-size`; `bugprone-sizeof-expression` |
| Pointer-arithmetic UB | CWE-469, CWE-823 | ARR30/36/37/39-C | UBSan `pointer-overflow` | `cppcoreguidelines-pro-bounds-pointer-arithmetic` |
| NULL deref | CWE-476 | EXP34-C | ASan SEGV; UBSan `null`, `nonnull-attribute` | `-Wanalyzer-null-dereference`; `clang-analyzer-core.NullDereference` |
| TOCTOU filesystem race | CWE-367 | FIO45-C, FIO01-C, FIO02-C | not sanitizer-detectable | review + static analysis |
| Data race | CWE-362 | — | **TSan** data-race report | `concurrency-mt-unsafe` (heuristic) |
| Reliance on UB (umbrella) | CWE-758 | MSC15-C | UBSan/ASan/MSan (subsets) | UBSan family |

> **CERT caveat (version-sensitive: verify).** MITRE's CWE-415 page cites a legacy CERT title
> *"MEM31-C. Free dynamically allocated memory exactly once."* Current SEI CERT renumbers this:
> **MEM31-C is now the *leak* rule** (CWE-401), and **double-free is covered by MEM30-C** "Do not
> access freed memory." Cite MEM30-C for double-free.

---

## Use-after-free and dangling references (CWE-416)

**What:** reading or writing memory after it is freed, or dereferencing a dangling
pointer/iterator/reference.

**Recognize:**
```cpp
free(p);           use(p);            // classic UAF (C)
delete obj;        obj->method();     // UAF (C++)
auto* r = vec.data(); vec.push_back(x); use(r);  // reallocation invalidates r (CTR51-CPP)
std::string_view sv = make_temp();    // view dangles into a destroyed temporary (EXP54-CPP)
return &local;                        // returns pointer to a dead local
```
Container mutation (`push_back`, `insert`, `erase`, `resize`, `clear`) **may** invalidate
pointers/iterators/references. The guarantee depends on the exact container, operation,
whether reallocation occurs, and (for positional operations) the element's position; verify
that contract before reporting → **CTR51-CPP**. `std::string_view`/`std::span`/by-reference lambda
captures that outlive their referent → **EXP54-CPP**. `bugprone-use-after-move` catches reads of a
moved-from object.

**In native addons:** a `napi_value` is valid only while its handle scope is open — storing one past
`napi_close_handle_scope`, or using one after the native method returns, is a UAF; so is a finalizer
touching native data freed elsewhere (see `napi-resource-model.md`). When two objects reference each
other, null the back-pointer before the referent frees — `node-sqlite: src/sqlite_impl.cpp:2339-2364`
nulls `database_` in `FinalizeFromDatabase()` so the later `~StatementSync()` is a no-op.

**Safe:** RAII + smart pointers; single ownership (C++CG **R.20/R.21**, **R.11** avoid explicit
`new`/`delete`); set the pointer to `nullptr` after free (**MEM01-C**); never return a view/pointer to
a local or temporary.

**Prove:** ASan `heap-use-after-free` (prints allocation + free stacks); `stack-use-after-return` /
`stack-use-after-scope` variants (ASan only). Valgrind "Invalid read/write … inside a block … free'd."
Static: `-Wanalyzer-use-after-free`, `clang-analyzer-cplusplus.NewDelete`, `bugprone-dangling-handle`.

## Double, invalid, and mismatched free (CWE-415, CWE-762, CWE-590)

**What:** freeing the same allocation twice (CWE-415), with the wrong deallocator (CWE-762), or on a
pointer that was never heap-allocated (CWE-590). Corrupts heap metadata; exploitable.

**Recognize — deallocator must match allocator:**

| Allocated with | Free with | Wrong pairing |
|---|---|---|
| `malloc`/`calloc`/`realloc` | `free` | `delete` → CWE-762 |
| `new T` | `delete` | `free` / `delete[]` → CWE-762, `new-delete-type-mismatch` |
| `new T[]` | `delete[]` | `delete` → CWE-762 (UB; only first dtor runs) |
| stack / global / interior ptr | never free | `free` → CWE-590 |

Also: a raw pointer copied into two owners that both delete (double-free); deleting a polymorphic
object through a base pointer with no virtual destructor is UB (**OOP52-CPP**). `free(nullptr)` and
`delete nullptr` are well-defined no-ops — which is why nulling after free is a valid mitigation.

**Safe:** single ownership via `std::unique_ptr` (**MEM51-CPP**); don't mix C and C++ allocation
(**R.10**); prefer containers / `std::make_unique<T[]>` over raw arrays; give a virtual destructor to
any class deleted through a base pointer.

**Prove:** ASan `attempting double-free`, `alloc-dealloc-mismatch`, `new-delete-type-mismatch`;
Valgrind "Invalid free() / delete / delete[]", "Mismatched free() / delete / delete []". Static:
`-Wanalyzer-double-free`, `-Wanalyzer-mismatching-deallocation`, `-Wanalyzer-free-of-non-heap`,
`clang-analyzer-cplusplus.NewDelete`, `cppcoreguidelines-owning-memory`.

## Memory, resource, and descriptor leaks (CWE-401, CWE-772)

**What:** an allocation or OS resource with no reachable owner at end of lifetime. Memory leak =
CWE-401. Non-memory resource leak (`FILE*`, POSIX fd, Windows `HANDLE`, socket, mutex lock) =
CWE-772 (fd/handle → CWE-775), leading to descriptor/handle exhaustion (DoS).

**Recognize:** `new`/`malloc`/`open`/`fopen`/`CreateFile`/`socket` on a path that early-returns or
throws before the matching release; ownership handed to a raw pointer later overwritten; `lock()`
without a scope guard. In addons: `napi_create_reference` without a matching `napi_delete_reference`
pins the JS object forever and blocks GC of its whole retained graph.

**Safe:** RAII for *every* resource (**R.1**, **E.6**, **P.8**), releasing in the destructor; hand each
allocation straight to a manager object (**R.12**). Match the release function to the allocator —
`fs-metadata: src/common/fd_guard.h` wraps a POSIX fd (move-only, `noexcept` dtor guarded by
`fd_ >= 0`, deleted copy, ownership-transferring `release()`); `fs-metadata: src/darwin/raii_utils.h`
does the same for `CFRelease`, `IOObjectRelease`, and `free`. Reach for
`std::unique_ptr<T, decltype(&free)>` before writing a new class when the deleter is a plain function
(`fs-metadata: src/linux/volume_metadata.cpp:140-157`). RAII survives exception unwinding; a manual
`close()` after an early return does not.

**Prove:** LeakSanitizer (`ASAN_OPTIONS=detect_leaks=1`, or standalone `-fsanitize=leak`) reports memory
leaks at exit. Valgrind `--leak-check=full` reports **definitely / indirectly / possibly lost** and
**still reachable**. "Definitely lost" is a true leak; "still reachable" is not a defect by
itself, because an intentional process-lifetime owner may remain. Report it only when the code's
intended lifetime is violated or repeated operations demonstrate harmful growth. **LSan and Valgrind's leak check do not track
fds/handles**: use `valgrind --track-fds=yes` to list descriptors still open at exit. Static:
`-Wanalyzer-malloc-leak`, `-Wanalyzer-fd-leak`, `-Wanalyzer-file-leak`,
`clang-analyzer-cplusplus.NewDeleteLeaks`, `clang-analyzer-unix.Malloc`.

## Buffer overflow and out-of-bounds access (CWE-787, CWE-125, CWE-121, CWE-122)

**What:** access outside a buffer's bounds. Out-of-bounds **write** is CWE-787 (perennial CWE Top-25
#1–2); location refines it — CWE-121 stack, CWE-122 heap. Out-of-bounds **read** is CWE-125.

**Recognize:**
```c
char buf[16]; strcpy(buf, untrusted);   // no bound (STR31-C)
memcpy(dst, src, n);                     // n attacker-controlled, dst too small (ARR38-C)
arr[i] = v;                              // i unchecked / off-by-one, i <= n (ARR30-C)
p[len] = '\0';                           // writes one past a len-sized buffer
```
Passing a non-null-terminated buffer to a string function reads until a stray `\0` (STR32-C). In
addons, trusting a JS-supplied length or offset when writing into an `ArrayBuffer` / typed-array /
`napi_create_buffer` backing store without checking the actual byte length is the common sink.

**Safe:** `std::array`/`std::vector` with `.at()`; `std::span` (C++20) to carry bounds; bound every
copy by the *destination* size; **ARR30-C**, **STR31-C**, C++CG **ES.42**. A bounds-checked `memcpy` is
correct even into a fixed buffer — `node-sqlite: src/aggregate_function.cpp:228-232` caps the copy at
`sizeof(buf) - 1` (it truncates rather than overflows; note truncation is then a *correctness* bug, not
a memory-safety one).

**Prove:** ASan `heap-buffer-overflow`, `stack-buffer-overflow`, `stack-buffer-underflow`,
`global-buffer-overflow` (with READ/WRITE, size, redzone). **Valgrind reliably catches heap overflows
only — it has no redzones for stack or global buffers**, so it misses those. UBSan `bounds` (arrays of
known size) and `local-bounds` (opt-in, not in `-fsanitize=undefined`). Static/hardening:
`-Wanalyzer-out-of-bounds`; `_FORTIFY_SOURCE=2`/`=3` adds runtime checks to `memcpy`/`strcpy`/`sprintf`
when the destination size is known; `-fstack-protector-strong` traps on stack smashing (a canary, not a
bounds check); `-D_GLIBCXX_ASSERTIONS` bounds-checks libstdc++ `operator[]`/iterators.

## Uninitialized reads (CWE-457, CWE-908)

**What:** using a value never initialized — junk stack/heap bytes (CWE-457 variable, CWE-908 resource).
Reading through an *uninitialized pointer* is CWE-824 and is especially dangerous.

**Recognize:** `int x; if (x) …`; `T obj; use(obj.field);`; `malloc` then read before write; a struct
partially initialized then fully read; a function returning a value only on some paths.

**Safe:** C++CG **ES.20** "always initialize an object"; brace-init `T x{};`; initialize members in the
constructor / with default member initializers (**EXP33-C**, **EXP53-CPP**).

**Prove:** **MemorySanitizer** is the dedicated tool — `use-of-uninitialized-value` when an uninit value
reaches a branch, a pointer, a syscall, or crosses a call. **MSan is Linux/NetBSD/FreeBSD-only,
x86-64-centric, requires the *whole* program (incl. libc++/deps) instrumented, and is mutually exclusive
with ASan.** Valgrind Memcheck flags the same class without recompiling: "Conditional jump or move
depends on uninitialised value(s)" (slower). Static: `-Wmaybe-uninitialized`/`-Wuninitialized`,
`-Wanalyzer-use-of-uninitialized-value`, `cppcoreguidelines-init-variables`. Defense-in-depth:
`-ftrivial-auto-var-init=zero` makes otherwise-uninitialized automatics deterministic zeros — it removes
the UB, not the logic bug.

## Integer overflow, truncation, and signedness (CWE-190, CWE-191, CWE-681)

**What:** arithmetic that overflows, wraps, truncates, or changes sign. The high-value review target is
the **overflow → under-allocation → overflow chain (CWE-680)**: an overflow in a *size calculation*
yields a too-small buffer, and the following copy overruns it.

**Recognize:**
```c
void* p = malloc(count * size);   // count*size wraps → tiny alloc (INT30-C, MEM35-C, CWE-680)
memcpy(p, src, count * size);     // copy uses the real length → heap overflow
size_t n = a - b;                 // b > a → huge value (unsigned wraparound)
int n = strlen(s);                // size_t → int truncation
if (signed_len < unsigned_count)  // sign-compare mixes domains
```
- **Signed overflow is undefined behavior** (**INT32-C**): the optimizer may assume it never happens and
  *delete* "impossible" bounds checks — a check can silently vanish.
- **Unsigned overflow wraps** modulo 2ⁿ — well-defined but almost always a logic bug (**INT30-C**).
- Narrowing/sign changes lose or misinterpret data (**INT31-C**, parent CWE-681).

**Safe:** check before you multiply — `count <= SIZE_MAX / size`, or `calloc(count, size)` which checks
the product (**MEM07-C**), or `std::vector`/`std::make_unique<T[]>(n)`. Guard at the API seam:
`fs-metadata: src/common/volume_utils.h:40-44` (`WouldOverflow(a,b)` → `b > 0 && a > UINT64_MAX / b`,
checked before `blockSize * blockCount`); `node-sqlite: src/sqlite_impl.h:73-78` (`SafeCastToInt`
throws `std::overflow_error` above `INT_MAX` before narrowing `size_t` to the `int` the SQLite C API
wants). Cast tainted `char` through `unsigned char` before `std::toupper`/`std::isalpha` — a negative
`char` (any UTF-8 byte ≥ 0x80) is UB there (`fs-metadata: src/windows/security_utils.h:58-63`).

**Prove:** UBSan `signed-integer-overflow` (in `-fsanitize=undefined`); `unsigned-integer-overflow`,
`implicit-signed-integer-truncation`, `implicit-unsigned-integer-truncation`,
`implicit-integer-sign-change` are **opt-in** (via `-fsanitize=integer`/`implicit-conversion`, *not* the
`undefined` group). UBSan default is **log-and-continue** — add `-fno-sanitize-recover=…` to abort in
CI. ASan fires on the overflow of the undersized buffer in a CWE-680 chain. Static: `-Wconversion`,
`-Wsign-conversion`, `-Wsign-compare`, `bugprone-narrowing-conversions`, `bugprone-sizeof-expression`,
`-Wanalyzer-tainted-allocation-size`. Hardening: `-fwrapv`/`-fno-strict-overflow` make signed overflow a
defined wrap so the optimizer keeps your checks (does not fix the arithmetic).

## Pointer-arithmetic UB and null dereference (CWE-469, CWE-476)

**What:** forming or dereferencing an invalid pointer.

**Pointer-arithmetic UB (CWE-469, CWE-823):** forming a pointer outside `[base, base+size]` is UB even
without dereferencing — only "one past the end" is legal. Subtracting pointers into different
arrays/objects is UB. Equality comparison is well-defined; built-in relational comparison of
unrelated object pointers has an unspecified result in C++17, while `std::less` provides a strict
total order when pointer ordering is actually required. In C, relational comparison outside the
same array object is undefined; apply the language's rule rather than treating all comparisons alike.
```c
if (p + len < p) …          // UB: wraparound "overflow check" is invalid
ptrdiff_t d = end - begin;  // UB if end,begin are not in the same array (ARR36-C)
```
CERT ARR30-C (form/use out-of-bounds pointer), ARR36-C (subtract/compare unrelated), ARR37-C, ARR39-C.
Prove: UBSan `pointer-overflow`; static `cppcoreguidelines-pro-bounds-pointer-arithmetic`,
`cppcoreguidelines-pro-bounds-array-to-pointer-decay`.

**NULL dereference (CWE-476, EXP34-C):** dereferencing a pointer expected valid but NULL. In C/C++ this
is UB, not a guaranteed trap — the optimizer may assume non-null and remove the null check.
- **Recognize:** unchecked return of `malloc`/`new(nothrow)`/`fopen`/`find`/`dynamic_cast<T*>`; a factory
  that can return null.
- **Safe:** check every fallible return; use references where nullability is not intended; C++CG
  **ES.65**, **ES.47** (`nullptr` over `0`/`NULL`).
- **Prove:** ASan reports the SEGV with a symbolized stack; UBSan `null`, `nonnull-attribute`,
  `returns-nonnull-attribute`. Static: `-Wanalyzer-null-dereference`, `-Wanalyzer-null-argument`,
  `clang-analyzer-core.NullDereference`. Hardening: `-fno-delete-null-pointer-checks` keeps the optimizer
  from removing your null checks.

## TOCTOU filesystem races (CWE-367)

**What:** a check on a path and the later use of that path are separated in time; an attacker swaps the
file (often via symlink) in between.
```c
if (access(path, W_OK) == 0) {   // check
    FILE* f = fopen(path, "w");  // use — path may now be a symlink to /etc/passwd
}
```

**Safe:** operate on a handle/fd, not a re-resolved name. Canonicalization (`realpath`) can reject
malformed paths and resolve `.`/`..` for validation (**FIO02-C**), but a later `open()` re-resolves
the pathname and leaves a race if an attacker can replace any component. Use fd-relative component
traversal with `openat` plus appropriate `O_NOFOLLOW` checks, or Linux `openat2()` resolution
constraints, and perform `fstat`/`fchmod`/`fstatvfs` on the resulting fd. Use `O_EXCL` for creation
and `O_CLOEXEC` to prevent descriptor inheritance. If portability forces canonicalize-then-open,
document the residual race rather than calling it race-free. CERT **FIO45-C**, **FIO01-C**.

**Prove:** *not* a sanitizer target — it is a filesystem logic race, found by review and static analysis.
ThreadSanitizer addresses *data* races, not filesystem TOCTOU.

## Data races (CWE-362)

**What:** two threads access the same memory concurrently, at least one writing, with no
synchronization — UB, and a source of torn reads/writes and stale values.

**Recognize:** a field read on a worker thread and written on the main thread (or vice versa) without a
mutex or atomic; a mutex held on some paths but not others; lock-order inversions. In addons this shows
up around libuv worker threads (`AsyncWorker`/`AsyncProgressWorker`): a job running
`sqlite3_backup_step` on the pool thread while the main thread mutates shared state
(`node-sqlite: src/sqlite_impl.h` `BackupJob`). Cross-thread flags must be `std::atomic`, as
`shutting_down_` is there and in `fs-metadata: src/common/shutdown.h` (a `std::atomic<bool>` in
per-env instance data, flipped by an env cleanup hook and polled by in-flight workers).

**Safe:** `std::atomic` for single-flag/counter cross-thread signals; `std::lock_guard`/`std::scoped_lock`
for compound state; document each shared object's owning thread; never touch V8/`napi_env` off the JS
thread except through a thread-safe function (see `napi-resource-model.md`).

**Prove:** **ThreadSanitizer** (`-fsanitize=thread`) reports data races and some lock-order issues. TSan
cannot be combined with ASan/MSan. Static analysis is weak here (`concurrency-mt-unsafe` is a heuristic).

---

## Detection-tool matrix

Full setup, flags, and CI wiring are in `proof-and-tooling.md`. What proves what, and each tool's blind
spots:

| Tool | Enable | Catches | Misses / caveats |
|---|---|---|---|
| **ASan** | `-fsanitize=address` (`/fsanitize=address` MSVC) | heap/stack/global overflow, UAF, use-after-return/scope, double-free, alloc-dealloc & new-delete-type mismatch, leaks (via LSan) | uninitialized reads (use MSan); ~2× slowdown; not for production |
| **LSan** | in ASan (`detect_leaks=1`) or `-fsanitize=leak` | memory leaks at exit | fd/handle leaks (use Valgrind `--track-fds`) |
| **UBSan** | `-fsanitize=undefined` (+ `integer`, `implicit-conversion`, `local-bounds`, `vptr` separately) | signed overflow, div-by-zero, shift, `bounds`, `null`/`nonnull`, `alignment`, `pointer-overflow`, `return` | truncation/sign-change opt-in; **default log-and-continue** — add `-fno-sanitize-recover` |
| **MSan** | `-fsanitize=memory` | reads of uninitialized memory | **incompatible with ASan**; needs fully-instrumented deps incl. libc++; Linux/NetBSD/FreeBSD only |
| **TSan** | `-fsanitize=thread` | data races, some lock-order bugs | filesystem TOCTOU, memory-safety bugs |
| **Valgrind Memcheck** | `--leak-check=full --track-fds=yes` (no recompile) | heap overflow, UAF, invalid/double/mismatched free, uninitialised-value use, leaks, fd leaks | **stack & global overflows** (no redzones); ~10–30× slowdown; not on Windows |
| **GCC `-fanalyzer`** | `-fanalyzer` (GCC 10+) | the `-Wanalyzer-*` family cited above | interprocedural precision limits; C++ lags C |
| **clang-tidy** | `--checks=…` | `clang-analyzer-*`, `bugprone-*`, `cppcoreguidelines-*` cited above | flow-sensitivity limits |

## Hardening is defense-in-depth, not detection

Compiler/linker hardening reduces the *exploitability* of surviving bugs; it does not find them.
Full guidance is in `compiler-hardening.md`. Cross-cutting caveats that bite reviewers:

- **`_FORTIFY_SOURCE` must be OFF under AddressSanitizer** — the OpenSSF guide advises against it in
  sanitizer builds (false positives/negatives). Gate it off the sanitizer profile; prepend
  `-U_FORTIFY_SOURCE` before redefining to avoid a redefinition warning.
- **Node addons are shared objects (`.node`)** — harden with `-fPIC`, *not* `-pie`/`-fPIE` (those are
  for executables).
- **`-fcf-protection` is x86-only** and hard-errors on arm64; **`-mbranch-protection` is arm64-only**.
  Put each under its `target_arch` gyp condition (`fs-metadata: binding.gyp`).
- **`-Wl,-z,relro`/`-z,now`/`-z,noexecstack` are ELF/Linux-only** — the macOS `ld64` linker rejects
  them; scope them to the Linux condition.

## Recognition grep starters

Grep finds *candidates*; it does not prove a bug. Every hit needs ownership/data-flow reasoning and then
a detector. Starting points:

```bash
rg -n '\bfree\(|\bdelete\b|delete\s*\[\]'      # frees: pair with alloc, check null-after-free
rg -n 'memcpy|memmove|strcpy|strcat|sprintf'   # unbounded / size-driven copies
rg -n 'reinterpret_cast|static_cast<int>|\(int\)|size_t' # narrowing / sign at API seams
rg -n '\*\s*count|count\s*\*|len\s*\*|\*\s*size'         # size arithmetic (CWE-680 chains)
rg -n 'access\(|\bstat\(|lstat\(|realpath|fopen\(|\bopen\(' # TOCTOU / fd handling
rg -n 'napi_create_reference|napi_delete_reference|HandleScope|EscapableHandleScope' # addon lifetime
rg -n 'std::thread|AsyncWorker|AsyncProgressWorker|std::atomic|lock_guard' # concurrency surface
```

---

## Primary sources

- MITRE CWE — CWE-416, 415, 762, 590, 401, 772/775, 787, 121/122, 125, 457/908/824, 190/191, 131, 680,
  681/197/195/196, 469/823, 476, 367, 362, 758. https://cwe.mitre.org/data/definitions/ (append
  `<id>.html`).
- SEI CERT C Coding Standard (MEM/INT/ARR/EXP/FIO/STR rules).
  https://cmu-sei.github.io/secure-coding-standards/sei-cert-c-coding-standard/rules/ — *CC BY 4.0 standards prose;
  MEM30-C vs MEM31-C renumbering is version-sensitive, re-verify.*
- SEI CERT C++ Coding Standard (MEM50/51-CPP, EXP53/54-CPP, CTR50/51-CPP, OOP52-CPP).
  https://cmu-sei.github.io/secure-coding-standards/sei-cert-cpp-coding-standard/rules/
- Clang — AddressSanitizer, UndefinedBehaviorSanitizer, MemorySanitizer, LeakSanitizer,
  ThreadSanitizer. https://clang.llvm.org/docs/AddressSanitizer.html (and sibling `*Sanitizer.html`) —
  *Apache-2.0 WITH LLVM-exception.*
- clang-tidy checks list. https://clang.llvm.org/extra/clang-tidy/checks/list.html
- GCC — Static Analyzer Options (`-fanalyzer`, `-Wanalyzer-*`, GCC 10+).
  https://gcc.gnu.org/onlinedocs/gcc/Static-Analyzer-Options.html
- Valgrind Memcheck manual (error/leak categories, `--track-fds`).
  https://valgrind.org/docs/manual/mc-manual.html
- OpenSSF — Compiler Options Hardening Guide for C and C++ (`_FORTIFY_SOURCE`/sanitizer conflict,
  `-fcf-protection`/`-mbranch-protection` arch split). *CC BY-4.0.*
  https://best.openssf.org/Compiler-Hardening-Guides/Compiler-Options-Hardening-Guide-for-C-and-C++.html
- ISO C++ Core Guidelines — R (resource management) and ES (expressions/statements),
  consulted under the Guidelines' custom license.
  https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines
- Node.js — Node-API "Object lifetime management" (handle scopes, `napi_ref`, finalizers). *MIT-style.*
  https://nodejs.org/api/n-api.html#object-lifetime-management
- Reference addons cited by path: `@photostructure/fs-metadata` (`/home/mrm/src/fs-metadata`) and
  `@photostructure/sqlite` (`/home/mrm/src/node-sqlite`).
