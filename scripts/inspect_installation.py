#!/usr/bin/env python3
"""Read-only inspector for locally installed DoubaoIme.app and offline ASR models.

Default mode prints a JSON snapshot comparing the installed app bundle and local
models against `environment.json` and `comparison/runtime-markers.json`, plus
open-ended discovery across all Mach-O binaries inside DoubaoIme.app.

Optional write modes:
  --write-runtime-markers  Regenerate comparison/runtime-markers.json from main binary
  --write-model-metadata   Regenerate comparison/model-metadata.json from extracted dirs
"""

import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import re

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_APP_PATH = Path("/Library/Input Methods/DoubaoIme.app")
DEFAULT_SUPPORT_DIR = Path.home() / "Library/Application Support/DoubaoIme"

RUNTIME_MARKER_PATTERNS = [
    rb"flute::asr::ntp_cif::PromptProcessor",
    rb"flute::asr::ntp_cif::PantherLLMEngineCreator",
    rb"N7panther4lite3cpu26QW4ConformerLayerRopeChunkE",
    rb"QW4ConformerLayerRopeChunkE",
    rb"N7panther4lite3cpu19W4A8Gpt2TransformerE",
    rb"W4A8Gpt2TransformerE",
    rb"flute\.asr\.[A-Za-z0-9_.]+",
    rb"flute\.vad\.TailVadProbeActor",
    rb"QW4ConformerLayerRopeChunk(?:Kernel)?: [^\x00\n]+",
    rb"PthCpuProviderQW4ConformerLayerRopeChunk",
    rb"PthCpuProviderW4A8GPT2TransformerBlock",
    rb"\x00QW4ConformerLayerRopeChunk\x00",
    rb"PthCpuProviderQW4ConformerLayerRopeChunk\x00",
    rb'QW4ConformerLayerRopeChunk", "QW4ConformerLayerRopeChunk"[^\x00\n]+',
    rb"QW4ConformerLayerRopeChunk info failed",
    rb"QW4ConformerLayerRopeChunk only support format BTN",
    rb"QW4ConformerLayerRopeChunk (?:CPU|Metal|layer_idx)[^\x00\n]+",
    rb"W4A8Gpt2Transformer[^\x00\n]+",
]

BACKEND_KEYWORDS = (
    b"MNN",
    b"Panther",
    b"CoreML",
    b"MLModel",
    b"MLX",
    b"ONNX",
    b"Metal",
    b"AppleNeuralEngine",
    b"FLUTE",
    b"symphony",
)

NETWORK_DOMAINS = (
    b"effect.snssdk.com",
    b"byteeffecttos.com",
    b"dig.zjurl.cn",
    b"zijieapi.com",
    b"doubao.com",
    b"speech.bytedance.com",
    b"oceancloudapi.com",
)


def redact_home(path: Path) -> str:
    resolved = path.expanduser().resolve()
    try:
        return "~/" + str(resolved.relative_to(Path.home().resolve()))
    except ValueError:
        return str(resolved)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(4 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def collect_app_info(app_path: Path) -> dict:
    info_plist = app_path / "Contents/Info.plist"
    plist = plistlib.loads(info_plist.read_bytes())
    exe_name = plist.get("CFBundleExecutable", "DoubaoIme")
    main_bin = app_path / "Contents/MacOS" / exe_name

    nested_apps = []
    apps_dir = app_path / "Contents/Applications"
    if apps_dir.is_dir():
        for nested in sorted(apps_dir.glob("*.app")):
            np = nested / "Contents/Info.plist"
            if np.is_file():
                nplist = plistlib.loads(np.read_bytes())
                nested_apps.append(
                    {
                        "name": nested.name,
                        "version": nplist.get("CFBundleShortVersionString"),
                        "build": str(nplist.get("CFBundleVersion", "")),
                    }
                )

    frameworks = []
    fw_dir = app_path / "Contents/Frameworks"
    if fw_dir.is_dir():
        frameworks = sorted(p.name for p in fw_dir.iterdir())

    return {
        "name": plist.get("CFBundleName", exe_name),
        "version": plist.get("CFBundleShortVersionString"),
        "build": str(plist.get("CFBundleVersion", "")),
        "wave_build_version": plist.get("Wave Build Version"),
        "build_number": str(plist.get("Wave Build Version Number", "")),
        "bundle_id": plist.get("CFBundleIdentifier"),
        "path": str(app_path),
        "main_binary": str(main_bin),
        "binary_sha256": sha256_file(main_bin),
        "nested_apps": nested_apps,
        "frameworks": frameworks,
    }


def collect_bundle_binaries(app_path: Path) -> list[Path]:
    binaries: list[Path] = []
    for candidate in (
        list((app_path / "Contents/MacOS").glob("*"))
        if (app_path / "Contents/MacOS").is_dir()
        else []
    ):
        if candidate.is_file():
            binaries.append(candidate)

    apps_dir = app_path / "Contents/Applications"
    if apps_dir.is_dir():
        for exe in sorted(apps_dir.glob("*.app/Contents/MacOS/*")):
            if exe.is_file():
                binaries.append(exe)

    fw_dir = app_path / "Contents/Frameworks"
    if fw_dir.is_dir():
        for dylib in sorted(fw_dir.glob("*.dylib")):
            if dylib.is_file():
                binaries.append(dylib)
        for fw in sorted(fw_dir.glob("*.framework")):
            fw_bin = fw / "Versions/A" / fw.stem
            if fw_bin.is_file():
                binaries.append(fw_bin)

    return binaries


def extract_runtime_markers(main_bin: Path, app_version: str) -> dict:
    data = main_bin.read_bytes()
    sha256 = hashlib.sha256(data).hexdigest()
    mnn_count = sum(1 for m in re.finditer(rb"[ -~]{4,}", data) if b"MNN" in m.group(0))

    matches = []
    seen = set()
    for pat in RUNTIME_MARKER_PATTERNS:
        for m in re.finditer(pat, data):
            off = m.start()
            raw = m.group(0)
            if raw.startswith(b"\x00"):
                off += 1
                raw = raw[1:]
            if raw.endswith(b"\x00"):
                raw = raw[:-1]
            if pat == rb"PthCpuProviderQW4ConformerLayerRopeChunk\x00":
                off += len("PthCpuProvider")
                raw = b"QW4ConformerLayerRopeChunk"
            txt = raw.decode("ascii")
            if data[m.end() : m.end() + 5] == b"\n\x1b[0m":
                txt += "[0m"
            key = (off, txt)
            if key not in seen:
                seen.add(key)
                matches.append({"offset": off, "text": txt})

    matches.sort(key=lambda x: (x["offset"], x["text"]))
    return {
        "app_version": app_version,
        "path": str(main_bin),
        "binary_sha256": sha256,
        "mnn_string_count": mnn_count,
        "matches": matches,
    }


def scan_app_bundle(app_path: Path) -> dict:
    declared_models: set[str] = set()
    flute_asr: set[str] = set()
    flute_vad: set[str] = set()
    oime_report_methods: set[str] = set()
    backend_hits = {k.decode(): 0 for k in BACKEND_KEYWORDS}
    domain_hits = {k.decode(): 0 for k in NETWORK_DOMAINS}
    sdk_versions: set[str] = set()

    for binary in collect_bundle_binaries(app_path):
        data = binary.read_bytes()
        for m in re.findall(rb"\bacllm_[a-z0-9_]+\b", data):
            declared_models.add(m.decode("ascii"))
        for m in re.findall(rb"flute\.asr\.[A-Za-z0-9_.]+", data):
            flute_asr.add(m.decode("ascii"))
        for m in re.findall(rb"flute\.vad\.[A-Za-z0-9_.]+", data):
            flute_vad.add(m.decode("ascii"))
        for m in re.findall(rb"(?:record|report)[A-Za-z0-9]+(?:Event|Data)", data):
            s = m.decode("ascii")
            if any(k in s for k in ("Keyboard", "UserExp", "ASR", "OfflineModel")):
                oime_report_methods.add(s)
        for m in re.findall(rb"2\.9\.\d{2,4}", data):
            sdk_versions.add(m.decode("ascii"))
        for kw in BACKEND_KEYWORDS:
            backend_hits[kw.decode()] += data.count(kw)
        for dom in NETWORK_DOMAINS:
            domain_hits[dom.decode()] += data.count(dom)

    return {
        "binaries_scanned": len(collect_bundle_binaries(app_path)),
        "declared_model_names": sorted(declared_models),
        "flute_asr_actors": sorted(flute_asr),
        "flute_vad_actors": sorted(flute_vad),
        "backend_keyword_hits": backend_hits,
        "network_domain_hits": domain_hits,
        "telemetry_methods": sorted(oime_report_methods),
        "sdk_version_candidates": sorted(sdk_versions),
    }


def collect_local_models(support_dir: Path) -> dict:
    result: dict = {"support_dir": redact_home(support_dir), "discovered_model_files": []}
    manifest_file = support_dir / "ASRContext/offline_model_manifest.json"
    if manifest_file.is_file():
        result["manifest"] = json.loads(manifest_file.read_text(encoding="utf-8"))
    layout_file = support_dir / "ASRContext/offline_model_active_layout.json"
    if layout_file.is_file():
        result["active_layout"] = json.loads(layout_file.read_text(encoding="utf-8"))

    if support_dir.is_dir():
        for model_file in sorted(support_dir.rglob("*.model")):
            if model_file.is_file():
                result["discovered_model_files"].append(
                    {"path": redact_home(model_file), "bytes": model_file.stat().st_size}
                )
    return result


def build_diff_summary(app_info: dict, local_models: dict, bundle_scan: dict) -> dict:
    env_path = REPO_ROOT / "environment.json"
    diff: dict = {}
    if env_path.is_file():
        env = json.loads(env_path.read_text(encoding="utf-8"))
        env_app = env.get("application", {})
        diff["app_changed"] = (
            env_app.get("version") != app_info["version"]
            or env_app.get("binary_sha256") != app_info["binary_sha256"]
            or env_app.get("wave_build_version") != app_info["wave_build_version"]
            or env_app.get("build_number") != app_info["build_number"]
        )
        env_md5s = {
            m.get("name"): m.get("md5")
            for m in env.get("models", {}).values()
            if isinstance(m, dict) and m.get("name")
        }
        manifest_models = local_models.get("manifest", {}).get("models", {})
        local_md5s = {
            name: records[0].get("sourceMD5")
            for name, records in manifest_models.items()
            if isinstance(records, list) and records
        }
        diff["models_changed"] = env_md5s != local_md5s
        diff["env_model_md5s"] = env_md5s
        diff["local_model_md5s"] = local_md5s

    rm_path = REPO_ROOT / "comparison/runtime-markers.json"
    if rm_path.is_file():
        rm = json.loads(rm_path.read_text(encoding="utf-8"))
        known_asr = {m["text"] for m in rm.get("matches", []) if m["text"].startswith("flute.asr.")}
        live_asr = set(bundle_scan["flute_asr_actors"])
        diff["new_flute_asr_actors"] = sorted(live_asr - known_asr)
        diff["removed_flute_asr_actors"] = sorted(known_asr - live_asr)

    return diff


def scan_packed_metadata(app_version: str, extracted_specs: list[tuple[str, Path]]) -> list[dict]:
    head_limit = 4 * 1024 * 1024
    tail_limit = 2 * 1024 * 1024
    env = json.loads((REPO_ROOT / "environment.json").read_text(encoding="utf-8"))
    records: list[dict] = []

    for variant, root_dir in extracted_specs:
        if not root_dir.is_dir():
            raise FileNotFoundError(f"Extracted directory not found: {root_dir}")
        model_info = env.get("models", {}).get(variant, {})
        cfg_path = root_dir / "config.yaml"
        config_label = model_info.get("config_label")
        if cfg_path.is_file():
            m = re.search(r"model_version:\s*([A-Za-z0-9_.-]+)", cfg_path.read_text(encoding="utf-8", errors="ignore"))
            if m:
                config_label = m.group(1)

        for packed in sorted(root_dir.rglob("*.packed")):
            size = packed.stat().st_size
            with packed.open("rb") as f:
                head = f.read(head_limit)
                f.seek(max(0, size - tail_limit))
                tail = f.read(tail_limit)
            blob = head + tail
            blob_lower = blob.lower()

            mnns = sorted(
                set(
                    m.decode("ascii")
                    for m in re.findall(
                        rb"(?:stream|nonstream|no_stream)/[A-Za-z0-9_.-]+\.mnn(?:\.weight)?",
                        blob,
                    )
                )
            )
            dec_layers = sorted(
                set(int(m) for m in re.findall(rb"gpt2\.transformer\.h\.(\d+)\.", blob))
            )
            enc_layers = sorted(set(int(m) for m in re.findall(rb"encoders\.(\d+)\.", blob)))
            feature_markers = sorted(
                marker
                for marker in ("audio_proj", "gpt", "macaron", "ntp1", "rope")
                if marker.encode("ascii") in blob_lower
            )

            records.append(
                {
                    "app_version": app_version,
                    "variant": variant,
                    "model_name": model_info.get("name"),
                    "model_version": model_info.get("version"),
                    "config_label": config_label,
                    "file": str(packed.relative_to(root_dir).as_posix()),
                    "file_bytes": size,
                    "scanned_head_bytes": min(head_limit, size),
                    "scanned_tail_bytes": min(tail_limit, size),
                    "embedded_mnn_files": mnns,
                    "decoder_layer_indices": dec_layers,
                    "encoder_layer_indices": enc_layers,
                    "feature_markers": feature_markers,
                }
            )

    return records


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect installed DoubaoIme.app and local offline models."
    )
    parser.add_argument(
        "--app",
        type=Path,
        default=DEFAULT_APP_PATH,
        help="Path to DoubaoIme.app bundle",
    )
    parser.add_argument(
        "--support-dir",
        type=Path,
        default=DEFAULT_SUPPORT_DIR,
        help="Path to DoubaoIme Application Support directory",
    )
    parser.add_argument(
        "--write-runtime-markers",
        action="store_true",
        help="Write regenerated comparison/runtime-markers.json from installed main binary",
    )
    parser.add_argument(
        "--write-model-metadata",
        action="store_true",
        help="Write regenerated comparison/model-metadata.json from extracted model directories",
    )
    parser.add_argument(
        "--extracted",
        action="append",
        default=[],
        metavar="VARIANT=DIR",
        help="Extracted directory mapping for --write-model-metadata (defaults to pro=.local-data/extracted-pro and general=.local-data/extracted-general)",
    )
    args = parser.parse_args()

    app_info = collect_app_info(args.app)
    main_bin = Path(app_info["main_binary"])

    if args.write_runtime_markers:
        rm = extract_runtime_markers(main_bin, app_info["version"])
        target = REPO_ROOT / "comparison/runtime-markers.json"
        target.write_text(json.dumps(rm, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(
            f"Wrote {target.relative_to(REPO_ROOT)}: {len(rm['matches'])} matches, "
            f"mnn_string_count={rm['mnn_string_count']}"
        )

    if args.write_model_metadata:
        if args.extracted:
            specs = []
            for item in args.extracted:
                variant, path_str = item.split("=", 1)
                specs.append((variant, Path(path_str).expanduser().resolve()))
        else:
            specs = [
                ("pro", REPO_ROOT / ".local-data/extracted-pro"),
                ("general", REPO_ROOT / ".local-data/extracted-general"),
            ]
        records = scan_packed_metadata(app_info["version"], specs)
        target = REPO_ROOT / "comparison/model-metadata.json"
        target.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {target.relative_to(REPO_ROOT)}: {len(records)} packed model records")

    if not args.write_runtime_markers and not args.write_model_metadata:
        local_models = collect_local_models(args.support_dir)
        bundle_scan = scan_app_bundle(args.app)
        diff_summary = build_diff_summary(app_info, local_models, bundle_scan)
        snapshot = {
            "application": app_info,
            "diff_vs_repo": diff_summary,
            "local_models": local_models,
            "bundle_scan": bundle_scan,
        }
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
