#!/usr/bin/env python3
"""Verify Doubao IME FLUTE v2/v3 ASR model directory, header layout, and key derivation.

Supports FLUTE v2 (plaintext directory) and FLUTE v3 (ChaCha20 encrypted directory)
containers across current dual-model releases and legacy 1.1.0 single-model releases.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

from Crypto.Cipher import ChaCha20


XOR_MASK = b"symphony"
DOUBAO_SUPPORT_DIR = Path.home() / "Library/Application Support/DoubaoIme"


def format_model_path(path: Path) -> str:
    resolved = path.expanduser().resolve()
    try:
        return "~/" + str(resolved.relative_to(Path.home().resolve()))
    except ValueError:
        return str(resolved)


def discover_local_models(support_dir: Path = DOUBAO_SUPPORT_DIR) -> list[Path]:
    versions_dir = support_dir / "ASRModel/versions"
    if not versions_dir.is_dir():
        return []
    candidates = [p for p in versions_dir.rglob("asr_model.model") if p.is_file()]
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates


def resolve_default_model() -> Path:
    layout_file = DOUBAO_SUPPORT_DIR / "ASRContext/offline_model_active_layout.json"
    if layout_file.exists():
        try:
            data = json.loads(layout_file.read_text())
            selected = data.get("selectedMainModelName")
            rel_path = data.get("mainModelPaths", {}).get(selected)
            if rel_path:
                candidate = DOUBAO_SUPPORT_DIR / rel_path
                if candidate.is_file():
                    return candidate
        except Exception:
            pass

    discovered = discover_local_models()
    if discovered:
        return discovered[0]

    return DOUBAO_SUPPORT_DIR / "ASRModel/versions/asr_model.model"


def load_32_byte_file(path: Path, label: str) -> bytes:
    if not path.is_file():
        raise ValueError(f"{label} file not found: {path}")
    data = path.read_bytes()
    if len(data) != 32:
        raise ValueError(f"{label} must contain exactly 32 raw bytes, got {len(data)}")
    return data


def read_container_prefix(file, model_size: int) -> tuple[int, int, int]:
    prefix = file.read(21)
    if len(prefix) != 21:
        raise ValueError("Model file is truncated (fewer than 21 header bytes)")
    magic = prefix[:5]
    version, header_size, count = struct.unpack_from("<IQI", prefix, 5)
    if magic != b"FLUTE" or version not in (2, 3):
        raise ValueError(f"Unsupported model container: magic={magic!r}, version={version}")
    min_header = 21 if version == 2 else 33
    if header_size < min_header or header_size > model_size:
        raise ValueError(
            f"Invalid header_size={header_size} for FLUTE v{version} (model_size={model_size})"
        )
    return version, header_size, count


def derive_key(seed: bytes, nonce: bytes, header_size: int) -> bytes:
    if len(seed) != 32:
        raise ValueError("Root seed must be 32 bytes")
    if len(nonce) != 12:
        raise ValueError("Nonce must be 12 bytes")
    buffer = bytearray(seed)
    for index, value in enumerate(nonce):
        buffer[index] ^= value
    size_bytes = struct.pack("<Q", header_size)
    for index, value in enumerate(size_bytes):
        buffer[24 + index] ^= value
    cipher = ChaCha20.new(key=bytes(buffer), nonce=nonce)
    return cipher.encrypt(b"\x00" * 32)


def decode_xor_prefix(data: bytes) -> bytes:
    return bytes(value ^ XOR_MASK[i % len(XOR_MASK)] ^ (i & 255) for i, value in enumerate(data))


def parse_directory(data: bytes, count: int, header_size: int, model_size: int):
    offset = 0
    entries = []
    expected_offset = header_size
    for _ in range(count):
        nul = data.find(b"\x00", offset)
        if nul < 0:
            raise ValueError("Truncated filename in directory")
        name = data[offset:nul].decode("ascii")
        offset = nul + 1
        if len(data) - offset < 24:
            raise ValueError("Truncated directory entry metadata")
        file_offset, size, mtime = struct.unpack_from("<qqq", data, offset)
        offset += 24
        if file_offset != expected_offset or size < 0 or file_offset + size > model_size:
            raise ValueError("Corrupt directory offsets or sizes")
        entries.append(dict(name=name, offset=file_offset, size=size, mtime=mtime))
        expected_offset += size
    if offset != len(data):
        raise ValueError("Trailing bytes in directory payload")
    if expected_offset != model_size:
        raise ValueError("Directory does not account for the entire file")
    return entries


def verify_payload_xor(model_path: Path, entries: list) -> bool:
    for target_name, expected_prefix in (
        ("config.yaml", b"objects:"),
        ("asr/feature_extractor/fbank.conf", b"--sample-frequency="),
        ("model_md5s.txt", b"# MD5 for Panther Lite"),
    ):
        for entry in entries:
            if entry["name"].lstrip("/") == target_name:
                with model_path.open("rb") as f:
                    f.seek(entry["offset"])
                    chunk = f.read(min(4096, entry["size"]))
                if decode_xor_prefix(chunk).startswith(expected_prefix):
                    return True
    return False


def _lookup_manifest_metadata(model_path: Path) -> dict:
    manifest_file = DOUBAO_SUPPORT_DIR / "ASRContext/offline_model_manifest.json"
    if not manifest_file.is_file():
        return {}
    try:
        resolved = model_path.expanduser().resolve()
        manifest = json.loads(manifest_file.read_text())
        for logical_name, records in manifest.get("models", {}).items():
            for record in records if isinstance(records, list) else []:
                rel = record.get("installRelativePath")
                if not rel:
                    continue
                if (DOUBAO_SUPPORT_DIR / rel).resolve() == resolved:
                    meta = {}
                    name = record.get("logicalName") or logical_name
                    version = record.get("version")
                    if name:
                        meta["model_name"] = str(name)
                    if version:
                        meta["model_version"] = str(version)
                    return meta
    except Exception:
        pass
    return {}


def detect_model_metadata(model_path: Path, entries: list) -> dict:
    meta = {}
    for entry in entries:
        if entry["name"].lstrip("/") == "config.yaml":
            try:
                with model_path.open("rb") as f:
                    f.seek(entry["offset"])
                    chunk = f.read(min(4096, entry["size"]))
                decoded = decode_xor_prefix(chunk).decode("utf-8", errors="ignore")
                m = re.search(r"model_version:\s*([A-Za-z0-9_.-]+)", decoded)
                if m:
                    meta["config_label"] = m.group(1)
            except Exception:
                pass
            break

    manifest_meta = _lookup_manifest_metadata(model_path)
    meta.update(manifest_meta)

    parts = model_path.expanduser().resolve().parts
    if "versions" in parts and ("model_name" not in meta or "model_version" not in meta):
        idx = parts.index("versions")
        tail = parts[idx + 1 :]
        if len(tail) >= 3:
            meta.setdefault("model_name", tail[0])
            ver_match = re.match(r"^(\d+)_(\d+)(?:_[0-9a-f]{32})?$", tail[1])
            if ver_match:
                meta.setdefault("model_version", f"{ver_match.group(1)}.{ver_match.group(2)}")
        elif len(tail) == 2:
            ver_match = re.match(r"^(\d+)_(\d+)$", tail[0])
            if ver_match:
                meta.setdefault("model_version", f"{ver_match.group(1)}.{ver_match.group(2)}")

    label = meta.get("config_label", "")
    if "model_name" not in meta:
        if label.startswith("LiteASRP_v1.1"):
            meta["model_name"] = "acllm_main_model_mac"
        elif label.startswith("LiteASRP_"):
            meta["model_name"] = "acllm_pro_model_mac"
        elif label.startswith("LiteASRm_"):
            meta["model_name"] = "acllm_general_model_mac"

    return meta


def verify_model(
    model_path: Path,
    seed_file: Path,
    key_file: Path | None = None,
    reference_directory: Path | None = None,
) -> dict:
    model_size = model_path.stat().st_size
    with model_path.open("rb") as file:
        version, header_size, count = read_container_prefix(file, model_size)
        file.seek(0)
        header = file.read(header_size)

    result = dict(
        model=format_model_path(model_path),
        model_bytes=model_size,
        layout_version=version,
        header_size=header_size,
        internal_files=count,
        payload_xor_verified=False,
        candidate_verified=False,
        attempts=[],
    )

    valid_entries = []
    if version == 2:
        result["key_source"] = "unencrypted plaintext directory (FLUTE v2)"
        directory = header[21:]
        try:
            entries = parse_directory(directory, count, header_size, model_size)
        except (ValueError, UnicodeDecodeError, struct.error) as error:
            result["error"] = str(error)
        else:
            if reference_directory:
                matches = directory == reference_directory.read_bytes()
                result["matches_reference"] = matches
                if not matches:
                    raise ValueError("Parsed directory differs from the reference directory")
            result["candidate_verified"] = True
            result["entries"] = entries
            result["directory_sha256"] = hashlib.sha256(directory).hexdigest()
            valid_entries = entries
    elif version == 3:
        nonce = header[21:33]
        if key_file:
            key = load_32_byte_file(key_file, "Key")
            key_source = "provided key"
        else:
            seed = load_32_byte_file(seed_file, "Seed")
            key = derive_key(seed, nonce, header_size)
            key_source = "derived from seed and model metadata"
        result["key_source"] = key_source
        result["nonce"] = nonce.hex()
        result["derived_key"] = key.hex()

        for counter in (0, 1):
            cipher = ChaCha20.new(key=key, nonce=nonce)
            cipher.seek(counter * 64)
            directory = cipher.decrypt(header[33:])
            attempt = dict(counter=counter, valid=False)
            try:
                entries = parse_directory(directory, count, header_size, model_size)
            except (ValueError, UnicodeDecodeError, struct.error) as error:
                attempt["error"] = str(error)
            else:
                attempt.update(
                    valid=True,
                    entries=entries,
                    directory_sha256=hashlib.sha256(directory).hexdigest(),
                )
                if reference_directory:
                    attempt["matches_reference"] = directory == reference_directory.read_bytes()
                    if not attempt["matches_reference"]:
                        raise ValueError(
                            "Independent decryption differs from the reference directory"
                        )
                result["candidate_verified"] = True
                valid_entries = entries
            result["attempts"].append(attempt)

    if valid_entries:
        result["payload_xor_verified"] = verify_payload_xor(model_path, valid_entries)
        if not result["payload_xor_verified"]:
            raise ValueError(
                "Payload XOR mask check failed on config.yaml / fbank.conf / model_md5s.txt"
            )
        meta = detect_model_metadata(model_path, valid_entries)
        result.update(meta)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Verify Doubao IME FLUTE v2/v3 ASR model containers."
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=None,
        help="Path to asr_model.model (defaults to currently active model)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Discover and verify all locally installed asr_model.model files",
    )
    parser.add_argument(
        "--seed-file",
        type=Path,
        default=Path(__file__).with_name("flute-v3-seed.bin"),
        help="Path to the 32-byte root seed (FLUTE v3)",
    )
    parser.add_argument(
        "--key-file",
        type=Path,
        default=None,
        help="Optional 32-byte key file to skip derivation (FLUTE v3)",
    )
    parser.add_argument(
        "--reference-directory",
        type=Path,
        default=None,
        help="Optional reference binary directory to compare against",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional destination path for JSON verification report",
    )
    args = parser.parse_args()

    if args.all:
        models = discover_local_models()
        if not models:
            parser.error("No locally installed asr_model.model found")
        results = [
            verify_model(m, args.seed_file, args.key_file, args.reference_directory)
            for m in models
        ]
        encoded = json.dumps(results, ensure_ascii=False, indent=2) + "\n"
        ok = all(r["candidate_verified"] for r in results)
    else:
        model_path = (args.model if args.model else resolve_default_model()).expanduser().resolve()
        if not model_path.is_file():
            parser.error(f"Model file not found: {model_path}")
        result = verify_model(model_path, args.seed_file, args.key_file, args.reference_directory)
        encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        ok = result["candidate_verified"]

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(encoded)
    print(encoded, end="")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
