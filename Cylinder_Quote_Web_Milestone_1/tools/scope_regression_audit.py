from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


TOOL_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = TOOL_ROOT / "app"
AUDIT_ROOT = TOOL_ROOT / "scope_audit"
BASELINES_ROOT = AUDIT_ROOT / "baselines"
REPORTS_ROOT = AUDIT_ROOT / "reports"
SHARED_FILES_REPORT = TOOL_ROOT / "Txt_files" / "shared_files_audit.txt"
TEXT_SUFFIXES = {".css", ".html", ".htm", ".js", ".json", ".py", ".txt", ".md"}
SHARED_TARGET_SUFFIXES = {".html", ".htm", ".css", ".js", ".db", ".csv"}
SHARED_SOURCE_SUFFIXES = {".css", ".html", ".htm", ".js", ".json", ".py", ".db", ".csv"}
STOP_WORDS = {
    "about", "after", "allow", "before", "change", "changes", "from", "into",
    "that", "the", "this", "with", "work", "application", "folder", "search",
    "scope", "file", "files", "only", "update", "using", "make", "support",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative_files(root: Path) -> list[Path]:
    return sorted(path.relative_to(root) for path in root.rglob("*") if path.is_file())


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def is_text_file(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES


def file_kind(path: Path) -> str:
    return path.suffix.lower().lstrip(".") or "binary"


def snapshot_manifest(snapshot_root: Path) -> dict:
    files = {}
    for relative_path in relative_files(snapshot_root / "app"):
        path = snapshot_root / "app" / relative_path
        files[relative_path.as_posix()] = {
            "sha256": sha256(path),
            "size": path.stat().st_size,
            "kind": file_kind(path),
        }
    return files


def tokens(value: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", value)
        if token.lower() not in STOP_WORDS
    }


def scope_terms(scope: str) -> set[str]:
    excluded = set()
    for match in re.findall(r"(?:exclude|out[- ]of[- ]scope)\s*:\s*([^.;]+)", scope, re.I):
        excluded.update(tokens(match))
    return tokens(scope) - excluded


def structural_summary(path: Path, content: str) -> list[str]:
    suffix = path.suffix.lower()
    findings = []
    if suffix in {".html", ".htm"}:
        for tag, attributes in re.findall(r"<([A-Za-z][\w:-]*)([^>]*)>", content):
            if tag.lower() in {"button", "input", "form", "a", "table", "dialog", "select", "textarea"}:
                ids = re.findall(r"\bid\s*=\s*['\"]([^'\"]+)", attributes, re.I)
                classes = re.findall(r"\bclass\s*=\s*['\"]([^'\"]+)", attributes, re.I)
                findings.append(f"HTML <{tag}> id={ids} class={classes}")
    elif suffix == ".css":
        for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", content):
            selector = " ".join(selector.split())
            if selector:
                declarations = [line.strip() for line in body.split(";") if ":" in line]
                findings.append(f"CSS {selector}: {'; '.join(declarations)}")
    elif suffix == ".js":
        for pattern, label in [
            (r"addEventListener\s*\(\s*['\"]([^'\"]+)", "event"),
            (r"(?:fetch|axios\.(?:get|post|put|patch|delete))\s*\(\s*[`'\"]([^`'\"]+)", "API"),
            (r"(?:getElementById|querySelector|querySelectorAll)\s*\(\s*['\"]([^'\"]+)", "DOM"),
        ]:
            findings.extend(f"JS {label}: {value}" for value in re.findall(pattern, content))
    elif suffix == ".py":
        for pattern, label in [
            (r"@(?:app|\w+_bp|\w+)\.(?:route|get|post|put|patch|delete)\s*\(\s*['\"]([^'\"]+)", "route"),
            (r"(?:select|insert|update|delete|execute)\s*\(", "database call"),
            (r"def\s+(\w+)\s*\(", "function"),
        ]:
            findings.extend(f"Python {label}: {value}" for value in re.findall(pattern, content))
    return findings


def file_reference_patterns(relative_path: Path) -> list[tuple[str, str]]:
    relative_name = relative_path.as_posix()
    basename = relative_path.name
    patterns = [
        (rf"(?<![A-Za-z0-9_./\\-]){re.escape(relative_name)}(?![A-Za-z0-9_./\\-])", "path"),
        (rf"(?<![A-Za-z0-9_.-]){re.escape(basename)}(?![A-Za-z0-9_.-])", "filename"),
    ]
    if relative_path.suffix.lower() == ".py":
        module_name = relative_path.with_suffix("").as_posix().replace("/", ".")
        patterns.append((rf"(?<![A-Za-z0-9_]){re.escape(module_name)}(?![A-Za-z0-9_])", "Python module"))
    return patterns


def shared_file_relationships() -> dict[str, list[tuple[str, str]]]:
    app_files = relative_files(APP_ROOT)
    source_files = [path for path in app_files if path.suffix.lower() in SHARED_SOURCE_SUFFIXES]
    target_files = [path for path in app_files if path.suffix.lower() in SHARED_TARGET_SUFFIXES]
    source_contents = {
        path.as_posix(): read_text(APP_ROOT / path)
        for path in source_files
    }
    relationships = {}
    for target in target_files:
        consumers = []
        for source in source_files:
            if source == target:
                continue
            source_name = source.as_posix()
            content = source_contents[source_name]
            evidence = next(
                (
                    reference_type
                    for pattern, reference_type in file_reference_patterns(target)
                    if re.search(pattern, content, re.IGNORECASE)
                ),
                None,
            )
            if evidence:
                consumers.append((source_name, evidence))
        if len(consumers) >= 2:
            relationships[target.as_posix()] = sorted(consumers)
    return dict(sorted(relationships.items()))


def write_shared_files_report() -> int:
    relationships = shared_file_relationships()
    SHARED_FILES_REPORT.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "SHARED APPLICATION FILES AUDIT",
        "================================",
        "",
        "Protected folder: app/",
        "A file is listed when an HTML, CSS, JS, DB, or CSV file is referenced by at least two other non-TXT files inside app/.",
        "TXT and Markdown files are ignored. References are detected using relative paths, filenames, and Python module names.",
        "",
    ]
    if not relationships:
        lines.append("No files were referenced by two or more other app/ files.")
    else:
        for index, (target, consumers) in enumerate(relationships.items(), start=1):
            lines.append(f"{index}. {target} ({len(consumers)} referencing files)")
            for letter_index, (consumer, evidence) in enumerate(consumers, start=1):
                lines.append(f"       {chr(96 + letter_index)}. {consumer} [{evidence} reference]")
            lines.append("")
    SHARED_FILES_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Shared-file report: {SHARED_FILES_REPORT}")
    print(f"Shared files found: {len(relationships)}")
    return 0


def unified_diff(before: str, after: str, relative_path: str) -> list[str]:
    return list(difflib.unified_diff(
        before.splitlines(), after.splitlines(),
        fromfile=f"baseline/app/{relative_path}",
        tofile=f"current/app/{relative_path}",
        lineterm="",
    ))


def explicit_exclusions(scope: str, relative_path: str) -> bool:
    for match in re.findall(r"(?:exclude|out[- ]of[- ]scope)\s*:\s*([^.;]+)", scope, re.I):
        if tokens(relative_path) & tokens(match):
            return True
    return False


def classify(relative_path: str, scope: str, changed_content: str, direct_paths: set[str], dependency_paths: set[str]) -> str:
    if explicit_exclusions(scope, relative_path):
        return "OUT OF SCOPE"
    if relative_path in direct_paths:
        return "IN SCOPE"
    path_terms = tokens(relative_path)
    matching_terms = path_terms & scope_terms(scope)
    if matching_terms or tokens(changed_content) & scope_terms(scope):
        return "IN SCOPE"
    if relative_path in dependency_paths:
        return "DEPENDENCY CHANGE"
    return "SUSPICIOUS"


def latest_baseline() -> Path:
    candidates = sorted(path for path in BASELINES_ROOT.iterdir() if path.is_dir()) if BASELINES_ROOT.exists() else []
    if not candidates:
        raise SystemExit("No baseline exists. Run the baseline command first.")
    return candidates[-1]


def create_baseline(scope: str) -> int:
    if not APP_ROOT.is_dir():
        raise SystemExit(f"Protected application folder not found: {APP_ROOT}")
    baseline_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = BASELINES_ROOT / baseline_id
    destination.mkdir(parents=True, exist_ok=False)
    shutil.copytree(APP_ROOT, destination / "app")
    manifest = snapshot_manifest(destination)
    (destination / "manifest.json").write_text(json.dumps({"files": manifest}, indent=2), encoding="utf-8")
    (destination / "scope.json").write_text(json.dumps({
        "approved_scope": scope,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "protected_root": "app/",
    }, indent=2), encoding="utf-8")
    print(f"Baseline created: {destination}")
    print(f"Captured {len(manifest)} files under app/")
    return 0


def audit(baseline_path: Path | None) -> int:
    baseline = baseline_path or latest_baseline()
    manifest = json.loads((baseline / "manifest.json").read_text(encoding="utf-8"))["files"]
    scope = json.loads((baseline / "scope.json").read_text(encoding="utf-8"))["approved_scope"]
    current_manifest = snapshot_manifest(TOOL_ROOT)
    baseline_paths = set(manifest)
    current_paths = set(current_manifest)
    added = sorted(current_paths - baseline_paths)
    deleted = sorted(baseline_paths - current_paths)
    modified = sorted(path for path in baseline_paths & current_paths if manifest[path]["sha256"] != current_manifest[path]["sha256"])
    unchanged = sorted((baseline_paths & current_paths) - set(modified))
    renamed = []
    remaining_added = set(added)
    remaining_deleted = set(deleted)
    for deleted_path in sorted(deleted):
        match = next((path for path in sorted(remaining_added) if manifest[deleted_path]["sha256"] == current_manifest[path]["sha256"]), None)
        if match:
            renamed.append((deleted_path, match))
            remaining_deleted.remove(deleted_path)
            remaining_added.remove(match)
    changed_paths = sorted(set(modified) | remaining_added | remaining_deleted)
    direct_paths = {path for path in changed_paths if path.lower() in scope.lower() or Path(path).name.lower() in scope.lower()}
    dependency_paths = set()
    for path in direct_paths:
        content = read_text(APP_ROOT / path) if (APP_ROOT / path).exists() else ""
        for candidate in changed_paths:
            if candidate != path and Path(candidate).name in content:
                dependency_paths.add(candidate)
    classifications = {category: [] for category in ("IN SCOPE", "DEPENDENCY CHANGE", "OUT OF SCOPE", "SUSPICIOUS")}
    details = []
    for path in changed_paths:
        before = read_text(baseline / "app" / path) if path in baseline_paths else "<file did not exist in baseline>"
        after = read_text(APP_ROOT / path) if path in current_paths else "<file was deleted after baseline>"
        change_type = "MODIFIED" if path in modified else "ADDED" if path in remaining_added else "DELETED"
        category = classify(path, scope, after, direct_paths, dependency_paths)
        classifications[category].append(path)
        details.append((path, change_type, category, before, after))
    report_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    REPORTS_ROOT.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_ROOT / f"scope_regression_audit_{report_id}.md"
    lines = [
        "# SCOPE REGRESSION AUDIT", "", "## APPROVED SCOPE", scope, "",
        f"## BASELINE\n`{baseline.name}` captured {len(manifest)} files under `app/`.", "",
        "## FILE CHANGES",
        f"- Modified: {len(modified)}", f"- Added: {len(remaining_added)}", f"- Deleted: {len(remaining_deleted)}",
        f"- Renamed: {len(renamed)}", f"- Unchanged: {len(unchanged)}", "",
    ]
    if renamed:
        lines += ["### Renamed", *[f"- `{old}` -> `{new}`" for old, new in renamed], ""]
    for category in ("IN SCOPE", "DEPENDENCY CHANGE", "OUT OF SCOPE", "SUSPICIOUS"):
        lines += [f"## {category}", ""]
        paths = classifications[category]
        if not paths:
            lines += ["No changes classified here.", ""]
            continue
        for path in paths:
            lines += [f"### `{path}`"]
            detail = next(item for item in details if item[0] == path)
            lines += [f"Change type: **{detail[1]}**", "", "Structural summary:"]
            summary = structural_summary(APP_ROOT / path, detail[4]) if path in current_paths else structural_summary(baseline / "app" / path, detail[3])
            lines += [f"- {item}" for item in summary[:80]] or ["- No focused structural items detected."]
            lines += ["", "Diff:", "", "```diff", *unified_diff(detail[3], detail[4], path)[:400], "```", ""]
    lines += ["## UNCHANGED / PROTECTED", "", f"{len(unchanged)} files remain byte-for-byte unchanged.", ""]
    review_required = bool(classifications["OUT OF SCOPE"] or classifications["SUSPICIOUS"])
    lines += ["## FINAL RESULT", "", "**REVIEW REQUIRED**" if review_required else "**PASS**", ""]
    if review_required:
        lines.append("Review every OUT OF SCOPE or SUSPICIOUS change before accepting the work.")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Audit report: {report_path}")
    print(f"Changed files: {len(changed_paths)}; unchanged files: {len(unchanged)}")
    print("Result: REVIEW REQUIRED" if review_required else "Result: PASS")
    return 1 if review_required else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare the protected app/ folder before and after scoped AI work.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    baseline_parser = subparsers.add_parser("baseline", help="Capture app/ and record approved scope.")
    baseline_parser.add_argument("--scope", required=True, help="Approved scope description.")
    audit_parser = subparsers.add_parser("audit", help="Compare current app/ against a baseline.")
    audit_parser.add_argument("--baseline", type=Path, help="Specific baseline directory; defaults to latest.")
    subparsers.add_parser("shared-files", help="List app/ files referenced by at least two other app/ files.")
    args = parser.parse_args()
    if args.command == "baseline":
        return create_baseline(args.scope)
    if args.command == "shared-files":
        return write_shared_files_report()
    return audit(args.baseline)


if __name__ == "__main__":
    sys.exit(main())
