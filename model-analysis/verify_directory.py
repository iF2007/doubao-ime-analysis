#!/usr/bin/env python3
import argparse
import hashlib
import json
import struct
from pathlib import Path

from Crypto.Cipher import ChaCha20

MODEL = Path.home() / 'Library/Application Support/DoubaoIme/ASRModel/versions/1_8/asr_model.model'


def derive_key(seed, nonce, header_size):
    if len(seed) != 32 or len(nonce) != 12:
        raise ValueError('The seed must be 32 bytes and the nonce 12 bytes')
    mixed = bytearray(seed)
    for i, value in enumerate(nonce):
        mixed[i] ^= value
    for i, value in enumerate(struct.pack('<Q', header_size)):
        mixed[24 + i] ^= value
    cipher = ChaCha20.new(key=bytes(mixed), nonce=nonce)
    return cipher.encrypt(bytes(32))


def parse_directory(data, count, header_size, model_size):
    position = 0
    previous_end = header_size
    entries = []
    for _ in range(count):
        end = data.index(0, position)
        name = data[position:end].decode('ascii')
        if not name or any(ord(c) < 32 or ord(c) > 126 for c in name):
            raise ValueError('Invalid internal filename')
        offset, size, mtime = struct.unpack_from('<qqq', data, end + 1)
        if offset != previous_end or size < 0 or offset + size > model_size:
            raise ValueError('Invalid internal file bounds')
        entries.append(dict(name=name, offset=offset, size=size, mtime=mtime))
        previous_end = offset + size
        position = end + 25
    if position != len(data) or previous_end != model_size:
        raise ValueError('Directory does not account for the complete model')
    return entries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--key-file', type=Path)
    parser.add_argument('--seed-file', type=Path, default=Path(__file__).with_name('model-seed.bin'))
    parser.add_argument('--reference-directory', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    with MODEL.open('rb') as file:
        header = file.read(1143)
        payload = file.read(4096)
    magic = header[:5]
    version, header_size, count = struct.unpack_from('<IQI', header, 5)
    if (magic, version, header_size, count) != (b'FLUTE', 3, 1143, 20):
        raise ValueError('The installed model layout differs from the inspected layout')
    key = args.key_file.read_bytes() if args.key_file else derive_key(args.seed_file.read_bytes(), header[21:33], header_size)
    if len(key) != 32:
        parser.error('The candidate must contain exactly 32 raw bytes')
    mask = b'symphony'
    decoded = bytes(value ^ mask[i % len(mask)] ^ (i & 255) for i, value in enumerate(payload))
    expected_prefix = b'# MD5 for Panther Lite ownership-marked models\n'
    if not decoded.startswith(expected_prefix):
        raise ValueError('The independently verified payload XOR mask no longer matches')
    result = dict(model='~/' + str(MODEL.relative_to(Path.home())), model_bytes=MODEL.stat().st_size,
                  layout_version=version, header_size=header_size, internal_files=count,
                  payload_xor_verified=True, candidate_verified=False,
                  key_source='provided key' if args.key_file else 'derived from seed and model metadata', attempts=[])
    for counter in (0, 1):
        cipher = ChaCha20.new(key=key, nonce=header[21:33])
        cipher.seek(counter * 64)
        directory = cipher.decrypt(header[33:header_size])
        attempt = dict(counter=counter, valid=False)
        try:
            entries = parse_directory(directory, count, header_size, MODEL.stat().st_size)
        except (ValueError, UnicodeDecodeError, struct.error) as error:
            attempt['error'] = str(error)
        else:
            attempt.update(valid=True, entries=entries, directory_sha256=hashlib.sha256(directory).hexdigest())
            if args.reference_directory:
                attempt['matches_reference'] = directory == args.reference_directory.read_bytes()
                if not attempt['matches_reference']:
                    raise ValueError('Independent decryption differs from the reference directory')
            result['candidate_verified'] = True
        result['attempts'].append(attempt)
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.report:
        args.report.write_text(encoded)
    print(encoded, end='')
    return 0 if result['candidate_verified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
