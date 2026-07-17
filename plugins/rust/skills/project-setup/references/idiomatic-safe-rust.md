# Idiomatic, Safe, Maintainable Rust

Use this reference for code/API design, ownership, errors, unsafe/FFI boundaries,
concurrency, documentation, and maintainability refactors. Apply it to the project's role
and compatibility promises; the Rust API Guidelines are considerations, not mandates.

## Contents

- [TL;DR](#tldr)
- [Start from ownership and capabilities](#start-from-ownership-and-capabilities)
- [Encode meaning and invariants in types](#encode-meaning-and-invariants-in-types)
- [Keep modules and public APIs intentional](#keep-modules-and-public-apis-intentional)
- [Design errors and panics](#design-errors-and-panics)
- [Govern unsafe code](#govern-unsafe-code)
- [FFI and native boundaries](#ffi-and-native-boundaries)
- [Concurrency and async](#concurrency-and-async)
- [Documentation and examples](#documentation-and-examples)
- [Refactoring discipline](#refactoring-discipline)
- [Common gotchas and non-findings](#common-gotchas-and-non-findings)
- [Primary sources](#primary-sources)

## TL;DR

1. Make ownership reflect reality: borrow for temporary access, own values retained by the
   callee, and avoid cloning merely to escape an unclear boundary.
2. Expose the narrow capability needed—slices, iterators, the standard I/O traits, or a concrete
   type—without making every API generic.
3. Encode domain distinctions and invalid states with types when the added structure pays
   for itself.
4. Keep visibility narrow; public fields, traits, variants, features, and dependency types
   become compatibility commitments.
5. Return `Result` for anticipated failure, reserve panics for bugs/invariants or truly
   unrecoverable context, and document both.
6. Forbid unsafe where unnecessary. Otherwise isolate it, state proof obligations, explain
   each discharge, and test the safe abstraction under hostile-but-safe use.
7. Prefer clear, boring control flow over compressed iterator/generic cleverness when the
   latter obscures ownership, failure, or lifecycle.

## Start from ownership and capabilities

Choose parameter and return types from the operation:

- borrow `&T`/`&mut T` when work is temporary and the caller retains ownership;
- take `T` when the callee stores, consumes, transfers, or independently owns it;
- return an owned value when it must outlive internal state; return a borrow only when the
  lifetime relationship is stable and useful to callers;
- accept `&[T]` instead of `&Vec<T>`, `&str` instead of `&String`, and path/byte abstractions
  that match the required capability;
- use `IntoIterator`, the standard I/O traits, `AsRef<Path>`, or generics when callers genuinely
  benefit—not to demonstrate abstraction;
- prefer `impl Trait` or a named type according to API stability, diagnostics, object use,
  and caller needs;
- avoid storing references in long-lived structs unless borrowing is fundamental to the
  model; owned/arena/index designs can be easier to evolve.

A clone can be the correct ownership boundary. A clone that immediately follows an
unnecessary borrow, hides shared mutation, or copies large data on a hot path deserves
review. Do not trade a cheap, clear clone for pervasive lifetime complexity without a
measured or architectural benefit.

Likewise, do not wrap everything in `Arc`. Shared ownership is a semantic choice that
affects destruction, cycles, thread-safety bounds, and API expectations.

## Encode meaning and invariants in types

Use types to prevent meaningful misuse:

- newtypes for identifiers, units, validated values, secrets, or values with different
  semantics despite identical representation;
- enums for a closed set of states/actions rather than strings or unlabeled booleans;
- structs/options/builders when a call has several same-typed arguments or construction
  rules;
- `NonZero*`, ranges, and domain wrappers when they make invalid states unrepresentable;
- `From`/`TryFrom`, `AsRef`/`AsMut`, and iterator traits for conventional conversions;
- derive `Debug` on essentially every public type; eagerly derive the other common traits
  (`Clone`, `Eq`/`PartialEq`, `Ord`/`PartialOrd`, `Hash`, `Default`) where their semantics
  are unsurprising, since the orphan rule stops downstream crates from adding them later.

Illustrative boundary validation:

```rust
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NonEmptyName(String);

impl TryFrom<String> for NonEmptyName {
    type Error = EmptyName;

    fn try_from(value: String) -> Result<Self, Self::Error> {
        if value.trim().is_empty() {
            Err(EmptyName)
        } else {
            Ok(Self(value))
        }
    }
}
```

Do not create a type-state maze, builder, trait, or newtype for every field. Count the
invalid calls prevented, repeated validation removed, documentation clarified, and public
compatibility improved against the abstraction cost.

Avoid `Deref` as generic method forwarding; it carries smart-pointer/coercion expectations.
Avoid implementing `Into` directly when implementing `From` gives the reciprocal `Into`
implementation. Make fallible conversion explicit with `TryFrom`/`TryInto`.

## Keep modules and public APIs intentional

- Start private. Use `pub(crate)` for cross-module internals and `pub` only for a supported
  external contract.
- Re-export a deliberate public surface rather than exposing directory layout wholesale.
- Keep domain logic independent from CLI/web/database/runtime adapters where practical.
- Give modules cohesive names; replace broad `utils`, `common`, or `helpers` buckets with
  responsibilities when patterns emerge.
- Keep functions small enough to name one responsibility, but do not fragment linear logic
  into helpers that require jumping between files to understand it.
- Prefer explicit data flow over hidden globals, thread-locals, service locators, or broad
  interior mutability.
- Minimize public generic parameters and trait bounds. Every bound affects callers,
  inference, compile time, diagnostics, and future compatibility.
- Keep struct fields private unless callers are intentionally allowed to construct and
  exhaustively destructure the representation.
- Mark types/variants `#[non_exhaustive]` or use private fields only when that future
  extensibility tradeoff matches caller ergonomics.
- Seal traits that downstream crates must not implement. Leave them open when ecosystem
  extension is the purpose.
- Avoid exposing third-party types in public signatures accidentally; doing so adopts part
  of that dependency's API and version policy.
- Follow RFC 430 casing: `snake_case` functions, methods, variables, and modules;
  `UpperCamelCase` types and traits; `SCREAMING_SNAKE_CASE` constants and statics.
- Signal conversion cost and ownership through method prefixes—`as_` for a cheap borrow,
  `to_` for an expensive or owning conversion, `into_` for a consuming one—and name getters
  `field()`, not `get_field()`.
- Provide construction through inherent associated functions (`Type::new`, `Type::with_*`)
  returning `Self`; reserve builders for genuinely complex or optional-heavy construction.
- Name collection iterator methods `iter`/`iter_mut`/`into_iter`, and name iterator types
  after the method that produces them.
- Prefer public types that are `Send` and `Sync` wherever the representation allows, so
  callers can move and share them across threads.
- Mark `#[must_use]` on returns whose value is the point of the call—builders, status
  `Result`s, and pure transforms—so accidental discards warn.

Public API review must account for Cargo's SemVer details: adding a field or enum variant,
tightening a bound, adding trait items, changing default features, or raising MSRV can
break downstream code even when local tests pass.

## Design errors and panics

Rust distinguishes anticipated recoverable failure from bugs/unrecoverable context:

- return `Result<T, E>` when callers can reasonably handle, report, retry, map, or compose
  the failure;
- use `Option<T>` when absence is the only relevant failure and its cause does not matter;
- panic for violated internal invariants/programmer mistakes or when continuation is not a
  meaningful contract in that layer;
- do not panic on routine malformed input, I/O, network, configuration, or user errors in
  reusable libraries;
- applications may choose to terminate at their top-level boundary after adding useful
  context; that does not justify panics deep in reusable code.

Public library errors should normally:

- be meaningful types implementing `Debug`, `Display`, and `std::error::Error` when `std`
  is available; `no_std` crates whose MSRV is Rust 1.81 or newer can implement
  `core::error::Error` (re-exported by `std`);
- preserve underlying causes through `source()` where useful;
- normally be `Send + Sync + 'static` so they cross threads and compose with
  `Box<dyn Error + Send + Sync>` and common error libraries;
- avoid `()` or opaque strings when callers need to distinguish recovery actions;
- avoid exposing private implementation details or secrets;
- balance stable variants against future extensibility (`#[non_exhaustive]` has ergonomic
  costs and benefits).

Prefer `?` and explicit mapping/context over repetitive matches. Do not mechanically ban
`unwrap`/`expect`: tests, examples, process initialization, and statically established
invariants differ from request/data paths. When an invariant justifies `expect`, phrase
the message as why the value **should** be present or valid; this improves diagnosis.

Document `# Errors` and `# Panics` for public functions where callers need those contracts.
Never rely on `Drop` to communicate recoverable failure; provide an explicit close/flush/
finish operation when callers must observe it.

## Govern unsafe code

Unsafe code defines proof obligations the compiler does not check. Choose a policy by
crate role:

| Crate/surface | Normal policy |
| --- | --- |
| Safe-only business/application/library crate | `unsafe_code = "forbid"` when no local unsafe is legitimate |
| Crate wrapping FFI or implementing a low-level abstraction | Deny implicit/undocumented unsafe; allow only in narrow reviewed modules |
| Generated bindings | Isolate generated unsafe from handwritten safe wrappers and lint it separately |
| Build script/proc macro | Runtime `unsafe_code` policy does not cover its external effects or dependencies; review separately |

Where unsafe is necessary:

1. State the invariant and why safe Rust cannot express the required operation adequately.
2. Keep the unsafe block as small as practical without splitting one proof into fragments.
3. Put unsafe behind a private boundary and expose a safe API only if **all safe callers**
   preserve soundness.
4. State the contract for every `unsafe fn` and unsafe trait, regardless of visibility.
   Use a `# Safety` section for public APIs and an adjacent contract comment for private
   ones, spelling out caller or implementor obligations.
5. Add a local `SAFETY:` explanation for every unsafe block and `unsafe impl`, tied to the
   callee/language preconditions rather than “tests pass.”
6. Enable `unsafe_op_in_unsafe_fn` so an unsafe function body still marks each discharged
   operation explicitly.
7. Audit validity, initialization, alignment, provenance, aliasing, lifetimes, ownership,
   integer/length calculations, unwind paths, and thread-safety.
8. Test safe callers that use zero lengths, empty values, overlapping lifetimes, panics,
   concurrency, cancellation, and teardown; run Miri/sanitizers/fuzzing where supported.

Unsafe abstractions cannot rely on destructors always running: `mem::forget` is safe, and
cycles/process termination can also skip expected cleanup. Memory safety invariants must
survive leaked values. Audit `ManuallyDrop`, `MaybeUninit`, raw parts, self-references,
pinning, callbacks, and manual `Send`/`Sync` implementations especially carefully.

Pinning adds a narrower drop guarantee: once pinned, a value must remain valid at its
address until its destructor runs. If it is leaked and `Drop` never runs, its storage must
not be invalidated or reused as though destruction occurred. Custom pinned storage must
run `drop_in_place` before reuse. This does not make ordinary cleanup guaranteed.

Include unsafe declarations and attributes in the audit, not only unsafe blocks: review
every extern declaration and use of `no_mangle`, `export_name`, or `link_section`. In
edition 2024 these are made explicit with `unsafe extern`, `#[unsafe(no_mangle)]`,
`#[unsafe(export_name = "...")]`, and `#[unsafe(link_section = "...")]`. Also review
standard-library calls that an edition migration newly wraps in `unsafe`; automated syntax
does not prove their preconditions. Treat references to `static mut` as almost always the
wrong abstraction; the 2024 edition denies them by default.

Do not report missing comments as unsoundness. Report the missing proof contract as a
maintainability Gap; a defect requires showing which invariant can be violated.

## FFI and native boundaries

For FFI or stable ABI surfaces:

- use the correct ABI and `repr(C)`/explicit representation only where the external
  contract requires it;
- define ownership for every pointer, allocation, callback, and returned buffer: who
  creates, borrows, mutates, frees, and on which thread;
- validate nullability, length, alignment, lifetime, encoding, discriminants, and integer
  conversion before creating Rust references/slices/values;
- for `slice::from_raw_parts`, require a non-null aligned pointer even for length zero, one
  allocation, initialized elements, valid aliasing, and total size no greater than
  `isize::MAX`;
- use `Vec::from_raw_parts` only with the original compatible allocator/layout, exact
  capacity and initialized length, and exclusive ownership—ordinary C allocations cannot
  generally be adopted this way;
- pair `CString::from_raw` only with a pointer returned by `CString::into_raw`; foreign
  code must not change the string length, and a C allocator/free is not interchangeable;
- keep raw declarations separate from handwritten safe wrappers;
- do not let borrowed Rust references outlive foreign storage or callbacks;
- define unwind behavior at the boundary and prevent accidental cross-language unwinding;
- translate errors without exposing Rust layouts or panics as an undocumented ABI;
- audit callback reentrancy, thread affinity, shutdown, library unloading, and foreign
  ownership transfer;
- compile/test every supported target ABI and native-library mode;
- document system vs bundled native dependencies, required versions, and licensing.

The fact that an FFI wrapper exposes only safe functions is a strong promise: arbitrary
well-typed callers must not be able to trigger undefined behavior. Validate that promise
nonlocally across mutation, callbacks, `Drop`, `mem::forget`, and concurrent use.
Test that the safe boundary rejects invalid pointer metadata before it enters unsafe code;
never violate an unsafe primitive's preconditions merely to see whether a test fails.

## Concurrency and async

Rust prevents data races in safe code, not deadlocks, starvation, logical races, blocking,
or cancellation bugs.

- Use message passing, ownership transfer, immutable sharing, atomics, or locks according
  to the state transition—not ideology.
- Keep lock scope visible and small; define lock ordering when multiple locks can nest.
- Avoid holding a synchronous mutex guard across `.await`; use an async-aware primitive or
  restructure ownership when suspension is possible.
- Keep CPU/blocking I/O off async executor threads according to the runtime's documented
  mechanism.
- Define cancellation safety: what state exists if a future is dropped at each await?
- For a public async trait, choose and document whether returned futures must be `Send`;
  bare `async fn` in a public trait does not promise `Send`, and downstream users cannot
  strengthen that trait contract themselves.
- Give tasks a clear owner, shutdown signal, and join/error-observation path; detached work
  should be intentional.
- Avoid unbounded channels/queues unless memory growth is explicitly acceptable.
- Audit manual `unsafe impl Send/Sync`; compiler-derived traits prove structural bounds,
  while the abstraction must also uphold its documented semantic contract.
- For atomics, document the required happens-before relationship and why each ordering is
  sufficient; an atomic field does not by itself make surrounding non-atomic access safe.
- Treat mutex poisoning as advisory recovery information. Unsafe code must not rely on a
  poison error occurring to preserve soundness because poisoning can be skipped.
- `Rc<RefCell<T>>` can leak through cycles and panic on borrow violations; `Arc<Mutex<T>>`
  can deadlock or poison. Neither pattern is inherently wrong.

Test shutdown, cancellation, backpressure, lock ordering, task failure, and bounded resource
use. Miri can detect some executed data races; it is not a scheduler proof.

## Documentation and examples

For public libraries:

- add crate-level docs stating purpose, quick start, features, MSRV/targets, and important
  invariants;
- document intent and constraints rather than restating signatures;
- include `# Errors`, `# Panics`, and `# Safety` where applicable;
- make examples copyable and use `?` where error handling is part of the lesson;
- run examples as doctests when practical; use `no_run` for code that should compile but
  not execute and `compile_fail` for meaningful type-level rejection;
- use hidden doctest setup instead of `ignore` merely to shorten examples;
- keep large end-to-end examples under `examples/` and compile/run them in CI;
- use intra-doc links so renamed items fail visibly under rustdoc checks;
- consider `missing_docs = "deny"` for an established public surface and `warn` during
  adoption; private binaries may reasonably use a different policy.

`compile_fail` examples can become valid after language evolution. Pin/check the relevant
toolchain and ensure the example expresses a durable contract rather than an incidental
diagnostic.

## Refactoring discipline

Before an idiomatic refactor:

1. Map public signatures, features, error/panic behavior, MSRV/targets, serialization and
   ABI formats, and performance-sensitive paths.
2. Add characterization tests for behavior that must remain.
3. Change one ownership/API boundary at a time.
4. Avoid mixing mechanical formatting/lints, dependency updates, and semantic redesign in
   one opaque diff.
5. Run default/minimal/feature/target/MSRV checks that cover the changed surface.
6. Classify public changes using Cargo's SemVer guidance and document intentional breaks.

Prefer changes that remove states, branches, duplication, or hidden coupling. A shorter
implementation is not automatically clearer; optimize for the next maintainer's ability
to locate invariants and failure paths.

## Common gotchas and non-findings

- **Safe Rust is not bug-free Rust.** Panics, deadlocks, leaks, resource exhaustion,
  application races, and unsafe dependencies remain possible.
- **Unsafe is not automatically a defect.** It is a proof boundary that needs contracts and
  validation.
- **`forbid(unsafe_code)` covers local syntax, not dependency/build behavior.** Do not claim
  the entire product contains no unsafe code.
- **`unwrap` is contextual.** Focus on recoverable production paths and diagnostic quality.
- **Cloning can clarify ownership.** Do not replace it with lifetime/generic complexity
  without benefit.
- **Interior mutability is a design signal, not a failure.** Verify runtime borrow/lock
  behavior and visibility.
- **Trait-heavy is not synonymous with idiomatic.** Prefer concrete types until extension
  or substitution is real.
- **Public fields/traits/features are promises.** Local convenience can constrain every
  future release.
- **`Drop` is not generally guaranteed to run.** Pinning additionally forbids invalidating
  or reusing leaked pinned storage as though the pinned value had been dropped.
- **Async does not make blocking disappear.** Find executor-blocking calls and unowned
  tasks.
- **API Guidelines can age.** For example, current Cargo deprecates `authors`; current
  Cargo/rustdoc documentation overrides older checklist metadata.

## Primary sources

- [Rust API Guidelines checklist](https://rust-lang.github.io/api-guidelines/checklist.html)
- [Rust Reference: unsafety](https://doc.rust-lang.org/stable/reference/unsafety.html)
- [The `unsafe` keyword](https://doc.rust-lang.org/stable/std/keyword.unsafe.html)
- [Rust Reference: undefined behavior](https://doc.rust-lang.org/stable/reference/behavior-considered-undefined.html)
- [Edition Guide: unsafe extern blocks](https://doc.rust-lang.org/edition-guide/rust-2024/unsafe-extern.html)
- [Edition Guide: unsafe attributes](https://doc.rust-lang.org/edition-guide/rust-2024/unsafe-attributes.html)
- [Edition Guide: `static mut` references](https://doc.rust-lang.org/edition-guide/rust-2024/static-mut-references.html)
- [Rustonomicon](https://doc.rust-lang.org/nomicon/)
- [Rust Book: error handling](https://doc.rust-lang.org/stable/book/ch09-00-error-handling.html)
- [`std::error::Error`](https://doc.rust-lang.org/std/error/trait.Error.html)
- [`core::error::Error`](https://doc.rust-lang.org/core/error/trait.Error.html)
- [`Pin` and the drop guarantee](https://doc.rust-lang.org/core/pin/index.html#subtle-details-and-the-drop-guarantee)
- [`slice::from_raw_parts`](https://doc.rust-lang.org/core/slice/fn.from_raw_parts.html)
- [`Vec::from_raw_parts`](https://doc.rust-lang.org/alloc/vec/struct.Vec.html#method.from_raw_parts)
- [`CString::from_raw`](https://doc.rust-lang.org/alloc/ffi/struct.CString.html#method.from_raw)
- [Atomic memory orderings](https://doc.rust-lang.org/core/sync/atomic/enum.Ordering.html)
- [`Mutex` poisoning](https://doc.rust-lang.org/std/sync/struct.Mutex.html#poisoning)
- [rustdoc: how to write documentation](https://doc.rust-lang.org/rustdoc/how-to-write-documentation.html)
- [Cargo SemVer compatibility](https://doc.rust-lang.org/cargo/reference/semver.html)
- [`mem::forget`](https://doc.rust-lang.org/std/mem/fn.forget.html)

<!-- Original synthesis of primary Rust ecosystem guidance. See ../ATTRIBUTION.md. -->
