#!/usr/bin/env python3
import argparse
import re
from pathlib import Path

def process_gcode(lines, z_up=5, z_down=0, z_feed=500, use_g0=True, keep_s=True, scan_feed=None):
    out = []
    # Use relative Z moves. Track whether we're currently lifted.
    is_raised = False
    # Only apply Z insertion within Scan section
    in_scan_section = False

    # Extract numeric S value from a line if present
    def get_s_value(line):
        code = line.split(';', 1)[0]
        if not code.strip():
            return None
        m = re.search(r"(?i)S\s*(-?\d+(?:\.\d+)?)", code)
        if not m:
            return None
        try:
            return float(m.group(1))
        except ValueError:
            return None

    # format with up to 3 decimals, trim trailing zeros
    def _fmt(val):
        try:
            f = float(val)
        except Exception:
            return str(val)
        s = f"{f:.3f}"
        s = s.rstrip('0').rstrip('.')
        return s if s else "0"

    def zcmd(value):
        cmd_g = "G0" if use_g0 else "G1"
        cmd = f"{cmd_g} Z{_fmt(value)}"
        if z_feed:
            cmd += f" F{_fmt(z_feed)}"
        return cmd

    def replace_feed(line):
        if scan_feed is None:
            return line
        # Replace any F<number> (with optional decimals and optional spaces) with F{scan_feed}
        return re.sub(r"F\s*[-+]?\d+(?:\.\d+)?", lambda m: f"F{_fmt(scan_feed)}", line)

    for line in lines:
        lstripped = line.lstrip()
        # Detect section transitions by comment lines
        if lstripped.startswith(';'):
            if re.search(r"(?i)\bScan\b", lstripped):
                in_scan_section = True
                is_raised = False  # reset state at start of each Scan block
            if re.search(r"(?i)\b(Offset|Cut)\b", lstripped):
                in_scan_section = False
                is_raised = False  # ensure lowered outside scan
        # detect S off/on by numeric value
        s_val = get_s_value(lstripped)
        needs_up = (s_val == 0)
        needs_down = (s_val is not None and s_val > 0)

        if in_scan_section and needs_up:
            if not is_raised:
                out.append(f"{zcmd(z_up)}\n")  # lift by +z_up
                is_raised = True
        if in_scan_section and needs_down:
            if is_raised:
                out.append(f"{zcmd(-float(z_up))}\n")  # drop by -z_up
                is_raised = False

        if keep_s:
            out.append(replace_feed(line))
        else:
            # Remove S0/S900 tokens even when glued, keep rest of the line intact
            cleaned = re.sub(r"(?i)S(?:0|900)(?!\d)", "", line)
            out.append(replace_feed(cleaned))

    return out

def main():
    ap = argparse.ArgumentParser(description="Insert Z moves before S0/S900 in raster G-code.")
    ap.add_argument("input", type=Path, help="Input G-code file")
    ap.add_argument("output", type=Path, help="Output G-code file")
    ap.add_argument("--z-up", type=float, default=5, help="Z height before S0 (default: 5)")
    ap.add_argument("--z-down", type=float, default=0, help="Z height before S900 (default: 0)")
    ap.add_argument("--z-feed", type=float, default=500, help="Feedrate for Z moves (default: 500)")
    ap.add_argument("--scan-feed", type=float, default=None, help="Override scan feedrate for moves; if not set, auto-detect from ';Scan @ <n> mm/min' header")
    ap.add_argument("--remove-s", action="store_true", help="Remove S commands from output")
    args = ap.parse_args()

    with args.input.open('r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    # Auto-detect scan feed from header comment if not provided
    scan_feed = args.scan_feed
    if scan_feed is None:
        for ln in lines[:50]:  # look in first 50 lines
            m = re.search(r";\s*Scan\s*@\s*(\d+(?:\.\d+)?)\s*mm\s*/?\s*min", ln, flags=re.IGNORECASE)
            if m:
                try:
                    scan_feed = float(m.group(1))
                except ValueError:
                    pass
                break

    result = process_gcode(
        lines,
        z_up=args.z_up,
        z_down=args.z_down,
        z_feed=args.z_feed,
        use_g0=True,
        keep_s=not args.remove_s,
        scan_feed=scan_feed,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', encoding='utf-8') as f:
        f.writelines(result)

if __name__ == "__main__":
    main()
