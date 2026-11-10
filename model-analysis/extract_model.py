import argparse
from contextlib import nullcontext
import hashlib
import json
import os
import re
import struct
from pathlib import Path, PurePosixPath

import numpy as np
from Crypto.Cipher import ChaCha20

from verify_directory import MODEL, derive_key, parse_directory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    model_size = MODEL.stat().st_size
    seed = Path(__file__).with_name('model-seed.bin').read_bytes()
    mask = b'symphony'
    pattern = np.array([mask[i % 8] ^ i for i in range(256)], dtype=np.uint8)
    source_md5 = hashlib.md5()
    extracted = []
    with MODEL.open('rb') as source:
        header = source.read(1143)
        version, header_size, count = struct.unpack_from('<IQI', header, 5)
        if (header[:5], version, header_size, count) != (b'FLUTE', 3, 1143, 20):
            raise ValueError('The model differs from the verified FLUTE v3 layout')
        key = derive_key(seed, header[21:33], header_size)
        cipher = ChaCha20.new(key=key, nonce=header[21:33])
        cipher.seek(64)
        entries = parse_directory(cipher.decrypt(header[33:]), count, header_size, model_size)
        paths = []
        for entry in entries:
            path = PurePosixPath(entry['name'].lstrip('/'))
            if not path.parts or '..' in path.parts or str(path) == '.':
                raise ValueError('Unsafe internal filename')
            paths.append(path)
        if len(set(paths)) != len(paths):
            raise ValueError('Duplicate internal filename')
        if args.verify_only:
            if not output.is_dir():
                raise ValueError('The output directory does not exist')
        else:
            output.mkdir()
        source_md5.update(header)
        for entry, path in zip(entries, paths):
            target = output.joinpath(*path.parts)
            if not args.verify_only:
                target.parent.mkdir(parents=True, exist_ok=True)
            remaining = entry['size']
            position = 0
            md5 = hashlib.md5()
            sha256 = hashlib.sha256()
            if source.tell() != entry['offset']:
                raise ValueError('The source position differs from the directory')
            with nullcontext(None) if args.verify_only else target.open('xb') as destination:
                while remaining:
                    chunk = source.read(min(4 * 1024 * 1024, remaining))
                    if not chunk:
                        raise EOFError('Model ended before the internal file was complete')
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
                os.utime(target, (entry['mtime'], entry['mtime']))
            extracted.append(dict(path=str(path), bytes=entry['size'],
                                  md5=md5.hexdigest(), sha256=sha256.hexdigest()))
            action = 'Verified source payload' if args.verify_only else 'Extracted'
            print(f"{action} {path} ({entry['size']} bytes)", flush=True)
    if source_md5.hexdigest() != 'c31bdfbd138e9beac48e02672f98f1e8':
        raise ValueError('Source model MD5 differs from the verified model')
    for entry in extracted:
        target = output / entry['path']
        digest = hashlib.sha256()
        with target.open('rb') as file:
            while chunk := file.read(4 * 1024 * 1024):
                digest.update(chunk)
        if target.stat().st_size != entry['bytes'] or digest.hexdigest() != entry['sha256']:
            raise ValueError(f"Written file failed verification: {entry['path']}")
    expected = []
    mismatches = []
    actual = {entry['path']: entry for entry in extracted}
    for line in (output / 'model_md5s.txt').read_text().splitlines():
        match = re.fullmatch(r'([0-9a-f]{32})\s+(.+)', line)
        if not match:
            if line.strip() and not line.startswith('#'):
                raise ValueError('Unrecognized model MD5 entry')
            continue
        digest, path = match.groups()
        if path not in actual:
            raise ValueError(f'The manifest references an absent file: {path}')
        if actual[path]['md5'] != digest:
            mismatches.append(dict(path=path, expected_md5=digest, actual_md5=actual[path]['md5']))
        expected.append(path)
    if len(expected) != 8:
        raise ValueError('The internal MD5 manifest differs from the verified model')
    report = dict(source='~/' + str(MODEL.relative_to(Path.home())), source_bytes=model_size,
                  source_md5=source_md5.hexdigest(), extraction_verified=True,
                  extracted_files=len(extracted), extracted_bytes=sum(e['bytes'] for e in extracted),
                  written_files_verified=len(extracted), model_md5_entries_checked=len(expected),
                  model_md5_entries_matched=len(expected)-len(mismatches),
                  model_md5_manifest_matches=not mismatches, model_md5_mismatches=mismatches,
                  files=extracted)
    (output / 'extraction-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f'Verified all {len(extracted)} output files against decrypted source payloads.', flush=True)
    print(f'Internal model MD5 manifest: {len(expected)-len(mismatches)} matched, {len(mismatches)} mismatched.', flush=True)
    print(output, flush=True)


if __name__ == '__main__':
    main()
