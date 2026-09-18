#!/usr/bin/env python3

from pathlib import Path
import re
import subprocess
import sys

ROOT = Path.cwd()

ELF = ROOT / "disc/infection/root/SLUS_202.67"

SOURCE_MAP = ROOT / "build/research/ccc/source-address-map.tsv"

SPLAT_SYMBOLS = ROOT / "config/infection/symbol_addrs.txt"

REPORT = ROOT / "build/research/validation/source-range-validation.txt"
TSV = ROOT / "build/research/validation/source-range-validation.tsv"


# ----------------------------------------------------------------------
# Candidate translation units to inspect first.
#
# These were chosen because CCC gave them concrete addresses and they
# appear early enough in the executable to make comparison straightforward.
# ----------------------------------------------------------------------

CANDIDATES = [
    "prog/system/sysmem.cpp",
    "prog/system/sysdebug.cpp",
    "prog/system/syshelper.cpp",
    "prog/system/syspad.cpp",
    "prog/system/sysframe.cpp",
    "prog/system/system.cpp",
    "prog/system/libcc3d.cpp",
    "prog/system/main.cpp",
    "prog/source/camera.cpp",
]


for required in (ELF, SOURCE_MAP, SPLAT_SYMBOLS):
    if not required.exists():
        print(f"ERROR: required file is missing:")
        print(f"  {required}")
        sys.exit(1)


# ======================================================================
# Parse CCC source markers
# ======================================================================

markers = []

lines = SOURCE_MAP.read_text(errors="replace").splitlines()

for line in lines[1:]:
    if not line.strip():
        continue

    parts = line.split("\t")

    if len(parts) < 3:
        continue

    addr_text, original_path, normalized_path = parts[:3]

    try:
        address = int(addr_text, 16)
    except ValueError:
        continue

    markers.append({
        "address": address,
        "original": original_path,
        "path": normalized_path,
    })


# Deduplicate exact address/path pairs.

dedup = {}

for marker in markers:
    dedup[(marker["address"], marker["path"])] = marker

markers = sorted(
    dedup.values(),
    key=lambda m: (m["address"], m["path"].lower())
)


# ======================================================================
# Parse ELF symbols with readelf
# ======================================================================

result = subprocess.run(
    ["readelf", "-Ws", str(ELF)],
    capture_output=True,
    text=True,
    check=True,
)

elf_functions = []

for raw in result.stdout.splitlines():

    line = raw.strip()

    if not line:
        continue

    # Typical:
    #
    #  123: 00100370   388 FUNC GLOBAL DEFAULT 4 SymbolName
    #

    parts = line.split(None, 7)

    if len(parts) < 8:
        continue

    if not parts[0].endswith(":"):
        continue

    try:
        address = int(parts[1], 16)
        size = int(parts[2], 10)
    except ValueError:
        continue

    sym_type = parts[3]
    ndx = parts[6]
    name = parts[7]

    if sym_type != "FUNC":
        continue

    if ndx == "UND":
        continue

    if address == 0:
        continue

    elf_functions.append({
        "address": address,
        "size": size,
        "name": name,
    })

elf_functions.sort(
    key=lambda f: (f["address"], f["name"])
)


# ======================================================================
# Parse Splat symbol map
# ======================================================================

splat_by_address = {}

symbol_re = re.compile(
    r"^\s*([A-Za-z0-9_.$@]+)\s*=\s*"
    r"0x([0-9A-Fa-f]+);"
)

for line in SPLAT_SYMBOLS.read_text(errors="replace").splitlines():

    match = symbol_re.match(line)

    if not match:
        continue

    name = match.group(1)
    address = int(match.group(2), 16)

    splat_by_address.setdefault(address, []).append(name)


# ======================================================================
# Helper functions
# ======================================================================

def funcs_at(address):
    return [
        f for f in elf_functions
        if f["address"] == address
    ]


def funcs_in_range(start, end):
    return [
        f for f in elf_functions
        if start <= f["address"] < end
    ]


def next_marker_after(index):
    if index + 1 >= len(markers):
        return None

    return markers[index + 1]


def extension(path):
    return Path(path).suffix.lower()


# ======================================================================
# Validate selected ranges
# ======================================================================

results = []

for candidate in CANDIDATES:

    candidate_markers = [
        (index, marker)
        for index, marker in enumerate(markers)
        if marker["path"].lower() == candidate.lower()
    ]

    if not candidate_markers:

        results.append({
            "candidate": candidate,
            "found": False,
        })

        continue


    for index, marker in candidate_markers:

        start = marker["address"]

        next_marker = next_marker_after(index)

        if next_marker is None:
            continue

        end = next_marker["address"]

        functions = funcs_in_range(start, end)

        exact_start = funcs_at(start)

        exact_end = funcs_at(end)

        splat_start = splat_by_address.get(start, [])

        splat_end = splat_by_address.get(end, [])

        first_function = functions[0] if functions else None
        last_function = functions[-1] if functions else None


        # --------------------------------------------------------------
        # Confidence here refers only to the SOURCE MARKER.
        #
        # It does NOT mean "proven original object boundary".
        # --------------------------------------------------------------

        if exact_start and splat_start:
            confidence = "STRONG"
        elif exact_start or splat_start:
            confidence = "PLAUSIBLE"
        else:
            confidence = "WEAK"


        results.append({
            "candidate": candidate,
            "found": True,

            "start": start,
            "end": end,
            "range_size": end - start,

            "next_path": next_marker["path"],

            "functions": functions,

            "exact_start": exact_start,
            "exact_end": exact_end,

            "splat_start": splat_start,
            "splat_end": splat_end,

            "first_function": first_function,
            "last_function": last_function,

            "confidence": confidence,
        })


# ======================================================================
# Human-readable report
# ======================================================================

REPORT.parent.mkdir(parents=True, exist_ok=True)

with REPORT.open("w", encoding="utf-8") as out:

    out.write(
        "CCC SOURCE-RANGE VALIDATION\n"
        "===========================\n\n"
        "IMPORTANT:\n"
        "STRONG means that a CCC source marker is independently supported\n"
        "by both the retail ELF function table and the Splat symbol map.\n"
        "It does NOT yet prove an original linker object boundary.\n\n"
    )


    for r in results:

        out.write("=" * 78 + "\n")
        out.write(f"{r['candidate']}\n")
        out.write("=" * 78 + "\n")

        if not r["found"]:

            out.write("CCC marker: NOT FOUND\n\n")
            continue


        out.write(
            f"Marker confidence: {r['confidence']}\n\n"
        )

        out.write(
            f"Start:       0x{r['start']:08X}\n"
            f"End:         0x{r['end']:08X}\n"
            f"Range size:  0x{r['range_size']:X} "
            f"({r['range_size']} bytes)\n"
            f"Next marker: {r['next_path']}\n\n"
        )


        out.write("ELF function exactly at marker start:\n")

        if r["exact_start"]:

            for f in r["exact_start"]:
                out.write(
                    f"  0x{f['address']:08X} "
                    f"+0x{f['size']:X} "
                    f"{f['name']}\n"
                )

        else:
            out.write("  NONE\n")


        out.write("\nSplat symbol exactly at marker start:\n")

        if r["splat_start"]:

            for name in r["splat_start"]:
                out.write(f"  {name}\n")

        else:
            out.write("  NONE\n")


        out.write("\nNext marker ELF function:\n")

        if r["exact_end"]:

            for f in r["exact_end"]:
                out.write(
                    f"  0x{f['address']:08X} "
                    f"+0x{f['size']:X} "
                    f"{f['name']}\n"
                )

        else:
            out.write("  NONE\n")


        out.write("\nNext marker Splat symbol:\n")

        if r["splat_end"]:

            for name in r["splat_end"]:
                out.write(f"  {name}\n")

        else:
            out.write("  NONE\n")


        out.write(
            f"\nFunctions inside candidate range: "
            f"{len(r['functions'])}\n"
        )


        for f in r["functions"]:

            end_addr = f["address"] + f["size"]

            out.write(
                f"  0x{f['address']:08X}-"
                f"0x{end_addr:08X} "
                f"{f['name']}\n"
            )


        if r["last_function"]:

            last_end = (
                r["last_function"]["address"]
                + r["last_function"]["size"]
            )

            tail_gap = r["end"] - last_end

            out.write(
                f"\nEnd of final ELF function: "
                f"0x{last_end:08X}\n"
            )

            out.write(
                f"Bytes between final function end "
                f"and next marker: "
                f"0x{tail_gap:X} ({tail_gap})\n"
            )


        out.write("\n")


# ======================================================================
# TSV report
# ======================================================================

with TSV.open("w", encoding="utf-8") as out:

    out.write(
        "source\tconfidence\tstart\tend\t"
        "range_size\tfunction_count\t"
        "next_marker\n"
    )

    for r in results:

        if not r["found"]:
            out.write(
                f"{r['candidate']}\tNOT_FOUND\t\t\t\t\t\n"
            )
            continue

        out.write(
            f"{r['candidate']}\t"
            f"{r['confidence']}\t"
            f"0x{r['start']:08X}\t"
            f"0x{r['end']:08X}\t"
            f"0x{r['range_size']:X}\t"
            f"{len(r['functions'])}\t"
            f"{r['next_path']}\n"
        )


# ======================================================================
# Console summary
# ======================================================================

print()
print("Candidate validation summary")
print("============================")
print()

for r in results:

    if not r["found"]:
        print(
            f"{r['candidate']:<35} "
            f"NOT FOUND"
        )
        continue

    print(
        f"{r['candidate']:<35} "
        f"{r['confidence']:<10} "
        f"0x{r['start']:08X}-0x{r['end']:08X} "
        f"{len(r['functions']):>3} funcs"
    )

print()
print(f"Wrote:")
print(f"  {REPORT}")
print(f"  {TSV}")
