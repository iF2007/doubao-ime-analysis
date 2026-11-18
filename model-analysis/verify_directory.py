#!/usr/bin/env python3
import argparse
import hashlib
import json
import struct
from pathlib import Path

from Crypto.Cipher import ChaCha20

DEFAULT_PRO_MODEL = (
    Path.home()
    / "Library/Application Support/DoubaoIme/ASRModel/versions/acllm_pro_model_mac/1_5_4f19c90670291b502a4dd34b936e5f2f/asr_model.model"
)
DEFAULT_GENERAL_MODEL = (
    Path.home()
    / "Library/Application Support/DoubaoIme/ASRModel/versions/acllm_general_model_mac/1_8_a6846b0a91ac8a9579468e252c1da2e5/asr_model.model"
)
DEFAULT_LEGACY_MODEL = (
    Path.home()
    / "Library/Application Support/DoubaoIme/ASRModel/versions/1_8/asr_model.model"
)


def resolve_default_model():
    base_dir = Path.home() / "Library/Application Support/DoubaoIme"
    layout_file = base_dir / "ASRContext/offline_model_active_layout.json"
    if layout_file.exists():
        try:
            layout = json.loads(layout_file.read_text())
            selected = layout.get("selectedMainModelName")
            paths = layout.get("mainModelPaths", {})
            if selected and selected in paths:
                p = base_dir / paths[selected]
                if p.exists():
                    return p
            for rel in paths.values():
                p = base_dir / rel
                if p.exists():
                    return p
        except Exception:
            pass
    for candidate in [DEFAULT_PRO_MODEL, DEFAULT_GENERAL_MODEL, DEFAULT_LEGACY_MODEL]:
        if candidate.exists():
            return candidate
    return DEFAULT_PRO_MODEL


def derive_key(seed, nonce, header_size):
    if len(seed) != 32 or len(nonce) != 12:
        raise ValueError("The seed must be 32 bytes and the nonce 12 bytes")
    mixed = bytearray(seed)
    for i, value in enumerate(nonce):
        mixed[i] ^= value
    for i, value in enumerate(struct.pack("<Q", header_size)):
        mixed[24 + i] ^= value
    cipher = ChaCha20.new(key=bytes(mixed), nonce=nonce)
    return cipher.encrypt(bytes(32))


def parse_directory(data, count, header_size, model_size):
    position = 0
    previous_end = header_size
    entries = []
    for _ in range(count):
        end = data.index(0, position)
        name = data[position:end].decode("ascii")
        if not name or any(ord(c) < 32 or ord(c) > 126 for c in name):
            raise ValueError("Invalid internal filename")
        offset, size, mtime = struct.unpack_from("<qqq", data, end + 1)
        if offset != previous_end or size < 0 or offset + size > model_size:
            raise ValueError("Invalid internal file bounds")
        entries.append(dict(name=name, offset=offset, size=size, mtime=mtime))
        previous_end = offset + size
        position = end + 25
    if position != len(data) or previous_end != model_size:
        raise ValueError("Directory does not account for the complete model")
    return entries


def main():
    parser = argparse.ArgumentParser(
        description="Verify FLUTE v2/v3 ASR model container directories and key derivation."
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=None,
        help="Path to asr_model.model (defaults to currently active model)",
    )
    parser.add_argument("--key-file", type=Path)
    parser.add_argument(
        "--seed-file",
        type=Path,
        default=Path(__file__).with_name("model-seed.bin"),
    )
    parser.add_argument("--reference-directory", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    model_path = args.model if args.model else resolve_default_model()
    if not model_path.exists():
        parser.error(f"Model file not found: {model_path}")

    model_size = model_path.stat().st_size
    with model_path.open("rb") as file:
        prefix = file.read(21)
        if len(prefix) < 21:
            raise ValueError("File too short to be a valid FLUTE model")
        magic = prefix[:5]
        version, header_size, count = struct.unpack_from("<IQI", prefix, 5)
        if magic != b"FLUTE" or version not in (2, 3):
            raise ValueError(f"Unsupported model container: magic={magic}, version={version}")

        file.seek(header_size)
        payload = file.read(4096)

    # Verify payload XOR mask
    mask = b"symphony"
    decoded = bytes(value ^ mask[i % len(mask)] ^ (i & 255) for i, value in enumerate(payload))
    if not (decoded.startswith(b"objects:") or decoded.startswith(b"# MD5 for Panther Lite")):
        raise ValueError("The independently verified payload XOR mask no longer matches")

    result = dict(
        model="~/" + str(model_path.relative_to(Path.home())),
        model_bytes=model_size,
        layout_version=version,
        header_size=header_size,
        internal_files=count,
        payload_xor_verified=True,
        candidate_verified=False,
        attempts=[],
    )

    if version == 2:
        # FLUTE v2 uses unencrypted directory starting directly at offset 21
        result["key_source"] = "unencrypted plaintext directory (FLUTE v2)"
        with model_path.open("rb") as file:
            file.seek(21)
            directory = file.read(header_size - 21)
        entries = parse_directory(directory, count, header_size, model_size)
        result["candidate_verified"] = True
        result["entries"] = entries
        result["directory_sha256"] = hashlib.sha256(directory).hexdigest()
    elif version == 3:
        # FLUTE v3 uses ChaCha20 encrypted directory
        with model_path.open("rb") as file:
            file.seek(0)
            header = file.read(header_size)
        nonce = header[21:33]
        key = (
            args.key_file.read_bytes()
            if args.key_file
            else derive_key(args.seed_file.read_bytes(), nonce, header_size)
        )
        if len(key) != 32:
            parser.error("The key must contain exactly 32 raw bytes")
        result["key_source"] = (
            "provided key" if args.key_file else "derived from seed and model metadata"
        )
        result["nonce"] = nonce.hex()
        result["derived_key"] = key.hex()

        for counter in (0, 1):
            cipher = ChaCha20.new(key=key, nonce=nonce)
            cipher.seek(counter * 64)
            directory = cipher.decrypt(header[33:header_size])
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
            result["attempts"].append(attempt)

    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.write_text(encoded)
    print(encoded, end="")
    return 0 if result["candidate_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
