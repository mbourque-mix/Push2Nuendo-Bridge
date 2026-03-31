"""
overview.py — Overview mode for the Push 2

Displays project tracks on the 8x8 pad grid.
- Each track = one pad in its color
- New row when the color changes
- Pads control Mute/Solo/Rec/Monitor according to the active mode
- Visuals: dim=mute, highlight=solo, red blink=rec, blink=monitor
"""


def compute_overview_layout(tracks, total_tracks, page=0):
    """Computes the track → pad position mapping.
    
    Tracks of the same color are on the same row.
    When the color changes, we move to the next row.
    Pagination is done in groups of 8 rows.
    
    Returns:
        pad_map: dict {(row, col): track_index}
        track_positions: dict {track_index: (row, col)}
        total_rows: int (total number of rows)
    """
    # First, compute all rows
    all_rows = []  # List of lists of track_index
    current_row = []
    prev_color = None
    
    for i in range(total_tracks):
        if i >= len(tracks):
            break
        
        track = tracks[i]
        if not track.name:
            continue
        
        current_color = track.color
        if prev_color is not None and current_color != prev_color:
            if current_row:
                all_rows.append(current_row)
                current_row = []
        
        current_row.append(i)
        prev_color = current_color
        
        if len(current_row) >= 8:
            all_rows.append(current_row)
            current_row = []
    
    if current_row:
        all_rows.append(current_row)
    
    total_rows = len(all_rows)
    
    # Extract the 8 rows for the requested page
    start_row = page * 8
    page_rows = all_rows[start_row:start_row + 8]
    
    pad_map = {}
    track_positions = {}
    
    for row_idx, row_tracks in enumerate(page_rows):
        for col_idx, track_idx in enumerate(row_tracks):
            if col_idx < 8:
                pad_map[(row_idx, col_idx)] = track_idx
                track_positions[track_idx] = (row_idx, col_idx)
    
    return pad_map, track_positions, total_rows


def get_pad_color_for_overview(track, is_any_solo_active, lower_mode):
    """Determines the color of a pad in Overview mode."""
    r, g, b = track.color
    
    base_color = _rgb_to_pad_color(r, g, b)
    dim_color = _rgb_to_pad_color(r // 3, g // 3, b // 3)
    if dim_color == 0:
        dim_color = 1  # At least dim white
    
    # Rec active → bright red (priority)
    if track.is_armed:
        return 4, True  # Bright red, blink
    
    # Monitor active → color, blink
    if track.is_monitored:
        return base_color, True
    
    # Mute active → dim
    if track.is_muted:
        return dim_color, False
    
    # Solo active somewhere
    if is_any_solo_active:
        if track.is_solo:
            return base_color, False  # Bright
        else:
            return dim_color, False   # Dim
    
    # Normal
    return base_color, False


def _rgb_to_pad_color(r, g, b):
    """Converts an RGB color to a Push 2 palette index.
    
    The Push 2 palette is organized in color groups.
    We use the documented Ableton values.
    Each color has 3 intensities: dim (idx), mid (idx+1), bright (idx+2)
    """
    lum = (r + g + b) / 3
    if lum < 10:
        return 0  # Off
    
    max_c = max(r, g, b)
    min_c = min(r, g, b)
    diff = max_c - min_c
    
    if diff < 25:
        # Grey/white
        if lum > 100:
            return 122  # Bright white
        else:
            return 123  # Dim white
    
    # Hue calculation (0-360)
    if diff == 0:
        hue = 0
    elif max_c == r:
        hue = 60 * (((g - b) / diff) % 6)
    elif max_c == g:
        hue = 60 * ((b - r) / diff + 2)
    else:
        hue = 60 * ((r - g) / diff + 4)
    if hue < 0:
        hue += 360
    
    # Push 2 color table (based on Ableton documentation)
    # Format: (hue_min, hue_max, palette_bright)
    color_table = [
        (0,   15,  4),    # Red
        (15,  40,  10),   # Orange
        (40,  55,  14),   # Yellow-orange
        (55,  75,  16),   # Yellow
        (75,  100, 20),   # Yellow-green
        (100, 140, 26),   # Green
        (140, 170, 30),   # Cyan-green
        (170, 200, 34),   # Cyan
        (200, 230, 42),   # Blue
        (230, 260, 46),   # Indigo-blue
        (260, 290, 50),   # Purple
        (290, 320, 54),   # Magenta
        (320, 345, 58),   # Pink
        (345, 360, 4),    # Red (wrap)
    ]
    
    base = 122  # White by default
    for h_min, h_max, pal_idx in color_table:
        if h_min <= hue < h_max:
            base = pal_idx
            break
    
    # Adjust brightness: -2=dim, -1=mid, 0=bright
    if lum < 60:
        return max(1, base - 2)
    elif lum < 120:
        return max(1, base - 1)
    return base
