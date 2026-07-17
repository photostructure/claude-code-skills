# Rust Packaging, Publishing, and Release Hygiene

Use this reference for crates that may be distributed through crates.io or another Cargo
registry. Packaging inspection and publish dry runs are safe preparation; a real publish,
registry owner change, tag, push, or hosted release requires explicit authorization.

## Contents

- [TL;DR](#tldr)
- [Decide what is publishable](#decide-what-is-publishable)
- [Complete package metadata](#complete-package-metadata)
- [Control and inspect package contents](#control-and-inspect-package-contents)
- [Review compatibility before release](#review-compatibility-before-release)
- [Build useful documentation](#build-useful-documentation)
- [Run the dry-run release gate](#run-the-dry-run-release-gate)
- [Choose authentication and ownership](#choose-authentication-and-ownership)
- [Review dependencies and build-time execution](#review-dependencies-and-build-time-execution)
- [Common gotchas](#common-gotchas)
- [Primary sources](#primary-sources)

## TL;DR

1. Put `publish = false` on every internal crate; use a registry allowlist when a crate may
   publish only to named registries.
2. Treat the packaged archive—not the Git checkout—as the release input. List it, inspect
   it for secrets and omissions, build it, and run a publish dry run.
3. Review public API, default features, MSRV, supported targets, and dependency requirements
   for SemVer impact before changing the version.
4. Prefer short-lived, narrowly scoped, identity-based trusted publishing where crates.io
   and the CI provider currently support it. Protect the first release and owner list.
5. Never turn release preparation into `cargo publish` by implication. Publication is
   effectively permanent; yanking does not delete a release.

## Decide what is publishable

Inventory every workspace member and make intent explicit:

```toml
[package]
name = "internal-release-tool"
publish = false
```

For a crate restricted to selected registries, Cargo accepts a registry-name allowlist:

```toml
[package]
publish = ["crates-io"]
```

Verify syntax and registry names with the project's Cargo version. Do not treat a private
repository, undocumented crate, workspace location, or absent release workflow as a
publication control. A package is publishable unless the effective manifest prevents it.

Classify examples, benchmarks, fixtures, fuzz targets, xtasks, generated crates, and native
helpers too. Internal crates can still be unintentionally packaged as path dependencies or
workspace members.

## Complete package metadata

For a public crate, verify at least:

- a unique package name and intentional version;
- license expression and/or packaged `license-file`, matching the actual terms;
- concise description, repository, README, and useful documentation/homepage links;
- appropriate categories and keywords within the registry's **current** limits;
- edition and declared `rust-version`/MSRV policy;
- authors/maintainers only when the project intentionally wants that metadata—do not copy
  old templates mechanically;
- feature and platform documentation, especially default features and native prerequisites.

Cargo metadata keys and crates.io constraints evolve. Verify live rather than copying an
old “perfect manifest.” The Rust API Guidelines are helpful design prompts, but older
metadata examples do not override current Cargo behavior.

Use SPDX expressions accurately. Do not claim `MIT OR Apache-2.0`, for example, unless the
repository actually grants both choices and packages the required notices/licenses.

## Control and inspect package contents

`cargo package` builds a source archive from selected files, rewrites parts of the
manifest, and verifies the packaged crate. Make the archive self-contained:

- include source, manifests, README/license/notice files, generated inputs required to
  build, and any vendored/native data whose license permits distribution;
- exclude credentials, environment files, signing material, private fixtures, local build
  output, large irrelevant assets, and repository-only tooling;
- ensure `build.rs`, proc macros, `include_str!`/`include_bytes!`, tests needed for package
  verification, and generated source references still work outside the checkout;
- give every non-development path dependency a registry `version`; Cargo removes/ignores
  the local `path` when publishing, so that version must resolve from the registry (a
  `publish = false` helper is not bundled merely because it is local);
- inspect the normalized `Cargo.toml` inside the package when workspace inheritance,
  targets, examples, or unusual dependency tables matter.

Cargo omits workspace-only `[patch]`, `[replace]`, and `[workspace]` tables from the
normalized manifest. It includes a minimized `Cargo.lock` by default, may add best-effort
`.cargo_vcs_info.json`, and flattens symlinks into archive content. Do not use
`--exclude-lockfile` as a routine library convention: Cargo documents it as exceptional,
and locked installation workflows expect the packaged lockfile. Treat VCS metadata as a
hint, not verified provenance.

Use `include` for a deliberately small allowlist or `exclude` for focused omissions; they
are mutually exclusive. Once `include` is present, do not assume Git ignore rules still
select files the same way. Global Git ignore rules and untracked state can also surprise
package selection. The only reliable answer is the actual package list/archive.

`cargo package --list` is a good first view, not a secret scanner. Check suspicious names
and inspect content where appropriate. If a secret ever entered Git history or an archive,
remove it from the package **and rotate it**; deletion alone does not revoke it.

## Review compatibility before release

Classify the release against Cargo's current SemVer compatibility guidance and the
project's documented policy. Review more than function signatures:

- public items, fields, enum variants, traits, implementations, bounds, auto traits, and
  macro behavior;
- public dependency types and re-exports;
- feature names, default features, optional dependency exposure, and supported feature
  combinations;
- MSRV/edition, platforms/targets, native-library requirements, panic/error behavior, and
  documented invariants;
- serialized formats, CLI/config/file protocols, database schemas, and network contracts
  governed outside Rust's type system.

Adding an item is not universally non-breaking. New enum variants, public fields, trait
items/implementations, inherent methods, or blanket impls can break exhaustive matches,
construction, method resolution, coherence, or downstream implementations. Evaluate the
actual public surface and downstream use.

An MSRV increase may be treated differently by ecosystem policies, but it still breaks
users on the former floor. State the policy, test it, and communicate changes explicitly.
Do not let an automatic version bump make the compatibility decision for you.

For current Cargo versions supporting multi-package publish (stabilized in Cargo 1.90),
prefer `--workspace` or repeated `--package` selections for interdependent workspace
crates. Cargo plans dependency order and waits for registry visibility before publishing
dependents. This is still **not atomic**: an error can leave a partially published set.
Update inter-crate requirements deliberately, inspect the plan/dry run, and keep a recovery
plan. For older Cargo, compute and dry-run the sequence explicitly.

## Build useful documentation

Before publishing a library:

- build rustdoc with the package's supported/default feature policy and fail on applicable
  warnings;
- run doctests and ensure examples compile from the public API, not repository internals;
- document crate purpose, quick start, features, MSRV, platforms, errors, panics, and every
  public unsafe contract;
- check intra-doc links and intentionally hidden/private items;
- configure `[package.metadata.docs.rs]` only for real target/feature/build needs.

docs.rs has finite resources and its own current build environment. Avoid selecting
`all-features` when features conflict, pulling large native toolchains needlessly, or
assuming docs.rs proves every supported target builds. Verify current docs.rs metadata and
limits from its documentation.

## Run the dry-run release gate

Adapt package names, features, targets, MSRV, and registry. A typical gate is:

1. Start from a clean, reviewed commit. Confirm the intended changelog/version/license and
   that generated files are current.
2. Run the project's required format, lint, test, doctest, feature, target, MSRV, audit,
   and documentation matrix.
3. Review the exact file list:

   ```console
   cargo package --list --package example
   ```

4. Inspect the list/content for secrets, private data, missing licenses/readmes, and omitted
   build inputs.
5. Build and verify the package without silently changing dependency resolution:

   ```console
   cargo package --locked --package example
   ```

6. Inspect the generated archive and normalized manifest under `target/package/`. Where
   feasible, extract it to a clean temporary location and test the package as a consumer.
7. Exercise the registry checks without uploading:

   ```console
   cargo publish --dry-run --locked --package example
   ```

   For a supported interdependent workspace release, dry-run the same selection intended
   for release, for example `cargo package --workspace --locked` followed by
   `cargo publish --workspace --dry-run --locked` (or repeated `--package` selections).

8. Stop and report the dry-run result. Run the real `cargo publish` only when the user has
   explicitly authorized this crate, version, registry, and release operation.
9. After an authorized publish, verify registry metadata, install/use paths, docs.rs status,
   and release records; create/push tags or hosted releases only within the same explicit
   authority.

If Cargo times out while waiting for the registry index, the upload status is uncertain;
check the registry/index before retrying so an eventual success is not mistaken for a
failed upload.

Do not use `--allow-dirty` to normalize an unexplained working tree or `--no-verify` to
bypass package verification. If a legitimate release process needs either, document the
specific reason and independently reproduce the omitted check.

## Choose authentication and ownership

Prefer crates.io trusted publishing when its **current** supported CI/provider model fits
the project. It exchanges workload identity for short-lived publication credentials and
avoids storing a long-lived crates.io token in ordinary CI. Bind the configuration as
narrowly as supported to repository, workflow, environment, and crate.

Trusted publishing still needs operational design:

- follow the current crates.io bootstrap rules for a crate's first release;
- protect the release workflow/environment and the branches/tags that can invoke it;
- pin/review third-party release actions and minimize workflow permissions;
- require human approval where release risk warrants it;
- keep a documented, tested recovery path for provider or registry outages.

If a token is required, use Cargo's supported credential-provider mechanism, minimum
scope, protected secrets, non-logging commands, rotation, and revocation procedures. Do
not put tokens in manifests, repository files, command lines captured by logs, or broad
developer bootstrap scripts.

Review the crates.io owner/team list periodically. Maintain at least enough trusted
maintainers to recover from account loss without granting broad unused access. Require
strong account authentication and remove departed owners promptly. Adding/removing owners
is an external security-sensitive mutation requiring explicit authorization.

## Review dependencies and build-time execution

- Run a current RustSec advisory check against the dependency resolution used for release.
  `cargo-audit` is the RustSec-supported Cargo client.
- Treat allow/ignore entries as expiring decisions with a reason and compensating action;
  a clean advisory scan is not proof that dependencies are safe or maintained.
- Review new/changed direct dependencies for necessity, maintenance, licenses, source, and
  feature footprint. Use a policy tool such as the third-party `cargo-deny` only when its
  license/source/duplicate/advisory policy matches the project.
- Remember that build scripts and proc macros execute during builds. Audit the relevant
  dependency change and protect CI/release credentials from untrusted build execution.
- Review lockfile updates as code/dependency changes. For libraries, test both the locked
  project resolution and a deliberate newest-compatible consumer resolution.

Package verification is not a complete reproducible-build or provenance system. If the
project signs artifacts, publishes SBOMs/attestations, or promises reproducibility, define
those as separate verified release controls.

## Common gotchas

- **Publishing is effectively irreversible.** crates.io versions cannot be overwritten or
  deleted through the normal workflow; yanking only discourages new resolution.
- **The package is not the checkout.** Ignored files, workspace inheritance, generated
  content, path dependencies, and rewritten manifests can change what consumers receive.
- **Non-development path dependencies need registry versions.** A local unpublished helper
  is not embedded in the dependent crate.
- **Workspace publication is not atomic.** Cargo can order and wait for dependencies, but
  an interrupted run can still publish only part of the selected set.
- **`publish = false` is per package.** Setting it on one workspace member does not protect
  its siblings.
- **A dry run is not authorization.** It is a local/registry validation step, not consent
  to upload, tag, push, modify owners, or create a hosted release.
- **`--all-features` may be invalid.** Mutually exclusive features need an explicit matrix;
  do not weaken the release gate to a combination users cannot select.
- **docs.rs success is not target coverage.** Its environment and selected features are one
  documentation build.
- **An advisory database has coverage limits.** Scan results do not assess unpublished
  weaknesses, malicious code, build scripts, proc macros, or application misuse.
- **Automation moves trust.** Trusted publishing removes a stored registry token but makes
  workflow integrity, identity binding, action pinning, and environment protection central.

## Primary sources

- [Cargo manifest format](https://doc.rust-lang.org/cargo/reference/manifest.html)
- [Cargo packaging and publishing](https://doc.rust-lang.org/cargo/reference/publishing.html)
- [Cargo package selection](https://doc.rust-lang.org/cargo/commands/cargo-package.html)
- [Cargo SemVer compatibility](https://doc.rust-lang.org/cargo/reference/semver.html)
- [Cargo registries and authentication](https://doc.rust-lang.org/cargo/reference/registries.html)
- [crates.io publishing guide](https://doc.rust-lang.org/cargo/reference/publishing.html)
- [docs.rs metadata](https://docs.rs/about/metadata)
- [crates.io trusted publishing announcement](https://blog.rust-lang.org/2025/07/11/crates-io-development-update-2025-07/)
- [RustSec advisory database and tools](https://rustsec.org/)
- [cargo-deny documentation](https://embarkstudios.github.io/cargo-deny/)
