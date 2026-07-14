#!/usr/bin/env python3
"""Validate the dual Claude Code and Codex plugin marketplace."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PLUGINS = {"coding", "security", "cpp"}
EXPECTED_REPOSITORY = "https://github.com/photostructure/coding-skills"
EXPECTED_REVIEWER_METHODS = {
    "coding": "skills/review/references/single-pass.md",
    "security": "skills/web-security-review/references/validation-pass.md",
    "cpp": "skills/resource-review/references/validation-pass.md",
}
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)"
    r"(?:-(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)(?:\."
    r"(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+[^)]*)?\)")
SEMVER_LITERAL_RE = re.compile(r"`\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?`")


class Validation:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.skill_count = 0

    def check(self, condition: bool, message: str) -> None:
        if not condition:
            self.errors.append(message)

    def load_json(self, path: Path) -> dict:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            self.errors.append(f"{path.relative_to(ROOT)}: invalid JSON: {error}")
            return {}
        if not isinstance(payload, dict):
            self.errors.append(f"{path.relative_to(ROOT)}: root must be an object")
            return {}
        return payload


def resolve_inside_repo(validation: Validation, raw_path: str, label: str) -> Path | None:
    if not isinstance(raw_path, str) or not raw_path.startswith("./"):
        validation.errors.append(f"{label}: path must be a ./-prefixed string")
        return None
    resolved = (ROOT / raw_path).resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError:
        validation.errors.append(f"{label}: path escapes the repository")
        return None
    validation.check(resolved.exists(), f"{label}: path does not exist: {raw_path}")
    return resolved


def validate_marketplaces(validation: Validation) -> dict[str, Path]:
    native_path = ROOT / ".agents" / "plugins" / "marketplace.json"
    claude_path = ROOT / ".claude-plugin" / "marketplace.json"
    native = validation.load_json(native_path)
    claude = validation.load_json(claude_path)

    validation.check(native.get("name") == "photostructure", "native marketplace name must be photostructure")
    interface = native.get("interface")
    validation.check(
        isinstance(interface, dict) and bool(interface.get("displayName")),
        "native marketplace requires interface.displayName",
    )

    native_roots: dict[str, Path] = {}
    native_entries = native.get("plugins")
    if not isinstance(native_entries, list):
        validation.errors.append("native marketplace plugins must be an array")
        native_entries = []
    for index, entry in enumerate(native_entries):
        label = f"native marketplace plugins[{index}]"
        if not isinstance(entry, dict):
            validation.errors.append(f"{label}: entry must be an object")
            continue
        name = entry.get("name")
        source = entry.get("source")
        policy = entry.get("policy")
        validation.check(isinstance(name, str) and bool(name), f"{label}: missing name")
        validation.check(
            isinstance(source, dict) and source.get("source") == "local",
            f"{label}: source.source must be local",
        )
        validation.check(
            isinstance(policy, dict)
            and policy.get("installation") == "AVAILABLE"
            and policy.get("authentication") == "ON_INSTALL",
            f"{label}: required AVAILABLE/ON_INSTALL policy is missing",
        )
        validation.check(bool(entry.get("category")), f"{label}: category is required")
        if isinstance(name, str) and isinstance(source, dict):
            root = resolve_inside_repo(validation, source.get("path"), f"{label}.source")
            if root is not None:
                native_roots[name] = root

    native_names = set(native_roots)
    validation.check(native_names == EXPECTED_PLUGINS, f"native plugin set is {sorted(native_names)}")

    claude_names: set[str] = set()
    claude_entries = claude.get("plugins")
    if not isinstance(claude_entries, list):
        validation.errors.append("Claude marketplace plugins must be an array")
        claude_entries = []
    for index, entry in enumerate(claude_entries):
        label = f"Claude marketplace plugins[{index}]"
        if not isinstance(entry, dict):
            validation.errors.append(f"{label}: entry must be an object")
            continue
        name = entry.get("name")
        source = entry.get("source")
        if not isinstance(name, str):
            validation.errors.append(f"{label}: missing name")
            continue
        claude_names.add(name)
        root = resolve_inside_repo(validation, source, f"{label}.source")
        if root is None:
            continue
        claude_manifest = validation.load_json(root / ".claude-plugin" / "plugin.json")
        validation.check(root.name == name, f"{label}: directory name does not match {name}")
        validation.check(claude_manifest.get("name") == name, f"{label}: Claude manifest name mismatch")

    validation.check(claude_names == EXPECTED_PLUGINS, f"Claude plugin set is {sorted(claude_names)}")
    validation.check(native_names == claude_names, "native and Claude marketplaces expose different plugins")
    return native_roots


def parse_skill_frontmatter(validation: Validation, path: Path) -> dict[str, str]:
    content = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---(?:\n|$)", content, re.DOTALL)
    if match is None:
        validation.errors.append(f"{path.relative_to(ROOT)}: invalid frontmatter delimiters")
        return {}
    values: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line.strip() or ":" not in line:
            validation.errors.append(f"{path.relative_to(ROOT)}: unsupported frontmatter line: {line!r}")
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip()
    validation.check(
        set(values) == {"name", "description"},
        f"{path.relative_to(ROOT)}: frontmatter keys must be exactly name and description",
    )
    validation.check(bool(values.get("description")), f"{path.relative_to(ROOT)}: description is empty")
    return values


def yaml_string(line: str, key: str, label: str, validation: Validation) -> str:
    prefix = f"  {key}: "
    if not line.startswith(prefix):
        validation.errors.append(f"{label}: expected {key}")
        return ""
    try:
        value = json.loads(line[len(prefix) :])
    except json.JSONDecodeError as error:
        validation.errors.append(f"{label}: {key} must be a quoted YAML string: {error}")
        return ""
    if not isinstance(value, str) or not value.strip():
        validation.errors.append(f"{label}: {key} must be non-empty")
        return ""
    return value


def validate_openai_yaml(
    validation: Validation,
    skill_dir: Path,
    invocation_name: str,
) -> None:
    path = skill_dir / "agents" / "openai.yaml"
    label = str(path.relative_to(ROOT))
    if not path.is_file():
        validation.errors.append(f"{label}: missing")
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) != 4 or lines[0] != "interface:":
        validation.errors.append(f"{label}: expected generated four-line interface metadata")
        return
    yaml_string(lines[1], "display_name", label, validation)
    short = yaml_string(lines[2], "short_description", label, validation)
    prompt = yaml_string(lines[3], "default_prompt", label, validation)
    validation.check(25 <= len(short) <= 64, f"{label}: short_description must be 25-64 characters")
    validation.check(
        f"${invocation_name}" in prompt,
        f"{label}: default_prompt must mention ${invocation_name}",
    )


def validate_plugin_reviewer(
    validation: Validation,
    plugin_name: str,
    plugin_root: Path,
) -> None:
    path = plugin_root / "agents" / "reviewer.md"
    label = str(path.relative_to(ROOT))
    if not path.is_file():
        validation.errors.append(f"{label}: missing")
        return

    content = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---(?:\n|$)", content, re.DOTALL)
    if match is None:
        validation.errors.append(f"{label}: invalid frontmatter delimiters")
        return

    values: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line.strip() or ":" not in line:
            validation.errors.append(f"{label}: unsupported frontmatter line: {line!r}")
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip()

    validation.check(
        set(values) == {"name", "description", "tools", "disallowedTools"},
        f"{label}: unexpected frontmatter keys",
    )
    validation.check(values.get("name") == "reviewer", f"{label}: name must be reviewer")
    validation.check(bool(values.get("description")), f"{label}: description is empty")
    validation.check(
        values.get("tools") == "Read, Grep, Glob, Bash",
        f"{label}: tools must be the read-oriented reviewer allowlist",
    )
    validation.check(
        values.get("disallowedTools") == "Agent, Skill",
        f"{label}: Agent and Skill must be explicitly denied",
    )

    method = EXPECTED_REVIEWER_METHODS.get(plugin_name)
    if method is None:
        validation.errors.append(f"{label}: no reviewer methodology configured for {plugin_name}")
        return
    validation.check(
        (plugin_root / method).is_file(),
        f"{label}: {method} does not exist",
    )
    validation.check(
        f"${{CLAUDE_PLUGIN_ROOT}}/{method}" in content,
        f"{label}: must load {method}",
    )
    validation.check("You are a leaf reviewer." in content, f"{label}: missing leaf role")
    validation.check("Never delegate" in content, f"{label}: missing delegation guard")


def validate_plugins_and_skills(validation: Validation, plugin_roots: dict[str, Path]) -> None:
    for marketplace_name, plugin_root in sorted(plugin_roots.items()):
        manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
        manifest = validation.load_json(manifest_path)
        manifest_name = manifest.get("name")
        validation.check(plugin_root.name == marketplace_name, f"{marketplace_name}: directory name mismatch")
        validation.check(manifest_name == marketplace_name, f"{marketplace_name}: native manifest name mismatch")
        validation.check(
            manifest.get("repository") == EXPECTED_REPOSITORY,
            f"{marketplace_name}: native manifest repository must be {EXPECTED_REPOSITORY}",
        )
        version = manifest.get("version")
        validation.check(
            isinstance(version, str) and SEMVER_RE.fullmatch(version) is not None,
            f"{marketplace_name}: native version must be strict SemVer",
        )
        claude_manifest = validation.load_json(plugin_root / ".claude-plugin" / "plugin.json")
        validation.check(
            claude_manifest.get("version") == version,
            f"{marketplace_name}: Claude and native manifest versions must match",
        )
        validation.check(manifest.get("skills") == "./skills/", f"{marketplace_name}: skills must be ./skills/")
        validate_plugin_reviewer(validation, marketplace_name, plugin_root)

        skills_dir = plugin_root / "skills"
        validation.check(skills_dir.is_dir(), f"{marketplace_name}: missing skills directory")
        if not skills_dir.is_dir():
            continue
        skill_dirs = sorted(path for path in skills_dir.iterdir() if path.is_dir())
        validation.check(bool(skill_dirs), f"{marketplace_name}: skills directory is empty")
        for skill_dir in skill_dirs:
            skill_md = skill_dir / "SKILL.md"
            validation.check(skill_md.is_file(), f"{skill_dir.relative_to(ROOT)}: missing SKILL.md")
            if not skill_md.is_file():
                continue
            validation.skill_count += 1
            frontmatter = parse_skill_frontmatter(validation, skill_md)
            skill_name = frontmatter.get("name", "")
            validation.check(skill_name == skill_dir.name, f"{skill_md.relative_to(ROOT)}: name must match directory")
            validate_openai_yaml(
                validation,
                skill_dir,
                f"{marketplace_name}:{skill_name}",
            )

    validation.check(validation.skill_count == 13, f"expected 13 skills, found {validation.skill_count}")


def validate_install_documentation(validation: Validation) -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    try:
        codex_install = readme.split("## Install in Codex", 1)[1].split(
            "## Install in Claude Code", 1
        )[0]
    except IndexError:
        validation.errors.append("README.md: missing Codex or Claude Code install section")
        return
    validation.check(
        SEMVER_LITERAL_RE.search(codex_install) is None,
        "README.md: Codex install instructions must derive versions from manifests",
    )
    validation.check(
        "`.codex-plugin/plugin.json`" in codex_install,
        "README.md: Codex install instructions must name manifests as version ground truth",
    )


def validate_relative_links(validation: Validation) -> None:
    for path in sorted(ROOT.rglob("*.md")):
        if ".git" in path.parts:
            continue
        content = path.read_text(encoding="utf-8")
        for match in MARKDOWN_LINK_RE.finditer(content):
            target = match.group(1).strip("<>")
            parsed = urlparse(target)
            if not target or target.startswith("#") or parsed.scheme or target.startswith("//"):
                continue
            relative = unquote(target.split("#", 1)[0].split("?", 1)[0])
            if not relative:
                continue
            resolved = (path.parent / relative).resolve()
            validation.check(
                resolved.exists(),
                f"{path.relative_to(ROOT)}: broken relative link {target}",
            )


def validate_portability_tokens(validation: Validation) -> None:
    operational = [
        path
        for path in (ROOT / "plugins").rglob("*.md")
        if path.name not in {"ATTRIBUTION.md", "LICENSE"}
        and not (
            len(path.relative_to(ROOT).parts) == 4
            and path.relative_to(ROOT).parts[0] == "plugins"
            and path.relative_to(ROOT).parts[2] == "agents"
        )
    ]
    forbidden = {
        "AskUserQuestion": re.compile(r"\bAskUserQuestion\b"),
        "Claude slash skill": re.compile(r"(?<![\w.-])/(?:coding|security|cpp):[a-z]"),
        "Claude /tpp command": re.compile(r"`/tpp(?:\s|`)"),
        "Claude wrapper": re.compile(r"\bclaude\.sh\b"),
        "Claude model class": re.compile(r"\b(?:opus|sonnet)(?:-class)?\b", re.IGNORECASE),
        "Claude frontmatter": re.compile(r"^(?:allowed-tools|disable-model-invocation|argument-hint|license):", re.MULTILINE),
        "literal Claude tool": re.compile(r"`(?:Task|Agent|Bash|Edit|Write|AskUserQuestion)`"),
        "Codex-only bundled skill invocation": re.compile(
            r"\$(?:coding|security|cpp):[a-z][a-z-]*"
        ),
        "Codex-only runtime wording": re.compile(r"\bCodex\b"),
        "unqualified bundled skill": re.compile(
            r"\$(?:tpp|handoff|project-setup|resource-review|web-security-review)\b"
        ),
    }
    for path in operational:
        content = path.read_text(encoding="utf-8")
        for label, pattern in forbidden.items():
            if pattern.search(content):
                validation.errors.append(f"{path.relative_to(ROOT)}: contains {label}")

        for number, line in enumerate(content.splitlines(), start=1):
            if "Claude" not in line:
                continue
            if "CLAUDE.md" in line or "photostructure.com/coding/claude-code" in line:
                continue
            validation.errors.append(f"{path.relative_to(ROOT)}:{number}: unexpected Claude runtime reference")

    for relative in (
        "plugins/coding/skills/double-review/SKILL.md",
        "plugins/coding/skills/stage/SKILL.md",
    ):
        content = (ROOT / relative).read_text(encoding="utf-8")
        shell_tokens = {
            "/tmp": re.compile(r"/tmp"),
            "stdin redirection": re.compile(r"</dev/null"),
            "awk": re.compile(r"(?<![\w-])awk(?:\s|`)"),
            "tail": re.compile(r"(?<![\w-])tail(?:\s|`)"),
            "shell substitution": re.compile(r"\$\("),
            "heredoc": re.compile(r"\bheredoc\b", re.IGNORECASE),
            "cp": re.compile(r"(?<![\w-])cp(?:\s|`)"),
            "sed": re.compile(r"(?<![\w-])sed(?:\s|`)"),
        }
        for label, pattern in shell_tokens.items():
            validation.check(
                pattern.search(content) is None,
                f"{relative}: contains non-portable token {label!r}",
            )


def main() -> int:
    validation = Validation()
    roots = validate_marketplaces(validation)
    validate_plugins_and_skills(validation, roots)
    validate_install_documentation(validation)
    validate_relative_links(validation)
    validate_portability_tokens(validation)

    if validation.errors:
        print("Repository validation failed:")
        for error in validation.errors:
            print(f"- {error}")
        return 1
    print(
        "Repository validation passed: "
        f"2 marketplaces, {len(roots)} plugins, {validation.skill_count} skills"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
