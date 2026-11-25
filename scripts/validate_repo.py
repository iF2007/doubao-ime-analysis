#!/usr/bin/env python3
"""Deterministic repository consistency, privacy, and artifact validation gate.

Checks:
1. All tracked JSON files parse cleanly.
2. FILE_INDEX.md matches `git ls-files` exactly (including reported file counts).
3. All relative Markdown links resolve to existing files.
4. Privacy & hygiene: no `/Users/<name>` leaks, no forbidden model/weight artifacts tracked.
5. Cross-file version, SHA-256, and architecture diagram PNG dimensions stay in sync.
6. Optional `--verify-local`: verifies `model-config/` against `.local-data/extracted-*`
   and runs `model-analysis/verify_directory.py` against all locally installed models.
"""

import argparse
import json
from pathlib import Path
import re
import struct
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN_EXTENSIONS = {
    ".model",
    ".packed",
    ".pthlite",
    ".mnn",
    ".weight",
    ".onnx",
    ".safetensors",
    ".dylib",
    ".zip",
}
FORBIDDEN_PREFIXES = (".local-data/", ".local-tools/", ".audit/", "lulu-backups/")
USER_PATH_RE = re.compile(r"/Users/[A-Za-z0-9._-]+/")


def git_ls_files() -> list[str]:
    out = subprocess.check_output(["git", "ls-files"], cwd=REPO_ROOT).decode("utf-8")
    return sorted(line for line in out.splitlines() if line)


def read_png_dimensions(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError(f"Not a valid PNG file: {path}")
    return struct.unpack(">II", header[16:24])


def check_json_files(tracked: list[str], errors: list[str]) -> dict[str, object]:
    loaded = {}
    for rel in tracked:
        if not rel.endswith(".json"):
            continue
        path = REPO_ROOT / rel
        try:
            loaded[rel] = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"Invalid JSON in {rel}: {exc}")
    return loaded


def check_file_index(tracked: list[str], errors: list[str]) -> None:
    fi_path = REPO_ROOT / "FILE_INDEX.md"
    if not fi_path.is_file():
        errors.append("Missing FILE_INDEX.md")
        return

    fi_text = fi_path.read_text(encoding="utf-8")
    tracked_set = set(tracked)
    listed = {
        href
        for _, href in re.findall(r"\[([^\]]+)\]\(([^)]+)\)", fi_text)
        if not href.startswith(("#", "http://", "https://"))
    }
    missing = sorted(tracked_set - listed)
    extra = sorted(listed - tracked_set)
    if missing:
        errors.append(f"FILE_INDEX.md missing tracked files: {missing}")
    if extra:
        errors.append(f"FILE_INDEX.md lists non-tracked files: {extra}")

    m = re.search(r"共包含\s+\*\*(\d+)\s+个文件\*\*", fi_text)
    if m and int(m.group(1)) != len(tracked):
        errors.append(
            f"FILE_INDEX.md claims {m.group(1)} files, but git tracks {len(tracked)}"
        )

    readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    rm = re.search(r"全部\s+(\d+)\s+个文件的职责索引", readme_text)
    if rm and int(rm.group(1)) != len(tracked):
        errors.append(
            f"README.md claims {rm.group(1)} files in directory tree, but git tracks {len(tracked)}"
        )


def check_markdown_links(tracked: list[str], errors: list[str]) -> None:
    for rel in tracked:
        if not rel.endswith(".md"):
            continue
        md_path = REPO_ROOT / rel
        text = md_path.read_text(encoding="utf-8")
        for m in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", text):
            href = m.group(1).strip()
            if href.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target = href.split("#", 1)[0]
            if not target:
                continue
            resolved = (md_path.parent / target).resolve()
            if not resolved.exists():
                errors.append(f"Broken relative link in {rel}: {href}")


def check_privacy_and_hygiene(tracked: list[str], errors: list[str], warnings: list[str]) -> None:
    for rel in tracked:
        if rel.startswith(FORBIDDEN_PREFIXES):
            errors.append(f"Forbidden local path tracked in git: {rel}")
        path = REPO_ROOT / rel
        if path.suffix.lower() in FORBIDDEN_EXTENSIONS:
            errors.append(f"Forbidden binary/model artifact tracked in git: {rel}")
        if path.suffix.lower() in {".md", ".json", ".yaml", ".yml", ".py", ".dot", ".conf", ".txt"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for hit in USER_PATH_RE.findall(text):
                if hit in ("/Users/<user>/", "/Users/<username>/"):
                    continue
                errors.append(f"Absolute home directory path leaked in {rel}: {hit}")

    try:
        name = subprocess.check_output(["git", "config", "user.name"], cwd=REPO_ROOT).decode().strip()
        email = subprocess.check_output(["git", "config", "user.email"], cwd=REPO_ROOT).decode().strip()
        if (name, email) != ("Anonymous", "anonymous@invalid"):
            warnings.append(
                f"Git author is {name!r} <{email}>; PRIVACY.md expects 'Anonymous <anonymous@invalid>'"
            )
    except subprocess.CalledProcessError:
        warnings.append("Git user.name / user.email not configured")


def check_cross_file_consistency(loaded_json: dict[str, object], errors: list[str]) -> None:
    env = loaded_json.get("environment.json")
    if not isinstance(env, dict):
        return
    app = env.get("application", {})
    app_ver = app.get("version")
    app_sha = app.get("binary_sha256")
    wave_ver = app.get("wave_build_version")
    build_num = app.get("build_number")

    if not app_ver or not app_sha:
        errors.append("environment.json missing application.version or application.binary_sha256")
        return

    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    for label, expected in (
        ("version", f"macOS `{app_ver}`"),
        ("binary_sha256", app_sha),
        ("wave_build_version", f"Wave `{wave_ver}`"),
        ("build_number", f"Build Number `{build_num}`"),
    ):
        if expected not in readme:
            errors.append(f"README.md missing expected {label} from environment.json: {expected}")

    rm = loaded_json.get("comparison/runtime-markers.json")
    if isinstance(rm, dict):
        if rm.get("app_version") != app_ver:
            errors.append(
                f"comparison/runtime-markers.json app_version={rm.get('app_version')!r} != {app_ver!r}"
            )
        if rm.get("binary_sha256") != app_sha:
            errors.append(
                "comparison/runtime-markers.json binary_sha256 differs from environment.json"
            )

    mm = loaded_json.get("comparison/model-metadata.json")
    if isinstance(mm, list):
        for item in mm:
            if item.get("app_version") != app_ver:
                errors.append(
                    f"comparison/model-metadata.json entry {item.get('file')!r} has "
                    f"app_version={item.get('app_version')!r} != {app_ver!r}"
                )

    dot_text = (REPO_ROOT / "diagrams/doubao-asr-architecture.dot").read_text(encoding="utf-8")
    if f"豆包输入法 {app_ver}" not in dot_text:
        errors.append(
            f"diagrams/doubao-asr-architecture.dot label does not mention '豆包输入法 {app_ver}'"
        )

    png_path = REPO_ROOT / "diagrams/doubao-asr-architecture.png"
    diag_readme = (REPO_ROOT / "diagrams/README.md").read_text(encoding="utf-8")
    if png_path.is_file():
        w, h = read_png_dimensions(png_path)
        expected_dim = f"{w} × {h}"
        if expected_dim not in diag_readme:
            errors.append(
                f"diagrams/README.md does not match actual PNG size ({expected_dim})"
            )


def check_local_models(errors: list[str], warnings: list[str]) -> None:
    support = Path.home() / "Library/Application Support/DoubaoIme/ASRModel/versions"
    if not support.is_dir():
        warnings.append("Local DoubaoIme ASRModel directory not found; skipped local model checks")
        return

    models = sorted(support.rglob("asr_model.model"))
    if not models:
        warnings.append("No local asr_model.model found; skipped verify_directory.py")
    for model in models:
        res = subprocess.run(
            [sys.executable, str(REPO_ROOT / "model-analysis/verify_directory.py"), "--model", str(model)],
            capture_output=True,
            text=True,
        )
        if res.returncode != 0:
            errors.append(f"verify_directory.py failed for {model.name}: {res.stderr.strip()}")

    config_pairs = [
        ("model-config/pro-config.yaml", ".local-data/extracted-pro/config.yaml"),
        ("model-config/general-config.yaml", ".local-data/extracted-general/config.yaml"),
        (
            "model-config/asr/feature_extractor/fbank.conf",
            ".local-data/extracted-pro/asr/feature_extractor/fbank.conf",
        ),
    ]
    for repo_rel, local_rel in config_pairs:
        local_path = REPO_ROOT / local_rel
        if local_path.is_file():
            if (REPO_ROOT / repo_rel).read_bytes() != local_path.read_bytes():
                errors.append(f"{repo_rel} differs from local extracted {local_rel}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate repository JSON, links, privacy hygiene, and version consistency."
    )
    parser.add_argument(
        "--verify-local",
        action="store_true",
        help="Also verify local installed ASR models and compare extracted configs against model-config/",
    )
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []

    tracked = git_ls_files()
    loaded_json = check_json_files(tracked, errors)
    check_file_index(tracked, errors)
    check_markdown_links(tracked, errors)
    check_privacy_and_hygiene(tracked, errors, warnings)
    check_cross_file_consistency(loaded_json, errors)
    if args.verify_local:
        check_local_models(errors, warnings)

    for w in warnings:
        print(f"[WARN] {w}")
    if errors:
        for e in errors:
            print(f"[FAIL] {e}")
        return 1

    print(
        f"[OK] Validated {len(tracked)} tracked files, {len(loaded_json)} JSON files, "
        f"links, privacy hygiene, and cross-file consistency."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
