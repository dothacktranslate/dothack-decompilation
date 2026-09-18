#!/usr/bin/env python3

from pathlib import Path

INPUT = Path("build/research/ccc/files.txt")
UNCC_DIR = Path("build/research/uncc")

SOURCES = UNCC_DIR / "SOURCES.txt"
ADDRESS_MAP = Path("build/research/ccc/source-address-map.tsv")
UNRESOLVED = Path("build/research/ccc/source-address-unresolved.txt")

if not INPUT.exists():
    raise SystemExit(f"ERROR: {INPUT} does not exist")

UNCC_DIR.mkdir(parents=True, exist_ok=True)


def normalize_path(path: str) -> str:
    path = path.replace("\\", "/")

    game_prefix = "D:/usr/RpgUS/prog/"
    cw_prefix = "C:/CodeWarrior/"

    if path.lower().startswith(game_prefix.lower()):
        # Preserve the original prog/source and prog/system layout.
        return "prog/" + path[len(game_prefix):]

    if path.lower().startswith(cw_prefix.lower()):
        # Keep SDK/MSL files isolated from reconstructed game sources.
        return "sdk/CodeWarrior/" + path[len(cw_prefix):]

    # Fallback for anything unexpected.
    path = path.replace(":", "")
    return "unknown/" + path.lstrip("/")


entries = []
addressed = []
unresolved = []

seen_sources = set()

for raw in INPUT.read_text(errors="replace").splitlines():
    raw = raw.strip()

    if not raw:
        continue

    parts = raw.split(maxsplit=1)

    if len(parts) != 2:
        continue

    address_text, original_path = parts
    normalized = normalize_path(original_path)

    # SOURCES.txt should contain each source path once.
    if normalized not in seen_sources:
        entries.append(normalized)
        seen_sources.add(normalized)

    try:
        address = int(address_text, 16)
    except ValueError:
        continue

    if address == 0xFFFFFFFF:
        unresolved.append((original_path, normalized))
    else:
        addressed.append((address, original_path, normalized))


SOURCES.write_text(
    "\n".join(entries) + "\n",
    encoding="utf-8",
)

with ADDRESS_MAP.open("w", encoding="utf-8") as f:
    f.write("address\toriginal_path\tnormalized_path\n")

    for address, original, normalized in sorted(addressed):
        f.write(
            f"0x{address:08X}\t"
            f"{original}\t"
            f"{normalized}\n"
        )

with UNRESOLVED.open("w", encoding="utf-8") as f:
    for original, normalized in unresolved:
        f.write(f"{original}\t{normalized}\n")


print(f"SOURCES.txt entries:      {len(entries)}")
print(f"Addressed source records: {len(addressed)}")
print(f"Unresolved records:       {len(unresolved)}")
print()
print(f"Wrote: {SOURCES}")
print(f"Wrote: {ADDRESS_MAP}")
print(f"Wrote: {UNRESOLVED}")
