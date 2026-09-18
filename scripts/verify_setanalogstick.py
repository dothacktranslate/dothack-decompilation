#!/usr/bin/env python3

from pathlib import Path
import struct
import sys


ROOT = Path(__file__).resolve().parents[1]

RETAIL = ROOT / "disc/infection/root/SLUS_202.67"
OBJECT = ROOT / "build/matching/syspad/SetAnalogStick.o"

FUNCTION_VADDR = 0x00102390
FUNCTION_SIZE = 0x16C

# Relocatable-object call positions:
#   0x84 -> sqrtf
#   0xB0 -> fptosi
#   0xF0 -> atan2f
RELOCATION_OFFSETS = {
    0x84,
    0xB0,
    0xF0,
}


def u16(data, offset):
    return struct.unpack_from("<H", data, offset)[0]


def u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def check_elf32_le(data, name):
    if data[:4] != b"\x7fELF":
        raise RuntimeError(f"{name}: not an ELF file")

    if data[4] != 1:
        raise RuntimeError(f"{name}: expected ELF32")

    if data[5] != 1:
        raise RuntimeError(f"{name}: expected little-endian ELF")


def section_bytes(data, wanted):
    check_elf32_le(data, "object")

    shoff = u32(data, 0x20)
    shentsize = u16(data, 0x2E)
    shnum = u16(data, 0x30)
    shstrndx = u16(data, 0x32)

    headers = []

    for i in range(shnum):
        offset = shoff + i * shentsize

        fields = struct.unpack_from(
            "<IIIIIIIIII",
            data,
            offset,
        )

        headers.append(fields)

    if shstrndx >= len(headers):
        raise RuntimeError("invalid section string table index")

    shstr = headers[shstrndx]

    strings_offset = shstr[4]
    strings_size = shstr[5]

    strings = data[
        strings_offset:
        strings_offset + strings_size
    ]

    def read_name(index):
        end = strings.find(b"\0", index)

        if end < 0:
            end = len(strings)

        return strings[index:end].decode(
            "ascii",
            errors="replace",
        )

    for header in headers:
        name = read_name(header[0])

        if name != wanted:
            continue

        offset = header[4]
        size = header[5]

        return data[offset:offset + size]

    raise RuntimeError(
        f"section {wanted!r} not found"
    )


def retail_function_bytes(data):
    check_elf32_le(data, "retail ELF")

    phoff = u32(data, 0x1C)
    phentsize = u16(data, 0x2A)
    phnum = u16(data, 0x2C)

    for i in range(phnum):
        offset = phoff + i * phentsize

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
            data,
            offset,
        )

        # PT_LOAD
        if p_type != 1:
            continue

        start = p_vaddr
        end = p_vaddr + p_filesz

        if not (
            start <= FUNCTION_VADDR
            and FUNCTION_VADDR + FUNCTION_SIZE <= end
        ):
            continue

        file_offset = (
            p_offset
            + FUNCTION_VADDR
            - p_vaddr
        )

        return data[
            file_offset:
            file_offset + FUNCTION_SIZE
        ]

    raise RuntimeError(
        "could not map SetAnalogStick through a PT_LOAD segment"
    )


retail_data = RETAIL.read_bytes()
object_data = OBJECT.read_bytes()

retail = retail_function_bytes(retail_data)
candidate = section_bytes(object_data, ".text")

if len(retail) != FUNCTION_SIZE:
    raise RuntimeError(
        f"retail size is {len(retail)}, expected {FUNCTION_SIZE}"
    )

if len(candidate) != FUNCTION_SIZE:
    print(
        f"FAIL: candidate .text is {len(candidate)} bytes; "
        f"expected {FUNCTION_SIZE}"
    )
    sys.exit(1)


matches = 0
comparable = 0
differences = []

for offset in range(0, FUNCTION_SIZE, 4):

    retail_word = struct.unpack_from(
        "<I",
        retail,
        offset,
    )[0]

    candidate_word = struct.unpack_from(
        "<I",
        candidate,
        offset,
    )[0]

    if offset in RELOCATION_OFFSETS:
        # Retail should contain JAL at these locations.
        if (retail_word >> 26) != 0x03:
            raise RuntimeError(
                f"retail offset 0x{offset:X} is not JAL"
            )

        continue

    comparable += 1

    if retail_word == candidate_word:
        matches += 1
    else:
        differences.append(
            (
                offset,
                retail_word,
                candidate_word,
            )
        )


print("SetAnalogStick verification")
print("===========================")
print(f"Retail size:       {len(retail)} bytes")
print(f"Candidate size:    {len(candidate)} bytes")
print(f"Comparable words: {comparable}")
print(f"Exact words:      {matches}/{comparable}")
print()

if differences:
    print("Mismatches:")

    for offset, retail_word, candidate_word in differences:
        print(
            f"  +0x{offset:03X}: "
            f"retail={retail_word:08X} "
            f"candidate={candidate_word:08X}"
        )

    sys.exit(1)


if matches != 88 or comparable != 88:
    raise RuntimeError(
        "unexpected comparable-word count"
    )


print("PASS: all 88 non-relocated instruction words match retail.")
print()
print(
    "Relocation words still require normal link-time resolution at "
    "+0x84, +0xB0, and +0xF0."
)
