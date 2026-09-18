#!/usr/bin/env python3

from pathlib import Path
import json
import re
import shutil
import struct
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]

RETAIL = ROOT / "disc/infection/root/SLUS_202.67"

OBJDIFF = ROOT / "objdiff.json"

AUTO_TARGET_ROOT = (
    ROOT
    / "build/objdiff/target/resident-auto"
)

INVENTORY = (
    ROOT
    / "build/objdiff/resident-functions.tsv"
)

BASE_SETANALOG = (
    ROOT
    / "build/objdiff/base/prog/system/syspad/SetAnalogStick.o"
)

TARGET_SETANALOG = (
    ROOT
    / "build/objdiff/target/prog/system/syspad/SetAnalogStick.o"
)

SETANALOG_NAME = "SetAnalogStick__FPfPUcii"
SETANALOG_ADDR = 0x00102390
SETANALOG_SIZE = 0x16C

RESIDENT_START = 0x00100000
RESIDENT_END = 0x001DAC80


def u16(data, off):
    return struct.unpack_from("<H", data, off)[0]


def u32(data, off):
    return struct.unpack_from("<I", data, off)[0]


def align(value, amount):
    return (
        value + amount - 1
    ) & ~(amount - 1)


def read_string(table, offset):
    if offset >= len(table):
        return ""

    end = table.find(b"\0", offset)

    if end < 0:
        end = len(table)

    return table[offset:end].decode(
        "ascii",
        errors="replace",
    )


class Elf32LE:
    def __init__(self, path):
        self.path = Path(path)
        self.data = self.path.read_bytes()

        if self.data[:4] != b"\x7fELF":
            raise RuntimeError(
                f"{self.path}: not ELF"
            )

        if self.data[4] != 1:
            raise RuntimeError(
                f"{self.path}: expected ELF32"
            )

        if self.data[5] != 1:
            raise RuntimeError(
                f"{self.path}: expected little-endian"
            )

        self.e_machine = u16(
            self.data,
            0x12,
        )

        self.e_flags = u32(
            self.data,
            0x24,
        )

        self.phoff = u32(
            self.data,
            0x1C,
        )

        self.phentsize = u16(
            self.data,
            0x2A,
        )

        self.phnum = u16(
            self.data,
            0x2C,
        )

        self.shoff = u32(
            self.data,
            0x20,
        )

        self.shentsize = u16(
            self.data,
            0x2E,
        )

        self.shnum = u16(
            self.data,
            0x30,
        )

        self.shstrndx = u16(
            self.data,
            0x32,
        )

        self.sections = []

        for index in range(self.shnum):
            off = (
                self.shoff
                + index * self.shentsize
            )

            fields = struct.unpack_from(
                "<IIIIIIIIII",
                self.data,
                off,
            )

            self.sections.append({
                "index": index,
                "name_off": fields[0],
                "type": fields[1],
                "flags": fields[2],
                "addr": fields[3],
                "offset": fields[4],
                "size": fields[5],
                "link": fields[6],
                "info": fields[7],
                "align": fields[8],
                "entsize": fields[9],
            })

        shstr = self.sections[
            self.shstrndx
        ]

        names = self.data[
            shstr["offset"]:
            shstr["offset"]
            + shstr["size"]
        ]

        for section in self.sections:
            section["name"] = read_string(
                names,
                section["name_off"],
            )

    def symbols(self):
        output = []

        for section in self.sections:

            # SHT_SYMTAB
            if section["type"] != 2:
                continue

            strtab = self.sections[
                section["link"]
            ]

            strings = self.data[
                strtab["offset"]:
                strtab["offset"]
                + strtab["size"]
            ]

            entsize = (
                section["entsize"] or 16
            )

            count = (
                section["size"]
                // entsize
            )

            for index in range(count):

                off = (
                    section["offset"]
                    + index * entsize
                )

                (
                    st_name,
                    st_value,
                    st_size,
                    st_info,
                    st_other,
                    st_shndx,
                ) = struct.unpack_from(
                    "<IIIBBH",
                    self.data,
                    off,
                )

                output.append({
                    "index": index,
                    "name": read_string(
                        strings,
                        st_name,
                    ),
                    "value": st_value,
                    "size": st_size,
                    "bind": st_info >> 4,
                    "type": st_info & 0xF,
                    "other": st_other,
                    "shndx": st_shndx,
                })

        return output

    def bytes_at_vaddr(
        self,
        address,
        size,
    ):
        for i in range(self.phnum):

            off = (
                self.phoff
                + i * self.phentsize
            )

            (
                p_type,
                p_offset,
                p_vaddr,
                _p_paddr,
                p_filesz,
                _p_memsz,
                _p_flags,
                _p_align,
            ) = struct.unpack_from(
                "<IIIIIIII",
                self.data,
                off,
            )

            # PT_LOAD
            if p_type != 1:
                continue

            if not (
                p_vaddr <= address
                and
                address + size
                <= p_vaddr + p_filesz
            ):
                continue

            file_off = (
                p_offset
                + address
                - p_vaddr
            )

            result = self.data[
                file_off:
                file_off + size
            ]

            if len(result) != size:
                raise RuntimeError(
                    "short PT_LOAD read"
                )

            return result

        raise RuntimeError(
            f"cannot map vaddr "
            f"0x{address:08X}+0x{size:X}"
        )


def add_string(table, text):
    encoded = (
        text.encode(
            "ascii",
            errors="replace",
        )
        + b"\0"
    )

    offset = len(table)
    table.extend(encoded)

    return offset


def make_symbol(
    name_off,
    value,
    size,
    info,
    shndx,
):
    return struct.pack(
        "<IIIBBH",
        name_off,
        value,
        size,
        info,
        0,
        shndx,
    )


def make_function_object(
    output,
    code,
    symbol_name,
    binding,
    e_machine,
    e_flags,
):
    """
    Minimal ELF32 MIPS relocatable containing:
        section 1: .text
        section 2: .symtab
        section 3: .strtab
        section 4: .shstrtab

    This is sufficient for target-only objdiff
    progress units.
    """

    strtab = bytearray(b"\0")

    symbol_name_off = add_string(
        strtab,
        symbol_name,
    )

    shstr = bytearray(b"\0")

    text_name = add_string(
        shstr,
        ".text",
    )

    symtab_name = add_string(
        shstr,
        ".symtab",
    )

    strtab_name = add_string(
        shstr,
        ".strtab",
    )

    shstr_name = add_string(
        shstr,
        ".shstrtab",
    )

    symtab = bytearray()

    # STN_UNDEF
    symtab += bytes(16)

    # Local STT_SECTION for .text.
    symtab += make_symbol(
        0,
        0,
        0,
        0x03,
        1,
    )

    # Preserve LOCAL/GLOBAL binding where practical.
    #
    # STT_FUNC = 2.
    function_info = (
        (binding << 4) | 2
    )

    symtab += make_symbol(
        symbol_name_off,
        0,
        len(code),
        function_info,
        1,
    )

    # Number of local symbols preceding first global.
    #
    # NULL + SECTION + local function = 3
    # NULL + SECTION                  = 2
    symtab_info = (
        3 if binding == 0 else 2
    )

    blob = bytearray(bytes(52))

    while len(blob) % 16:
        blob.append(0)

    text_offset = len(blob)
    blob += code

    while len(blob) % 4:
        blob.append(0)

    symtab_offset = len(blob)
    blob += symtab

    strtab_offset = len(blob)
    blob += strtab

    shstr_offset = len(blob)
    blob += shstr

    while len(blob) % 4:
        blob.append(0)

    shoff = len(blob)

    sections = [
        # NULL
        (
            0, 0, 0, 0,
            0, 0, 0, 0,
            0, 0,
        ),

        # .text
        (
            text_name,
            1,
            0x6,
            0,
            text_offset,
            len(code),
            0,
            0,
            16,
            0,
        ),

        # .symtab
        (
            symtab_name,
            2,
            0,
            0,
            symtab_offset,
            len(symtab),
            3,
            symtab_info,
            4,
            16,
        ),

        # .strtab
        (
            strtab_name,
            3,
            0,
            0,
            strtab_offset,
            len(strtab),
            0,
            0,
            1,
            0,
        ),

        # .shstrtab
        (
            shstr_name,
            3,
            0,
            0,
            shstr_offset,
            len(shstr),
            0,
            0,
            1,
            0,
        ),
    ]

    for section in sections:
        blob += struct.pack(
            "<IIIIIIIIII",
            *section,
        )

    ident = bytearray(
        b"\x7fELF"
        + bytes([
            1,  # ELFCLASS32
            1,  # little-endian
            1,  # current version
            0,  # SYSV ABI
        ])
        + bytes(8)
    )

    header = (
        bytes(ident)
        + struct.pack(
            "<HHIIIIIHHHHHH",
            1,          # ET_REL
            e_machine,
            1,
            0,
            0,
            shoff,
            e_flags,
            52,
            0,
            0,
            40,
            len(sections),
            4,
        )
    )

    if len(header) != 52:
        raise RuntimeError(
            "bad ELF header length"
        )

    blob[:52] = header

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output.write_bytes(blob)


def sanitize_symbol(name):
    result = re.sub(
        r"[^A-Za-z0-9_.@+-]+",
        "_",
        name,
    )

    result = result.strip("_")

    if not result:
        result = "unnamed"

    # Address prefix guarantees uniqueness,
    # so extremely long mangled names can be trimmed.
    return result[:96]


def main():
    elf = Elf32LE(RETAIL)

    # --------------------------------------------------------------
    # Obtain the proven R3.01 build and the special normalized
    # SetAnalogStick target.
    # --------------------------------------------------------------

    subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / "scripts/build_objdiff.py"
            ),
            str(
                BASE_SETANALOG.relative_to(
                    ROOT
                )
            ),
        ],
        cwd=ROOT,
        check=True,
    )

    subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / "scripts/build_objdiff.py"
            ),
            str(
                TARGET_SETANALOG.relative_to(
                    ROOT
                )
            ),
        ],
        cwd=ROOT,
        check=True,
    )

    # --------------------------------------------------------------
    # Collect resident functions.
    # --------------------------------------------------------------

    raw = []

    for symbol in elf.symbols():

        # STT_FUNC
        if symbol["type"] != 2:
            continue

        if symbol["shndx"] == 0:
            continue

        if symbol["size"] <= 0:
            continue

        start = symbol["value"]
        end = start + symbol["size"]

        if start < RESIDENT_START:
            continue

        if end > RESIDENT_END:
            continue

        if start >= RESIDENT_END:
            continue

        raw.append(symbol)

    raw.sort(
        key=lambda s: (
            s["value"],
            s["size"],
            s["name"],
        )
    )

    # Exact-range aliases must not double-count code.
    by_range = {}

    aliases = []

    for symbol in raw:
        key = (
            symbol["value"],
            symbol["size"],
        )

        previous = by_range.get(key)

        if previous is None:
            by_range[key] = symbol
            continue

        aliases.append(
            (
                previous,
                symbol,
            )
        )

        # Prefer GLOBAL over LOCAL only for display.
        if (
            previous["bind"] == 0
            and symbol["bind"] != 0
        ):
            by_range[key] = symbol

    functions = sorted(
        by_range.values(),
        key=lambda s: (
            s["value"],
            s["size"],
            s["name"],
        )
    )

    # --------------------------------------------------------------
    # Detect non-identical overlaps.
    #
    # Do not silently double-count ambiguous code ranges.
    # --------------------------------------------------------------

    accepted = []
    overlaps = []

    previous = None

    for symbol in functions:

        if previous is not None:

            previous_end = (
                previous["value"]
                + previous["size"]
            )

            if symbol["value"] < previous_end:

                overlaps.append(
                    (
                        previous,
                        symbol,
                    )
                )

                # Keep the earlier range as the canonical
                # denominator entry.
                continue

        accepted.append(symbol)
        previous = symbol

    functions = accepted

    if not functions:
        raise RuntimeError(
            "no resident functions discovered"
        )

    # --------------------------------------------------------------
    # Regenerate target-only objects.
    # --------------------------------------------------------------

    shutil.rmtree(
        AUTO_TARGET_ROOT,
        ignore_errors=True,
    )

    AUTO_TARGET_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    units = []

    inventory_rows = []

    total_code = 0
    matched_code = 0
    matched_functions = 0

    found_setanalog = False

    for symbol in functions:

        address = symbol["value"]
        size = symbol["size"]
        name = symbol["name"]

        if not name:
            name = f"func_{address:08X}"

        total_code += size

        # ----------------------------------------------------------
        # Existing matched unit.
        # ----------------------------------------------------------

        if (
            address == SETANALOG_ADDR
            and size == SETANALOG_SIZE
            and name == SETANALOG_NAME
        ):
            found_setanalog = True
            matched_code += size
            matched_functions += 1

            units.append({
                "name":
                    "prog/system/syspad/SetAnalogStick",

                "target_path":
                    str(
                        TARGET_SETANALOG.relative_to(
                            ROOT
                        )
                    ),

                "base_path":
                    str(
                        BASE_SETANALOG.relative_to(
                            ROOT
                        )
                    ),

                "metadata": {},
            })

            inventory_rows.append({
                "address": address,
                "size": size,
                "bind": symbol["bind"],
                "status": "MATCHED",
                "symbol": name,
                "unit":
                    "prog/system/syspad/SetAnalogStick",
            })

            continue

        # ----------------------------------------------------------
        # Unmatched target-only unit.
        # ----------------------------------------------------------

        safe = sanitize_symbol(name)

        filename = (
            f"{address:08X}_{safe}.o"
        )

        target = (
            AUTO_TARGET_ROOT
            / filename
        )

        code = elf.bytes_at_vaddr(
            address,
            size,
        )

        make_function_object(
            output=target,
            code=code,
            symbol_name=name,
            binding=symbol["bind"],
            e_machine=elf.e_machine,
            e_flags=elf.e_flags,
        )

        unit_name = (
            f"resident/"
            f"{address:08X}/"
            f"{name}"
        )

        units.append({
            "name": unit_name,

            "target_path":
                str(
                    target.relative_to(
                        ROOT
                    )
                ),

            # No base_path yet:
            # this is intentionally unmatched.
            "metadata": {
                "auto_generated": True,
            },
        })

        inventory_rows.append({
            "address": address,
            "size": size,
            "bind": symbol["bind"],
            "status": "UNMATCHED",
            "symbol": name,
            "unit": unit_name,
        })

    if not found_setanalog:
        raise RuntimeError(
            "matched SetAnalogStick range was not "
            "found in resident symbol inventory"
        )

    # --------------------------------------------------------------
    # Generate objdiff configuration.
    # --------------------------------------------------------------

    project = {
        "$schema":
            "https://raw.githubusercontent.com/"
            "encounter/objdiff/main/"
            "config.schema.json",

        "custom_make":
            "python3",

        "custom_args": [
            "scripts/build_objdiff.py",
        ],

        # Targets are generated by this configurator.
        "build_target":
            False,

        "build_base":
            True,

        "watch_patterns": [
            "src/**/*.c",
            "src/**/*.cc",
            "src/**/*.cpp",
            "include/**/*.h",
            "include/**/*.hpp",
            "scripts/**/*.py",
            "scripts/**/*.sh",
            "config/**/*.txt",
            "config/**/*.yaml",
            "config/**/*.json",
        ],

        "ignore_patterns": [
            "build/**/*",
            "asm/**/*",
            "disc/**/*",
            "tools/**/*",
        ],

        "units": units,
    }

    OBJDIFF.write_text(
        json.dumps(
            project,
            indent=2,
        )
        + "\n"
    )

    INVENTORY.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with INVENTORY.open(
        "w",
        encoding="utf-8",
    ) as out:

        out.write(
            "address\t"
            "size\t"
            "binding\t"
            "status\t"
            "symbol\t"
            "unit\n"
        )

        for row in inventory_rows:

            out.write(
                f"0x{row['address']:08X}\t"
                f"{row['size']}\t"
                f"{row['bind']}\t"
                f"{row['status']}\t"
                f"{row['symbol']}\t"
                f"{row['unit']}\n"
            )

    print("Resident function inventory")
    print("===========================")
    print(
        f"Range:              "
        f"0x{RESIDENT_START:08X}"
        f"-0x{RESIDENT_END:08X}"
    )
    print(
        f"Raw FUNC symbols:   "
        f"{len(raw)}"
    )
    print(
        f"Exact-range aliases:"
        f" {len(aliases)}"
    )
    print(
        f"Skipped overlaps:   "
        f"{len(overlaps)}"
    )
    print(
        f"Progress functions: "
        f"{len(functions)}"
    )
    print(
        f"Total function code:"
        f" {total_code} bytes"
    )
    print(
        f"Matched code:       "
        f"{matched_code} bytes"
    )
    print(
        f"Matched functions:  "
        f"{matched_functions}"
    )
    print(
        f"Initial percentage: "
        f"{matched_code / total_code * 100:.6f}%"
    )
    print()
    print(
        f"Generated units:    "
        f"{len(units)}"
    )
    print(
        f"objdiff config:     "
        f"{OBJDIFF.relative_to(ROOT)}"
    )
    print(
        f"inventory:          "
        f"{INVENTORY.relative_to(ROOT)}"
    )

    if aliases:
        print()
        print("Exact-range aliases:")
        for old, new in aliases[:20]:
            print(
                f"  0x{old['value']:08X} "
                f"0x{old['size']:X} "
                f"{old['name']} / "
                f"{new['name']}"
            )

        if len(aliases) > 20:
            print(
                f"  ... "
                f"{len(aliases) - 20} more"
            )

    if overlaps:
        print()
        print("WARNING: non-identical overlapping ranges skipped:")

        for old, new in overlaps[:20]:
            print(
                f"  0x{old['value']:08X}"
                f"+0x{old['size']:X} "
                f"{old['name']}  overlaps  "
                f"0x{new['value']:08X}"
                f"+0x{new['size']:X} "
                f"{new['name']}"
            )

        if len(overlaps) > 20:
            print(
                f"  ... "
                f"{len(overlaps) - 20} more"
            )


if __name__ == "__main__":
    main()
