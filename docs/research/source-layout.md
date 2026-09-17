# Original Source Layout

Recovered from debug information and embedded paths in SLUS_202.67.

## prog/source

Source files belonging primarily to game logic.

## prog/system

Source files belonging primarily to engine/system code.

## Translation Unit Mapping

Function-to-source-file boundaries are still being reconstructed.

## Validated Candidate: prog/system/syspad.cpp

CCC and retail-symbol validation supports the following candidate text range:

- Start VRAM: `0x00102390`
- End VRAM: `0x00103410`
- Extracted-image offsets: `0x002390` to `0x003410`
- Size: `0x1080`

Functions:

- `SetAnalogStick__FPfPUcii`
- `Init__5ccPadFUcUc`
- `Ctrl__5ccPadFv`
- `SetActuater__5ccPadFiii`
- `Read__5ccPadFv`
- `ccPadThread__FP6ccTscb`

The range has been isolated as `prog/system/syspad` in the Splat
configuration. Both boundaries coincide with retail ELF function symbols
and generated Splat symbols.

This is treated as a strongly supported candidate translation unit.
Successful matching and relinking will provide further confirmation.
