#!/usr/bin/env python3

from pathlib import Path
import collections
import re
import subprocess
import sys

ELF = Path("disc/infection/root/SLUS_202.67")
OUTPUT = Path("config/infection/symbol_addrs.txt")

# Main resident EE code.
CODE_START = 0x00100000
CODE_END = 0x001DAC80

if not ELF.exists():
    print(f"ERROR: {ELF} not found.")
    sys.exit(1)

result = subprocess.run(
    ["readelf", "-W", "-s", str(ELF)],
    check=True,
    text=True,
    stdout=subprocess.PIPE,
)

symbols = []

pattern = re.compile(
    r"^\s*\d+:\s+"
    r"([0-9A-Fa-f]+)\s+"
    r"(\d+)\s+"
    r"FUNC\s+"
    r"\S+\s+"
    r"\S+\s+"
    r"(\S+)\s+"
    r"(.+?)\s*$"
)

for line in result.stdout.splitlines():
    match = pattern.match(line)

    if not match:
        continue

    address = int(match.group(1), 16)
    size = int(match.group(2))
    section = match.group(3)
    name = match.group(4)

    # Section 4 is the resident "main" section in SLUS_202.67.
    if section != "4":
        continue

    if not (CODE_START <= address < CODE_END):
        continue

    symbols.append((address, size, name))

symbols.sort()

name_counts = collections.Counter(name for _, _, name in symbols)
used_names = set()

def safe_name(name, address):
    # Most MWCC C++ mangled names are already assembler-safe.
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", name)

    if not cleaned:
        cleaned = f"func_{address:08X}"

    if cleaned[0].isdigit():
        cleaned = "_" + cleaned

    # A handful of PS2 SDK functions occur under the same local symbol name.
    if name_counts[name] > 1 or cleaned in used_names:
        cleaned = f"{cleaned}_{address:08X}"

    used_names.add(cleaned)
    return cleaned

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

with OUTPUT.open("w", encoding="utf-8") as f:
    f.write("// Auto-generated from the retail SLUS_202.67 symbol table.\n")
    f.write("// Resident main EE code only.\n\n")

    for address, size, original_name in symbols:
        name = safe_name(original_name, address)

        f.write(
            f"{name} = 0x{address:08X}; "
            f"// type:func size:0x{size:X}"
        )

        f.write("\n")

print(f"Wrote {len(symbols)} function symbols to {OUTPUT}")
