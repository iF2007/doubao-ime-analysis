#!/usr/bin/env python3
"""Verify Doubao IME FLUTE v2/v3 ASR model directory, header layout, and key derivation.

Supports:
- 1.1.1 acllm_pro_model_mac (FLUTE v3, 1.48 GB, 6 packed files)
- 1.1.1 acllm_general_model_mac (FLUTE v2, 463 MB, 6 packed files)
- 1.1.0 acllm_main_model_mac (FLUTE v3, 825 MB, 20 loose files)
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

from Crypto.Cipher import ChaCha20


XOR_MASK = b"symphony"

DEFAULT_MODELS = [
    Path.home()
    / "Library/Application Support/DoubaoIme/ASRModel/versions/acllm_pro_model_mac/1_5_4f19c90670291b502a4dd34b936e5f2f/asr_model.model",
    Path.home()
    / "Library/Application Support/DoubaoIme/ASRModel/versions/acllm_general_model_mac/1_8_a6846b0a91ac8a9579468e252c1da2e5/asr_model.model",
    Path.home()
    / "Library/Application Support/DoubaoIme/ASRModel/versions/1_8/asr_model.model",
]


def format_model_path(path: Path) -> str:
    resolved = path.expanduser().resolve()
    try:
        return "~/" + str(resolved.relative_to(Path.home().resolve()))
    except ValueError:
        return str(resolved)


def resolve_default_model() -> Path:
    layout_file = (
        Path.home()
        / "Library/Application Support/DoubaoIme/ASRContext/offline_model_active_layout.json"
    )
    if layout_file.exists():
        try:
            data = json.loads(layout_file.read_text())
            selected = data.get("selectedMainModelName")
            rel_path = data.get("mainModelPaths", {}).get(selected)
            if rel_path:
                candidate = (
                    Path.home()
                    / "Library/Application Support/DoubaoIme"
                    / rel_path
                )
                if candidate.exists():
                    return candidate
        except Exception:
            pass

    for candidate in DEFAULT_MODELS:
        if candidate.exists():
            return candidate

    return DEFAULT_MODELS[0]


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
        ("model_md5s.txt", b"# MD5 for Panther Lite"),
    ):
        for entry in entries:
            if entry["name"].lstrip("/") == target_name:
                with model_path.open("rb") as f:
                    f.seek(entry["offset"])
                    chunk = f.read(min(4096, entry["size"]))
                return decode_xor_prefix(chunk).startswith(expected_prefix)
    return False


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

    path_str = str(model_path)
    label = meta.get("config_label", "")
    if "acllm_pro_model_mac" in path_str or label.startswith("LiteASRP_v1.2"):
        meta["model_name"] = "acllm_pro_model_mac"
        meta["model_version"] = "1.5"
    elif "acllm_general_model_mac" in path_str or label.startswith("LiteASRm_"):
        meta["model_name"] = "acllm_general_model_mac"
        meta["model_version"] = "1.8"
    elif "acllm_main_model_mac" in path_str or label.startswith("LiteASRP_v1.1"):
        meta["model_name"] = "acllm_main_model_mac"
        meta["model_version"] = "1.8"

    return meta


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
        "--seed-file",
        type=Path,
        default=Path(__file__).with_name("model-seed.bin"),
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

    model_path = (args.model if args.model else resolve_default_model()).expanduser().resolve()
    if not model_path.is_file():
        parser.error(f"Model file not found: {model_path}")

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
        entries = parse_directory(directory, count, header_size, model_size)
        if args.reference_directory:
            matches = directory == args.reference_directory.read_bytes()
            result["matches_reference"] = matches
            if not matches:
                raise ValueError("Parsed directory differs from the reference directory")
        result["candidate_verified"] = True
        result["entries"] = entries
        result["directory_sha256"] = hashlib.sha256(directory).hexdigest()
        valid_entries = entries
    elif version == 3:
        nonce = header[21:33]
        if args.key_file:
            key = load_32_byte_file(args.key_file, "Key")
            key_source = "provided key"
        else:
            seed = load_32_byte_file(args.seed_file, "Seed")
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
                if args.reference_directory:
                    attempt["matches_reference"] = directory == args.reference_directory.read_bytes()
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
            raise ValueError("Payload XOR mask check failed on config.yaml / model_md5s.txt")
        meta = detect_model_metadata(model_path, valid_entries)
        result.update(meta)

    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(encoded)
    print(encoded, end="")
    return 0 if result["candidate_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
