#!/usr/bin/env python3

from pathlib import Path
import argparse
import struct


FUNCTION_NAME = "SetAnalogStick__FPfPUcii"
FUNCTION_VADDR = 0x00102390
FUNCTION_SIZE = 0x16C

RELOCS = [
    (0x84, "sqrtf"),
    (0xB0, "fptosi"),
    (0xF0, "atan2f"),
]

R_MIPS_26 = 4


def align(value, amount):
    return (value + amount - 1) & ~(amount - 1)


def u16(data, offset):
    return struct.unpack_from("<H", data, offset)[0]


def u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def retail_function(data):
    if data[:4] != b"\x7fELF":
        raise RuntimeError("retail file is not ELF")

    if data[4] != 1 or data[5] != 1:
        raise RuntimeError("expected ELF32 little-endian retail executable")

    phoff = u32(data, 0x1C)
    phentsize = u16(data, 0x2A)
    phnum = u16(data, 0x2C)

    for i in range(phnum):
        off = phoff + i * phentsize

        (
            p_type,
            p_offset,
            p_vaddr,
            _p_paddr,
            p_filesz,
            _p_memsz,
            _p_flags,
            _p_align,
        ) = struct.unpack_from("<IIIIIIII", data, off)

        if p_type != 1:
            continue

        if not (
            p_vaddr <= FUNCTION_VADDR
            and FUNCTION_VADDR + FUNCTION_SIZE
            <= p_vaddr + p_filesz
        ):
            continue

        file_offset = (
            p_offset
            + FUNCTION_VADDR
            - p_vaddr
        )

        result = bytearray(
            data[file_offset:file_offset + FUNCTION_SIZE]
        )

        if len(result) != FUNCTION_SIZE:
            raise RuntimeError("short retail function read")

        return result

    raise RuntimeError(
        "could not map SetAnalogStick through a PT_LOAD segment"
    )


def add_string(table, value):
    encoded = value.encode("ascii") + b"\0"
    offset = len(table)
    table.extend(encoded)
    return offset


def make_sym(name, value, size, info, shndx):
    return struct.pack(
        "<IIIBBH",
        name,
        value,
        size,
        info,
        0,
        shndx,
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--retail",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--flags-from",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--output",
        required=True,
        type=Path,
    )

    args = parser.parse_args()

    retail_data = args.retail.read_bytes()
    base_data = args.flags_from.read_bytes()

    if base_data[:4] != b"\x7fELF":
        raise RuntimeError("base compiler output is not ELF")

    text = retail_function(retail_data)

    # Convert final linked JALs back into the form stored in a
    # relocatable MWCC object.
    for offset, symbol in RELOCS:
        word = struct.unpack_from("<I", text, offset)[0]

        opcode = word >> 26

        if opcode != 0x03:
            raise RuntimeError(
                f"+0x{offset:X} ({symbol}) is not JAL "
                f"in retail: {word:08X}"
            )

        struct.pack_into(
            "<I",
            text,
            offset,
            0x0C000000,
        )

    # ----------------------------------------------------------------
    # Symbol string table.
    # ----------------------------------------------------------------

    strtab = bytearray(b"\0")

    fn_name = add_string(strtab, FUNCTION_NAME)
    sqrtf_name = add_string(strtab, "sqrtf")
    fptosi_name = add_string(strtab, "fptosi")
    atan2f_name = add_string(strtab, "atan2f")

    # Symbol indices:
    #   0 NULL
    #   1 .text section
    #   2 SetAnalogStick
    #   3 sqrtf
    #   4 fptosi
    #   5 atan2f

    symtab = bytearray()

    symtab += bytes(16)

    # STB_LOCAL | STT_SECTION
    symtab += make_sym(
        0,
        0,
        0,
        0x03,
        1,
    )

    # STB_GLOBAL | STT_FUNC
    symtab += make_sym(
        fn_name,
        0,
        FUNCTION_SIZE,
        0x12,
        1,
    )

    # STB_GLOBAL | STT_NOTYPE, SHN_UNDEF
    symtab += make_sym(
        sqrtf_name,
        0,
        0,
        0x10,
        0,
    )

    symtab += make_sym(
        fptosi_name,
        0,
        0,
        0x10,
        0,
    )

    symtab += make_sym(
        atan2f_name,
        0,
        0,
        0x10,
        0,
    )

    symbol_indices = {
        "sqrtf": 3,
        "fptosi": 4,
        "atan2f": 5,
    }

    reltext = bytearray()

    for offset, symbol in RELOCS:
        r_info = (
            symbol_indices[symbol] << 8
        ) | R_MIPS_26

        reltext += struct.pack(
            "<II",
            offset,
            r_info,
        )

    # ----------------------------------------------------------------
    # Section-name string table.
    # ----------------------------------------------------------------

    shstr = bytearray(b"\0")

    sh_text = add_string(shstr, ".text")
    sh_reltext = add_string(shstr, ".rel.text")
    sh_symtab = add_string(shstr, ".symtab")
    sh_strtab = add_string(shstr, ".strtab")
    sh_shstrtab = add_string(shstr, ".shstrtab")

    # ----------------------------------------------------------------
    # Lay out ELF contents.
    # ----------------------------------------------------------------

    blob = bytearray(bytes(52))

    while len(blob) % 16:
        blob.append(0)

    text_offset = len(blob)
    blob += text

    while len(blob) % 4:
        blob.append(0)

    reltext_offset = len(blob)
    blob += reltext

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

    # Section 0: NULL
    sections = [
        (0, 0, 0, 0, 0, 0, 0, 0, 0, 0),

        # .text
        (
            sh_text,
            1,          # SHT_PROGBITS
            0x6,        # SHF_ALLOC | SHF_EXECINSTR
            0,
            text_offset,
            len(text),
            0,
            0,
            16,
            0,
        ),

        # .rel.text
        (
            sh_reltext,
            9,          # SHT_REL
            0,
            0,
            reltext_offset,
            len(reltext),
            3,          # linked symtab
            1,          # applies to .text
            4,
            8,
        ),

        # .symtab
        (
            sh_symtab,
            2,          # SHT_SYMTAB
            0,
            0,
            symtab_offset,
            len(symtab),
            4,          # linked strtab
            2,          # first GLOBAL symbol
            4,
            16,
        ),

        # .strtab
        (
            sh_strtab,
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
            sh_shstrtab,
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

    # ----------------------------------------------------------------
    # ELF header.
    #
    # Copy identification and MIPS flags from the real R3.01 object
    # so objdiff sees the same architecture characteristics.
    # ----------------------------------------------------------------

    ident = bytearray(base_data[:16])

    e_machine = u16(base_data, 0x12)
    e_flags = u32(base_data, 0x24)

    header = bytes(ident) + struct.pack(
        "<HHIIIIIHHHHHH",
        1,                  # ET_REL
        e_machine,
        1,                  # EV_CURRENT
        0,                  # entry
        0,                  # phoff
        shoff,
        e_flags,
        52,                 # ehsize
        0,                  # phentsize
        0,                  # phnum
        40,                 # shentsize
        len(sections),
        5,                  # shstrndx
    )

    if len(header) != 52:
        raise RuntimeError(
            f"bad ELF header size: {len(header)}"
        )

    blob[:52] = header

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.output.write_bytes(blob)

    print(
        f"Generated {args.output} "
        f"({FUNCTION_SIZE} bytes of target code)"
    )


if __name__ == "__main__":
    main()
