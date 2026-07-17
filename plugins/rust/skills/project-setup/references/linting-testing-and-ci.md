# Rust Linting, Testing, and CI

Use this reference to establish strict but usable rustc/Clippy/rustfmt policy, testing
coverage, MSRV and target CI, and conditional Miri/fuzz/sanitizer checks.

## Contents

- [TL;DR](#tldr)
- [Formatting policy](#formatting-policy)
- [Lint policy](#lint-policy)
- [A maintainable strict baseline](#a-maintainable-strict-baseline)
- [Suppressions and toolchain upgrades](#suppressions-and-toolchain-upgrades)
- [Testing layers](#testing-layers)
- [Feature, target, and MSRV matrix](#feature-target-and-msrv-matrix)
- [Miri, sanitizers, and fuzzing](#miri-sanitizers-and-fuzzing)
- [CI design](#ci-design)
- [Common gotchas](#common-gotchas)
- [Primary sources](#primary-sources)

## TL;DR

1. Gate `cargo fmt --all --check` using a stable documented style edition.
2. Keep ordinary rustc and default Clippy warnings clean; use CI `-D warnings` when the
   toolchain update policy can absorb new lints.
3. Treat `clippy::pedantic` as opt-in policy with narrow exceptions. Never enable
   `clippy::restriction` or `clippy::nursery` wholesale.
4. Put shared lint policy in `[workspace.lints]` only when the Cargo/MSRV supports it,
   and make every intended member opt in with `[lints] workspace = true`.
5. Test default, no-default, valid all-features, important combinations, supported
   platforms, MSRV, current stable, docs, and release packaging as distinct concerns.
6. Run Miri/fuzz/sanitizers where their execution model covers risky unsafe, parser, FFI,
   or concurrency code. A clean run is evidence for paths exercised, not proof.

## Formatting policy

Prefer rustfmt's standard style. Ecosystem consistency reduces contributor debate and
keeps mechanical diffs predictable.

Gate formatting without rewriting files:

```text
cargo fmt --all --check
```

Keep `rustfmt.toml` small. Set both `edition` (parser behavior) and `style_edition`
(formatting rules) explicitly when direct rustfmt/editor runs must match `cargo fmt`.
Cargo can pass a package's edition, but direct rustfmt otherwise defaults to the 2015
edition when no configuration supplies one. Verify both settings against the project's
rustfmt/toolchain, especially in mixed-edition workspaces. Avoid nightly-only formatting
options in a stable project unless the project intentionally pins nightly rustfmt.

Formatting is not code review. A formatted module can still be opaque; do not contort
clear code to satisfy arbitrary line or import preferences outside standard rustfmt.

## Lint policy

Use lint levels intentionally:

- `warn` makes migration visible without blocking all work;
- `deny` is enforceable but can be overridden narrowly when justified;
- `forbid` cannot be overridden and should be reserved for rules with no legitimate
  local exception, such as `unsafe_code` in a genuinely safe-only crate;
- `allow` should be narrow and explained when it suppresses project policy.

Clippy groups have different promises:

| Group | Default approach |
| --- | --- |
| `clippy::correctness` | Deny; these lints identify code considered wrong or useless |
| Default `clippy::all` groups | Run everywhere and keep warning-clean |
| `clippy::pedantic` | Enable when the team accepts opinionated findings and scoped exceptions |
| `clippy::restriction` | Never enable wholesale; cherry-pick policy lints because members can conflict |
| `clippy::nursery` | Never enable wholesale in a stable gate; cherry-pick only after validating toolchain behavior |
| `clippy::cargo` | Consider for publishable manifests; expect policy/noise tradeoffs |

Do not equate “more lints” with maintainability. A rule that produces regular false
positives, encourages obscure rewrites, or breaks on every toolchain update can cost more
than it prevents.

Keep `clippy.toml`/`.clippy.toml` small. Clippy configuration options are explicitly
unstable and can change across toolchains; verify every key against the pinned Clippy and
prefer manifest lint levels for policy that Cargo can express.

## A maintainable strict baseline

For a workspace whose MSRV supports Cargo's lint tables, start near this shape and adapt:

```toml
[workspace.lints.rust]
unsafe_op_in_unsafe_fn = "deny"
missing_docs = "warn" # normally public libraries; allow or omit for private binaries

[workspace.lints.clippy]
all = { level = "warn", priority = -1 }
correctness = "deny"
pedantic = { level = "warn", priority = -1 }
dbg_macro = "deny"
todo = "deny"
unimplemented = "deny"
missing_safety_doc = "deny"
undocumented_unsafe_blocks = "deny"
```

Each intended member needs:

```toml
[lints]
workspace = true
```

Then gate warnings on the selected current toolchain:

```text
cargo clippy --workspace --all-targets --all-features --locked -- -D warnings
```

Adapt this rather than copying it:

- omit `--all-features` when features are mutually exclusive or target-specific;
- a safe-only crate can set `unsafe_code = "forbid"` under rust lints;
- a crate that needs unsafe should normally deny undocumented/implicit unsafe and permit
  it only in reviewed modules;
- `missing_docs` is useful for public libraries but can create noise for private binary
  internals unless visibility is already disciplined;
- `todo`/`unimplemented` may be allowed in prototypes or tests by explicit local policy;
- strict `unwrap_used`/`expect_used` rules should target recoverable production paths,
  not be enabled blindly across tests and proven initialization invariants;
- verify every lint name and Cargo `[lints]` support against the MSRV before adding it.

`cargo clippy -- -D warnings` also denies rustc warnings. Keep an ordinary `cargo check`
job so compilation behavior is visible without relying on Clippy as a compiler wrapper.

## Suppressions and toolchain upgrades

Prefer eliminating the cause. When an exception is correct:

1. scope it to the smallest item/expression/module;
2. name the exact lint, not an entire group;
3. explain the invariant or tradeoff;
4. use `#[expect(..., reason = "...")]` when the MSRV supports lint expectations so a
   stale suppression is reported;
5. otherwise pair a narrow `#[allow(...)]` with a nearby rationale;
6. do not hide generated/third-party warnings by weakening first-party policy globally.

Clippy adds and changes lints with Rust releases. `-D warnings` can therefore break CI on
a toolchain update without a source regression. Choose one of these coherent policies:

- pin the CI/contributor toolchain and update it through reviewed automation;
- follow stable and accept prompt lint maintenance;
- keep new optional lint groups warning-only while default correctness remains gating.

Do not permanently allow `unknown_lints` to make a too-new policy appear MSRV-compatible.
Separate stable lint CI from an older MSRV compile/test job when necessary.

## Testing layers

Use the smallest layer that proves the behavior, while retaining realistic boundary
tests:

- **unit tests:** private invariants, edge cases, pure logic, error paths;
- **integration tests:** public API and binary behavior from an external consumer view;
- **doctests:** public examples that compile and run with documented imports/features;
- **compile-fail tests:** intentional type-system or macro rejection contracts;
- **examples:** larger workflows that at least compile in CI and run when practical;
- **property/fuzz tests:** parsers, serializers, state machines, unsafe wrappers, and
  inputs with large combinatorial spaces;
- **benchmarks:** measured performance contracts, not correctness substitutes.

Test failures, panics, cancellation, partial I/O, cleanup, and recovery—not only happy
paths. For concurrency, test shutdown and lock ordering. For libraries, test how a
downstream crate imports and uses public items.

`cargo test` normally includes unit, integration, and library documentation tests, and
builds examples; target flags change that selection. Confirm what the exact command runs.
Do not disable doctests merely to make CI faster if documentation examples are part of
the public API.

rustdoc injects several `allow` attributes into doctest crates, so a passing doctest does
not prove the example satisfies every project warning. Add deliberate doctest attributes
with `#![doc(test(attr(...)))]` only when that is the actual policy, and give every ignored
doctest a reason; prefer runnable, `no_run`, or `compile_fail` examples where accurate.

## Feature, target, and MSRV matrix

A practical baseline might include these independently adapted checks:

```text
cargo check --workspace --all-targets --locked
cargo test --workspace --locked
cargo test --workspace --no-default-features --locked
cargo test --workspace --all-features --locked
cargo clippy --workspace --all-targets --all-features --locked -- -D warnings
cargo doc --workspace --no-deps --all-features
```

Do not run the last two feature forms when all features cannot coexist. Build a named
matrix of supported combinations instead.

Required CI should cover:

- default features and no-default for libraries that claim minimal configurations;
- all features when valid plus important pairwise/composed features;
- every Tier/target/platform the project promises, including target-specific modules;
- the declared MSRV with supported features;
- current stable with the newest compatible dependencies in a separate intentional job;
- examples and public docs/doctests;
- the release/package configuration that ships.

MSRV verification should use the exact declared version, not `stable`. If the MSRV is
older than lint-table or Clippy-policy support, compile/test at MSRV and lint with the
documented current contributor toolchain.

Clippy normally derives its MSRV-aware behavior from Cargo's `rust-version`; avoid a
second, divergent `msrv` in Clippy configuration unless intentional. Keep
`incompatible_msrv` enabled, decide whether tests must also avoid newer APIs
(`check-incompatible-msrv-in-tests` defaults to false), and still compile/test on the
actual MSRV—lint suppression and suggestions are not compatibility proof.

Lock ordinary CI with `--locked`. A separate latest-dependencies job should deliberately
refresh resolution and must not masquerade as the reproducible build.

## Miri, sanitizers, and fuzzing

### Miri

Use Miri for code whose unsafe, aliasing, validity, alignment, initialization, or
concurrency behavior is exercised by tests:

```text
cargo +nightly miri test
MIRIFLAGS="-Zmiri-many-seeds=0..16" cargo +nightly miri test
```

Pin/update the nightly used by CI. Miri is an interpreter and does not support every FFI
or platform API; it explores executed paths and a finite set of schedules/addresses.
Consider multiple seeds and cross-interpretation for code sensitive to interleavings,
endianness, or alignment. Its default isolation substitutes deterministic environment,
randomness, and clocks; this is useful for reproducibility but not a cryptographic-randomness
test. `-Zmiri-disable-isolation` is not a sandbox—never expose secrets to code merely
because it runs under Miri. A clean run is not a soundness proof.

### Sanitizers

Use Rust's sanitizer support conditionally for unsafe, FFI, allocation, and concurrent
code. Official support is nightly/unstable and target-specific; verify exact invocation,
runtime, target, and incompatibilities live. Keep sanitizer jobs separate from ordinary
stable/MSRV builds and ensure failures gate CI.

### Fuzzing

Use cargo-fuzz or another project-approved engine when attacker-shaped or highly varied
inputs reach parsers, codecs, protocol/state machines, unsafe wrappers, or native code.
Commit targets and small regression corpus inputs, bound CI smoke runs, and run longer
campaigns on a schedule. Treat every crash as a lead requiring minimization and root-cause
analysis; “no crashes” is not proof.

Avoid adding expensive tools merely for badge value. State which risk and code path each
job covers.

## CI design

Keep jobs purpose-specific so failures are diagnosable:

| Job | Typical contract |
| --- | --- |
| Format | rustfmt check only; no source mutation |
| Current stable check/lint | all intended workspace members/targets/features; warnings gate |
| Test | unit/integration/doctest and supported feature sets |
| MSRV | exact `rust-version`, selected compatible dependencies, promised features |
| Platforms/targets | compile and test target-specific code on supported runners |
| Docs | rustdoc warnings, doctests, docs.rs-like feature/target config |
| Unsafe analysis | Miri/sanitizer/fuzz coverage for named paths |
| Dependency/security | latest-resolution compatibility and RustSec/license/source policy |
| Package | `cargo package --locked` and archive/file-list verification |

Pin third-party CI actions/tools to reviewed immutable revisions where the platform
supports it, then update pins deliberately. Cache dependencies/build outputs for speed,
not as a substitute for lockfile or package verification. Never let a scheduled advisory
job be the only gate before a vulnerable dependency reaches a release.

## Common gotchas

- **`clippy::restriction` contains contradictions.** Cherry-pick; never enable the group.
- **`pedantic` expects exceptions.** A pile of contorted fixes is worse than narrow reasons.
- **`forbid` is irreversible below that scope.** Use it only when no exception is valid.
- **Workspace lints need member opt-in.** Root policy alone proves nothing.
- **`-D warnings` makes toolchain updates source events.** Pin/update intentionally.
- **All-features is not all configurations.** Minimal/default and incompatible sets differ.
- **MSRV and current lint toolchains may need separate jobs.** Do not weaken both to one.
- **Doctests are real tests.** `ignore` hides drift; prefer `no_run`, `compile_fail`, or
  hidden setup where accurate.
- **Doctests receive implicit allows.** Passing does not prove the snippet meets every
  project warning policy.
- **Miri and sanitizers are conditional tools.** Unsupported FFI or targets are Needs
  verification/Not applicable, not permission to claim safety.
- **Coverage percentages are not specifications.** Test boundaries, invariants, and
  failures that matter.

## Primary sources

- [Clippy usage and lint groups](https://doc.rust-lang.org/stable/clippy/usage.html)
- [Clippy configuration](https://doc.rust-lang.org/stable/clippy/configuration.html)
- [Cargo manifest lint tables](https://doc.rust-lang.org/cargo/reference/manifest.html#the-lints-section)
- [rustc lint levels](https://doc.rust-lang.org/stable/rustc/lints/levels.html)
- [Rust style editions](https://doc.rust-lang.org/stable/style-guide/editions.html)
- [rustfmt configuration](https://github.com/rust-lang/rustfmt#configuring-rustfmt)
- [rustdoc documentation tests](https://doc.rust-lang.org/rustdoc/write-documentation/documentation-tests.html)
- [`cargo test`](https://doc.rust-lang.org/cargo/commands/cargo-test.html)
- [Cargo continuous integration](https://doc.rust-lang.org/stable/cargo/guide/continuous-integration.html)
- [Miri](https://github.com/rust-lang/miri/)
- [Rust sanitizer documentation](https://doc.rust-lang.org/beta/unstable-book/compiler-flags/sanitizer.html)
- [Rust Fuzz Book](https://rust-fuzz.github.io/book/)

<!-- Original synthesis of primary Rust ecosystem guidance. See ../ATTRIBUTION.md. -->
