#!/usr/bin/env python3

from pathlib import Path
import re

FILES_INPUT = Path("build/research/ccc/files.txt")
FUNCS_INPUT = Path("build/research/ccc/functions.cpp")

MAP_OUTPUT = Path("build/research/ccc/source-function-map.tsv")
SUMMARY_OUTPUT = Path("build/research/ccc/source-range-summary.txt")
UNMAPPED_OUTPUT = Path("build/research/ccc/unmapped-functions.txt")

# Current conservative EE code region used by our initial Splat config.
CODE_START = 0x00100000
CODE_END = 0x001DAC80


def normalize_path(path: str) -> str:
    return path.replace("\\", "/")


# ----------------------------------------------------------------------
# Parse source/debug markers.
# Format:
#
#   00100370 D:\usr\RpgUS\prog\system\sysmem.cpp
# ----------------------------------------------------------------------

markers = []

for line in FILES_INPUT.read_text(errors="replace").splitlines():
    line = line.strip()

    if not line:
        continue

    parts = line.split(maxsplit=1)

    if len(parts) != 2:
        continue

    addr_text, path = parts

    try:
        addr = int(addr_text, 16)
    except ValueError:
        continue

    # FFFFFFFF means CCC knows the filename but not a usable address.
    if addr == 0xFFFFFFFF:
        continue

    if not (CODE_START <= addr < CODE_END):
        continue

    markers.append({
        "address": addr,
        "path": normalize_path(path),
    })


# Sort and remove exact duplicate (address,path) pairs.
unique = {}
for marker in markers:
    unique[(marker["address"], marker["path"])] = marker

markers = sorted(
    unique.values(),
    key=lambda m: (m["address"], m["path"].lower())
)


# ----------------------------------------------------------------------
# Parse functions.cpp.
#
# Example:
#   /* 00100370 00000184 */ ccHeap::InitFirst(...) {}
# ----------------------------------------------------------------------

func_re = re.compile(
    r"^/\*\s*"
    r"([0-9A-Fa-f]{8})\s+"
    r"([0-9A-Fa-f]{8})"
    r"\s*\*/\s+"
    r"(.+?)\s*\{"
)

functions = []

for line in FUNCS_INPUT.read_text(errors="replace").splitlines():
    match = func_re.match(line.strip())

    if not match:
        continue

    addr = int(match.group(1), 16)
    size = int(match.group(2), 16)
    declaration = match.group(3).strip()

    if not (CODE_START <= addr < CODE_END):
        continue

    # Strip the placeholder parameter text for a cleaner research display.
    declaration = declaration.replace("(/* parameters unknown */)", "()")

    functions.append({
        "address": addr,
        "size": size,
        "declaration": declaration,
    })

functions.sort(key=lambda f: f["address"])


# ----------------------------------------------------------------------
# Build marker ranges.
#
# The range end is the next source marker.
#
# IMPORTANT:
# This means "nearest preceding debug/source marker", NOT "confirmed
# translation-unit boundary".
# ----------------------------------------------------------------------

ranges = []

for index, marker in enumerate(markers):
    start = marker["address"]

    if index + 1 < len(markers):
        end = markers[index + 1]["address"]
    else:
        end = CODE_END

    ranges.append({
        "start": start,
        "end": end,
        "path": marker["path"],
        "functions": [],
    })


# ----------------------------------------------------------------------
# Assign each function to the nearest preceding marker.
# ----------------------------------------------------------------------

unmapped = []

range_index = 0

for function in functions:

    while (
        range_index + 1 < len(ranges)
        and function["address"] >= ranges[range_index]["end"]
    ):
        range_index += 1

    current = ranges[range_index] if ranges else None

    if (
        current is not None
        and current["start"] <= function["address"] < current["end"]
    ):
        current["functions"].append(function)
    else:
        unmapped.append(function)


# ----------------------------------------------------------------------
# Write detailed TSV.
# ----------------------------------------------------------------------

with MAP_OUTPUT.open("w", encoding="utf-8") as f:
    f.write(
        "marker_start\tmarker_end\tsource_path\t"
        "function_address\tfunction_size\tfunction\n"
    )

    for r in ranges:
        if not r["functions"]:
            f.write(
                f"0x{r['start']:08X}\t"
                f"0x{r['end']:08X}\t"
                f"{r['path']}\t"
                f"\t\t\n"
            )
            continue

        for function in r["functions"]:
            f.write(
                f"0x{r['start']:08X}\t"
                f"0x{r['end']:08X}\t"
                f"{r['path']}\t"
                f"0x{function['address']:08X}\t"
                f"0x{function['size']:X}\t"
                f"{function['declaration']}\n"
            )


# ----------------------------------------------------------------------
# Write human-readable summary.
# ----------------------------------------------------------------------

with SUMMARY_OUTPUT.open("w", encoding="utf-8") as f:
    f.write(
        "CCC ADDRESS-BASED SOURCE MAP\n"
        "============================\n\n"
        "NOTE:\n"
        "These ranges are based on nearest-preceding source/debug markers.\n"
        "They are NOT yet proven linker object/translation-unit boundaries.\n\n"
    )

    for r in ranges:
        f.write(
            f"0x{r['start']:08X}-0x{r['end']:08X} "
            f"{r['path']}\n"
        )

        f.write(
            f"  Functions: {len(r['functions'])}\n"
        )

        for function in r["functions"]:
            f.write(
                f"    0x{function['address']:08X} "
                f"+0x{function['size']:X} "
                f"{function['declaration']}\n"
            )

        f.write("\n")


with UNMAPPED_OUTPUT.open("w", encoding="utf-8") as f:
    for function in unmapped:
        f.write(
            f"0x{function['address']:08X}\t"
            f"0x{function['size']:X}\t"
            f"{function['declaration']}\n"
        )


print(f"Source markers:      {len(markers)}")
print(f"Functions parsed:    {len(functions)}")
print(f"Functions unmapped:  {len(unmapped)}")
print()
print(f"Wrote {MAP_OUTPUT}")
print(f"Wrote {SUMMARY_OUTPUT}")
print(f"Wrote {UNMAPPED_OUTPUT}")
