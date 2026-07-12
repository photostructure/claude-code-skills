<!-- Original synthesis. Adapted sources: cppreference (CC BY-SA 3.0/GFDL), SEI CERT standards prose (CC BY 4.0), and OpenSSF Compiler Hardening Guide (CC BY 4.0). The C++ Core Guidelines (custom license) were consulted, not relicensed. This file: CC BY-SA 4.0. See ../ATTRIBUTION.md. -->

# Modern C++ Conventions

Conventions for clear, maintainable, safe C++17 in Node.js native addons (node-addon-api /
Node-API, built with node-gyp) and general modern C++. These are the habits that prevent the
defects `/cpp:resource-review` hunts: leaks, double-frees, use-after-free, dangling views,
data races, and exceptions crossing the C ABI. Rule IDs are C++ Core Guidelines unless marked
CERT (`DCL57-CPP`) or CWE. Flags and clang-tidy wiring live in `compiler-hardening.md`,
`sanitizers-and-analysis.md`, and `build-and-toolchain.md` — this file is about the code.

## Contents

- [RAII: one owning wrapper per resource](#raii-one-owning-wrapper-per-resource)
- [Ownership in the type system](#ownership-in-the-type-system)
- [Rule of zero, three, five](#rule-of-zero-three-five)
- [Errors across the C ABI boundary](#errors-across-the-c-abi-boundary)
- [const-correctness and non-owning views](#const-correctness-and-non-owning-views)
- [Concurrency correctness](#concurrency-correctness)
- [Header hygiene](#header-hygiene)
- [A thin, testable boundary](#a-thin-testable-boundary)
- [Maintainability: fail fast, split, DRY](#maintainability-fail-fast-split-dry)
- [Checklist](#checklist)
- [Primary sources](#primary-sources)

## RAII: one owning wrapper per resource

**R.1 — manage every paired acquire/release with a resource handle.** Anything with
`open`/`close`, `malloc`/`free`, `CreateFile`/`CloseHandle`, `lock`/`unlock`, `new`/`delete`
gets an object that acquires in its constructor and releases in its destructor. The language
then runs the release *exactly once on every path* — early `return`, `throw`, stack unwinding
included. That is what makes exception safety automatic (E.6): you never write cleanup on the
error path. Prefer scoped locals to heap allocation (R.5); avoid `malloc`/`free` (R.10) and
naked `new`/`delete` (R.11, ES.60) — every naked `new` implies a naked `delete` somewhere.

**One wrapper per resource, with the release matched to the allocator.** The single most
common resource bug is freeing with the wrong deallocator. A handle from a C library must be
released with *that library's* function. `fs-metadata` applies this uniformly across three
OSes: `FdGuard` closes a POSIX fd with `close(2)` (`fs-metadata: src/common/fd_guard.h`);
`CFReleaser<T>` uses `CFRelease` per CoreFoundation's Create/Copy rule; `IOObjectGuard` uses
`IOObjectRelease` (**not** `CFRelease`); `HandleGuard` uses `CloseHandle` while `FindHandleGuard`
uses `FindClose` (**not** `CloseHandle`) — all in `fs-metadata: src/darwin/raii_utils.h` and
`src/windows/security_utils.h`. Put the ordering quirks in the wrapper too: `DASessionRAII`
calls `DASessionSetDispatchQueue(session, nullptr)` *before* `CFRelease` so Apple's
unschedule-before-release order lives in exactly one place.

**Reach for `std::unique_ptr` with a custom deleter before hand-rolling a class.** When the
release is a plain function, an empty functor deleter costs zero bytes (empty-base
optimization) and needs no rule-of-five boilerplate:

```cpp
struct FileCloser { void operator()(std::FILE* f) const noexcept { if (f) std::fclose(f); } };
using unique_file = std::unique_ptr<std::FILE, FileCloser>;   // sizeof == sizeof(FILE*)
```

`fs-metadata` uses `std::unique_ptr<char, decltype(&free)>` for libblkid strings
(`src/linux/volume_metadata.cpp`) rather than a bespoke class. A **function-pointer** deleter
works but is stored, enlarging the object — prefer a named empty functor. Hand-write a class
only when the release is not a plain `free`/`delete`, or when the handle is a non-pointer type
(`int` fd, or a `HANDLE` whose empty sentinel is `INVALID_HANDLE_VALUE == (HANDLE)-1`, not
`nullptr`) that a fancy-pointer `unique_ptr` would mishandle — which is exactly why `FdGuard`
is a small move-only class, not a shoe-horned `unique_ptr`.

## Ownership in the type system

Express ownership through the type; a signature should advertise who frees.

| Construct | Owns? | Rule |
|---|---|---|
| `T*` / `T&` | **No** — non-owning; a position, never a transfer | R.3, R.4, I.11 |
| `std::unique_ptr<T>` | Yes — the default, exclusive owner | R.20, R.21 |
| `std::shared_ptr<T>` | Yes — only when ownership is *genuinely* shared | R.20, R.34 |
| `std::weak_ptr<T>` | No — observer; breaks `shared_ptr` cycles | R.24 |
| container / view | container owns; `string_view`/`span` do **not** | R.2, R.14 |

- **I.11 — never transfer ownership by a raw `T*`/`T&`.** Sink ownership with `unique_ptr` by
  value (`void sink(std::unique_ptr<widget>)`, R.32); share with `shared_ptr` by value (R.34).
- **F.7 — a function that merely *uses* an object takes `T*`/`T&` (or a view), not a smart
  pointer.** Passing `shared_ptr` by value where sharedness is unused is a silent atomic
  refcount pessimization. Smart-pointer parameters exist only to state lifetime intent (R.30).
- **`unique_ptr` is the default.** It is move-only, predictable (you know exactly when the
  destructor runs), and has no atomic refcount. Use `make_unique` (R.23, C++14). A
  `unique_ptr<Derived>` converted to `unique_ptr<Base>` **UB-deletes unless `~Base` is virtual**
  (C.35).
- **`shared_ptr` only for real sharing** (multiple independent owners, indeterminate last
  owner). Use `make_shared` (R.22). Its refcount is atomic, but *the pointee is not* —
  protecting shared data still needs its own synchronization. Never build a second `shared_ptr`
  from another's `.get()` (two control blocks → double free); share by copying the `shared_ptr`.
- **`weak_ptr` breaks cycles (R.24).** Two objects holding `shared_ptr`s to each other never hit
  refcount zero → leak. Make the back/parent edge a `weak_ptr` and `lock()` it on use. This is
  the model for node-sqlite's parent/child link (below), done with raw pointers + manual detach.

Wrong vs. right:

```cpp
widget* make_widget();                 // WRONG (I.11): who deletes it? leak or double-free
std::unique_ptr<widget> make_widget(); // RIGHT: ownership transfer is in the type
void use(const std::shared_ptr<widget>&); // WRONG (F.7): refcount traffic for a mere use
void use(const widget&);                  // RIGHT: works for any ownership scheme
```

## Rule of zero, three, five

- **Rule of Zero (C.20) is the target.** Define *none* of the special members; let
  `std::string`/`std::vector`/`unique_ptr`/`shared_ptr` members manage themselves. The
  compiler-generated operations are then correct and fastest. A class that manages a raw handle
  (fd, `FILE*`, `HANDLE`, owning `T*`) cannot use rule-of-zero and must deal *exclusively* with
  ownership (single responsibility).
- **Rule of Three:** need a user destructor, copy ctor, *or* copy assign → you need all three,
  or an implicit shallow copy double-frees.
- **Rule of Five:** declaring *any* of {dtor, copy ctor, copy assign} **suppresses the implicit
  moves** — they silently become copies. Declaring a move **deletes the implicit copies** —
  the class becomes move-only. So once you touch one, **declare the whole set explicitly** (C.21).

```cpp
struct M2 { ~M2(){ delete[] rep; } pair<int,int>* rep; };  // WRONG: dtor, no copy/move
M2 x, y; x = y;   // implicit copy assign shallow-copies rep → double delete (CWE-415/416)
```

Fix by rule of zero (`std::vector<pair<int,int>> rep;`, drop the dtor) or the full rule of
five. `fs-metadata`'s `FdGuard` is the model: `explicit` ctor, `noexcept` dtor guarded by
`fd_ >= 0`, `=delete`d copy, move ctor/assign that null the source, and move-assign that closes
the current fd *before* taking the new one (self-assignment-safe).

- **C.66 — make moves `noexcept`.** `std::vector` reallocation moves elements only if the move
  is `noexcept`, otherwise it *copies* to preserve the strong guarantee. A throwing move is a
  silent pessimization. Steal + null the source (`std::exchange(other.p, nullptr)`).
- **F.48 — don't `return std::move(local);`** — it defeats NRVO. Just `return result;`.
- **C.67 — a polymorphic base suppresses public copy/move** to prevent slicing; provide a
  virtual `clone()` if deep copies are needed.

Enforce with `cppcoreguidelines-special-member-functions` (see `sanitizers-and-analysis.md`).
node-sqlite's `StepGuard` and `AuthorizerGuard` model the deliberate variant: `noexcept`
ctor/dtor, `=delete`d copies (`node-sqlite: src/sqlite_impl.h`).

## Errors across the C ABI boundary

**The pivotal addon rule: a C++ exception must never propagate across a C ABI frame.** Node-API
is a C API; the runtime, libuv, V8, and the `napi_register_module_v1` shim are compiled as C,
with no exception-unwind support. An exception unwinding into such a frame — or escaping a
`noexcept`/effective-`noexcept` boundary — calls `std::terminate` and aborts the process
(`ERR55-CPP`). The strategy (decide it early, E.1): **exceptions + RAII internally; translate
to a pending JS error at the seam.**

- Throw purpose-designed types by value, catch by reference (E.14/E.15). Let them propagate to
  the *one* handler that can act — the boundary function — instead of wrapping every function in
  `try`/`catch` (E.17/E.18). RAII makes this safe: every `throw` runs destructors in reverse
  order (E.6).
- **Validate arguments and throw a `Napi::` error *synchronously* at the entry point, before
  queuing any async work.** With `NAPI_CPP_EXCEPTIONS`, a thrown `Napi::TypeError` is caught by
  node-addon-api's wrapper and converted to a JS exception; a raw `std::runtime_error` from the
  same frame is **not** translated and aborts. `fs-metadata` documents this exact trap inline
  (`fs-metadata: src/binding.cpp`, entry points in `src/*/volume_metadata.cpp`).
- Choose the node-gyp dependency deliberately: `node_addon_api_except` handles only
  `Napi::Error` (others abort); `node_addon_api_except_all` also maps `std::exception` →
  `Napi::Error` carrying `what()`. Pick one per build (version-sensitive: verify).
- **Async workers must be exception-tight.** `AsyncWorker::Execute()` runs off the loop and must
  never throw, touch `napi_env`, or run JS. Wrap the work in `try/catch(...)` and funnel to
  `SetError`; interact with JS only in `OnOK`/`OnError` on the loop thread. `fs-metadata`'s
  `SafeAsyncWorker` does this and skips the completion callbacks when the env is shutting down.
- **Capture C-library error state at the throw site.** node-sqlite's `SqliteException` snapshots
  `sqlite3_extended_errcode()` / `sqlite3_system_errno()` in its constructor, before any cleanup
  call overwrites them (`node-sqlite: src/sqlite_exception.h`), then a single boundary converts
  C++ → JS (`node-sqlite: src/sqlite_impl.cpp`).

**Destructors must not throw (C.36/C.37, `DCL57-CPP`).** A throw during unwinding calls
`std::terminate`. A destructor is *implicitly* `noexcept` iff all members are; mark it `noexcept`
explicitly so a later member change can't silently poison the class. If a release genuinely
cannot complete, it is a design error — there is no general recovery. (Build note: C++ exceptions
require `-fexceptions`; see `build-and-toolchain.md`.) See `napi-resource-model.md` for the
handle/scope model.

## const-correctness and non-owning views

- **Con.1/Con.2/Con.3 — immutable by default; member functions `const` by default; pass in-params
  by `const&`.** `const` diffuses: a non-`const` member poisons `const` access up the call chain.
- **F.16 — pass cheap types (~2–3 words) by value, others by `const&`.** `f(const int&)` is bad;
  don't reach for `T&&` "for speed" — most such rumors are false. Enforce with
  `misc-const-correctness`; never `const_cast` a genuinely-const object (ES.50).
- **`string_view` and `span` are non-owning `{pointer, length}` views** (`string_view` is C++17;
  `std::span` is C++20 — under a C++17 baseline use `gsl::span`). They do **not** own or extend
  the lifetime of their backing storage. Dangling views compile cleanly and fail at runtime —
  the highest-risk maintainability trap.

```cpp
std::string_view good{"literal"};              // OK: static storage
std::string_view bad{"tmp"s};                  // DANGLES: the std::string dies at the ';'
std::string_view f(){ return std::string("x"); } // DANGLES: returns a view into a dead temporary
```

- **`string_view::data()` is not guaranteed null-terminated** (e.g. after `remove_suffix` or a
  substring). Passing `sv.data()` to a C API expecting a `const char*` (`fopen`, `getenv`) is a
  bug; materialize a `std::string(sv)` first, or use a size-aware API.
- **Addon hazard:** `Napi::String::Utf8Value()` returns a `std::string` *by value*. Taking a
  `string_view` (or a `sv.data()` pointer) into that temporary dangles the instant the statement
  ends. Bind the `std::string` to a named local first, and never store the view past the call.
  A `Napi::Value`/`napi_value` handle is itself a view scoped to the callback — treat it exactly
  like a `string_view`, never stash it. Catch dangling handles with `bugprone-dangling-handle`.

## Concurrency correctness

A **data race is undefined behavior** — not a torn read, but *anything* (miscompiles, security
bugs). Two threads touching one non-atomic object, ≥1 writer, no happens-before edge, is a race
(CP.2). File-scope and function-local `static` mutable state are classic culprits.

- **Synchronize with `std::mutex` + RAII locks.** Default to `std::scoped_lock` in C++17 (it is
  the RAII form of deadlock-avoiding `std::lock` and handles one *or more* mutexes); use
  `lock_guard` for a single mutex, `unique_lock` for condition variables / manual unlock. Never
  raw `lock()`/`unlock()` (CP.20). **Name the guard** — `std::scoped_lock{m};` is an unnamed
  temporary that unlocks immediately and locks nothing for the rest of the scope (CP.44). Keep
  critical sections minimal (CP.43) and define the mutex next to the data it guards (CP.50).
- **`std::atomic` gives atomicity of *one* object, not invariants across several** — a
  check-then-act sequence or a multi-variable invariant (keeping `width*height` consistent) needs
  a mutex. `volatile` is *not* a synchronization tool (CP.8; no atomicity, no ordering).
  `memory_order_relaxed` is idiomatic only for a standalone counter (a `shared_ptr` strong-count
  *increment*); publishing/reclaiming data needs acquire/release — default to `seq_cst` unless
  measured. arm64 is weakly ordered, so ordering bugs that "work" on x86 surface on Apple Silicon.
- **Deadlock:** take multiple mutexes with one `std::scoped_lock`/`std::lock` (order-independent)
  or a single documented lock order (CP.21, `CON53-CPP`). **Never call unknown/re-entrant code —
  especially a JS callback — while holding a native lock** (CP.22): JS can re-enter your addon
  and deadlock. Release, capture what you need, then call into JS.
- **Condition variables always wait with a predicate** — `cv.wait(lk, pred)` — to survive
  spurious wakeups and lost notifications, and mutate the shared condition *under the mutex* even
  if it is atomic (CP.42, `CON54-CPP`). No hand-rolled double-checked locking; use a
  function-local `static` or `std::call_once` (CP.110).
- **RAII scope guards for logical invariants, not just memory.** node-sqlite's `StepGuard` raises
  a depth counter in its ctor and unwinds it in its dtor, capturing the owning pointer *at
  construction* so Enter/Leave stay balanced across early returns and exceptions
  (`node-sqlite: src/sqlite_impl.h`); `AuthorizerGuard` does the same for re-entrancy tracking.

**Node-API thread-affinity is absolute.** A `napi_env` and every `napi_value` belong to the one
JS thread that created them — never cache one, make it global, or hand it to a `std::thread`.
Off-loop work runs in `AsyncWorker::Execute()` using only plain C++ types; the *only* way to call
JS from another thread is a `ThreadSafeFunction` (balance `Acquire`/`Release`, handle backpressure).
Addon state that would otherwise be a global belongs in per-env instance data
(`napi_set_instance_data` / `Napi::Addon<T>`), because one process hosts many JS environments
(worker_threads, Electron, agents). Static tools: `-Wthread-safety` (Clang; `GUARDED_BY`),
`concurrency-mt-unsafe`, and ThreadSanitizer (`-fsanitize=thread`, not on MSVC) — see
`sanitizers-and-analysis.md`. Full model in `napi-resource-model.md`.

## Header hygiene

- **SF.7 — no `using namespace` at global scope in a header.** It removes an includer's ability
  to disambiguate and makes include order significant. Fully qualify (`std::string`) in headers.
- **SF.11 — headers self-contained; SF.10 — don't depend on transitively-included names.**
  A header must compile when included first, having included everything it uses. This *is* the
  include-what-you-use principle: for every symbol used in `foo.cpp`, either `foo.cpp` or `foo.h`
  includes the header that declares it. Run `iwyu` to add missing includes and drop unused ones.
- **Forward-declare when you only need a pointer/reference** (`class Foo;`) instead of
  `#include`-ing the full header — the main lever for cutting rebuild fan-out and the Pimpl
  enabler (I.27). A Pimpl class must define its dtor and move ops **in the .cpp** where the impl
  is complete, moves marked `noexcept`.
- **SF.22 — internal linkage (anonymous namespace / `static`) belongs in .cpp files, never
  headers (SF.21).** Prefer `constexpr`/`const`, `enum class`, and `inline` functions over macros
  (ES.30/ES.31); reserve `ALL_CAPS` for the macros you cannot avoid (node-addon-api's own).

## A thin, testable boundary

Keep two languages apart at one exception-tight seam. Three layers:

| Layer | Surface | Errors | Tested with |
|---|---|---|---|
| **Pure C++ core** | `std::` types, RAII handles — **no `napi_*`** | C++ exceptions | plain C++ unit tests, no Node |
| **Boundary / glue** | `Napi::*` / `napi_value` | translate C++ ⇄ JS | Node integration tests |
| **C ABI seam** | `extern "C"` registration | **no exception may cross** | — |

```
src/
  core/     resize.hpp/.cpp   # C++17, no napi headers; throws std::exception; single op (F.2)
  binding/  binding.cpp       # ONLY file including <napi.h>; marshals + translates errors
  test/     resize_test.cpp   # links core/ directly — no Node process needed
```

The core never sees `napi_env`, so it is unit-testable in plain C++ and portable; the compiler/
ABI concerns of I.26 (Node-API is a deliberate C-style subset for cross-compiler stability) never
touch it. Marshal narrow, strongly-typed values (I.4); ownership crosses by value (`unique_ptr`,
owning containers), never by raw pointer (I.11); non-owning views never escape the call. With
`NAPI_CPP_EXCEPTIONS` + `node_addon_api_except_all`, core `std::exception`s auto-translate at the
seam, so the glue stays tiny — add a `try/catch` only to *map* a specific C++ error to a specific
JS type. See `report-format.md` and `defect-classes.md` for how `/cpp:resource-review` reads it.

## Maintainability: fail fast, split, DRY

- **Fail fast; no silent defaults or truncation.** When an assumption breaks, error visibly
  rather than patching over it. node-sqlite's fixed 4096-byte aggregate buffer silently truncates
  any string/BLOB/object over 4095 bytes and substitutes `{"_truncated":true}` — a correctness
  bug, not a limit (`node-sqlite: src/aggregate_function.cpp` / `aggregate_function.h`).
  Guard size math instead: `fs-metadata`'s `WouldOverflow(a,b)` and node-sqlite's
  `SafeCastToInt` throw before narrowing/multiplying, closing CWE-190 at the API seam. A
  constructor that can't establish its invariant must throw (E.5), not return a half-built object.
- **Split oversized translation units.** node-sqlite's ~4,500-line `sqlite_impl.cpp` defines five
  classes; splitting into `database.cpp` / `statement.cpp` / `session.cpp` / `backup.cpp` (the
  headers already separate the declarations) cuts rebuild time and review surface with no
  behavior change. A TU should have one reason to change (F.2).
- **Extract duplicated converters.** node-sqlite's near-identical `SqliteValueToJS` /
  `JSValueToSqliteResult` copies in `user_function.cpp` and `aggregate_function.cpp` are a drift
  hazard — a fix to one is easily missed in the other. Pull correctness-critical conversion into
  one shared unit.
- **Re-enable the checks that matter on first-party code.** `cppcoreguidelines-owning-memory`,
  `cppcoreguidelines-special-member-functions`, and `bugprone-use-after-move` are exactly what
  flags lifetime hazards; both reference projects disable them on some paths. Scope them to your
  RAII wrappers and ObjectWrap subclasses via `HeaderFilterRegex` (`sanitizers-and-analysis.md`,
  `ci-and-release.md`).

## Checklist

- [ ] Every C resource has one RAII wrapper; release matches the allocator; prefer `unique_ptr`
      + custom deleter before a hand-rolled class. No naked `new`/`delete` or `malloc`/`free`.
- [ ] Ownership is in the type: raw `T*`/`T&` never transfer; `unique_ptr` default, `shared_ptr`
      only for real sharing, `weak_ptr` for cycles.
- [ ] Touch one special member → declare all five; moves are `noexcept`; destructors are
      `noexcept` and cannot throw.
- [ ] `const` by default; in-params by value (cheap) or `const&`; no `const_cast`. No
      `string_view`/`span`/`napi_value` outlives its backing storage; `.data()` not passed to C.
- [ ] Shared mutable state is atomic or mutex-guarded; RAII locks, named, minimal scope; multiple
      mutexes via `scoped_lock`; `cv.wait` with a predicate; no JS callback under a native lock.
- [ ] No `napi_env`/`napi_value` cached or crossed threads; addon state in instance data;
      off-loop work never touches JS except via a `ThreadSafeFunction`.
- [ ] No C++ exception can reach a C ABI frame; arguments validated with `Napi::` throws at the
      entry point; async workers exception-tight.
- [ ] Headers self-contained, no global `using namespace`, forward-declare over `#include`.
- [ ] Pure C++ core has no `napi_*` and is unit-testable; the glue is the single translation seam.
- [ ] Fail fast — no silent truncation/defaults; oversized TUs split; duplicated converters DRYed.

## Primary sources

- ISO C++ Core Guidelines (consulted under its custom license) — R.1–R.37, C.20–C.22,
  C.31, C.35–C.37, C.64–C.67, E.1–E.31,
  F.2/F.7/F.16/F.48, I.4/I.11/I.26/I.27, SF.7/SF.10/SF.11/SF.21/SF.22, Con.1–Con.5,
  CP.2/CP.8/CP.20–CP.22/CP.42–CP.44/CP.50/CP.110, ES.30/ES.50/ES.60:
  https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines
- cppreference (CC BY-SA) — rule of three/five/zero, `unique_ptr`, `shared_ptr`, `weak_ptr`,
  `basic_string_view` (+ `::data`), `span`, destructors, `noexcept`, `std::memory_order`,
  `std::atomic`, `std::scoped_lock`, `std::condition_variable`:
  https://en.cppreference.com/w/cpp
- Node.js Node-API reference (MIT) — `napi_throw*`, exception-pending APIs, ABI stability,
  `napi_set_instance_data`, `napi_create_async_work`, threadsafe functions, context awareness:
  https://nodejs.org/api/n-api.html , https://nodejs.org/api/addons.html
- node-addon-api docs (MIT) — error handling (`NAPI_CPP_EXCEPTIONS`, `except_all`), object
  lifetime / `HandleScope`, `Reference`, `AsyncWorker`, `ThreadSafeFunction`, `Addon<T>`:
  https://github.com/nodejs/node-addon-api/tree/main/doc
- SEI CERT C/C++ (CC BY 4.0 standards prose; MIT code examples) — DCL57-CPP,
  ERR55-CPP, CON53/54/55-CPP, FIO02-C:
  https://cmu-sei.github.io/secure-coding-standards/
- LLVM / clang-tidy (Apache-2.0 WITH LLVM-exception) — check names, Thread Safety Analysis,
  ThreadSanitizer: https://clang.llvm.org/extra/clang-tidy/checks/list.html
- include-what-you-use (NCSA): https://github.com/include-what-you-use/include-what-you-use
- CWE — CWE-190, CWE-415/416, CWE-787: https://cwe.mitre.org/
