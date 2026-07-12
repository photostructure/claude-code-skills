# Attribution

`resource-review` is an original synthesis of memory- and resource-safety guidance for
modern C/C++ (C++17) and Node.js native addons. It is not affiliated with or endorsed by
the organizations listed below.

## Adapted sources

| Source | License | Use in this skill |
| --- | --- | --- |
| [cppreference](https://en.cppreference.com/) | CC BY-SA 3.0 / GFDL | Language-level lifetime, object model, and standard-library semantics behind the defect classes. |
| [SEI CERT C and C++ Coding Standards](https://cmu-sei.github.io/secure-coding-standards/) | CC BY 4.0 standards prose; MIT code examples | Rule identifiers and framing for memory, integer, and file-I/O defects (mapped alongside CWE). No SEI code example is intentionally reproduced. |
| [OpenSSF Compiler Options Hardening Guide for C and C++](https://best.openssf.org/Compiler-Hardening-Guides/Compiler-Options-Hardening-Guide-for-C-and-C++.html) | CC BY 4.0 | Sanitizer compatibility guidance used to keep proof builds valid. |

The [C++ Core Guidelines](https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines)
were consulted for RAII and ownership design guidance. They use a
[custom license](https://github.com/isocpp/CppCoreGuidelines/blob/master/LICENSE), not
MIT. The Guidelines and their license are not relicensed as part of this skill; the
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

- [CWE (MITRE)](https://cwe.mitre.org/) for the defect-class identifiers (CWE-416, -415,
  -401, -787/-125, -457/-908, -190/-191, -367, -362, and related).
- [Clang AddressSanitizer / UBSan / ThreadSanitizer / LeakSanitizer](https://clang.llvm.org/docs/)
  (Apache-2.0 WITH LLVM-exception) and the [Valgrind manual](https://valgrind.org/docs/manual/)
  for how each defect is proven and what each tool does not catch.
- [Node.js Node-API reference](https://nodejs.org/api/n-api.html) and
  [node-addon-api documentation](https://github.com/nodejs/node-addon-api/tree/main/doc)
  (MIT-style) for handle/reference/finalizer/threadsafe-function lifetime rules.

The material was narrowed to provable memory/resource defects, rewritten, and reorganized
into a proof-gated review workflow (Proven / Lead / Theoretical) with a sanitizer trace,
reproducer, or fully traced lifetime required for every finding, and hardening advice
deliberately deferred to `project-setup`.

## Licensing

Because this skill adapts cppreference material under CC BY-SA 3.0, the combined skill is
distributed under **CC BY-SA 4.0**, a permitted later version. CC BY 4.0 material from
SEI and OpenSSF is compatible with that adapter license. The separately licensed C++ Core
Guidelines were consulted but are not relicensed by this notice. See [`LICENSE`](./LICENSE).

Composite adaptation Copyright (c) 2026 Matthew McEachen.
