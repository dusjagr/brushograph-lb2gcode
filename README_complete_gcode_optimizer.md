# MiniPenzlograf G-code Optimizer (single-file usage)

This README explains how to use `complete_gcode_optimizer.py` directly, without installing anything.

## Requirements
- Python 3.8 or newer
- The file: `scripts/complete_gcode_optimizer.py`

## Quick Start
```bash
# From the repository root or the scripts folder
python3 scripts/complete_gcode_optimizer.py <input.gcode>
# Output defaults to <input>_optimized.gcode
```

## Common Usage
- Specify output file:
```bash
python3 scripts/complete_gcode_optimizer.py input.gcode -o output.gcode
```
- Change pickup distance threshold (mm):
```bash
python3 scripts/complete_gcode_optimizer.py input.gcode -d 120
```
- Only force pickups beyond a multiple of the threshold (default 2.0):
```bash
python3 scripts/complete_gcode_optimizer.py input.gcode -d 100 -f 2.5
```
- Enable debug logs:
```bash
python3 scripts/complete_gcode_optimizer.py input.gcode --debug
```
- Aggressive mode (insert pickups anywhere after threshold):
```bash
python3 scripts/complete_gcode_optimizer.py input.gcode --aggressive
```
- Analyze structure only (no changes written):
```bash
python3 scripts/complete_gcode_optimizer.py input.gcode --analyze
```

## What it does
- Adds homing header and a clean ending sequence.
- Formats G-code for the miniPenzlograf painting CNC:
  - Uses `G0` for positioning and `G1` for drawing.
  - Manages Z moves as separate, safe operations.
  - Simplifies some Z values and maintains clean feedrate usage.
- Inserts color pick-up sequences at layer starts and when path length exceeds the threshold.
- Inserts washing sequences when changing colors.
- Picks clean transition points (Z-lifts, end-of-stroke) and only returns to the previous XY if a stroke was interrupted.

## Notes
- No external dependencies; it uses only Python standard library.
- You can mark layers in your input with comments like `;Layer Green`, `;Layer Blue`, etc. The script maps these to built‑in color and washing sequences.
- Default preferences match the miniPenzlograf setup. If you need different color locations or sequences, edit the block constants near the top of the script.

## Examples
```bash
# Basic run
python3 scripts/complete_gcode_optimizer.py MAG_new.gcode

# Custom output name + debug
python3 scripts/complete_gcode_optimizer.py MAG_new.gcode -o MAG_new_fixed.gcode --debug

# Larger threshold, force later
python3 scripts/complete_gcode_optimizer.py MAG_new.gcode -d 150 -f 2.5
```

## Make it executable (optional)
```bash
chmod +x scripts/complete_gcode_optimizer.py
./scripts/complete_gcode_optimizer.py input.gcode
```
