#!/usr/bin/env python3

from pathlib import Path
import argparse
import struct
import sys


def u16(data, off):
    return struct.unpack_from("<H", data, off)[0]


def u32(data, off):
    return struct.unpack_from("<I", data, off)[0]


class Elf32LE:
    def __init__(self, path):
        self.path = Path(path)
        self.data = self.path.read_bytes()

        if self.data[:4] != b"\x7fELF":
            raise RuntimeError(
                f"{self.path}: not an ELF file"
            )

        if self.data[4] != 1:
            raise RuntimeError(
                f"{self.path}: expected ELF32"
            )

        if self.data[5] != 1:
            raise RuntimeError(
                f"{self.path}: expected little-endian ELF"
            )

        self.shoff = u32(self.data, 0x20)
        self.shentsize = u16(self.data, 0x2E)
        self.shnum = u16(self.data, 0x30)
        self.shstrndx = u16(self.data, 0x32)

        self.sections = []

        for index in range(self.shnum):
            off = self.shoff + index * self.shentsize

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

        shstr = self.sections[self.shstrndx]

        self.shstr = self.data[
            shstr["offset"]:
            shstr["offset"] + shstr["size"]
        ]

        for section in self.sections:
            section["name"] = self.string(
                self.shstr,
                section["name_off"],
            )

    @staticmethod
    def string(table, offset):
        if offset >= len(table):
            return ""

        end = table.find(b"\0", offset)

        if end < 0:
            end = len(table)

        return table[offset:end].decode(
            "ascii",
            errors="replace",
        )

    def symbols(self):
        result = []

        for section in self.sections:

            # SHT_SYMTAB
            if section["type"] != 2:
                continue

            if section["link"] >= len(self.sections):
                raise RuntimeError(
                    "invalid symbol string table link"
                )

            strsec = self.sections[section["link"]]

            strings = self.data[
                strsec["offset"]:
                strsec["offset"] + strsec["size"]
            ]

            entsize = section["entsize"] or 16

            count = section["size"] // entsize

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

                result.append({
                    "index": index,
                    "name": self.string(
                        strings,
                        st_name,
                    ),
                    "value": st_value,
                    "size": st_size,
                    "info": st_info,
                    "bind": st_info >> 4,
                    "type": st_info & 0xF,
                    "other": st_other,
                    "shndx": st_shndx,
                })

        return result

    def function(self, name):
        matches = [
            symbol
            for symbol in self.symbols()
            if symbol["name"] == name
            and symbol["type"] == 2  # STT_FUNC
        ]

        if not matches:
            raise RuntimeError(
                f"{self.path}: function {name!r} not found"
            )

        # Prefer a defined, non-zero-sized symbol.
        matches.sort(
            key=lambda s: (
                s["shndx"] == 0,
                s["size"] == 0,
            )
        )

        symbol = matches[0]

        if symbol["shndx"] == 0:
            raise RuntimeError(
                f"{self.path}: function is undefined"
            )

        if symbol["shndx"] >= len(self.sections):
            raise RuntimeError(
                f"{self.path}: invalid section index "
                f"{symbol['shndx']}"
            )

        section = self.sections[symbol["shndx"]]

        start = section["offset"] + symbol["value"]
        end = start + symbol["size"]

        if end > len(self.data):
            raise RuntimeError(
                f"{self.path}: function extends beyond file"
            )

        return symbol, section, self.data[start:end]


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("target", type=Path)
    parser.add_argument("base", type=Path)
    parser.add_argument("symbol")

    args = parser.parse_args()

    target_elf = Elf32LE(args.target)
    base_elf = Elf32LE(args.base)

    target_sym, target_sec, target_data = (
        target_elf.function(args.symbol)
    )

    base_sym, base_sec, base_data = (
        base_elf.function(args.symbol)
    )

    print("Function extraction")
    print("===================")

    print(
        f"Target section: "
        f"[{target_sec['index']}] "
        f"{target_sec['name']}"
    )

    print(
        f"Base section:   "
        f"[{base_sec['index']}] "
        f"{base_sec['name']}"
    )

    print(
        f"Target size:    "
        f"{target_sym['size']} bytes"
    )

    print(
        f"Base size:      "
        f"{base_sym['size']} bytes"
    )

    print()

    if len(target_data) != len(base_data):
        print("FAIL: function sizes differ.")
        sys.exit(1)

    differences = []

    for off in range(
        0,
        len(target_data),
        4,
    ):
        target_word = struct.unpack_from(
            "<I",
            target_data,
            off,
        )[0]

        base_word = struct.unpack_from(
            "<I",
            base_data,
            off,
        )[0]

        if target_word != base_word:
            differences.append(
                (
                    off,
                    target_word,
                    base_word,
                )
            )

    if differences:
        print(
            f"FAIL: {len(differences)} "
            f"instruction word(s) differ."
        )

        for off, target_word, base_word in differences:
            print(
                f"  +0x{off:03X}: "
                f"target={target_word:08X} "
                f"base={base_word:08X}"
            )

        sys.exit(1)

    word_count = len(target_data) // 4

    print(
        f"PASS: all {word_count} instruction words "
        f"are byte-identical."
    )


if __name__ == "__main__":
    main()
