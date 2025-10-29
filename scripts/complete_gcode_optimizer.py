#!/usr/bin/env python3
"""
MiniPenzlograf G-code Optimizer
================================

This script optimizes G-code files for the miniPenzlograf CNC painting machine.
It inserts color pickup and washing sequences, formats G-code for best performance,
and provides detailed output about drawing paths and color transitions.

How to Use:
-----------
Basic optimization (creates <input_file>_optimized.gcode):
    python3 scripts/complete_gcode_optimizer.py input.gcode

Specify output filename:
    python3 scripts/complete_gcode_optimizer.py input.gcode -o custom_output.gcode

Change color pickup distance threshold (in mm):
    python3 scripts/complete_gcode_optimizer.py input.gcode -d 120

Force color pickup if path exceeds a multiple of the threshold (default 2.0):
    python3 scripts/complete_gcode_optimizer.py input.gcode -d 100 -f 2.5

Enable debug output:
    python3 scripts/complete_gcode_optimizer.py input.gcode --debug

Aggressive mode (insert pickups at any point after threshold):
    python3 scripts/complete_gcode_optimizer.py input.gcode --aggressive

Analyze G-code structure (no optimization):
    python3 scripts/complete_gcode_optimizer.py input.gcode --analyze

Examples:
---------
    python3 scripts/complete_gcode_optimizer.py coconutLogo2.gcode
    python3 scripts/complete_gcode_optimizer.py RandenTreeSmall_new.gcode -d 150 --debug
    python3 scripts/complete_gcode_optimizer.py artwork.gcode -o artwork_cleaned.gcode --analyze

"""

import sys
import math
import re
import os
import argparse
from datetime import datetime

# Sequences based on user preferences from AllMoves file
HOMING_SEQUENCE = """
G0 Z10 F500;      ; Move to clearance level - Z motion limited to 500
; G0 X-10 Y-10 F1200; Homing
; G0 X-5 Y-5 F1200; go in
; G10 P0 L20 X0 Y0; set to zero
G1 F1200;           ; Set feed rate to 1000
"""

COLOR1_SEQUENCE = """
; Color 1 picking sequence
G1 Z10 F500;         ; Raise brush to safe height
G0 X41 Y5 F1200;    ; Rapid move to color 1 position
G1 Z0 F500;         ; Lower into color - controlled movement
G1 X40.102Y7.295Z0S800F1200
G1 X40.026Y7.642Z0F1200
G1 X40Y8Z0F1200
G1 X40.026Y8.358Z0F1200
G1 X40.102Y8.705Z0F1200
G1 X40.225Y9.041Z0F1200
G1 X40.393Y9.362Z0F1200
G1 X40.603Y9.668Z0F1200
G1 X40.854Y9.957Z0F1200
G1 X41.142Y10.226Z0F1200
G1 X41.464Y10.475Z0F1200
G1 X41.82Y10.701Z0F1200
G1 X42.204Y10.902Z0F1200
G1 X42.617Y11.078Z0F1200
G1 X43.054Y11.225Z0F1200
G1 X43.513Y11.343Z0F1200
G1 X43.992Y11.429Z0F1200
G1 X44.489Y11.482Z0F1200
G1 X45Y11.5Z0F1200
G1 X45.511Y11.482Z0F1200
G1 X46.008Y11.429Z0F1200
G1 X46.487Y11.343Z0F1200
G1 X46.946Y11.225Z0F1200
G1 X47.383Y11.078Z0F1200
G1 X47.796Y10.902Z0F1200
G1 X48.18Y10.701Z0F1200
G1 X48.536Y10.475Z0F1200
G1 X48.858Y10.226Z0F1200
G1 X49.146Y9.957Z0F1200
G1 X49.397Y9.668Z0F1200
G1 X49.607Y9.362Z0F1200
G1 X49.775Y9.041Z0F1200
G1 X49.898Y8.705Z0F1200
G1 X49.974Y8.358Z0F1200
G1 X50Y8Z0F1200
G1 X49.974Y7.642Z0F1200
G1 X49.898Y7.295Z0F1200
G1 X49.775Y6.959Z0F1200
G1 X49.607Y6.638Z0F1200
G1 X49.397Y6.332Z0F1200
G1 X49.146Y6.043Z0F1200
G1 X48.858Y5.774Z0F1200
G1 X48.536Y5.525Z0F1200
G1 X48.18Y5.299Z0F1200
G1 X47.796Y5.098Z0F1200
G1 X47.383Y4.922Z0F1200
G1 X46.946Y4.775Z0F1200
G1 X46.487Y4.657Z0F1200
G1 X46.008Y4.571Z0F1200
G1 X45.511Y4.518Z0F1200
G1 X45Y4.5Z0F1200
G1 X44.489Y4.518Z0F1200
G1 X43.992Y4.571Z0F1200
G1 X43.513Y4.657Z0F1200
G1 X43.054Y4.775Z0F1200
G1 X42.617Y4.922Z0F1200
G1 X42.204Y5.098Z0F1200
G1 X41.82Y5.299Z0F1200
G1 X41.464Y5.525Z0F1200
G1 X41.142Y5.774Z0F1200
G1 X40.854Y6.043Z0F1200
G1 X40.603Y6.332Z0F1200
G1 X40.393Y6.638Z0F1200
G1 X40.225Y6.959Z0F1200
G1 Z7 F800;         ; Raise from color - controlled movement
G1 X34 Y8 Z1 F1200;     ; Movement in paint - controlled movement
G1 X24 Y12 Z8 F500;     ; Move in paint - controlled movement
G1 F1200;           ; Set feed rate to 1000
"""

# Helper to derive other color sequences by shifting X coordinates
def _offset_x_in_gcode_block(block: str, dx: float) -> str:
    """Shift all X-coordinates in a G-code text block by dx, preserving decimal precision and whitespace."""
    # Match 'X', optional spaces, numeric value with optional decimals
    pattern = re.compile(r"X(\s*)(-?\d+(?:\.\d+)?)")

    def repl(m: re.Match) -> str:
        space = m.group(1)
        orig = m.group(2)
        # Determine decimal places to preserve formatting
        if '.' in orig:
            decimals = len(orig.split('.')[1])
        else:
            decimals = 0
        try:
            new_val = float(orig) + dx
        except ValueError:
            return m.group(0)  # fallback, should not happen
        if decimals > 0:
            formatted = f"{new_val:.{decimals}f}"
        else:
            # keep integer format if originally integer
            formatted = str(int(round(new_val)))
        return f"X{space}{formatted}"

    return pattern.sub(repl, block)

COLOR2_SEQUENCE = _offset_x_in_gcode_block(COLOR1_SEQUENCE, 45)

COLOR3_SEQUENCE = """
; Color 3 picking sequence, minimal cos it's at the edge
G1 Z10 F500;         ; Raise brush to safe height
G0 X124 Y12 F1200;    ; Rapid move to color 1 position
G1 Z0 F500;         ; Lower into color - controlled movement
G1 Z7 F800;         ; Raise from color - controlled movement
G1 X119 Y12 Z1 F1200;     ; Movement in paint - controlled movement
G1 X114 Y15 Z8 F500;     ; Move in paint - controlled movement
G1 F1200;           ; Set feed rate to 1000
"""

WASHING_SEQUENCE = """
; Washing sequence (no color)
G1 Z10 F1000;        ; Raise brush to safe height
G0 X5 Y5 F1200;     ; Rapid move to brush cleaning position
G1 Z-1 F800;         ; Lower brush for cleaning - controlled movement
G1 X10 Y12 Z8 F1200;     ; Rapid move to brush cleaning position
G1 Z-1 F800;         ; Lower brush for cleaning - controlled movement
G1 X25 Y14 Z6 F800;     ; Move across cleaning area - controlled movement
G1 Z8 F800;         ; Maintain brush height - controlled movement
G0 X5 Y5 F1200;     ; Rapid move to brush cleaning position
G1 Z-1 F800;         ; Lower brush for cleaning - controlled movement
G1 X15 Y12 Z8 F1200;     ; Rapid move to brush cleaning position
G1 Z-1 F800;         ; Lower brush for cleaning - controlled movement
G1 X25 Y14 Z6 F800;     ; Move across cleaning area - controlled movement
G1 Z10 F800;         ; Maintain brush height - controlled movement
G1 F1200;           ; Set feed rate to 1000
"""

ENDING_SEQUENCE = """
; Return to 2,0 wash and park
G1 Z10 F1000;        ; Raise brush to safe height
G0 X5 Y5 F1200;     ; Rapid move to brush cleaning position
G1 Z-1 F800;         ; Lower brush for cleaning - controlled movement
G1 X10 Y12 Z8 F1200;     ; Rapid move to brush cleaning position
G1 Z-1 F800;         ; Lower brush for cleaning - controlled movement
G1 X25 Y14 Z6 F800;     ; Move across cleaning area - controlled movement
G0 X5 Y5 F1200;     ; Rapid move to brush cleaning position
G1 Z-1 F800;         ; Lower brush for cleaning - controlled movement
G1 X15 Y12 Z8 F1200;     ; Rapid move to brush cleaning position
G1 Z-1 F800;         ; Lower brush for cleaning - controlled movement
G1 X25 Y14 Z6 F800;     ; Move across cleaning area - controlled movement
G1 Z10 F800;         ; Maintain brush height - controlled movement
G0 X20 Y110 Z10 F500;; Move to parking position with Z at safe height
M2;                 ; End program
"""

# Map layer names to color sequences and names
LAYER_COLOR_MAP = {
    "Green": {"sequence": COLOR1_SEQUENCE, "name": "Color 1"},
    "Blue": {"sequence": COLOR2_SEQUENCE, "name": "Color 2"},
    "Red": {"sequence": COLOR3_SEQUENCE, "name": "Color 3"},
    "C03": {"sequence": COLOR3_SEQUENCE, "name": "Color 3"},
    "C00": {"sequence": COLOR1_SEQUENCE, "name": "Color 1"},
    "Wash": {"sequence": WASHING_SEQUENCE, "name": "Washing"},
    "default": {"sequence": WASHING_SEQUENCE, "name": "Washing"}
}

def next_z_lift_in_range(lines, start_index, max_lookahead=50):
    """Check if there's a Z lift (G0 Z) within the next max_lookahead lines"""
    end_index = min(start_index + max_lookahead, len(lines))
    for i in range(start_index, end_index):
        if re.search(r'G0\s*Z[1-9]|G0.*Z[1-9]', lines[i]):
            return i - start_index
    return None

def optimize_gcode(input_file, output_file=None, distance_threshold=100, force_multiplier=2.0, debug=False, aggressive=False):
    """
    Comprehensive G-code optimizer that:
    1. Adds homing sequence at the beginning
    2. Formats G-codes according to user preferences
    3. Adds color pickup sequences at the start of each layer
    4. Adds color pickup sequences when the accumulated length exceeds distance_threshold
    5. Adds washing sequence when transitioning between different colors
    6. Forces pickup only when path length exceeds force_multiplier * distance_threshold
    
    Args:
        input_file: Path to input G-code file
        output_file: Path to output G-code file (default: input_file_optimized.gcode)
        distance_threshold: Distance threshold for color pickups (mm)
        force_multiplier: Only force pickups when path length exceeds this multiple of threshold
        debug: Print additional debug information
        aggressive: Aggressively insert pickups at any point if force threshold is exceeded
    """
    if output_file is None:
        base_name = os.path.splitext(input_file)[0]
        output_file = f"{base_name}_optimized.gcode"
    
    # Read the G-code file
    try:
        with open(input_file, 'r') as f:
            content = f.read()
            # Ensure each line ends with a newline
            lines = [line + '\n' if not line.endswith('\n') else line for line in content.splitlines()]
            if debug:
                print(f"Read {len(lines)} lines from {input_file}")
    except Exception as e:
        print(f"Error reading file {input_file}: {e}")
        return 0, {}
    
    # Initialize variables
    total_length = 0
    accumulated_length = 0  # Length since last color pickup
    current_x, current_y = 0, 0
    prev_x, prev_y = 0, 0
    is_drawing = False  # Set initial state to not drawing
    current_segment_length = 0  # Length of the current segment for tracking
    layer_lengths = {}  # Track length of each layer
    path_lengths = {}  # Track length of each path
    current_path = "None"  # Current path identifier
    current_layer = "default"  # Default layer name
    previous_layer = None
    pickup_segments = []  # Store segments for output summary
    color_pickup_count = {"Color 1": 0, "Color 2": 0, "Color 3": 0, "Washing": 0}  # Count color pickups
    
    # Current color tracking
    current_color_sequence = WASHING_SEQUENCE
    current_color_name = "Washing"
    last_color_name = None  # Track the last color used for washing decisions
    
    # Track paths between color pickups
    segment_start_position = (0, 0)
    
    # Regular expressions for parsing
    coord_regex = re.compile(r'G[01]\s*X([\d.-]+)Y([\d.-]+)Z[\d.-]+F')
    layer_regex = re.compile(r';Layer\s+(\w+)')
    m8_regex = re.compile(r'M8')
    path_regex = re.compile(r'; Path\s+(\d+)')
    plunge_regex = re.compile(r'Z0F')
    retract_regex = re.compile(r'Z[2-9]F')
    
    # Start building the output file
    output_lines = []
    
    # Add homing sequence
    output_lines.append(HOMING_SEQUENCE)
    
    # Process the file
    line_index = 0
    processed_count = 0
    found_m8 = False
    
    while line_index < len(lines):
        line = lines[line_index]
        
        # Check for M8 command (marker for new section)
        if m8_regex.search(line):
            found_m8 = True
            output_lines.append(line)  # Add the M8 line
            line_index += 1
            
            # Look ahead to find layer label
            look_ahead_limit = 6  # Look ahead up to 6 lines for layer label
            next_layer = None
            
            # Save the current position
            look_ahead_index = line_index
            
            # Search forward for layer label
            for i in range(look_ahead_limit):
                if look_ahead_index < len(lines):
                    ahead_line = lines[look_ahead_index]
                    layer_match = layer_regex.search(ahead_line)
                    if layer_match:
                        next_layer = layer_match.group(1)
                        break
                    look_ahead_index += 1
            
            # If layer found, add color pickup after M8
            if next_layer in LAYER_COLOR_MAP:
                current_layer = next_layer
                if current_layer != previous_layer:
                    layer_lengths[current_layer] = layer_lengths.get(current_layer, 0)
                    accumulated_length = 0  # Reset accumulated length on layer change
                    current_segment_length = 0  # Also reset segment length
                    print(f"\n==== Layer transition to {current_layer} - Resetting distance tracking ====\n")
                    
                    # Set color sequence based on the layer
                    previous_color_name = current_color_name if current_color_name else "None"
                    current_color_sequence = LAYER_COLOR_MAP[current_layer]["sequence"]
                    current_color_name = LAYER_COLOR_MAP[current_layer]["name"]
                    
                    print(f"\nLayer {current_layer} - Using {current_color_name}")
                    
                    # First add washing sequence if changing to a different color
                    if previous_color_name != "None" and previous_color_name != current_color_name:
                        print(f"Adding washing sequence for color change: {previous_color_name} -> {current_color_name}")
                        output_lines.append(WASHING_SEQUENCE)
                        color_pickup_count["Washing"] += 1
                    
                    # Then add the appropriate color pickup sequence after M8
                    output_lines.append(current_color_sequence)
                    color_pickup_count[current_color_name] += 1
                    previous_layer = current_layer
                    last_color_name = current_color_name
            continue
        
        # Check for layer change (if not handled by M8)
        layer_match = layer_regex.search(line)
        if layer_match and not found_m8:
            current_layer = layer_match.group(1)
            if current_layer != previous_layer and previous_layer is None:
                layer_lengths[current_layer] = layer_lengths.get(current_layer, 0)
                accumulated_length = 0  # Reset accumulated length on layer change
                
                # Set color sequence based on the layer
                if current_layer in LAYER_COLOR_MAP:
                    current_color_sequence = LAYER_COLOR_MAP[current_layer]["sequence"]
                    current_color_name = LAYER_COLOR_MAP[current_layer]["name"]
                else:
                    current_color_sequence = LAYER_COLOR_MAP["default"]["sequence"]
                    current_color_name = LAYER_COLOR_MAP["default"]["name"]
                    
                print(f"\nLayer {current_layer} - Using {current_color_name}")
                
                # First add washing sequence if changing to a different color
                if previous_color_name != "None" and previous_color_name != current_color_name:
                    print(f"Adding washing sequence for color change: {previous_color_name} -> {current_color_name}")
                    output_lines.append(WASHING_SEQUENCE)
                    color_pickup_count["Washing"] += 1
                
                # Then add the appropriate color pickup sequence at the start of the layer
                output_lines.append(current_color_sequence)
                color_pickup_count[current_color_name] += 1
                previous_layer = current_layer
                last_color_name = current_color_name
        
        # Reset M8 flag when we hit a layer label
        if layer_match:
            found_m8 = False
            # Make sure segment length is also reset when hitting a new layer label
            if current_layer != previous_layer:
                accumulated_length = 0
                current_segment_length = 0
                print(f"\n==== Layer label found {current_layer} - Resetting distance tracking ====\n")
        
        # Format and add the current line
        # Fix G-code commands and Z values
        if re.search(r'G1 Z3\.0000', line):
            output_lines.append("G1 Z3 F1000;         ; Raise brush\n")
        elif re.search(r'G1 Z0\.0000', line):
            output_lines.append("G1 Z0 F1000;         ; Position at surface\n")
        elif re.search(r'G1 Z-0\.1000 F500', line):
            output_lines.append("G1 Z-0.1 F1000;      ; Plunge brush to painting depth\n")
        elif re.search(r'^G1 (X.*Y.* F1200)$', line):
            match = re.search(r'^G1 (X.*Y.* F1200)$', line)
            output_lines.append(f"G0 {match.group(1)}   ; Move to starting position\n")
        else:
            output_lines.append(line)
        
        # Check for path change
        path_match = path_regex.search(line)
        if path_match:
            if current_path != "None":
                print(f"Path {current_path} length: {path_lengths.get(current_path, 0):.2f} mm")
            current_path = path_match.group(1)
            path_lengths[current_path] = 0
        
        # Check if we're retracting (not drawing)
        if retract_regex.search(line):
            is_drawing = False
        
        # Check if we're plunging (starting to draw)
        if plunge_regex.search(line):
            is_drawing = True
        
        # Extract coordinates
        coord_match = coord_regex.search(line)
        if coord_match:
            prev_x, prev_y = current_x, current_y
            current_x = float(coord_match.group(1))
            current_y = float(coord_match.group(2))
            
            # If already moved at least once and currently drawing
            if (prev_x != 0 or prev_y != 0) and is_drawing and "G1" in line:
                # Calculate Euclidean distance
                segment_length = math.sqrt((current_x - prev_x)**2 + (current_y - prev_y)**2)
                total_length += segment_length
                accumulated_length += segment_length
                
                # Update layer length
                layer_lengths[current_layer] = layer_lengths.get(current_layer, 0) + segment_length
                
                # Update path length
                path_lengths[current_path] = path_lengths.get(current_path, 0) + segment_length
                
                # Update segment length
                current_segment_length += segment_length
                
                # Check if we need to add another color pickup
                if accumulated_length > distance_threshold:
                    # Different behavior for aggressive vs normal mode
                    is_clean_transition = False
                    # Ensure force_pickup is always defined regardless of branch
                    force_pickup = False
                    
                    if aggressive:
                        # In aggressive mode: ANY G0/G1 command can be a pickup point once we exceed the threshold
                        if re.search(r'G[01]', line):
                            is_clean_transition = True
                            if debug:
                                print(f"AGGRESSIVE: Inserting pickup at any G-code command at line {line_index}")
                                print(f"  Length: {accumulated_length:.2f}mm, Line: {line.strip()}")
                    else:
                        # Normal mode - strongly prioritize natural transitions
                        
                        # Best transition: Current line is a G0 Z lift
                        if re.search(r'G0\s*Z[1-9]|G0.*Z[1-9]', line):
                            is_clean_transition = True
                            if debug:
                                print(f"IDEAL: Found Z-lift at line {line_index}: {line.strip()}")
                        
                        # Second best: End of a drawing segment (where G1 drawing is followed by G0 positioning)
                        elif line_index > 0 and line_index + 1 < len(lines):
                            prev_is_g1 = re.search(r'G1\s*X|G1\s*Y', lines[line_index-1]) is not None
                            next_is_g0 = re.search(r'G0\s*', lines[line_index+1]) is not None
                            if prev_is_g1 and next_is_g0:
                                is_clean_transition = True
                                if debug:
                                    print(f"GOOD: Found G1→G0 transition at line {line_index}")
                    
                    # Force pickup logic with lookahead - applies to normal mode only
                    if not aggressive and not is_clean_transition:
                        force_pickup = accumulated_length >= (force_multiplier * distance_threshold)
                        
                        # Before forcing, look ahead to see if a Z lift is coming soon
                        if force_pickup:
                            z_lift_distance = next_z_lift_in_range(lines, line_index, 20)  # Look 20 lines ahead
                            
                            # If a Z lift is coming soon, prefer to wait for it
                            if z_lift_distance is not None and z_lift_distance < 10:  # Within 10 lines
                                if debug:
                                    print(f"WAITING: Z lift coming in {z_lift_distance} lines, postponing pickup")
                                force_pickup = False  # Don't force, wait for the Z lift
                            
                            # Otherwise, force pickup at a reasonable point (G0/G1 command)
                            elif re.search(r'G[01]', line):
                                is_clean_transition = True
                                if debug:
                                    print(f"FORCING: No Z lifts nearby, pickup at {accumulated_length:.2f}mm")
                        
                    # If in aggressive mode, force pickup at any valid position
                    elif aggressive and not is_clean_transition:
                        force_pickup = accumulated_length >= (force_multiplier * distance_threshold)
                        if force_pickup and re.search(r'G[01]', line):
                            is_clean_transition = True
                            if debug:
                                print(f"AGGRESSIVE FORCE: Pickup at {accumulated_length:.2f}mm")
                    
                    # Emergency pickup logic - applies to both modes
                    # If we're way over the threshold (3x), force a pickup at ANY position
                    if accumulated_length >= (3.0 * distance_threshold) and not is_clean_transition:
                        is_clean_transition = True
                        if debug:
                            print(f"EMERGENCY PICKUP: Extremely long path {accumulated_length:.2f}mm (>3x threshold)")
                    
                    # Only insert pickup if we're at a clean transition point
                    if is_clean_transition:
                        if current_layer in LAYER_COLOR_MAP:
                            current_color_name = LAYER_COLOR_MAP[current_layer]["name"]
                            current_color_sequence = LAYER_COLOR_MAP[current_layer]["sequence"]
                        else:
                            current_color_name = LAYER_COLOR_MAP["default"]["name"]
                            current_color_sequence = LAYER_COLOR_MAP["default"]["sequence"]
                        
                        # More detailed debug output
                        if force_pickup and accumulated_length >= (force_multiplier * distance_threshold):
                            print(f"FORCING {current_color_name} pickup after {accumulated_length:.2f} mm (exceeded {force_multiplier*100}% threshold)")
                        else:
                            print(f"Adding {current_color_name} pickup after {accumulated_length:.2f} mm")
                        
                        # Save current position so we can return properly
                        return_x = current_x
                        return_y = current_y
                        return_z = 0  # We want to return to Z=0 for painting
                        
                        # First check if we need to wash when changing colors
                        if last_color_name and last_color_name != current_color_name:
                            if debug:
                                print(f"Adding washing sequence for color change: {last_color_name} -> {current_color_name}")
                            output_lines.append(WASHING_SEQUENCE)
                            color_pickup_count["Washing"] += 1
                        
                        # Then add the standard color pickup sequence
                        color_pickup_count[current_color_name] += 1
                        output_lines.append(current_color_sequence)
                        last_color_name = current_color_name  # Update last used color
                        
                        pickup_segments.append((current_layer, current_color_name, accumulated_length))
                        
                        # Reset counters after pickup
                        accumulated_length = 0
                        current_segment_length = 0
                        
                        # Decide if we interrupted an active drawing stroke; only then return to previous XY
                        next_line_is_g1 = (line_index + 1 < len(lines)) and (re.search(r'G1\s*X|G1\s*Y', lines[line_index+1]) is not None)
                        next_line_is_g0 = (line_index + 1 < len(lines)) and (re.search(r'G0\s*', lines[line_index+1]) is not None)
                        current_has_z_lift = re.search(r'G0\s*Z[1-9]|G0.*Z[1-9]', line) is not None
                        interrupted_active_stroke = is_drawing and next_line_is_g1 and not current_has_z_lift and not next_line_is_g0
                        
                        if interrupted_active_stroke:
                            # Then, add a proper return sequence with separate Z management
                            # First move X/Y with Z raised, then lower Z separately
                            return_sequence = f"""
; Return to drawing position
G0 X{return_x:.3f} Y{return_y:.3f} F1200;  ; Return to position with raised Z
G1 Z{return_z} F1000;                       ; Lower Z to drawing position
"""
                            output_lines.append(return_sequence)
        
        line_index += 1
        processed_count += 1
        if debug and processed_count % 100 == 0:
            print(f"Processed {processed_count} lines so far, current path length: {total_length:.2f}mm")
    
    if debug:
        print(f"Finished processing {processed_count} lines out of {len(lines)}")
        print(f"Final path length: {total_length:.2f}mm")
        if processed_count < len(lines):
            print(f"WARNING: Not all lines were processed. Last line: {line_index}")
    
    # Replace the ending with proper sequence
    output_lines.append(ENDING_SEQUENCE)
    
    # Combine the output lines into a single string with proper line breaks
    optimized_g_code = ''
    for line in output_lines:
        # Ensure each line ends with exactly one newline
        if not line.endswith('\n'):
            optimized_g_code += line + '\n'
        else:
            optimized_g_code += line
    
    # Write the optimized G-code to the output file
    with open(output_file, 'w') as f:
        f.write(optimized_g_code)
    
    # Print summary statistics
    print(f"\nSummary:")
    print(f"Total drawing path length: {total_length:.2f} mm ({total_length/1000:.2f} meters)\n")
    
    print(f"Layer Lengths:")
    for layer, length in layer_lengths.items():
        print(f"Layer {layer}: {length:.2f} mm")
    
    print("\nPath Segments Between Color Pickups:")
    for segment in pickup_segments:
        print(f"Layer {segment[0]}, Color {segment[1]}: {segment[2]:.2f} mm")
    
    print("\nColor Pickup Insertions:")
    for color, count in color_pickup_count.items():
        if count > 0:
            print(f"{color}: {count} pickups added")
    
    print(f"\nComprehensively optimized G-code written to: {output_file}")
    
    return total_length, layer_lengths

def next_line_content(lines, index, look_ahead=3):
    """
    Look ahead a few lines and return their content
    """
    content = ""
    for i in range(look_ahead):
        if index + i < len(lines):
            content += lines[index + i]
    return content

def analyze_gcode(input_file, debug=True):
    """Analyze the G-code file to understand its structure and drawing patterns."""
    with open(input_file, 'r') as f:
        lines = f.readlines()
    
    # Look for common patterns
    drawing_areas = 0
    z_moves = 0
    z0_moves = 0
    g0_moves = 0
    
    for i, line in enumerate(lines):
        if re.search(r'G0\s*Z[0-9.]+', line):
            z_moves += 1
            if i + 2 < len(lines):
                if re.search(r'G0\s*X[0-9.]+Y[0-9.]+', lines[i+1]) and re.search(r'G1\s*Z0', lines[i+2]):
                    drawing_areas += 1
                    if debug:
                        print(f"Drawing area at line {i+1}: {lines[i+1].strip()}")
        
        if re.search(r'G1\s*Z0', line):
            z0_moves += 1
        
        if re.search(r'G0\s*X|G0\s*Y', line):
            g0_moves += 1
    
    print(f"\nG-code Analysis for {input_file}:")
    print(f"  Total lines: {len(lines)}")
    print(f"  Detected drawing areas: {drawing_areas}")
    print(f"  Z movements (lifts): {z_moves}")
    print(f"  Z0 movements (drawing): {z0_moves}")
    print(f"  G0 positioning moves: {g0_moves}\n")
    
    return drawing_areas

def main():
    parser = argparse.ArgumentParser(description="Optimize G-code for miniPenzlograf")
    parser.add_argument("input_file", help="Input G-code file")
    parser.add_argument("-o", "--output", help="Output G-code file (default: input_file_optimized.gcode)")
    parser.add_argument("-d", "--distance", type=float, default=100, help="Distance threshold for color pickups (mm)")
    parser.add_argument("-f", "--force-multiplier", type=float, default=2.0, 
                     help="Only force pickups when path length exceeds this multiple of threshold (default: 2.0)")
    parser.add_argument("--debug", action="store_true", help="Print additional debug information")
    parser.add_argument("--analyze", action="store_true", help="Analyze the G-code file structure without optimizing")
    parser.add_argument("--aggressive", action="store_true", help="Aggressively insert pickups at any point if force threshold is exceeded")
    args = parser.parse_args()
    
    # Analyze file structure if requested
    if args.analyze:
        analyze_gcode(args.input_file)
        return
    
    # Generate default output filename if not specified
    if not args.output:
        base_name = os.path.basename(args.input_file)
        file_name, file_ext = os.path.splitext(base_name)
        args.output = f"{file_name}_optimized{file_ext}"
    
    # Run the optimization
    optimize_gcode(args.input_file, args.output, args.distance, args.force_multiplier, args.debug, args.aggressive)

if __name__ == "__main__":
    main()
