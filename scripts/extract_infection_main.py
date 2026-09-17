#!/usr/bin/env python3

from pathlib import Path
import hashlib
import sys

SOURCE = Path("disc/infection/root/SLUS_202.67")
OUTPUT = Path("build/infection/SLUS_202.67.main.bin")

FILE_OFFSET = 0x100
FILE_SIZE = 0x278880

if not SOURCE.exists():
    print(f"ERROR: {SOURCE} not found.")
    sys.exit(1)

data = SOURCE.read_bytes()

if data[:4] != b"\x7fELF":
    print("ERROR: SLUS_202.67 is not an ELF file.")
    sys.exit(1)

end = FILE_OFFSET + FILE_SIZE

if len(data) < end:
    print("ERROR: SLUS_202.67 is smaller than expected.")
    sys.exit(1)

runtime = data[FILE_OFFSET:end]

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_bytes(runtime)

sha1 = hashlib.sha1(runtime).hexdigest()
sha256 = hashlib.sha256(runtime).hexdigest()

print(f"Wrote:  {OUTPUT}")
print(f"Size:   {len(runtime)} bytes (0x{len(runtime):X})")
print(f"SHA-1:  {sha1}")
print(f"SHA256: {sha256}")
