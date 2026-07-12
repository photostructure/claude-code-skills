# Attribution

`project-setup` is an original synthesis of build-hardening, analysis-tooling, and
maintainable-code guidance for cross-platform modern C++ (C++17) and Node.js native
addons. It is not affiliated with or endorsed by the organizations listed below.

## Adapted sources

| Source | License | Use in this skill |
| --- | --- | --- |
| [OpenSSF Compiler Options Hardening Guide for C and C++](https://best.openssf.org/Compiler-Hardening-Guides/Compiler-Options-Hardening-Guide-for-C-and-C++.html) | CC BY 4.0 | The compiler/linker hardening flag baseline, minimum-toolchain notes, and sanitizer-compatibility rules. |
| [cppreference](https://en.cppreference.com/) | CC BY-SA 3.0 / GFDL | Standard-library and language semantics behind the conventions. |
| [SEI CERT C and C++ Coding Standards](https://cmu-sei.github.io/secure-coding-standards/) | CC BY 4.0 standards prose; MIT code examples | Secure-coding rule identifiers and framing for the conventions and analysis checks. No SEI code example is intentionally reproduced. |

The [C++ Core Guidelines](https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines)
were consulted for RAII, ownership, rule-of-five, and exception-safety design guidance.
They use a [custom license](https://github.com/isocpp/CppCoreGuidelines/blob/master/LICENSE),
not MIT. The Guidelines and their license are not relicensed as part of this skill; the
examples and explanations here are independently written.

### SEI supplied notice

© 2026 Carnegie Mellon University. The CERT® secure coding standards project is based
upon work funded and supported by the Department of War under Air Force Contract Nos.
FA8702-15-D-0002 and FA870225DB003 with Carnegie Mellon University for operation of the
Software Engineering Institute, a federally funded research and development center. The
views, opinions, and findings are those of the authors and should not be construed as an
official Government position, policy, or decision unless designated by other
documentation. Carnegie Mellon and CERT are registered trademarks of Carnegie Mellon
University. DM26-0304.

The SEI CERT standards prose is licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), and its code examples under
the [MIT License](https://opensource.org/license/mit). Material used here was modified,
narrowed, and reorganized for this skill.

## Consulted primary sources

Cited next to the relevant reference sections; used to verify factual and version-sensitive
behavior, with original surrounding expression:

- Compiler/linker vendor docs — [GCC](https://gcc.gnu.org/onlinedocs/gcc/),
  [Clang/LLVM](https://clang.llvm.org/docs/), and
  [Microsoft Learn (MSVC)](https://learn.microsoft.com/en-us/cpp/build/reference/) — for
  exact flag behavior, architecture applicability, and the flags that hard-error if
  mis-applied.
- [node-gyp](https://github.com/nodejs/node-gyp),
  [Node.js Node-API / C++ addons](https://nodejs.org/api/n-api.html),
  [node-addon-api](https://github.com/nodejs/node-addon-api), and
  [prebuildify](https://github.com/prebuild/prebuildify) / node-gyp-build for the addon
  toolchain, ABI stability, and prebuild/CI model.
- [AddressSanitizer / clang-tidy](https://clang.llvm.org/docs/) and the
  [Valgrind manual](https://valgrind.org/docs/manual/) for analysis wiring, and
  [SQLite compile-time options](https://www.sqlite.org/compile.html) (public domain) for
  the vendored-source hardening example.

The material was narrowed to cross-platform node-gyp/modern-C++ projects, rewritten, and
reorganized into an applicability-aware assessment (Met / Gap / Not applicable / Needs
verification) that credits toolchain defaults, arch-gates dangerous flags, and separates
hardening priority from the defect severity used by `resource-review`.

## Licensing

Because this skill adapts cppreference material under CC BY-SA 3.0, the combined skill is
distributed under **CC BY-SA 4.0**, a permitted later version. CC BY 4.0 material from
OpenSSF and SEI is compatible with that adapter license. The separately licensed C++ Core
Guidelines were consulted but are not relicensed by this notice. See [`LICENSE`](./LICENSE).

Composite adaptation Copyright (c) 2026 Matthew McEachen.
