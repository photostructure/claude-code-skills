# Rust Project, Workspace, and Toolchain

Use this reference to create or assess `Cargo.toml`, workspace topology, toolchain/MSRV
policy, features, lockfiles, build scripts, and target support.

## Contents

- [TL;DR](#tldr)
- [Profile every package](#profile-every-package)
- [Manifest and workspace baseline](#manifest-and-workspace-baseline)
- [Cargo configuration and invocation directory](#cargo-configuration-and-invocation-directory)
- [Edition, resolver, MSRV, and toolchain](#edition-resolver-msrv-and-toolchain)
- [Lockfiles and dependency resolution](#lockfiles-and-dependency-resolution)
- [Features and optional dependencies](#features-and-optional-dependencies)
- [Package and module layout](#package-and-module-layout)
- [Build scripts, proc macros, and native code](#build-scripts-proc-macros-and-native-code)
- [Profiles and target configuration](#profiles-and-target-configuration)
- [Common gotchas](#common-gotchas)
- [Primary sources](#primary-sources)

## TL;DR

1. Give every package one clear role and set `publish = false` on internal helpers.
2. Declare edition and `rust-version`; test the MSRV instead of inferring it from a
   contributor toolchain.
3. In workspaces, centralize shared package/dependency/lint policy and verify every member
   opts in. Virtual workspaces need an explicit resolver.
4. Keep features additive and test default, no-default, all-features when valid, and the
   important combinations users actually select.
5. Track `Cargo.lock` when it helps deterministic development/CI; separately verify the
   newest dependency resolution that consumers may receive.
6. Treat `build.rs`, proc macros, and native build dependencies as build-time code
   execution. Keep them deterministic, target-correct, and minimal.
7. Resolve effective Cargo configuration from the directory where Cargo is invoked; a
   member-local `.cargo/config.toml` is not loaded by a command run at the workspace root.

## Profile every package

Inventory all workspace members and implicit packages, including excluded paths:

| Role | Questions |
| --- | --- |
| Public library | What is the public API, MSRV, feature and platform promise? Is it published? |
| Binary/application | What exact dependency snapshot and deployment targets ship? Does `cargo install --locked` matter? |
| Proc macro | What code executes in downstream builds? What syntax/span/hygiene contract is public? |
| `build.rs` / `*-sys` | What host code executes, what target/native library is built or discovered, and what licenses/tools are required? |
| `no_std`/embedded/WASM | Which allocators, panic handlers, targets and features are required? |
| Example/test/benchmark | Is it part of public documentation or only repository validation? |
| xtask/fuzz/internal tool | Is `publish = false` explicit? Does it need the workspace MSRV or a different contributor toolchain? |

One repository may legitimately contain packages with different release and MSRV policies.
Do not force a workspace-wide value where roles differ; document the exception.

## Manifest and workspace baseline

For a multi-package repository, prefer inheriting genuinely shared values. This is an
illustrative current-style shape, not a version-independent template:

```toml
[workspace]
members = ["crates/*"]
resolver = "3" # verify against edition and MSRV; required explicitly for virtual workspaces

[workspace.package]
edition = "2024"
rust-version = "1.xx"
license = "MIT OR Apache-2.0"
repository = "https://example.invalid/owner/project"

[workspace.dependencies]
serde = { version = "1", default-features = false }

[workspace.lints.rust]
unsafe_op_in_unsafe_fn = "deny"

[workspace.lints.clippy]
all = { level = "warn", priority = -1 }
```

Each member explicitly opts in:

```toml
[package]
name = "example"
version = "0.1.0"
edition.workspace = true
rust-version.workspace = true
license.workspace = true
repository.workspace = true

[dependencies]
serde.workspace = true

[lints]
workspace = true
```

Check current Cargo support before recommending this to an older MSRV. Workspace
inheritance is opt-in per field. `[workspace.lints]` does nothing for a member unless it
declares `[lints] workspace = true`.

Other workspace facts that surprise maintainers:

- all members share the root `Cargo.lock` and target directory;
- `[patch]`, `[replace]`, and profile tables are read only from the workspace root;
- default command selection differs between virtual and non-virtual workspaces and can be
  changed with `default-members`;
- a member's edition does not choose the resolver for a virtual workspace;
- broad globs can accidentally enroll generated, fuzz, vendor, or fixture packages.

Workspace dependency inheritance is deliberately limited. A member using
`dependency.workspace = true` may add only `optional` and `features`; it cannot replace
the shared version or `default-features` policy. Feature lists from the workspace and
member are additive, and disabling default features on one dependency edge does not
disable them when another edge enables them.

Keep package names, paths, and roles discoverable. Use `exclude` for nested packages that
must not join the parent workspace, and verify what `cargo metadata` actually selects.

## Cargo configuration and invocation directory

Cargo discovers `.cargo/config.toml` from its invocation directory and then searches
parent directories. When invoked from a workspace root, it does not read configuration
inside a member crate. Record where contributor, editor, CI, release, and nested-tool
commands start, then inspect their effective linker, runner, target, `rustflags`, registry,
network, alias, and credential-provider settings.

Prefer a root configuration for genuinely shared workspace behavior. Keep machine-local
settings out of the repository, and avoid requiring contributors to enter a member
directory merely to activate hidden build policy. A checked-in config file is evidence of
intent, not proof that every invocation sees it; compare the actual command environment
when local, CI, cross-target, and release builds disagree.

## Edition, resolver, MSRV, and toolchain

These are separate decisions:

| Setting | Contract |
| --- | --- |
| `edition` | Language/module/migration behavior for one package |
| workspace `resolver` | Dependency feature and Rust-version resolution for the top-level build |
| `package.rust-version` | Minimum supported Rust toolchain promised to consumers |
| `rust-toolchain.toml` | Toolchain/components/targets used by contributors and ordinary CI |

For new projects, select the latest stable edition supported by the intended MSRV; verify
the current edition/resolver mapping live. Do not upgrade edition merely for aesthetics:
run the edition migration, review automated changes, and test behavior and macros.

Declare `rust-version` when the project promises an MSRV. A credible policy answers:

- which packages/features/targets the MSRV covers;
- how CI tests it;
- how and when it may be raised;
- whether an MSRV increase is communicated as potentially incompatible;
- how dependencies are constrained or resolved compatibly.

Use `rust-toolchain.toml` when reproducible contributor components/targets or a pinned
nightly matter:

```toml
[toolchain]
channel = "stable" # use an exact release/date when reproducibility or nightly requires it
profile = "minimal"
components = ["clippy", "rustfmt"]
targets = ["wasm32-unknown-unknown"]
```

A stable channel follows new releases and new lints. An exact stable version improves
reproducibility but needs automated updates. Pin nightly by date when nightly-only tools or
features are required. Test the declared MSRV in a separate job even if contributors use a
newer pinned toolchain.

With resolver version 3, Cargo's default Rust-version-aware selection prefers dependencies
compatible with the relevant package `rust-version`; it is a fallback heuristic, not an
MSRV enforcement guarantee. Cargo may select an incompatible version when no compatible
match is available. In mixed-MSRV workspaces, one member's version requirements can also
affect the shared resolution. The exact MSRV build/test job remains authoritative.

## Lockfiles and dependency resolution

Current Cargo defaults to tracking `Cargo.lock`; the historical blanket rule that
libraries must ignore it is stale. Decide from project needs:

- applications and binaries normally track it for deterministic builds;
- libraries benefit from reproducible CI, bisects, MSRV verification, and contributor
  consistency;
- consumers of a library resolve from its `Cargo.toml`, not the repository lockfile;
- published binaries may tell users to use `cargo install --locked` when the packaged
  lockfile represents the supported dependency set.

A lockfile can hide future consumer breakage. Pair ordinary locked CI with an intentional
job that resolves the newest compatible dependencies. Do not casually run `cargo update`
inside an unrelated change; lockfile updates are reviewable dependency changes.

Use `--locked` for deterministic CI and release preparation. Use `--frozen` only when both
the lockfile and network-offline constraint are intended; it is not a generic synonym for
“safe.”

Avoid exact `=` requirements for libraries unless a concrete incompatibility requires one;
overly narrow requirements can make the wider dependency graph unsatisfiable. Never use a
wildcard as a claim of compatibility with every future release.

A workspace-level `[patch]` can cause Cargo to load manifests beyond the package being
tested. Keep every manifest needed by the patched resolution parseable on the promised
oldest compiler, or document and test the narrower support boundary explicitly.

## Features and optional dependencies

Treat feature names and defaults as public API for published crates.

- Make features additive: enabling one should add capability, not disable or replace
  behavior selected by another feature.
- Prefer capability names (`serde`, `tls`, `simd`) over internal architecture or vague
  placeholders.
- Use `dep:name` to keep an optional dependency from automatically becoming an accidental
  feature name when the project's Cargo/MSRV supports it.
- Keep default features small and unsurprising. Removing a feature from `default` or making
  it gate existing API can be breaking.
- Avoid mutually exclusive features where possible. If unavoidable, emit a clear compile
  error and test each supported selection separately; `--all-features` cannot represent a
  valid build.
- Remember feature unification: dependency features enabled anywhere in the graph may be
  active together. Never use a feature to remove a public item or weaken a safety invariant.
- Document feature effects, platform prerequisites, and SemVer expectations.

Test at least the default set, `--no-default-features`, `--all-features` when valid, and
important supported combinations. An exhaustive powerset grows exponentially; select it
only when the feature count and risk justify the cost.

Use Cargo's graph view to explain unexpected activation instead of guessing:

```text
cargo tree -e features
cargo tree -f "{p} {f}"
cargo tree -e features -i dependency-name
```

For public dependency types or suspicious duplicate versions, also inspect
`cargo tree --duplicates`; duplicate versions are not automatically defects, but can
produce incompatible nominal types or excess build/runtime cost.

## Package and module layout

Prefer structure that communicates ownership and stability:

- keep one obvious library entry point and thin binary entry points;
- separate domain logic from I/O, runtime/framework adapters, CLI parsing, and persistence;
- use private modules and `pub(crate)` until an API must be public;
- avoid a generic `utils` dumping ground; name modules after cohesive responsibilities;
- keep examples copyable and representative of the public API;
- use integration tests for externally observable package behavior and unit tests for
  private invariants;
- avoid creating a crate per module—crate boundaries add dependency, feature, compile-time,
  visibility, and release coordination costs;
- split crates when there is a real reuse, dependency isolation, target, compile-time, or
  release-policy boundary.

For workspace libraries, avoid exposing dependency types in public signatures unless that
dependency is intentionally part of the compatibility contract.

## Build scripts, proc macros, and native code

`build.rs` and procedural macros execute during builds. Safe Rust in the runtime crate
does not constrain their filesystem, process, or network effects.

For build scripts:

- write generated output only under `OUT_DIR`; do not mutate checked-in source;
- emit precise `rerun-if-changed` and `rerun-if-env-changed` instructions;
- do not assume `OUT_DIR` starts empty;
- avoid network access and nondeterministic inputs;
- use Cargo's `TARGET`/`CARGO_CFG_*` inputs for the compilation target—`cfg!` in the build
  script describes the host executing the script;
- register custom cfg names with `rustc-check-cfg` where supported;
- declare `links` for native libraries so Cargo can prevent duplicate native linkage and
  pass metadata to immediate dependents;
- document system-vs-bundled native code, required tools, supported cross targets, and
  licenses.

Generate checked-in sources with a maintenance command or xtask, then have CI compare the
result. Do not regenerate them opportunistically in `build.rs`.

For proc macros, minimize dependencies and global state, preserve spans/hygiene where
appropriate, produce actionable compile errors, and test accepted and rejected syntax.
Their input/output API and diagnostics are maintainability surfaces even though they run
at compile time.

## Profiles and target configuration

Cargo's defaults are often appropriate. Add profile settings only for measured product
needs and keep root-only workspace behavior in mind.

- Do not prescribe `panic = "abort"`, LTO, one codegen unit, stripped symbols, or maximum
  optimization universally; each changes debugging, build time, binary size, performance,
  or unwind behavior.
- Keep release debug information when operations/crash diagnosis needs it.
- Test the profile that ships; debug-only success does not prove release behavior.
- Put target-specific dependencies under the narrow correct `cfg` table and compile them
  on required targets.
- For cross-compilation, separate host tools/build dependencies from target artifacts.
- Avoid repository-wide `RUSTFLAGS` that silently change dependent crates or make editor,
  CI, docs.rs, and release builds disagree.

## Common gotchas

- **Newest edition is not the same as newest compiler support.** Reconcile edition,
  resolver, and MSRV.
- **A toolchain file is not an MSRV declaration.** It controls local selection.
- **Virtual workspaces need an explicit resolver.** Member editions do not supply it.
- **Workspace policy is not inherited automatically.** Check each opted-in field/member.
- **Cargo config follows the invocation directory.** Root commands skip member-local
  `.cargo/config.toml` files.
- **Resolver 3 prefers compatible dependencies; it does not prove MSRV.** Test the floor.
- **Dependency features are additive across edges.** One `default-features = false` cannot
  cancel another edge that enables defaults.
- **The lockfile proves only one resolution.** Test newest allowed dependencies separately.
- **All-features can be invalid or insufficient.** It misses minimal and mutually exclusive
  configurations.
- **Build scripts inspect the host by default.** Cross-target decisions need Cargo target
  variables.
- **Safe source can execute powerful build dependencies.** Review proc macros/build scripts
  and their dependencies as build-time code.
- **Public dependency types leak compatibility.** A minor dependency change can become a
  major public API change.
- **Over-splitting crates increases maintenance.** Use real boundaries, not directory size.

## Primary sources

- [Cargo manifest format](https://doc.rust-lang.org/cargo/reference/manifest.html)
- [Cargo workspaces](https://doc.rust-lang.org/cargo/reference/workspaces.html)
- [Cargo configuration](https://doc.rust-lang.org/cargo/reference/config.html)
- [Cargo Rust version](https://doc.rust-lang.org/stable/cargo/reference/rust-version.html)
- [Cargo features](https://doc.rust-lang.org/stable/cargo/reference/features.html)
- [Cargo resolver](https://doc.rust-lang.org/cargo/reference/resolver.html)
- [Cargo lockfile FAQ](https://doc.rust-lang.org/cargo/faq.html#why-have-cargolock-in-version-control)
- [Cargo build scripts](https://doc.rust-lang.org/cargo/reference/build-scripts.html)
- [Rust procedural macros](https://doc.rust-lang.org/reference/procedural-macros.html)
- [rustup toolchain files](https://rust-lang.github.io/rustup/overrides.html#the-toolchain-file)

<!-- Original synthesis of primary Rust ecosystem guidance. See ../ATTRIBUTION.md. -->
