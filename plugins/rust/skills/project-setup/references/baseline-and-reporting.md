# Rust Baseline Selection and Reporting

Use this reference for every `project-setup` assessment and when deciding which setup
controls to implement. It defines applicability and evidence; domain references provide
the concrete recipes.

## Contents

- [Baseline backbone](#baseline-backbone)
- [Profile-driven applicability](#profile-driven-applicability)
- [Evidence rules](#evidence-rules)
- [State calibration](#state-calibration)
- [Priority calibration](#priority-calibration)
- [Common false positives](#common-false-positives)
- [Assessment template](#assessment-template)
- [Source and version policy](#source-and-version-policy)

## Baseline backbone

Use current primary documentation, adapted to the actual project:

| Source | Owns | Caution |
| --- | --- | --- |
| Rust Reference and standard library | Language, unsafe, ABI, layout, trait and library semantics | Stable guarantees are narrower than common folklore |
| Cargo Book/reference | Manifests, workspaces, features, resolver, MSRV, packaging, publishing | Behavior is version-sensitive; check the project's Cargo |
| rustc, Clippy, rustfmt, rustdoc docs | Lints, formatting, docs, tests and analysis workflow | Lint inventory and defaults change with toolchains |
| Rust API Guidelines | Idiomatic public-library API considerations | Recommendations, not mandates; some metadata examples are stale |
| crates.io/docs.rs/RustSec | Registry, docs builds, advisories and release tooling | Limits, providers and schemas change |

Never fabricate a lint, Cargo key, command flag, feature behavior, MSRV floor, target
guarantee, SemVer classification, or registry rule. Verify uncertain names against the
installed toolchain or current official docs.

## Profile-driven applicability

Start with package role and promises:

| Profile fact | Normally applicable controls |
| --- | --- |
| Public library | `rust-version`/MSRV policy, public docs/doctests, API Guidelines, SemVer/feature review, package dry run |
| Application/binary | deterministic lockfile, supported deployment targets, integration tests, release artifact/update policy |
| Workspace | explicit membership/default-members, resolver, shared package/dependency/lint policy, every member opting into inheritance |
| Safe-only crate | `unsafe_code = "forbid"` or an equally effective policy |
| Unsafe/FFI/native code | narrow unsafe modules, `unsafe_op_in_unsafe_fn`, `# Safety` contracts, `SAFETY:` reasons, Miri/sanitizers where executable, ABI/ownership/unwind review |
| Proc macro or `build.rs` | build-time execution/dependency scrutiny, host-vs-target correctness, deterministic inputs, `OUT_DIR`, precise rerun triggers |
| `no_std`/embedded/WASM | target matrix, feature gating, allocator/panic assumptions, docs.rs target, platform-specific tests |
| Async/concurrent code | cancellation/cleanup semantics, blocking boundaries, `Send`/`Sync` contracts, deadlock and race tests, Miri/loom-like checks where applicable |
| Publishable crate | complete metadata, intended package file list, registry-compatible dependencies, docs.rs, release auth/ownership, irreversible-publish awareness |
| Private helper/xtask/fuzz crate | `publish = false`; public docs and broad target support may be Not applicable |

Do not mark a domain Not applicable merely because relevant files sit outside the
requested diff. Read shared manifests, workspace roots, CI, and public callers first.

## Evidence rules

Accept as evidence:

- effective manifest values after workspace inheritance, including each member's
  `[lints] workspace = true` opt-in;
- exact lockfile, edition, resolver, `rust-version`, toolchain, targets, and feature
  combinations used by required CI jobs;
- commands that ran successfully on the relevant packages/targets/features and whose
  exit code gates CI;
- source-level visibility, public signatures/docs, lint exceptions, and local safety
  explanations;
- `cargo package --list`, the extracted package, clean package verification, and dry-run
  output for the exact publishable member;
- current official documentation for version-sensitive defaults.

Treat as leads, not proof:

- a `rust-toolchain.toml` without an MSRV job;
- `[workspace.lints]` without member opt-in;
- `cargo test` at a non-virtual workspace root without confirming selected members;
- `--all-features` without default/no-default or intentional mutually exclusive sets;
- a clean Clippy/Miri/audit run outside required CI or against only one target;
- `#![forbid(unsafe_code)]` in one crate while build scripts, proc macros, dependencies, or
  other workspace members execute code outside that policy;
- `.gitignore` or an `include` list without inspecting the package archive;
- types compiling as `Send`/`Sync` without confirming that unsafe implementations and
  semantic thread-safety promises are correct.

For every Met or Gap, cite `file:line` plus the effective behavior. For Needs
verification, name the missing fact and a safe command or inspection that would resolve
it.

## State calibration

| Observation | State |
| --- | --- |
| Applicable policy is effective for every intended member/target/feature and evidenced | **Met** |
| Applicable policy is absent, disabled, bypassed, or materially incomplete | **Gap** |
| Surface is absent by project design and the reason is documented | **Not applicable** |
| A concrete external, runtime, registry, target, or CI fact cannot be established | **Needs verification** |

Partial coverage is normally Gap when the omitted part matters. Describe what is covered:
“default features lint clean; no-default configuration is not compiled,” rather than
calling the whole lint domain absent.

## Priority calibration

Use **Essential** for foundational contracts and high-impact release mistakes, such as:

- a crate intended to remain private but still publishable;
- package contents that include credentials or omit required build inputs;
- promised MSRV/targets/features that required CI never builds;
- broad or public unsafe code with no stated safety contracts or containment;
- a safe public API whose documented invariant depends on unchecked caller behavior;
- a publish workflow relying on an exposed or broadly scoped long-lived token.

Use **Recommended** for controls with clear ongoing value:

- inherited workspace lints, stable formatting, strict gated warnings;
- default/no-default/important-feature testing and doctests;
- narrow error types, visibility, module/API boundaries, and documented panics/errors;
- Miri for executable unsafe paths and current RustSec auditing;
- package/archive inspection, dry runs, changelog/tag discipline, docs.rs configuration.

Use **Optional** for context-dependent maturity:

- exhaustive feature powersets, broad target matrices, fuzzing or sanitizers where the
  risk and execution model justify their cost;
- extra curated pedantic/restriction lints;
- deeper dependency/license/source policy and release automation.

Priority never proves a defect or vulnerability.

## Common false positives

- **No `#![forbid(unsafe_code)]` is not automatically a gap.** A crate may need audited
  unsafe or FFI; assess its actual policy and containment.
- **An `unsafe` block is not automatically unsound.** Missing contracts are a reviewability
  gap; unsoundness needs a violated invariant and reachable operation.
- **An `unwrap` is not automatically unidiomatic.** Tests, examples, initialization, and
  statically proven invariants differ from recoverable input paths. Prefer an `expect`
  message explaining why an invariant should hold when it improves diagnosis.
- **A `clone` is not automatically wasteful.** It may be the clearest ownership boundary;
  prove avoidable cost or confusion before demanding lifetime complexity.
- **`Arc<Mutex<T>>` is not automatically good design or a defect.** Establish ownership,
  contention, poisoning, blocking, and async-runtime behavior.
- **More generics are not automatically more idiomatic.** They can complicate signatures,
  compile time, code size, and public compatibility.
- **`cargo clippy --all-features` is not full feature coverage.** Minimal and incompatible
  combinations need their own model.
- **A committed `Cargo.lock` is not a library mistake.** Current Cargo defaults to tracking
  it; decide from project needs and separately test latest compatible dependencies.
- **A clean Miri run is not proof of soundness.** It covers executed paths and supported
  operations only.
- **A clean dependency audit is not proof that dependencies are benign.** Advisories are
  one input; build scripts and proc macros execute during builds.

## Assessment template

```markdown
## Rust Project Baseline Review: <scope>

**Mode:** Assess
**Profile:** <library/binary/workspace; targets; MSRV/edition; features; unsafe; publish>
**Baseline:** Current official Rust/Cargo guidance adapted to <constraints>
**Assumptions:** <unresolved facts>

### Coverage Summary
| Domain | Met | Gap | Needs verification | Not applicable |
| --- | ---: | ---: | ---: | ---: |
| Project/workspace/toolchain | | | | |
| Linting/formatting | | | | |
| Testing/CI/analysis | | | | |
| Idiomatic API/safety/docs | | | | |
| Packaging/publishing/release | | | | |

### Essential Gaps
#### [RUST-001] <control> — Gap
- **Applicability:** <profile fact>
- **Evidence:** `<path>:<line>` and effective behavior
- **Recommendation:** <minimal concrete change>
- **Tradeoffs:** <MSRV/API/target/compile-time/operations>
- **Source:** <primary link>

### Recommended Gaps
### Optional Improvements
### Needs Verification
### Controls Already Met
### Not Applicable
### Remediation Roadmap
1. Now — foundational contracts and low-risk gates.
2. Next — maintainability, feature/target coverage, and package readiness.
3. Later — optional analysis and release maturity.
```

If no gaps remain, say all **examined applicable controls** were Met. Never say the
project is “sound,” “secure,” or “fully idiomatic” based only on this baseline.

## Source and version policy

When online, verify at least:

- current stable edition/resolver behavior and the project's installed Cargo/MSRV;
- current rustc/Clippy lint names, groups, defaults, and MSRV;
- current package/archive behavior, registry limits, trusted-publishing providers, and
  docs.rs constraints;
- current Miri/sanitizer/fuzz support for the target and toolchain;
- active RustSec advisories and the installed audit-tool behavior.

When offline, identify which facts were not re-verified. Do not copy a “strict Rust
template” without reconciling it with the actual MSRV, feature model, target matrix, and
package roles.

## Primary sources

- [Cargo reference](https://doc.rust-lang.org/cargo/reference/)
- [Clippy documentation](https://doc.rust-lang.org/stable/clippy/)
- [Rust Reference: unsafety](https://doc.rust-lang.org/stable/reference/unsafety.html)
- [Rust API Guidelines](https://rust-lang.github.io/api-guidelines/)
- [RustSec Advisory Database](https://rustsec.org/)

<!-- Original synthesis of primary Rust ecosystem guidance. See ../ATTRIBUTION.md. -->
