<!-- Original synthesis. Adapted sources: cppreference (CC BY-SA 3.0/GFDL), SEI CERT standards prose (CC BY 4.0), and OpenSSF Compiler Hardening Guide (CC BY 4.0). The C++ Core Guidelines (custom license) were consulted, not relicensed. This file: CC BY-SA 4.0. See ../ATTRIBUTION.md. -->

# Node-API Resource Model

The addon-specific lifetime hazards a general C++ reviewer misses. A `napi_value` looks like
a pointer, an `ObjectWrap` destructor looks like RAII, a `ThreadSafeFunction` looks like a
callback — each carries a lifetime contract enforced by V8's GC and the libuv loop, not by
the C++ type system. This is a "defect vs correct" catalog a reviewer consults. For memory/RAII
defects that apply to *any* C++, see [`defect-classes.md`](./defect-classes.md); for proving a
finding, [`proof-and-tooling.md`](./proof-and-tooling.md); for output, [`report-format.md`](./report-format.md).

## Contents

- [Recognizing addon code](#recognizing-addon-code)
- [Mental model: three ownership layers](#mental-model-three-ownership-layers)
- [1. Handles are call-scoped and non-owning](#1-handles-are-call-scoped-and-non-owning)
- [2. HandleScope discipline in loops and off-call callbacks](#2-handlescope-discipline-in-loops-and-off-call-callbacks)
- [3. References and ref-count leaks](#3-references-and-ref-count-leaks)
- [4. ObjectWrap finalizers, reference RAII, and deferral](#4-objectwrap-finalizers-reference-raii-and-deferral)
- [5. ThreadSafeFunction acquire, release, abort](#5-threadsafefunction-acquire-release-abort)
- [6. AsyncWorker and the worker boundary](#6-asyncworker-and-the-worker-boundary)
- [7. Exceptions must not cross the C ABI](#7-exceptions-must-not-cross-the-c-abi)
- [8. Context-awareness: instance data, not global statics](#8-context-awareness-instance-data-not-global-statics)
- [9. Copy at the C boundary; external buffers and memory](#9-copy-at-the-c-boundary-external-buffers-and-memory)
- [Pitfall-to-fix quick table](#pitfall-to-fix-quick-table)
- [Grep starters](#grep-starters)
- [Primary sources](#primary-sources)

## Recognizing addon code

| Indicator | Layer |
| --- | --- |
| `#include <node_api.h>`, `napi_*` types | Node-API (C, ABI-stable) |
| `#include <napi.h>`, `Napi::`, `NODE_API_MODULE(...)` | node-addon-api (C++ wrapper, MIT; not Node core) |
| `#include <v8.h>`/`<node.h>`/`<uv.h>`/`<node_buffer.h>`, `Nan::` | **NOT ABI-stable** — recompile per Node major; red flag for legacy hand-rolled lifetimes |
| `binding.gyp`, `node-gyp`, `prebuildify`, `node-gyp-build` | native build/packaging |

Only `node_api.h` is ABI-stable, which is why this whole model exists. The C++ wrapper maps
down to the C API — **reason about lifetime at the C layer.** Addons are shared libraries
(loadable modules), so they build with `-fPIC`, never `-pie`/`-fPIE`; toolchain myths live in
[`compiler-hardening.md`](../../project-setup/references/compiler-hardening.md).

## Mental model: three ownership layers

| Thing | Owns the JS object? | Valid for | Cross-thread? |
| --- | --- | --- | --- |
| `napi_value` / `Napi::Value` | No — a **handle** in the current `HandleScope` | until the scope closes (default = the native call) | **No** — thread-affine to the creating `napi_env` |
| `napi_ref` / `Napi::Reference` | Strong when count > 0; weak at 0 | until you `napi_delete_reference` / `Reset` it | No |
| `napi_env` | context handle | until the addon instance/Worker unloads | **No** — one env per JS thread |

Two hard rules underpin everything below. **(a)** `napi_env` and every `napi_value` belong to
one JS thread; touching them from another thread, or after the env unloads, is undefined
behavior (crash, not exception). **(b)** Caching `napi_env` for reuse or passing it between
Worker threads "is not allowed" (Node-API docs); reach JS from a foreign native thread only via
a `ThreadSafeFunction` (§5).

## 1. Handles are call-scoped and non-owning

`napi_value`/`Napi::Value` is a handle into the current handle scope, not an owning smart
pointer. The default scope closes when the native method returns to JS. **Storing a bare
`napi_value` past the call, or using one after its scope closes, is use-after-free (CWE-416).**
To keep a JS value across calls, hold a *reference* (§3).

```cpp
// DEFECT: stashing a call-scoped handle for later
Napi::Value cached_;                          // member handle outlives its scope
void Remember(const Napi::CallbackInfo& i) { cached_ = i[0]; }   // dangling after return

// CORRECT: hold a reference, materialize a handle on demand
Napi::Reference<Napi::Value> ref_;
void Remember(const Napi::CallbackInfo& i) { ref_ = Napi::Persistent(i[0]); }  // strong, count 1
Napi::Value Recall() { return ref_.Value(); }
```

`Napi::Persistent(v)` starts at count 1 (strong). Bare `Napi::Reference::New(v)` defaults to
count **0 → weak** (§3). Flag any `napi_value`/`Napi::Value` stored as a member, static, in a
container, or captured by a lambda that outlives the callback.

## 2. HandleScope discipline in loops and off-call callbacks

A handle keeps its JS object alive until its scope closes. The default scope closes only on
return to JS, so handles **accumulate and leak** (CWE-401) in two cases: a long loop creating
many values, and any code running *outside* a native method (libuv/timer/TSFN callbacks).
Node-API docs: for "code outside the execution of a native method … the module is required to
create a scope before invoking any functions that can result in the creation of JavaScript
values."

```cpp
// DEFECT: N handles pile up in the default scope; none freed until the method returns
for (size_t i = 0; i < huge.size(); ++i)
  out.Set(i, Napi::String::New(env, huge[i]));

// CORRECT: RAII HandleScope per iteration → at most one transient value alive
for (size_t i = 0; i < huge.size(); ++i) {
  Napi::HandleScope scope(env);               // destructor closes at end of iteration
  out.Set(i, Napi::String::New(env, huge[i]));
}
```

To return a value out of an inner scope, use `Napi::EscapableHandleScope` and
`scope.Escape(v)` — callable **at most once** per scope (else `napi_escape_called_twice`).
Scopes are strict LIFO; RAII enforces it. C API: `napi_open_handle_scope`/
`napi_close_handle_scope`, `napi_open_escapable_handle_scope`/`napi_close_escapable_handle_scope`,
`napi_escape_handle`. Flag loops building many values without an inner scope, and any
libuv/timer/TSFN callback body creating values without opening a `HandleScope` first.

## 3. References and ref-count leaks

A reference (`napi_ref` / `Napi::Reference<T>`) pins a JS value beyond the current scope.
Count > 0 is **strong** (cannot be GC'd); count == 0 is **weak** (collectible;
`napi_get_reference_value` then yields empty). A reference is a **native resource independent
of the GC** — failing to delete it leaks even when weak.

| C function | Effect |
| --- | --- |
| `napi_create_reference(env, value, initial_refcount, &ref)` | create with initial count |
| `napi_reference_ref` / `napi_reference_unref` | ++ / -- the count |
| `napi_get_reference_value` | recover a handle (empty if collected) |
| `napi_delete_reference` | destroy — **required, or it leaks** |

```cpp
Napi::Reference<Napi::Object>::New(obj);      // DEFECT: initialRefcount 0 → WEAK; may vanish
cb_ = Napi::Persistent(fn);                   // DEFECT if never released → pins fn + its graph forever
cb_ = Napi::Persistent(fn); /* ...later... */ cb_.Unref();   // CORRECT when weak retention is intended
```

Flag: every `Ref`/`napi_reference_ref` needing a matching `Unref`; a stored
`FunctionReference` for async work that is never released (CWE-401/CWE-772); `Reference::New`
where a strong ref was intended. `SuppressDestruct()` disables teardown release and is for
`static` references only — node-addon-api says "avoid using this if at all possible" and warns
that static references make the addon **not** thread-safe (§8).

## 4. ObjectWrap finalizers, reference RAII, and deferral

`Napi::ObjectWrap<T>` (`napi_wrap`/`napi_unwrap`/`napi_remove_wrap`) ties a C++ instance's
lifetime to a JS object, but **the GC decides if and when** the destructor/finalizer runs:
"the call to the C++ destructor may be deferred until a later time." Finalizers may run much
later than unreachability, or **not at all** on abrupt exit. Two rules:

1. **Never rely on a finalizer for timely or critical release** — fds, sockets, locks, large
   allocations. Expose an explicit, idempotent `close()`/`dispose()`; the finalizer is a
   backstop. node-sqlite imposes teardown order manually in `DatabaseSync::InternalClose()`
   (`node-sqlite: src/sqlite_impl.cpp`, lines 1310-1339) — stop backups, finalize statements,
   delete sessions, then `sqlite3_close`, falling back to `sqlite3_close_v2()` on `SQLITE_BUSY`.
2. **Do not call JS from a synchronous finalizer.** When a callback receives
   `node_api_basic_env`, it may call only APIs accepting that basic environment; use
   `node_api_post_finalizer` to defer work needing a full `napi_env` or JavaScript. A normal
   node-addon-api `ObjectWrap` destructor remains an RAII boundary because node-addon-api
   performs or safely defers restricted reference cleanup for the active finalizer context.
   *(Version-sensitive: `node_api_basic_env`/`node_api_post_finalizer` are Experimental,
   added v18.20/v20.12/v21.6 — verify.)*

### Ordinary reference teardown is RAII

`Napi::Reference` is an RAII owner. During normal `ObjectWrap` finalization,
node-addon-api deletes the C++ instance; its member destructors then release their references
or safely defer the underlying Node-API deletion when finalizer restrictions require it.
Explicit `Reset()` is also valid while the owning `napi_env` is alive and the current callback
is allowed to use that API. Do not flag either pattern merely because GC initiated finalization.

The restriction to check is the **kind of finalizer and API used**, not the platform libc.
A basic finalizer may call only APIs that accept `node_api_basic_env`. Cleanup needing other
Node-API operations or JavaScript must be scheduled with `node_api_post_finalizer` (or performed
earlier from an ordinary callback/explicit `close()`). Current node-addon-api accounts for these
rules in its reference and `ObjectWrap` teardown; hand-written C callbacks must do so explicitly.

```cpp
// CORRECT: ordinary node-addon-api RAII; member teardown releases js_ref_
~StatementSync() { sqlite3_finalize(stmt_); }

// BASIC FINALIZER: native-only cleanup now; defer non-basic Node-API/JS work
void Finalize(node_api_basic_env env, void* data, void*) {
  auto* state = static_cast<State*>(data);
  state->ReleaseNativeResources();
  node_api_post_finalizer(env, FinishOnJsThread, state, nullptr);
}
```

node-sqlite also uses **bidirectional "detach before free"**: when the database tears down
first it nulls each statement's `database_` (`FinalizeFromDatabase`, `node-sqlite:
src/sqlite_impl.cpp`, lines 2354-2364) so the later destructor is a no-op on the freed side —
the standard fix for arbitrary GC-order teardown of mutually-referencing wrapped objects.

## 5. ThreadSafeFunction acquire, release, abort

A `ThreadSafeFunction` (TSFN) marshals a JS call from a native thread onto the loop thread —
the *only* correct way to invoke JS off-thread. It has **two independent counters**; do not
conflate them.

| Counter | Moved by | Governs |
| --- | --- | --- |
| **Thread count** | `initialThreadCount` + `Acquire()` − `Release()`/`Abort()` | existence; at **0** the TSFN is destroyed and its finalizer runs on the loop thread |
| **Event-loop ref** | `Ref()` / `Unref()` | whether the TSFN keeps the process alive |

`initialThreadCount` must be **≥ 1**. Critical rule: **`Release()`/`Abort()` must be the LAST
call a thread makes** — "using any thread-safe APIs after having called [`Release`] has
undefined results … as it may have been destroyed" (CWE-416). If a call returns `napi_closing`,
that thread must **not** `Release()` again (`napi_closing` already includes it).

```cpp
// DEFECT: never Release()d → thread count stays > 0 → TSFN never finalized →
//         (default, ref'd) Node HANGS on exit; TSFN + queue + callback ref leak
std::thread([tsfn]() mutable { tsfn.BlockingCall(payload, callJs); }).detach();

// CORRECT: balanced, Release last, scope handles inside the callback
auto tsfn = Napi::ThreadSafeFunction::New(env, jsCb, "Resource", /*maxQueueSize*/0,
    /*initialThreadCount*/1, [](Napi::Env, Ctx* c){ c->worker.join(); delete c; }, ctx);
ctx->worker = std::thread([tsfn]() mutable {
  tsfn.BlockingCall(payload, [](Napi::Env env, Napi::Function cb, Payload* p) {
    Napi::HandleScope scope(env);             // §2: callback runs off a native method
    cb.Call({ Napi::Number::New(env, p->value) });
  });
  tsfn.Release();                             // LAST call this thread makes on tsfn
});                                           // finalizer joins this exact thread
```

Flag: **hang on exit** (unbalanced `Acquire`/`Release`, no `Abort`); **leak** (TSFN, queue,
callback ref, context never freed); **UAF** (use after `Release`/`napi_closing`); **missing
`HandleScope`** in the `call_js` callback (§2); `NonBlockingCall` ignoring `napi_queue_full`
when `maxQueueSize > 0`. A background TSFN that shouldn't hold the process open should `Unref()`
— but then something else must drive shutdown. C API: `napi_acquire_threadsafe_function`,
`napi_release_threadsafe_function` (`napi_tsfn_abort`), `napi_call_threadsafe_function`
(`napi_tsfn_blocking`/`napi_tsfn_nonblocking`), `napi_ref_threadsafe_function`/`napi_unref_threadsafe_function`.
*(Version-sensitive: `Ref`/`Unref` were added after the original method set — verify.)*

## 6. AsyncWorker and the worker boundary

`Napi::AsyncWorker` / `AsyncProgressWorker` (`napi_create_async_work`/`napi_queue_async_work`)
run `Execute()` on a **libuv thread-pool thread**, then `OnOK()`/`OnError()` on the loop
thread. **`Execute()` runs off the JS thread and must never touch `napi_env` or any
`napi_value`** — it "must avoid calling any methods from node-addon-api or running any code
that might invoke JavaScript." Report failure with `SetError(msg)`, surfaced in `OnError`.

```cpp
// DEFECT: reading JS on the pool thread (thread-affinity UB) + dangling input handle
class W : public Napi::AsyncWorker {
  Napi::Object cfg_;
  void Execute() override { auto p = cfg_.Get("path"); /* UB: env/value off-thread */ }
};

// CORRECT: snapshot inputs into native members on the JS thread; JS only in OnOK/OnError
class W : public Napi::AsyncWorker {
  std::string path_; Result result_;
 public:
  W(const Napi::Function& cb, std::string p) : AsyncWorker(cb), path_(std::move(p)) {}
  void Execute() override { result_ = doWork(path_); }              // native types only
  void OnOK() override {
    Napi::HandleScope scope(Env());
    Callback().Call({ Env().Null(), ToJS(Env(), result_) });
  }
};
```

Enforce: copy or ref-count every input in the **constructor** (JS thread) — by `Execute()`
the originating scope is gone; keep a JS object alive across the boundary with a strong
`Napi::Reference` made on the JS thread, released in `OnOK`/`OnError` (node-sqlite's `BackupJob`
holds a `Napi::ObjectReference source_ref_` plus an `std::atomic<bool> shutting_down_` read on
the worker thread — `node-sqlite: src/sqlite_impl.h`, lines 568-577, 606-609). A completed
worker **self-deletes** via `delete` (unless `SuppressDestruct()`), so `AsyncWorker`s must be
heap-allocated and never `delete`d or reused after `Queue()`. With C++ exceptions enabled,
node-addon-api's `AsyncWorker::OnExecute()` catches `const std::exception&` from `Execute()` and
routes its message through `SetError`/`OnError`. A custom wrapper is needed only for non-standard
throws, custom translation, or async machinery that does not provide that catch; no exception may
cross a raw C callback boundary.

## 7. Exceptions must not cross the C ABI

Node-API is a **C** API. Letting a C++ exception unwind through an `extern "C"` callback frame
into V8/Node C code is undefined behavior — typically `std::terminate` → process abort
(CWE-248). **Validate arguments and throw a Node error synchronously at the entry point,
before queuing async work.**

```cpp
// DEFECT: a plain C++ throw is NOT translated by node-addon-api → aborts the process
if (!info[0].IsString()) throw std::runtime_error("path required");

// CORRECT: a Napi error is caught at the wrapper boundary and converted to a JS exception
if (!info[0].IsString()) {
  Napi::TypeError::New(env, "path required").ThrowAsJavaScriptException();
  return env.Null();
}
```

With `NAPI_CPP_EXCEPTIONS`, `Napi::Error` extends `std::exception` and node-addon-api's
wrappers catch it at the boundary; a raw `std::runtime_error` is not (`node-sqlite:
src/sqlite_impl.cpp` translates at every entry via `catch (const SqliteException&)` /
`catch (const std::exception&)` → `ThrowAsJavaScriptException`). With
`NODE_ADDON_API_DISABLE_CPP_EXCEPTIONS` (+ `-fno-exceptions`), APIs return empty values; you
must check `env.IsExceptionPending()` and, in raw C, **check `napi_status` after every call**
(`napi_ok` "means the request succeeded and no uncaught JavaScript exception was thrown"; once
an exception is pending, further calls are unreliable). Silent status-dropping is the native
equivalent of swallowing an error. C helpers: `napi_throw_error`, `napi_throw_type_error`,
`napi_is_exception_pending`, `napi_get_and_clear_last_exception`. Exception mode is a
**build-time** choice (gyp targets `node_addon_api` / `node_addon_api_except` /
`node_addon_api_except_all` / `node_addon_api_maybe`) — see
[`build-and-toolchain.md`](../../project-setup/references/build-and-toolchain.md).

## 8. Context-awareness: instance data, not global statics

A Node process hosts multiple JS environments — the main thread plus every
`worker_threads.Worker`, plus embedders like Electron. node-addon-api: "It is **not safe to
store global data in static variables**," since an addon may load into multiple threads and
multiple times. Mutable `static`/global state is a data race and pins JS references valid in
only one context (wrong-context crash). **Per-env state belongs in instance data**, freed by a
finalizer and an env cleanup hook.

```cpp
// DEFECT: shared across every Worker with no synchronization; refs valid in one env only
static Napi::FunctionReference g_ctor;
static std::map<int, DB*> g_dbs;

// CORRECT: per-env instance data + finalizer (node-sqlite AddonData pattern)
struct AddonData { Napi::FunctionReference db_ctor; std::set<DatabaseSync*> dbs; std::mutex m; };
Napi::Object Init(Napi::Env env, Napi::Object exports) {
  auto* data = new AddonData();
  napi_set_instance_data(env, data, CleanupAddonData, nullptr);   // per-env slot + finalizer
  return exports;
}
```

node-sqlite registers `AddonData` via `napi_set_instance_data` (`node-sqlite: src/binding.cpp`,
lines 70-80) and clears databases and `Reset`s stored references under their mutexes in
`CleanupAddonData` (lines 11-39); callback wrappers additionally use `napi_add_env_cleanup_hook`
in constructors and `napi_remove_env_cleanup_hook` in destructors. fs-metadata stores a per-env
`ShutdownState` (`std::atomic<bool>`) via `napi_set_instance_data` and flips it from a cleanup
hook so in-flight workers short-circuit before touching napi (`fs-metadata: src/common/shutdown.h`,
lines 84-107). `Napi::Addon<T>` + `NODE_API_ADDON(T)` is sugar for the same mechanism.
Concurrency mechanics live in
[`sanitizers-and-analysis.md`](../../project-setup/references/sanitizers-and-analysis.md); flag
any mutable module-level `static`, and any `static Napi::Reference`/`FunctionReference`.

## 9. Copy at the C boundary; external buffers and memory

**Copy at the boundary.** When handing a pointer into a C library that may retain or read it
later, do not alias a soon-dead `std::string`/`ArrayBuffer`. node-sqlite passes
`SQLITE_TRANSIENT` to every result setter so SQLite copies immediately instead of aliasing a
buffer about to be freed (`node-sqlite: src/user_function.cpp`, `src/aggregate_function.cpp`).
For native memory exposed *to* JS, the mirror rules:

- **External buffers are not universal.** `napi_create_external_buffer` /
  `napi_create_external_arraybuffer` may return `napi_no_external_buffers_allowed` on some
  runtimes — "one such runtime is Electron." Provide a copying fallback (`napi_create_buffer_copy`
  / `Napi::Buffer::Copy`), or define `NODE_API_NO_EXTERNAL_BUFFERS_ALLOWED` to reject the
  external path at compile time.
- **Register external memory with the GC.** V8 sizes GC pressure from *heap* usage, so a tiny
  wrapper holding a 100 MB native buffer looks cheap and its freeing finalizer may be delayed
  indefinitely — RSS balloons. Pair `napi_adjust_external_memory(env, +bytes, …)` /
  `Napi::MemoryManagement::AdjustExternalMemory(env, +bytes)` at allocation with `-bytes` in the
  finalizer, which is the **only** hook to free the backing store (and is GC-timed, §4).

```cpp
Napi::MemoryManagement::AdjustExternalMemory(env, +int64_t(len));
auto buf = Napi::Buffer<uint8_t>::New(env, data, len, [](Napi::Env env, uint8_t* p) {
  Napi::MemoryManagement::AdjustExternalMemory(env, -int64_t(g_len));   // pair the +len
  std::free(p);                                                          // free backing store
});
```

Flag: a native backing store with no finalizer (leak); a finalizer that frees but omits the
negative `AdjustExternalMemory` (GC never pressured); external-buffer creation with no status
check or copy fallback where Electron is a target; a pointer handed to a C API without a copy
or a documented lifetime that outlives the call.

## Pitfall-to-fix quick table

| Pitfall | Root cause | Fix | CWE |
| --- | --- | --- | --- |
| Memory grows in a long loop / libuv or TSFN callback | `napi_value`s pile up in the default handle scope | inner `Napi::HandleScope` per iteration / atop any off-method callback | 401 |
| Empty/garbage value after a helper returns | value's owning scope closed | `EscapableHandleScope::Escape()` (once) | 416 |
| Stored `napi_value` dangles later | handle kept past its call scope | hold a `Napi::Reference`; materialize a handle on demand | 416 |
| JS object never collected | strong ref never `Unref`/`delete`d; or intended-strong ref left weak | balance `Ref`/`Unref`; `napi_delete_reference`; `Persistent` for strong | 401/772 |
| `node script.js` hangs on exit | TSFN thread count never reaches 0 | balance `Acquire`/`Release`; or `Unref()` if it shouldn't hold the loop | 401 |
| Crash calling a TSFN after shutdown | used after `Release`/`napi_closing` | `Release`/`Abort` must be the LAST call; don't `Release` after `napi_closing` | 416 |
| Native resource leaks despite ObjectWrap | relied on a finalizer that ran late or never | explicit idempotent `close()`/`dispose()`; finalizer is a backstop | 401/772 |
| Finalizer terminates the process | basic finalizer calls a non-basic or JS-executing API | native/basic cleanup only; defer other work with `node_api_post_finalizer` | 248 |
| RSS balloons; GC never reclaims big buffers | V8 unaware of external memory | `AdjustExternalMemory(+n)` on alloc, `(-n)` in finalizer | 401 |
| `napi_no_external_buffers_allowed` under Electron | runtime dropped external buffers | copy fallback; guard with `NODE_API_NO_EXTERNAL_BUFFERS_ALLOWED` | — |
| Process aborts on a thrown error | C++ exception unwound across the C ABI | throw a `Napi` error at the boundary; never let one escape a callback | 248 |
| Reads JS in `AsyncWorker::Execute()` | touching env/values off the JS thread | copy inputs to native members in the ctor; JS only in `OnOK`/`OnError` | 416 |
| Data race / wrong-context crash across Workers | cached `napi_env` or mutable static state | never cache/share `napi_env`; use `napi_set_instance_data`; cross threads only via TSFN | race/416 |

## Grep starters

Locate candidates, then read the code — these do not prove a bug.

```bash
# call-scoped handles stored past the call (member/static/container)
grep -rn "Napi::Value\|napi_value" --include=*.{h,cc,cpp} | grep -iv "CallbackInfo\|info\["
# references: weak-by-default ctor, and Reset/delete sites (verify env lifetime and callback API rules)
grep -rn "Reference<.*>::New\|napi_create_reference\|\.Reset(\|napi_delete_reference" --include=*.{cc,cpp}
# ObjectWrap destructors / finalizers — distinguish ordinary, basic, and post-finalizer callbacks
grep -rn "~.*ObjectWrap\|Finalize(" --include=*.{h,cc,cpp}
# TSFN balance and napi_closing handling
grep -rn "ThreadSafeFunction\|BlockingCall\|NonBlockingCall\|\.Release(\|\.Abort(" --include=*.{cc,cpp}
# AsyncWorker Execute bodies touching env/values (thread-affinity UB)
grep -rn "void Execute()" --include=*.{cc,cpp}
# raw throws at entry points (should be Napi errors)
grep -rn "throw " --include=*.{cc,cpp} | grep -iv "Napi::\|ThrowAsJavaScriptException"
# mutable global/static addon state; external buffers without copy fallback / accounting
grep -rn "static .*\(Napi::\|Reference\|std::map\|std::set\|std::vector\)" --include=*.{cc,cpp}
grep -rn "external_buffer\|external_arraybuffer\|AdjustExternalMemory\|SQLITE_TRANSIENT" --include=*.{cc,cpp}
```

## Primary sources

- Node.js — **Node-API reference** (env thread-affinity & unload; handle scopes; references;
  ThreadSafeFunction; finalization / `node_api_post_finalizer`; external buffers &
  `napi_adjust_external_memory`; error-handling status contract; `napi_set_instance_data` /
  `napi_add_env_cleanup_hook`): https://nodejs.org/api/n-api.html — *MIT*
- Node.js — **C++ addons** (context-awareness, Worker support): https://nodejs.org/api/addons.html
  — *MIT*; and **Learn: Thread-Safe Functions** (Ref/Unref exit semantics, `napi_closing` FAQ):
  https://nodejs.org/learn/node-api/special-topics/thread-safe-functions — *MIT*
- node-addon-api docs (MIT), https://github.com/nodejs/node-addon-api/tree/main/doc —
  `object_lifetime_management.md` / `handle_scope.md` / `escapable_handle_scope.md` (default
  scope, LIFO, single `Escape`); `reference.md` (weak-by-default, `SuppressDestruct`);
  `object_wrap.md` (deferred destructor); `async_worker.md` (`Execute` off-thread, self-delete);
  `threadsafe_function.md` ("undefined results after Release"); `memory_management.md` /
  `external_buffer.md`; `error_handling.md` ("C++ exceptions must not cross the C ABI boundary");
  `addon.md` (`Napi::Addon<T>`).
- SQLite C API — `sqlite3_close`/`sqlite3_close_v2` and `SQLITE_TRANSIENT` binding lifetime
  (public domain): https://www.sqlite.org/c3ref/close.html , https://www.sqlite.org/c3ref/bind_blob.html
- MITRE **CWE-401** (Missing Release of Memory), **CWE-416** (Use After Free), **CWE-772**
  (Missing Release of Resource), **CWE-248** (Uncaught Exception): https://cwe.mitre.org/
- Reference projects (paths cited inline): `@photostructure/sqlite` (`node-sqlite:
  src/binding.cpp`, `src/sqlite_impl.{h,cpp}`, `src/user_function.cpp`,
  `src/aggregate_function.cpp`); `@photostructure/fs-metadata` (`fs-metadata: src/common/shutdown.h`).
