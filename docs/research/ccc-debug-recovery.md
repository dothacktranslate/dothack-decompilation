# CCC Debug Recovery

Chaos Compiler Collection successfully recognizes both `.debug` and `.symtab`
information in SLUS_202.67.

Current recovery includes:

- source/debug file associations
- thousands of function records
- global-variable information
- partial type information

The `stdump files` addresses are treated as source/debug associations, not yet
as proven translation-unit or object boundaries. Header files, SDK headers,
duplicate filenames, and records with address `ffffffff` are present.

Type recovery is currently incomplete for this executable. CCC reports several
unsupported debug type forms, so automatically generated type declarations are
not considered authoritative.

Raw CCC output remains under `build/research/` and is not committed.

## UNCC Experiment

`uncc` successfully processed SLUS_202.67 but could not reconstruct the
original source-file tree from the available debug associations.

The experiment produced only `lost+found.h`, containing 8769 unsupported or
unassigned type declarations. No C or C++ translation units were generated.

This does not make the CCC data unusable. `stdump files` still provides useful
address-bearing source/debug markers, while `stdump functions` provides
function addresses and sizes.

The project therefore uses these records as a research aid to construct an
address-based source map. Such ranges are considered provisional until
validated against additional linker/debug evidence.

## Source Marker Validation

Candidate source/debug ranges are cross-checked against:

1. CCC `stdump files` source-address markers.
2. Function addresses from the retail ELF symbol table.
3. The generated Splat symbol map.

A source marker is considered to have strong marker evidence when both the
retail ELF and Splat contain a function symbol at the same starting address.

This is deliberately described as marker evidence rather than proof of an
original object-file boundary. Final translation-unit boundaries still require
validation against surrounding symbols, debug metadata, section layout, and
matching behavior.
