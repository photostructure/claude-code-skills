#!/usr/bin/env python3
"""List or stage selected hunks from one tracked file without a temp file."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Patch:
    header: bytes
    hunks: tuple[bytes, ...]


def run_git(
    args: list[str],
    *,
    input_data: bytes | None = None,
    cwd: Path | None = None,
) -> bytes:
    try:
        result = subprocess.run(
            ["git", *args],
            input=input_data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            check=False,
        )
    except OSError as error:
        raise RuntimeError(
            f"could not run git (is it installed and on PATH?): {error}"
        ) from error
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(message or f"git {' '.join(args)} failed")
    return result.stdout


def parse_patch(raw: bytes) -> Patch:
    lines = raw.splitlines(keepends=True)
    starts = [index for index, line in enumerate(lines) if line.startswith(b"@@ ")]
    if not starts:
        return Patch(raw, ())

    header = b"".join(lines[: starts[0]])
    hunks: list[bytes] = []
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        hunks.append(b"".join(lines[start:end]))
    return Patch(header, tuple(hunks))


def validate_patch_scope(raw: bytes, patch: Patch) -> None:
    file_headers = sum(
        1 for line in raw.splitlines() if line.startswith(b"diff --git ")
    )
    if file_headers != 1:
        raise ValueError(
            "expected a diff for exactly one file; refusing a broadened path selection"
        )

    metadata_prefixes = (
        b"old mode ",
        b"new mode ",
        b"new file mode ",
        b"deleted file mode ",
        b"similarity index ",
        b"dissimilarity index ",
        b"rename from ",
        b"rename to ",
        b"copy from ",
        b"copy to ",
    )
    if any(
        line.startswith(metadata_prefixes) for line in patch.header.splitlines()
    ):
        raise ValueError(
            "file mode, rename, copy, or create/delete metadata changed; "
            "attribute that change separately before staging content hunks"
        )


def is_binary_patch(raw: bytes) -> bool:
    return any(
        line.startswith((b"GIT binary patch", b"Binary files "))
        for line in raw.splitlines()
    )


def index_entry(file: str, *, cwd: Path | None = None) -> bytes:
    raw = run_git(
        [
            "--literal-pathspecs",
            "ls-files",
            "--stage",
            "--full-name",
            "-z",
            "--",
            file,
        ],
        cwd=cwd,
    )
    records = [record for record in raw.split(b"\0") if record]
    if len(records) != 1:
        raise ValueError(
            "expected exactly one tracked index entry for the selected file"
        )
    metadata, separator, _path = records[0].partition(b"\t")
    fields = metadata.split()
    if not separator or len(fields) != 3 or fields[2] != b"0":
        raise ValueError("the selected file has an unsupported unmerged index entry")
    return records[0]


def summarize_hunk(number: int, hunk: bytes) -> str:
    lines = hunk.decode("utf-8", errors="replace").splitlines()
    heading = lines[0] if lines else "@@"
    sample = next(
        (
            line
            for line in lines[1:]
            if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
        ),
        "",
    )
    suffix = f" | {sample[:100]}" if sample else ""
    return f"{number}: {heading}{suffix}"


def parse_indices(value: str, hunk_count: int) -> tuple[int, ...]:
    try:
        requested = [int(part.strip()) for part in value.split(",") if part.strip()]
    except ValueError as error:
        raise ValueError("--include must be a comma-separated list of hunk numbers") from error
    if not requested:
        raise ValueError("--include requires at least one hunk number")
    invalid = sorted({number for number in requested if number < 1 or number > hunk_count})
    if invalid:
        raise ValueError(f"hunk number out of range: {', '.join(map(str, invalid))}")
    return tuple(dict.fromkeys(requested))


def build_selected_patch(patch: Patch, indices: tuple[int, ...]) -> bytes:
    return patch.header + b"".join(patch.hunks[index - 1] for index in indices)


def self_test() -> None:
    raw = (
        b"diff --git a/demo.txt b/demo.txt\n"
        b"--- a/demo.txt\n"
        b"+++ b/demo.txt\n"
        b"@@ -1 +1 @@\n-old\n+new\n"
        b"@@ -4 +4 @@\n-before\n+after\n"
    )
    patch = parse_patch(raw)
    validate_patch_scope(raw, patch)
    assert len(patch.hunks) == 2
    assert parse_indices("2,1,2", 2) == (2, 1)
    selected = build_selected_patch(patch, (2,))
    assert b"before" in selected and b"old" not in selected
    assert is_binary_patch(b"diff --git a/image.png b/image.png\nGIT binary patch\n")
    assert is_binary_patch(
        b"diff --git a/image.png b/image.png\nBinary files a/image.png and b/image.png differ\n"
    )
    assert not is_binary_patch(
        b"@@ -1 +1 @@\n-Binary files are excluded\n+GIT binary patch is prose\n"
    )

    for invalid in (
        raw + raw.replace(b"demo.txt", b"other.txt"),
        raw.replace(
            b"--- a/demo.txt\n",
            b"old mode 100644\nnew mode 100755\n--- a/demo.txt\n",
        ),
    ):
        try:
            invalid_patch = parse_patch(invalid)
            validate_patch_scope(invalid, invalid_patch)
        except ValueError:
            pass
        else:
            raise AssertionError("unsafe patch scope was not rejected")

    cases = (
        ("default", (), False),
        ("relative", (("diff.relative", "true"),), False),
        ("noprefix", (("diff.noprefix", "true"),), False),
        ("mnemonic", (("diff.mnemonicPrefix", "true"),), False),
        # color.ui/color.diff = always colorizes even when stdout is a pipe,
        # which corrupts the patch with ANSI escapes.
        ("color-ui", (("color.ui", "always"),), False),
        ("color-diff", (("color.diff", "always"),), False),
        # A non-default diff.context changes the emitted context lines; a
        # zero-context patch will not apply without --unidiff-zero.
        ("context-zero", (("diff.context", "0"),), False),
        ("context-wide", (("diff.context", "7"),), False),
        # A large diff.interHunkContext merges adjacent hunks, so selecting
        # "hunk 1" would silently stage unrelated changes too.
        ("inter-hunk", (("diff.interHunkContext", "20"),), False),
        (
            "textconv",
            (("diff.stage-hunks-test.textconv", "git hash-object"),),
            True,
        ),
        (
            "combined",
            (
                ("diff.relative", "true"),
                ("diff.noprefix", "true"),
                ("diff.mnemonicPrefix", "true"),
                ("color.ui", "always"),
                ("diff.context", "0"),
                ("diff.interHunkContext", "20"),
                ("diff.stage-hunks-test.textconv", "git hash-object"),
            ),
            True,
        ),
    )
    for case, settings, use_textconv in cases:
        with tempfile.TemporaryDirectory(prefix=f"stage-hunks-{case}-") as temp:
            root = Path(temp)
            subdir = root / "sub"
            subdir.mkdir()
            tracked = subdir / "[id].txt"
            sibling = subdir / "i.txt"
            baseline = [
                "old first",
                "Binary files are ordinary prose.",
                "GIT binary patch is ordinary prose.",
                *(f"unchanged {number}" for number in range(4, 20)),
                "old last",
            ]
            changed = [*baseline]
            changed[0] = "new first"
            changed[-1] = "new last"

            run_git(["init", "--quiet"], cwd=root)
            tracked.write_text("\n".join(baseline) + "\n", encoding="utf-8")
            sibling.write_text("sibling\n", encoding="utf-8")
            paths = ["sub/[id].txt", "sub/i.txt"]
            if use_textconv:
                attributes = root / ".gitattributes"
                attributes.write_text(
                    "*.txt diff=stage-hunks-test\n", encoding="utf-8"
                )
                paths.append(".gitattributes")
            run_git(["--literal-pathspecs", "add", "--", *paths], cwd=root)
            for key, value in settings:
                run_git(["config", key, value], cwd=root)

            sibling_before = index_entry(sibling.name, cwd=subdir)
            tracked.write_text("\n".join(changed) + "\n", encoding="utf-8")
            sibling.write_text("changed sibling\n", encoding="utf-8")
            before = index_entry(tracked.name, cwd=subdir)
            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    tracked.name,
                    "--include",
                    "1",
                ],
                cwd=subdir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            assert result.returncode == 0, result.stderr.decode(
                "utf-8", errors="replace"
            )
            assert index_entry(tracked.name, cwd=subdir) != before
            expected_index = [*baseline]
            expected_index[0] = "new first"
            assert run_git(["show", ":sub/[id].txt"], cwd=root) == (
                "\n".join(expected_index) + "\n"
            ).encode()
            assert tracked.read_text(encoding="utf-8") == "\n".join(changed) + "\n"
            assert index_entry(sibling.name, cwd=subdir) == sibling_before
    print("stage_hunks.py self-test passed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="List or stage selected unstaged hunks from one tracked file."
    )
    parser.add_argument("file", nargs="?", help="Tracked file to inspect")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--list", action="store_true", help="List numbered hunks")
    action.add_argument("--include", help="Comma-separated hunk numbers to stage")
    parser.add_argument("--self-test", action="store_true", help="Run parser self-test")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        self_test()
        return 0
    if not args.file or (not args.list and args.include is None):
        raise ValueError("provide a file and either --list or --include")

    raw = run_git(
        [
            "--literal-pathspecs",
            "diff",
            "--binary",
            "--no-color",
            "--no-ext-diff",
            "--no-textconv",
            "--no-relative",
            "--src-prefix=a/",
            "--dst-prefix=b/",
            "--unified=3",
            "--inter-hunk-context=0",
            "--",
            args.file,
        ]
    )
    if not raw:
        raise ValueError(f"no unstaged tracked changes found for {args.file}")
    if is_binary_patch(raw):
        raise ValueError("binary diffs cannot be partially staged with this helper")

    patch = parse_patch(raw)
    validate_patch_scope(raw, patch)
    if not patch.hunks:
        raise ValueError("no text hunks found; inspect the file status manually")
    for number, hunk in enumerate(patch.hunks, start=1):
        print(summarize_hunk(number, hunk))

    if args.list:
        return 0

    indices = parse_indices(args.include, len(patch.hunks))
    selected = build_selected_patch(patch, indices)
    before = index_entry(args.file)
    run_git(["apply", "--cached", "--check", "--recount", "-"], input_data=selected)
    run_git(["apply", "--cached", "--recount", "-"], input_data=selected)
    if index_entry(args.file) == before:
        raise RuntimeError("git apply reported success but the index did not change")
    print(f"staged hunks {','.join(map(str, indices))} from {args.file}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2) from error
