# Attribution and source notes

This skill is an original synthesis licensed under the repository's
[MIT License](../../../../LICENSE). It is not affiliated with or endorsed by the Rust
Project, Rust Foundation, crates.io, docs.rs, RustSec, or the maintainers of the optional
tools it mentions.

The guidance was researched primarily from:

- the Rust Reference, standard-library documentation, Rust Book, Edition Guide, and the
  rustc, rustdoc, rustfmt, Cargo, Clippy, and Rustup books/documentation;
- official crates.io and docs.rs documentation and Rust Project announcements;
- the Rust API Guidelines, used as recommendations rather than a current Cargo contract;
- RustSec and upstream Miri/cargo-fuzz documentation;
- cargo-deny documentation from Embark Studios when discussing that optional third-party
  policy tool.

Rust and Cargo sources are generally offered under the Rust project's dual MIT/Apache-2.0
terms; each linked upstream source retains its own license and trademarks. This skill does
not intentionally reproduce substantial upstream prose or code. Its configuration and code
snippets are original, illustrative examples that must be adapted to the project's Cargo
version, MSRV, targets, and policies.

Some older Rust API Guidelines metadata examples no longer reflect current Cargo practice
(for example, Cargo has deprecated the `authors` field). Current official Cargo and registry
documentation takes precedence where guidance differs.
