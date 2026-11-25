#!/usr/bin/env python3
"""Extract and verify internal files from FLUTE v2/v3 ASR model containers.

Supports:
- 1.1.2 acllm_pro_model_mac (FLUTE v3, 1.48 GB, 6 packed files)
- 1.1.2 acllm_general_model_mac (FLUTE v2, 463 MB, 6 packed files)
- 1.1.0 acllm_main_model_mac (FLUTE v3, 825 MB, 20 loose files)
"""

import argparse
from contextlib import nullcontext
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re

import numpy as np
from Crypto.Cipher import ChaCha20

from verify_directory import (
    XOR_MASK,
    derive_key,
    detect_model_metadata,
    format_model_path,
    load_32_byte_file,
    parse_directory,
    read_container_prefix,
    resolve_default_model,
)


def main():
    parser = argparse.ArgumentParser(
        description="Extract and verify internal files from FLUTE v2/v3 ASR model containers."
    )
    parser.add_argument("output", type=Path, help="Directory to extract or verify files in")
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
        "--verify-only",
        action="store_true",
        help="Verify already-extracted files in <output> against the source model without writing",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional path to write extraction JSON report (defaults to <output>/extraction-report.json when extracting; omitted in --verify-only unless specified)",
    )
    args = parser.parse_args()

    model_path = (args.model if args.model else resolve_default_model()).expanduser().resolve()
    if not model_path.is_file():
        parser.error(f"Model file not found: {model_path}")

    output = args.output.expanduser().resolve()
    model_size = model_path.stat().st_size
    pattern = np.array([XOR_MASK[i % len(XOR_MASK)] ^ i for i in range(256)], dtype=np.uint8)
    source_md5 = hashlib.md5()
    extracted = []

    with model_path.open("rb") as source:
        version, header_size, count = read_container_prefix(source, model_size)
        source.seek(0)
        header = source.read(header_size)
        source_md5.update(header)

        if version == 2:
            directory = header[21:]
        else:
            seed = load_32_byte_file(args.seed_file, "Seed")
            nonce = header[21:33]
            key = derive_key(seed, nonce, header_size)
            cipher = ChaCha20.new(key=key, nonce=nonce)
            cipher.seek(64)
            directory = cipher.decrypt(header[33:])

        entries = parse_directory(directory, count, header_size, model_size)
        paths = []
        for entry in entries:
            path = PurePosixPath(entry["name"].lstrip("/"))
            if not path.parts or ".." in path.parts or str(path) == ".":
                raise ValueError(f"Unsafe internal filename: {entry['name']!r}")
            paths.append(path)
        if len(set(paths)) != len(paths):
            raise ValueError("Duplicate internal filename")

        if args.verify_only:
            if not output.is_dir():
                raise ValueError(f"Output directory does not exist: {output}")
        else:
            output.mkdir(parents=True, exist_ok=True)

        for entry, path in zip(entries, paths):
            target = output.joinpath(*path.parts)
            if not args.verify_only:
                target.parent.mkdir(parents=True, exist_ok=True)
            remaining = entry["size"]
            position = 0
            md5 = hashlib.md5()
            sha256 = hashlib.sha256()
            if source.tell() != entry["offset"]:
                raise ValueError("Source position differs from directory offset")

            with nullcontext(None) if args.verify_only else target.open("wb") as destination:
                while remaining:
                    chunk = source.read(min(4 * 1024 * 1024, remaining))
                    if not chunk:
                        raise EOFError("Model ended before internal file was complete")
                    source_md5.update(chunk)
                    data = np.frombuffer(chunk, dtype=np.uint8)
                    offsets = (np.arange(len(chunk), dtype=np.uint32) + position % 256) & 255
                    decoded = np.bitwise_xor(data, pattern[offsets]).tobytes()
                    if destination is not None:
                        destination.write(decoded)
                    md5.update(decoded)
                    sha256.update(decoded)
                    remaining -= len(chunk)
                    position += len(chunk)

            if not args.verify_only:
                os.utime(target, (entry["mtime"], entry["mtime"]))
            extracted.append(
                dict(
                    path=str(path),
                    size=entry["size"],
                    md5=md5.hexdigest(),
                    sha256=sha256.hexdigest(),
                )
            )
            action = "Hashed source" if args.verify_only else "Extracted"
            print(f"{action} {path} ({entry['size']} bytes)", flush=True)

    # Verify extracted files on disk against decrypted source payloads (both extract and --verify-only)
    for entry in extracted:
        target = output.joinpath(*PurePosixPath(entry["path"]).parts)
        if not target.is_file():
            raise ValueError(f"Missing extracted file: {target}")
        if target.stat().st_size != entry["size"]:
            raise ValueError(
                f"Size mismatch for {entry['path']}: expected {entry['size']}, got {target.stat().st_size}"
            )
        digest = hashlib.sha256()
        with target.open("rb") as file:
            while chunk := file.read(4 * 1024 * 1024):
                digest.update(chunk)
        if digest.hexdigest() != entry["sha256"]:
            raise ValueError(f"SHA-256 mismatch for {entry['path']}")

    # Check internal model_md5s.txt only if the container actually contains it (e.g. legacy 1.1.0)
    actual = {entry["path"]: entry for entry in extracted}
    expected = []
    mismatches = []
    has_manifest = "model_md5s.txt" in actual
    if has_manifest:
        manifest_file = output / "model_md5s.txt"
        for line in manifest_file.read_text().splitlines():
            match = re.fullmatch(r"([0-9a-f]{32})\s+(.+)", line)
            if not match:
                if line.strip() and not line.startswith("#"):
                    raise ValueError("Unrecognized model MD5 entry")
                continue
            digest, path = match.groups()
            if path not in actual:
                raise ValueError(f"Manifest references an absent file: {path}")
            if actual[path]["md5"] != digest:
                mismatches.append(dict(path=path, expected_md5=digest, actual_md5=actual[path]["md5"]))
            expected.append(path)

    meta = detect_model_metadata(model_path, entries)

    report = dict(
        source=format_model_path(model_path),
        model_name=meta.get("model_name"),
        model_version=meta.get("model_version"),
        config_label=meta.get("config_label"),
        source_bytes=model_size,
        source_md5=source_md5.hexdigest(),
        layout_version=version,
        extraction_verified=True,
        extracted_files=len(extracted),
        extracted_bytes=sum(e["size"] for e in extracted),
        written_files_verified=len(extracted),
        model_md5_entries_checked=len(expected),
        model_md5_entries_matched=len(expected) - len(mismatches),
        model_md5_manifest_matches=(not mismatches) if has_manifest else None,
        model_md5_mismatches=mismatches,
        files=extracted,
    )
    report_path = (
        args.report.expanduser().resolve()
        if args.report
        else (None if args.verify_only else output / "extraction-report.json")
    )
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"Verified all {len(extracted)} files on disk against decrypted source payloads.", flush=True)
    if has_manifest:
        print(
            f"Internal model MD5 manifest: {len(expected) - len(mismatches)} matched, {len(mismatches)} mismatched.",
            flush=True,
        )
    if report_path is not None:
        print(f"Report written to: {report_path}", flush=True)


if __name__ == "__main__":
    main()
