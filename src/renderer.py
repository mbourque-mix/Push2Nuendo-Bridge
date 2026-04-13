"""
renderer.py — Graphics rendering on the Push 2 display

The Push 2 screen is 960×160 pixels.
We divide it into 8 vertical zones of 120×160 pixels,
one per encoder.

This file handles drawing the interface based on
the active mode (Volume, Pan, Sends, Device, Inserts).

We use Pillow (PIL) for drawing, then convert
to BGR565 format to send to the Push 2.
"""

import numpy as np
import time
from PIL import Image, ImageDraw, ImageFont
from state import (
    MODE_VOLUME, MODE_PAN, MODE_SENDS, MODE_DEVICE, MODE_INSERTS, MODE_TRACK, MODE_OVERVIEW, MODE_CR,
    MODE_SETUP, MODE_MIDICC, AT_POLY, AT_CHANNEL, AT_OFF,
    VC_LINEAR, VC_LOG, VC_EXP, VC_SCURVE, VC_FIXED,
    BRIDGE_VERSION, BANK_SIZE, AppState
)
from control_room import (
    CR_PAGES, CR_PAGE_NAMES, CR_PAGE_MAIN, ControlRoomState
)

# ─────────────────────────────────────────────
# Screen dimensions
# ─────────────────────────────────────────────

SCREEN_WIDTH  = 960
SCREEN_HEIGHT = 160
CELL_WIDTH    = SCREEN_WIDTH // BANK_SIZE   # 120 pixels per cell

# ─────────────────────────────────────────────
# Color palette (RGB)
# ─────────────────────────────────────────────

COLOR_BG           = (18, 18, 18)     # General background (near black)
COLOR_BG_SELECTED  = (28, 28, 45)     # Selected track background (slightly blue)
COLOR_BG_MUTED     = (14, 14, 14)     # Muted track background (even darker)
COLOR_SEPARATOR    = (50, 50, 50)     # Cell separator line
COLOR_TEXT_MAIN    = (220, 220, 220)  # Main text (off white)
COLOR_TEXT_DIM     = (100, 100, 100)  # Secondary text (grey)
COLOR_TEXT_MUTED   = (60, 60, 60)     # Muted track text
COLOR_ACCENT       = (0, 180, 200)    # Cyan — general accent color
COLOR_VOLUME_BAR   = (0, 160, 100)    # Green for volume bars
COLOR_PAN_BAR      = (180, 120, 0)    # Orange for pan
COLOR_SEND_BAR     = (100, 80, 180)   # Purple for sends
COLOR_DEVICE_ARC   = (0, 160, 200)    # Cyan for device parameters
COLOR_WARNING      = (200, 60, 60)    # Red — clip or error
COLOR_SELECTED_HDR = (0, 140, 180)    # Selected track header

# ─────────────────────────────────────────────
# Character fonts
# ─────────────────────────────────────────────

def _load_fonts():
    """
    Load fonts. Uses system fonts if available,
    otherwise falls back to PIL default font.
    """
    try:
        # Try to load a clean monospace font
        font_large  = ImageFont.truetype("DejaVuSansMono.ttf", 14)
        font_medium = ImageFont.truetype("DejaVuSansMono.ttf", 11)
        font_small  = ImageFont.truetype("DejaVuSansMono.ttf", 9)
    except (IOError, OSError):
        # Fall back to PIL built-in font (always available)
        font_large  = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small  = ImageFont.load_default()
    return font_large, font_medium, font_small


FONT_LG, FONT_MD, FONT_SM = _load_fonts()


# ─────────────────────────────────────────────
# Drawing utility functions
# ─────────────────────────────────────────────

def _truncate(text, max_chars):
    """Truncate text and add '…' if too long."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 1] + "…"


def _abbreviate(text, max_chars):
    """
    Smart abbreviation: reduce text to max_chars by removing
    first lowercase vowels, then middle consonants of words,
    then spaces. Protects first char, last char, and
    digits at end of text.
    """
    if not text:
        return text
    if len(text) <= max_chars:
        return text
    
    n = len(text)
    vowels = set('aeiou')
    
    # Protect first char, last char, and trailing digits
    protected = set()
    protected.add(0)
    for i in range(n - 1, 0, -1):
        protected.add(i)
        if not text[i].isdigit() and text[i] != ' ':
            break
    
    remove_set = set()
    
    # Phase 1: remove lowercase vowels (except protected/first letter of word)
    for i in range(1, n):
        if i in protected:
            continue
        c = text[i]
        if c in vowels and text[i-1] not in (' ', '-', '_'):
            remove_set.add(i)
            if n - len(remove_set) <= max_chars:
                break
    
    if n - len(remove_set) <= max_chars:
        return ''.join(text[i] for i in range(n) if i not in remove_set)[:max_chars]
    
    # Phase 2: remove lowercase consonants from middle of words
    for i in range(1, n):
        if i in protected or i in remove_set:
            continue
        c = text[i]
        if c.islower() and c not in vowels:
            if text[i-1] not in (' ', '-', '_'):
                remove_set.add(i)
                if n - len(remove_set) <= max_chars:
                    break
    
    if n - len(remove_set) <= max_chars:
        return ''.join(text[i] for i in range(n) if i not in remove_set)[:max_chars]
    
    # Phase 3: remove spaces
    for i in range(1, n):
        if i in protected or i in remove_set:
            continue
        if text[i] == ' ':
            remove_set.add(i)
            if n - len(remove_set) <= max_chars:
                break
    
    return ''.join(text[i] for i in range(n) if i not in remove_set)[:max_chars]


def _draw_bar(draw, x, y, width, height, value, color, bg_color=(40, 40, 40)):
    """
    Draw a horizontal progress bar.
    
    value: 0.0 to 1.0
    """
    # Bar background
    draw.rectangle([x, y, x + width, y + height], fill=bg_color, outline=None)
    # Fill proportional to value
    fill_width = int(width * max(0.0, min(1.0, value)))
    if fill_width > 0:
        draw.rectangle([x, y, x + fill_width, y + height], fill=color)


def _draw_pan_indicator(draw, x, y, width, height, pan_value, color):
    """
    Draw a pan indicator.
    
    pan_value: -1.0 (L) to +1.0 (R), 0.0 = center
    The center is at the middle of the zone.
    """
    center_x = x + width // 2
    
    # Baseline
    draw.line([(x, y + height // 2), (x + width, y + height // 2)],
              fill=(60, 60, 60), width=1)
    # Center tick
    draw.line([(center_x, y), (center_x, y + height)],
              fill=(70, 70, 70), width=1)
    
    # Indicator position
    pos_x = center_x + int(pan_value * (width // 2))
    pos_x = max(x + 2, min(x + width - 2, pos_x))
    
    # Bar from center to position
    draw.rectangle([
        min(center_x, pos_x), y + 2,
        max(center_x, pos_x), y + height - 2
    ], fill=color)
    
    # Cursor
    draw.rectangle([pos_x - 2, y, pos_x + 2, y + height], fill=COLOR_TEXT_MAIN)


def _draw_arc_knob(draw, cx, cy, radius, value, color, bg_color=(50, 50, 50)):
    """
    Draw a value indicator as a horizontal bar.
    
    value: 0.0 to 1.0
    """
    bar_width = radius * 2
    bar_height = 6
    x1 = cx - radius
    y1 = cy - bar_height // 2
    
    # Background (grey)
    draw.rectangle([x1, y1, x1 + bar_width, y1 + bar_height], fill=bg_color)
    
    # Value bar (colored)
    if value > 0.01:
        fill_width = int(bar_width * value)
        draw.rectangle([x1, y1, x1 + fill_width, y1 + bar_height], fill=color)
    
    # Indicator dot
    dot_x = x1 + int(bar_width * value)
    draw.ellipse([dot_x - 4, cy - 4, dot_x + 4, cy + 4], fill=COLOR_TEXT_MAIN)


def _draw_speaker_icon(draw, x, y, color):
    """Draw a small speaker icon."""
    # Speaker body (rectangle)
    draw.rectangle([x + 2, y + 4, x + 7, y + 12], fill=color)
    # Horn (triangle)
    draw.polygon([(x + 7, y + 2), (x + 15, y - 2), (x + 15, y + 18), (x + 7, y + 14)], fill=color)
    # Sound waves (arcs)
    for i in range(2):
        offset = 4 + i * 4
        draw.arc([x + 14 + i * 3, y - 1 + i, x + 20 + i * 3, y + 17 - i],
                 start=-50, end=50, fill=color, width=1)


# ─────────────────────────────────────────────
# Cell rendering by mode
# ─────────────────────────────────────────────

def _draw_header(draw, cell_x, track, is_selected):
    """
    Draw a cell header: colored background + track name.
    
    Header height: 22 pixels (out of 160 total height)
    """
    # Header background with track color
    r, g, b = track.color
    # Slightly darken so text is readable
    header_color = (min(r, 180), min(g, 180), min(b, 180))
    
    if is_selected:
        # Brighter header for the selected track
        header_color = (
            min(r + 40, 220),
            min(g + 40, 220),
            min(b + 40, 220)
        )
    
    if track.is_muted:
        header_color = (40, 40, 40)
    
    draw.rectangle([cell_x, 0, cell_x + CELL_WIDTH - 1, 21],
                   fill=header_color)
    
    # Track name
    name = _abbreviate(track.name, 16)
    text_color = COLOR_TEXT_MAIN
    
    # State indicators: M (mute), S (solo), ● (record)
    indicators = []
    if track.is_muted:
        indicators.append(("M", (220, 200, 0)))      # Yellow
    if track.is_solo:
        indicators.append(("S", (0, 100, 220)))       # Blue
    if track.is_armed:
        indicators.append(("●", (220, 40, 40)))       # Red
    
    draw.text((cell_x + 4, 4), name, font=FONT_SM if len(name) > 10 else FONT_MD, fill=text_color)
    if indicators:
        ix = cell_x + CELL_WIDTH - 6 * len(indicators) - 2
        for char, icolor in indicators:
            draw.text((ix, 4), char, font=FONT_SM, fill=icolor)
            ix += 6


def _draw_volume_cell(draw, cell_x, track):
    """Draw a cell in Volume mode with compact bar + VU meter."""
    bar_y      = 30
    bar_height = 95
    
    # ── Volume bar (left side, narrow) ──
    vol_x = cell_x + 8
    vol_w = 25
    
    draw.rectangle([vol_x, bar_y, vol_x + vol_w, bar_y + bar_height],
                   fill=(35, 35, 35))
    
    fill_h = int(bar_height * track.volume)
    if fill_h > 0:
        color = COLOR_VOLUME_BAR
        if track.volume_db > 0.1:
            color = COLOR_WARNING
        draw.rectangle([
            vol_x,
            bar_y + bar_height - fill_h,
            vol_x + vol_w,
            bar_y + bar_height
        ], fill=color)
    
    # ── VU Meter (right side of the volume bar) ──
    vu_x = cell_x + 40
    vu_w = 18
    
    # Peak clipped outline (red flash)
    if track.peak_clipped:
        import time
        blink = int(time.time() * 4) % 2 == 0  # ~4Hz
        border_color = (255, 0, 0) if blink else (100, 0, 0)
        draw.rectangle([vu_x - 1, bar_y - 1, vu_x + vu_w + 1, bar_y + bar_height + 1],
                       outline=border_color, width=1)
    
    draw.rectangle([vu_x, bar_y, vu_x + vu_w, bar_y + bar_height],
                   fill=(20, 20, 20))
    
    # Logarithmic curve : the linear 0-1 value from Nuendo is already
    # approximately linear in dB. We amplify small values.
    import math
    vu_lin = track.vu_meter
    if vu_lin > 0:
        # Log conversion: amplify small values
        vu_db = 20 * math.log10(max(vu_lin, 0.0001))  # -8to 0 dB
        # Map -60 dB..0 dB → 0..1
        vu_display = max(0.0, min(1.0, (vu_db + 60) / 60))
    else:
        vu_display = 0.0
    
    vu_h = int(bar_height * vu_display)
    if vu_h > 0:
        # Draw by blocks for performance
        for y_px in range(vu_h):
            y_pos = bar_y + bar_height - y_px
            pct = y_px / bar_height
            if pct < 0.65:
                c = (30, 180, 30)    # Green
            elif pct < 0.85:
                c = (200, 200, 30)   # Yellow
            else:
                c = (220, 40, 40)    # Red
            draw.line([(vu_x + 1, y_pos), (vu_x + vu_w - 1, y_pos)], fill=c)
    
    # ── Value in dB ──
    if hasattr(track, 'volume_display') and track.volume_display:
        db_text = track.volume_display
    elif track.volume > 0:
        db_text = f"{track.volume_db:+.1f}"
    else:
        db_text = "-∞"
    draw.text((cell_x + 4, 132), db_text, font=FONT_MD, fill=COLOR_TEXT_MAIN)
    
    # ── Monitor and Rec icons (to the right of VU meter) ──
    icon_x = cell_x + 68
    
    # Monitor: speaker icon (upper part)
    if track.is_monitored:
        _draw_speaker_icon(draw, icon_x, 40, (220, 140, 0))  # Orange
    
    # Rec: red circle (lower part)
    if track.is_armed:
        cx_rec = icon_x + 10
        cy_rec = 95
        r_rec = 8
        draw.ellipse([cx_rec - r_rec, cy_rec - r_rec, cx_rec + r_rec, cy_rec + r_rec],
                     fill=(220, 40, 40))
    
    # Automation: R/W indicator below REC
    if track.automation_write:
        draw.text((icon_x + 2, 110), "W", font=FONT_SM, fill=(220, 40, 40))
    elif track.automation_read:
        draw.text((icon_x + 2, 110), "R", font=FONT_SM, fill=(0, 180, 80))


def _draw_pan_cell(draw, cell_x, track):
    """Draw a cell in Pan mode."""
    # Centered circular encoder
    cx = cell_x + CELL_WIDTH // 2
    cy = 75
    _draw_arc_knob(draw, cx, cy, 32, (track.pan + 1.0) / 2.0, COLOR_PAN_BAR)
    
    # Position indicator L/C/R
    if abs(track.pan) < 0.05:
        pan_text = "C"
    elif track.pan < 0:
        pan_text = f"L{int(abs(track.pan) * 100)}"
    else:
        pan_text = f"R{int(track.pan * 100)}"
    
    # Center the text
    draw.text((cell_x + CELL_WIDTH // 2 - 12, 118), pan_text,
              font=FONT_MD, fill=COLOR_TEXT_MAIN)


def _draw_send_cell(draw, cell_x, track, send_index):
    """Draw a cell in Sends."""
    send_val = track.sends[send_index] if send_index < len(track.sends) else 0.0
    send_name = track.send_names[send_index] if send_index < len(track.send_names) else "---"
    send_on = track.send_enabled[send_index] if send_index < len(track.send_enabled) else True
    
    # Send name
    draw.text((cell_x + 4, 25), _truncate(send_name, 9),
              font=FONT_SM, fill=COLOR_TEXT_DIM)
    
    # Circular encoder — color based on enabled
    cx = cell_x + CELL_WIDTH // 2
    cy = 80
    if send_on:
        arc_color = COLOR_SEND_BAR
        bg_color = (80, 80, 80)
    else:
        arc_color = (60, 50, 60)
        bg_color = (30, 30, 30)
    _draw_arc_knob(draw, cx, cy, 30, send_val, arc_color, bg_color)
    
    # Value — use Nuendo display value if available
    display = track.send_display[send_index] if send_index < len(track.send_display) else ''
    if not display:
        display = f"{send_val * 100:.0f}%"
    text_color = COLOR_TEXT_MAIN if send_on else COLOR_TEXT_DIM
    draw.text((cell_x + CELL_WIDTH // 2 - 12, 120), display,
              font=FONT_MD, fill=text_color)


def _draw_device_cell(draw, cell_x, quick_control):
    """Draw a cell in Device (Quick Controls) mode."""
    # Parameter name
    name = _truncate(quick_control.name, 10)
    draw.text((cell_x + 4, 25), name, font=FONT_SM, fill=COLOR_TEXT_DIM)
    
    # Circular encoder
    cx = cell_x + CELL_WIDTH // 2
    cy = 82
    _draw_arc_knob(draw, cx, cy, 30, quick_control.value, COLOR_DEVICE_ARC)
    
    # Displayed value
    val_text = _truncate(quick_control.display_value, 10)
    draw.text((cell_x + 4, 120), val_text, font=FONT_MD, fill=COLOR_TEXT_MAIN)



TRACK_PARAM_LABELS = ['Volume', 'Pan', 'Send 1', 'Send 2', 'Send 3', 'Send 4', 'Send 5', 'Send 6']
TRACK_PARAM_COLORS = [
    (100, 200, 100),  # Volume - green
    (200, 150, 50),   # Pan - orange
    (100, 80, 180),   # Send 1 - purple
    (100, 80, 180),   # Send 2
    (100, 80, 180),   # Send 3
    (100, 80, 180),   # Send 4
    (100, 80, 180),   # Send 5
    (100, 80, 180),   # Send 6
]

def _draw_track_combined_cell(draw, cell_x, track, col):
    """Draw a cell in combined Track mode."""
    label = TRACK_PARAM_LABELS[col] if col < len(TRACK_PARAM_LABELS) else '---'
    color = TRACK_PARAM_COLORS[col] if col < len(TRACK_PARAM_COLORS) else (100, 100, 100)
    
    # Parameter label
    draw.text((cell_x + 4, 25), label, font=FONT_SM, fill=COLOR_TEXT_DIM)
    
    # Value
    cx = cell_x + CELL_WIDTH // 2
    cy = 80
    
    if col == 0:
        # Volume
        _draw_arc_knob(draw, cx, cy, 30, track.volume, color)
        db_text = f"{track.volume_db:.1f} dB" if track.volume_db > -96 else "-inf"
        draw.text((cell_x + 4, 120), db_text, font=FONT_MD, fill=COLOR_TEXT_MAIN)
    elif col == 1:
        # Pan
        pan_norm = (track.pan + 1.0) / 2.0
        _draw_arc_knob(draw, cx, cy, 30, pan_norm, color)
        if abs(track.pan) < 0.01:
            pan_text = "C"
        elif track.pan < 0:
            pan_text = f"L{int(abs(track.pan) * 100)}"
        else:
            pan_text = f"R{int(track.pan * 100)}"
        draw.text((cell_x + CELL_WIDTH // 2 - 12, 120), pan_text, font=FONT_MD, fill=COLOR_TEXT_MAIN)
    elif col >= 2 and col <= 7:
        # Sends 1-6
        send_idx = col - 2
        send_val = track.sends[send_idx] if send_idx < len(track.sends) else 0.0
        send_on = track.send_enabled[send_idx] if send_idx < len(track.send_enabled) else True
        if send_on:
            _draw_arc_knob(draw, cx, cy, 30, send_val, color)
        else:
            _draw_arc_knob(draw, cx, cy, 30, send_val, (60, 50, 60), (30, 30, 30))
        display = track.send_display[send_idx] if send_idx < len(track.send_display) and track.send_display[send_idx] else f"{send_val * 100:.0f}%"
        text_color = COLOR_TEXT_MAIN if send_on else COLOR_TEXT_DIM
        draw.text((cell_x + CELL_WIDTH // 2 - 12, 120), display, font=FONT_MD, fill=text_color)


def _draw_insert_cell(draw, cell_x, insert, is_selected):
    """Draw a cell in Inserts (plug-in list).
    
    Upper row buttons = open/close UI
    Lower row buttons = bypass toggle
    """
    if insert is None or not insert.name:
        # Empty slot
        draw.text((cell_x + 4, 60), "  ---", font=FONT_MD, fill=(40, 40, 40))
        return
    
    # Background if selected
    if is_selected:
        draw.rectangle([cell_x + 1, 24, cell_x + CELL_WIDTH - 2, 140],
                       fill=(30, 30, 50))
        draw.rectangle([cell_x + 1, 24, cell_x + CELL_WIDTH - 2, 140],
                       outline=COLOR_ACCENT, width=1)
    
    # Slot number
    slot_num = insert.slot + 1 if hasattr(insert, 'slot') else '?'
    draw.text((cell_x + 4, 26), f"#{slot_num}", font=FONT_SM,
              fill=COLOR_TEXT_DIM)
    
    # Plugin name (on 2-3 lines)
    name = insert.name
    lines = []
    while name:
        lines.append(name[:11])
        name = name[11:]
    y = 44
    for line in lines[:3]:
        draw.text((cell_x + 4, y), line, font=FONT_MD, fill=COLOR_TEXT_MAIN)
        y += 16
    
    # Active/bypassed indicator
    if insert.is_active:
        draw.ellipse([cell_x + 4, 112, cell_x + 14, 122], fill=(0, 200, 80))
        draw.text((cell_x + 18, 112), "ON", font=FONT_SM, fill=(0, 200, 80))
    else:
        # Bypassed: orange
        draw.ellipse([cell_x + 4, 112, cell_x + 14, 122], fill=(200, 120, 0))
        draw.text((cell_x + 18, 112), "BYP", font=FONT_SM, fill=(200, 120, 0))
    
    # Upper and lower button labels
    draw.text((cell_x + 4, 130), "BYPASS", font=FONT_SM, fill=COLOR_TEXT_DIM)


def _render_inserts_screen(state):
    """Dedicated screen for Inserts: list or parameters."""
    try:
        if state.insert_params_mode:
            return _render_insert_params_screen(state)
        
        img = Image.new('RGB', (SCREEN_WIDTH, SCREEN_HEIGHT), color=COLOR_BG)
        draw = ImageDraw.Draw(img)
        
        selected = state.selected_track
        names = state.current_insert_names
        active = state.current_insert_active
        
        # Title at top
        track_name = selected.name if selected else "---"
        r, g, b = selected.color if selected else (150, 150, 150)
        draw.rectangle([0, 0, SCREEN_WIDTH, 21], fill=(min(r, 150), min(g, 150), min(b, 150)))
        draw.text((8, 3), f"◄  {track_name}  ·  INSERTS  ►", font=FONT_MD, fill=(255, 255, 255))
        
        # 8 columns = 8 slots
        for col in range(8):
            cell_x = col * CELL_WIDTH
            
            # Separator
            if col > 0:
                draw.line([(cell_x, 22), (cell_x, 141)], fill=COLOR_SEPARATOR)
            
            name = names[col] if col < len(names) else ''
            is_active = active[col] if col < len(active) else False
            is_sel = (col == state.selected_insert_slot)
            
            if not name:
                draw.text((cell_x + 8, 70), "No Insert", font=FONT_SM, fill=(50, 50, 50))
                continue
            
            # Background if selected
            if is_sel:
                draw.rectangle([cell_x + 1, 24, cell_x + CELL_WIDTH - 2, 140],
                               fill=(30, 30, 50))
                draw.rectangle([cell_x + 1, 24, cell_x + CELL_WIDTH - 2, 140],
                               outline=COLOR_ACCENT, width=1)
            
            # Slot number + EDIT label
            draw.text((cell_x + 4, 26), f"#{col + 1}", font=FONT_SM, fill=COLOR_TEXT_DIM)
            draw.text((cell_x + CELL_WIDTH - 36, 26), "EDIT", font=FONT_SM, fill=(100, 100, 100))
            
            # Plugin name (on 2-3 lines)
            lines = []
            n = name
            while n:
                lines.append(n[:11])
                n = n[11:]
            y = 44
            for line in lines[:3]:
                draw.text((cell_x + 4, y), line, font=FONT_MD, fill=COLOR_TEXT_MAIN)
                y += 16
            
            # Active/bypassed indicator
            if is_active:
                draw.ellipse([cell_x + 4, 112, cell_x + 14, 122], fill=(0, 200, 80))
                draw.text((cell_x + 18, 112), "ON", font=FONT_SM, fill=(0, 200, 80))
            else:
                draw.ellipse([cell_x + 4, 112, cell_x + 14, 122], fill=(200, 120, 0))
                draw.text((cell_x + 18, 112), "BYP", font=FONT_SM, fill=(200, 120, 0))
        
        # Bottom separator
        draw.line([(0, 142), (SCREEN_WIDTH, 142)], fill=(50, 50, 50))
        
        # Button labels: bypass on 1-4
        for col in range(4):
            cell_x = col * CELL_WIDTH
            name = names[col] if col < len(names) else ''
            if name:
                is_active = active[col] if col < len(active) else False
                bypass_color = (0, 160, 80) if is_active else (200, 120, 0)
                draw.text((cell_x + 4, 147), "BYPASS", font=FONT_SM, fill=bypass_color)
        
        # Buttons 5-8: Mute/Solo/Mon/Rec labels
        sel = state.selected_track_index
        track = state.tracks[sel] if 0 <= sel < len(state.tracks) else None
        if track:
            msrm = [
                ("MUTE", (220, 200, 0) if track.is_muted else (80, 80, 80)),
                ("SOLO", (0, 100, 220) if track.is_solo else (80, 80, 80)),
                ("MON",  (220, 140, 0) if track.is_monitored else (80, 80, 80)),
                ("REC",  (220, 40, 40) if track.is_armed else (80, 80, 80)),
            ]
            for j, (label, color) in enumerate(msrm):
                x = (4 + j) * CELL_WIDTH
                tw = FONT_SM.getlength(label) if hasattr(FONT_SM, 'getlength') else len(label) * 6
                draw.text((x + (CELL_WIDTH - tw) // 2, 147), label, font=FONT_SM, fill=color)
        
        return _to_push2_frame(img)
    except Exception as e:
        print(f"  ✗ Inserts screen error: {e}")
        return _render_empty_frame()


def _render_insert_params_screen(state):
    """Selected insert plugin parameters screen."""
    try:
        img = Image.new('RGB', (SCREEN_WIDTH, SCREEN_HEIGHT), color=COLOR_BG)
        draw = ImageDraw.Draw(img)
        
        selected = state.selected_track
        slot = state.selected_insert_slot
        plugin_name = state.current_insert_names[slot] if slot < len(state.current_insert_names) else '?'
        
        # Title at top: plugin name + navigation
        r, g, b = selected.color if selected else (150, 150, 150)
        draw.rectangle([0, 0, SCREEN_WIDTH, 21], fill=(min(r, 150), min(g, 150), min(b, 150)))
        draw.text((8, 3), f"◄ {plugin_name} ►", font=FONT_MD, fill=(255, 255, 255))
        # BACK label at top right
        draw.text((SCREEN_WIDTH - 50, 5), "BACK", font=FONT_SM, fill=(200, 200, 200))
        
        # 8 columns = 8 parameters
        param_names = state.insert_param_names
        param_values = state.insert_param_values
        
        for col in range(8):
            cell_x = col * CELL_WIDTH
            
            if col > 0:
                draw.line([(cell_x, 22), (cell_x, 141)], fill=COLOR_SEPARATOR)
            
            p_name = param_names[col] if col < len(param_names) else ''
            p_value = param_values[col] if col < len(param_values) else ''
            
            if not p_name:
                continue
            
            # Parameter name (at top, 2 lines max)
            lines = []
            n = p_name
            while n:
                lines.append(n[:11])
                n = n[11:]
            y = 26
            for line in lines[:2]:
                draw.text((cell_x + 4, y), line, font=FONT_SM, fill=COLOR_TEXT_DIM)
                y += 12
            
            # Parameter value (center, large)
            if p_value:
                # Truncate if too long
                display_val = p_value[:10]
                draw.text((cell_x + 4, 64), display_val, font=FONT_MD, fill=COLOR_TEXT_MAIN)
            
            # Visual separator bar
            draw.line([(cell_x + 4, 56), (cell_x + CELL_WIDTH - 4, 56)], fill=(40, 40, 40))
        
        # Bottom separator
        draw.line([(0, 142), (SCREEN_WIDTH, 142)], fill=(50, 50, 50))
        
        # Bottom button labels: actions 1-3
        labels = [
            ("OPEN UI", (200, 200, 200)),
            ("BYPASS", (0, 160, 200)),
            ("DEACTIV", (200, 60, 60)),
        ]
        for idx, (label, color) in enumerate(labels):
            cell_x = idx * CELL_WIDTH
            draw.text((cell_x + 4, 147), label, font=FONT_SM, fill=color)
        
        # Buttons 5-8: Mute/Solo/Mon/Rec
        sel = state.selected_track_index
        track = state.tracks[sel] if 0 <= sel < len(state.tracks) else None
        if track:
            msrm = [
                ("MUTE", (220, 200, 0) if track.is_muted else (80, 80, 80)),
                ("SOLO", (0, 100, 220) if track.is_solo else (80, 80, 80)),
                ("MON",  (220, 140, 0) if track.is_monitored else (80, 80, 80)),
                ("REC",  (220, 40, 40) if track.is_armed else (80, 80, 80)),
            ]
            for j, (label, color) in enumerate(msrm):
                x = (4 + j) * CELL_WIDTH
                tw = FONT_SM.getlength(label) if hasattr(FONT_SM, 'getlength') else len(label) * 6
                draw.text((x + (CELL_WIDTH - tw) // 2, 147), label, font=FONT_SM, fill=color)
        
        return _to_push2_frame(img)
    except Exception as e:
        print(f"  ✗ Insert params screen error: {e}")
        return _render_empty_frame()


def _render_device_screen(state):
    """Dedicated screen for Device: 8 Quick Controls of the selected track."""
    try:
        img = Image.new('RGB', (SCREEN_WIDTH, SCREEN_HEIGHT), color=COLOR_BG)
        draw = ImageDraw.Draw(img)
        
        selected = state.selected_track
        track_name = selected.name if selected else "---"
        r, g, b = selected.color if selected else (150, 150, 150)
        
        # Title at top
        draw.rectangle([0, 0, SCREEN_WIDTH, 21], fill=(min(r, 150), min(g, 150), min(b, 150)))
        draw.text((8, 3), f"◄  {track_name}  ·  QUICK CONTROLS  ►", font=FONT_MD, fill=(255, 255, 255))
        
        qcs = selected.quick_controls if selected else []
        
        for col in range(8):
            cell_x = col * CELL_WIDTH
            
            if col > 0:
                draw.line([(cell_x, 22), (cell_x, 141)], fill=COLOR_SEPARATOR)
            
            if col >= len(qcs):
                continue
            
            qc = qcs[col]
            name = qc.name if qc.name else ''
            
            if not name:
                continue
            
            # Parameter name (2 lines max)
            lines = []
            n = name
            while n:
                lines.append(n[:11])
                n = n[11:]
            y = 24
            for line in lines[:2]:
                draw.text((cell_x + 4, y), line, font=FONT_SM, fill=COLOR_TEXT_DIM)
                y += 12
            
            # Arc knob
            cx = cell_x + CELL_WIDTH // 2
            cy = 78
            _draw_arc_knob(draw, cx, cy, 24, qc.value, COLOR_DEVICE_ARC)
            
            # Displayed value
            val_text = _truncate(qc.display_value, 10) if qc.display_value else ''
            if val_text:
                draw.text((cell_x + 4, 112), val_text, font=FONT_MD, fill=COLOR_TEXT_MAIN)
        
        # Bottom separator
        draw.line([(0, 142), (SCREEN_WIDTH, 142)], fill=(50, 50, 50))
        
        # Bottom button labels
        draw.text((4, 147), "OPEN UI", font=FONT_SM, fill=(200, 200, 200))
        
        # Buttons 5-8: Mute/Solo/Mon/Rec labels
        sel = state.selected_track_index
        track = state.tracks[sel] if 0 <= sel < len(state.tracks) else None
        if track:
            msrm = [
                ("MUTE", (220, 200, 0) if track.is_muted else (80, 80, 80)),
                ("SOLO", (0, 100, 220) if track.is_solo else (80, 80, 80)),
                ("MON",  (220, 140, 0) if track.is_monitored else (80, 80, 80)),
                ("REC",  (220, 40, 40) if track.is_armed else (80, 80, 80)),
            ]
            for j, (label, color) in enumerate(msrm):
                x = (4 + j) * CELL_WIDTH
                tw = FONT_SM.getlength(label) if hasattr(FONT_SM, 'getlength') else len(label) * 6
                draw.text((x + (CELL_WIDTH - tw) // 2, 147), label, font=FONT_SM, fill=color)
        
        return _to_push2_frame(img)
    except Exception as e:
        print(f"  ✗ Device screen error: {e}")
        return _render_empty_frame()


def _render_sends_screen(state):
    """Dedicated screen for Sends: 8 sends of the selected track."""
    try:
        img = Image.new('RGB', (SCREEN_WIDTH, SCREEN_HEIGHT), color=COLOR_BG)
        draw = ImageDraw.Draw(img)
        
        selected = state.selected_track
        track_name = selected.name if selected else "---"
        r, g, b = selected.color if selected else (150, 150, 150)
        
        # Title at top
        draw.rectangle([0, 0, SCREEN_WIDTH, 21], fill=(min(r, 150), min(g, 150), min(b, 150)))
        draw.text((8, 3), f"◄  {track_name}  ·  SENDS  ►", font=FONT_MD, fill=(255, 255, 255))
        
        send_names = state.send_names
        send_levels = state.send_levels
        send_on = state.send_on
        send_prepost = state.send_prepost
        
        for col in range(8):
            cell_x = col * CELL_WIDTH
            
            if col > 0:
                draw.line([(cell_x, 22), (cell_x, 141)], fill=COLOR_SEPARATOR)
            
            name = send_names[col] if col < len(send_names) else ''
            level = send_levels[col] if col < len(send_levels) else ''
            is_on = send_on[col] if col < len(send_on) else False
            is_pre = send_prepost[col] if col < len(send_prepost) else False
            
            if not name:
                draw.text((cell_x + 8, 70), "No Send", font=FONT_SM, fill=(50, 50, 50))
                continue
            
            # ON/OFF label at top
            if is_on:
                draw.text((cell_x + 4, 24), "ON", font=FONT_SM, fill=(0, 200, 80))
            else:
                draw.text((cell_x + 4, 24), "OFF", font=FONT_SM, fill=(120, 60, 60))
            
            # Destination name (2 lines max)
            lines = []
            n = name
            while n:
                lines.append(n[:11])
                n = n[11:]
            y = 40
            name_color = COLOR_TEXT_MAIN if is_on else (80, 80, 80)
            for line in lines[:2]:
                draw.text((cell_x + 4, y), line, font=FONT_MD, fill=name_color)
                y += 16
            
            # Level value
            if level:
                draw.text((cell_x + 4, 80), level, font=FONT_MD, fill=COLOR_ACCENT if is_on else (60, 60, 60))
            
            # Pre/Post indicator
            pre_text = "PRE" if is_pre else "POST"
            pre_color = (0, 100, 220) if is_pre else (220, 140, 0)
            if not is_on:
                pre_color = (60, 60, 60)
            draw.text((cell_x + 4, 112), pre_text, font=FONT_SM, fill=pre_color)
        
        # Bottom separator
        draw.line([(0, 142), (SCREEN_WIDTH, 142)], fill=(50, 50, 50))
        
        # Bottom button labels
        for col in range(8):
            cell_x = col * CELL_WIDTH
            name = send_names[col] if col < len(send_names) else ''
            if name:
                is_pre = send_prepost[col] if col < len(send_prepost) else False
                pre_color = (0, 100, 220) if is_pre else (220, 140, 0)
                pre_text = "PRE" if is_pre else "POST"
                draw.text((cell_x + 4, 147), pre_text, font=FONT_SM, fill=pre_color)
        
        return _to_push2_frame(img)
    except Exception as e:
        print(f"  ✗ Sends screen error: {e}")
        return _render_empty_frame()


# ─────────────────────────────────────────────
# Bottom bar: global context info
# ─────────────────────────────────────────────

def _draw_bottom_bar(draw, state):
    """
    Draw an info bar at the bottom of the screen (y = 142 to 160).
    Display: active mode, bank, Nuendo connection.
    """
    # Bar background
    draw.rectangle([0, 142, SCREEN_WIDTH, SCREEN_HEIGHT], fill=(10, 10, 10))
    draw.line([(0, 142), (SCREEN_WIDTH, 142)], fill=(50, 50, 50), width=1)
    
    # Active mode (left side)
    mode_labels = {
        MODE_VOLUME:  "■ VOLUME",
        MODE_PAN:     "■ PAN",
        MODE_SENDS:   f"■ SEND {state.current_send + 1}",
        MODE_DEVICE:  "■ DEVICE",
        MODE_INSERTS: "■ INSERTS",
        MODE_TRACK:   "■ TRACK",
        MODE_OVERVIEW: "■ OVERVIEW",
    }
    mode_text = mode_labels.get(state.mode, state.mode.upper())
    draw.text((6, 147), mode_text, font=FONT_SM, fill=COLOR_ACCENT)
    
    # Lower mode label (Mute/Solo/Mon/Rec)
    lower_labels = {
        "mute":    ("MUTE", (220, 200, 0)),
        "solo":    ("SOLO", (0, 100, 220)),
        "monitor": ("MON",  (220, 140, 0)),
        "rec":     ("REC",  (220, 40, 40)),
    }
    lower_mode = getattr(state, 'lower_mode', 'mute')
    label, color = lower_labels.get(lower_mode, ("MUTE", (200, 120, 0)))
    draw.text((120, 147), label, font=FONT_SM, fill=color)
    
    # Current bank (at center)
    bank_num = state.bank_offset // BANK_SIZE + 1
    bank_text = f"Bk {bank_num}"
    draw.text((SCREEN_WIDTH // 2 - 20, 147), bank_text, font=FONT_SM, fill=COLOR_TEXT_DIM)
    
    # Tempo and position (at center)
    tempo = state.tempo_display or ""
    position = state.position_display or ""
    beats = state.beats_display or ""
    if state.repeat_enabled:
        repeat_text = f"RPT {state.repeat_tempo:.0f} BPM {state.repeat_subdivision}"
        draw.text((280, 147), repeat_text, font=FONT_SM, fill=(0, 200, 200))
    elif tempo:
        draw.text((280, 147), f"{tempo} BPM", font=FONT_SM, fill=(180, 180, 180))
    if position:
        draw.text((430, 147), position, font=FONT_SM, fill=(140, 140, 180))
    if beats:
        draw.text((550, 147), beats, font=FONT_SM, fill=(180, 160, 100))
    
    # Metronome
    if state.metronome_on:
        draw.text((580, 147), "♩", font=FONT_SM, fill=(0, 200, 80))
    
    # Connection status (right side)
    if state.nuendo_connected:
        draw.text((SCREEN_WIDTH - 90, 147), "● NUENDO", font=FONT_SM,
                  fill=(0, 200, 80))
    else:
        draw.text((SCREEN_WIDTH - 110, 147), "○ WAITING", font=FONT_SM,
                  fill=COLOR_WARNING)
    
    # RESCAN label above the 7th bottom button (index 6)
    rescan_x = 6 * CELL_WIDTH + CELL_WIDTH // 2 - 16
    draw.text((rescan_x, 147), "RESCAN", font=FONT_SM, fill=(120, 120, 120))


# ─────────────────────────────────────────────
# MIDI CC SCREEN
# ─────────────────────────────────────────────

# Common CC names for display
_CC_NAMES = {
    0: "Bank Sel", 1: "Mod Wheel", 2: "Breath", 3: "CC 3", 4: "Foot Ctrl",
    5: "Porta Time", 6: "Data MSB", 7: "Volume", 8: "Balance",
    10: "Pan", 11: "Expression", 12: "Fx Ctrl 1", 13: "Fx Ctrl 2",
    64: "Sustain", 65: "Portamento", 66: "Sostenuto", 67: "Soft Pedal",
    68: "Legato", 69: "Hold 2", 70: "Variation", 71: "Resonance",
    72: "Release", 73: "Attack", 74: "Cutoff", 75: "Decay",
    76: "Vib Rate", 77: "Vib Depth", 78: "Vib Delay",
    91: "Reverb", 92: "Tremolo", 93: "Chorus", 94: "Detune", 95: "Phaser",
}

def _render_midicc_screen(state):
    """Render the MIDI CC controller page."""
    try:
        img = Image.new('RGB', (SCREEN_WIDTH, SCREEN_HEIGHT), color=COLOR_BG)
        draw = ImageDraw.Draw(img)
        
        edit_mode = state.cc_edit_mode
        
        # Title bar
        draw.rectangle([0, 0, SCREEN_WIDTH, 18], fill=(30, 30, 50))
        title = "MIDI CC" if not edit_mode else "MIDI CC  [SELECT CC]"
        tw = FONT_SM.getlength(title) if hasattr(FONT_SM, 'getlength') else len(title) * 7
        title_color = (220, 160, 0) if edit_mode else COLOR_ACCENT
        draw.text(((SCREEN_WIDTH - tw) // 2, 2), title, fill=title_color, font=FONT_SM)
        
        for col in range(8):
            cell_x = col * CELL_WIDTH
            cc_num = state.cc_numbers[col]
            cc_val = state.cc_values[col]
            cc_name = _CC_NAMES.get(cc_num, f"CC {cc_num}")
            
            # Separator
            draw.line([(cell_x, 20), (cell_x, 141)], fill=COLOR_SEPARATOR)
            
            # CC number (top)
            cc_label = f"CC {cc_num}"
            tw = FONT_SM.getlength(cc_label) if hasattr(FONT_SM, 'getlength') else len(cc_label) * 6
            if edit_mode:
                # Highlight CC number when in edit mode
                draw.rectangle([cell_x + 1, 20, cell_x + CELL_WIDTH - 1, 34], fill=(60, 50, 0))
            draw.text((cell_x + (CELL_WIDTH - tw) // 2, 22), cc_label,
                      fill=(220, 160, 0) if edit_mode else COLOR_ACCENT, font=FONT_SM)
            
            # CC name
            name_trunc = cc_name[:12]
            tw = FONT_SM.getlength(name_trunc) if hasattr(FONT_SM, 'getlength') else len(name_trunc) * 6
            draw.text((cell_x + (CELL_WIDTH - tw) // 2, 36), name_trunc,
                      fill=(140, 140, 140), font=FONT_SM)
            
            # Value bar
            bar_x = cell_x + 20
            bar_w = CELL_WIDTH - 40
            bar_y = 56
            bar_h = 55
            
            # Bar background
            draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h],
                          fill=(30, 30, 30), outline=(50, 50, 50))
            
            # Filled portion
            fill_h = int((cc_val / 127.0) * bar_h)
            if fill_h > 0:
                bar_color = COLOR_ACCENT if cc_val < 127 else (0, 220, 120)
                draw.rectangle([bar_x + 1, bar_y + bar_h - fill_h,
                              bar_x + bar_w - 1, bar_y + bar_h - 1],
                              fill=bar_color)
            
            # Value text (centered below bar)
            val_text = str(cc_val)
            tw = FONT_MD.getlength(val_text) if hasattr(FONT_MD, 'getlength') else len(val_text) * 8
            draw.text((cell_x + (CELL_WIDTH - tw) // 2, 116), val_text,
                      fill=COLOR_TEXT_MAIN, font=FONT_MD)
        
        # Bottom separator and toggle labels
        draw.line([(0, 141), (SCREEN_WIDTH, 141)], fill=COLOR_SEPARATOR)
        for col in range(8):
            cell_x = col * CELL_WIDTH
            draw.line([(cell_x, 141), (cell_x, SCREEN_HEIGHT)], fill=COLOR_SEPARATOR)
            cc_val = state.cc_values[col]
            label = "ON" if cc_val > 0 else "OFF"
            color = (0, 200, 120) if cc_val > 0 else (80, 80, 80)
            tw = FONT_SM.getlength(label) if hasattr(FONT_SM, 'getlength') else len(label) * 6
            draw.text((cell_x + (CELL_WIDTH - tw) // 2, 146), label, fill=color, font=FONT_SM)
        
        return _to_push2_frame(img)
    except Exception as e:
        print(f"  ✗ MIDI CC screen error: {e}")
        return _render_empty_frame()


# ─────────────────────────────────────────────
# SETUP SCREEN
# ─────────────────────────────────────────────

# Setup page definitions
SETUP_PAGE_NAMES = ['MIDI Ctrl', 'Vel Curve', None, None, None, None, None, 'About']

# Per-page options: list of (label, value) for lower row buttons
SETUP_PAGE_OPTIONS = {
    0: [  # MIDI Controller page — Aftertouch only
        ('Poly AT', AT_POLY),
        ('Chan AT', AT_CHANNEL),
        ('AT Off',  AT_OFF),
    ],
    1: [  # Velocity Curve page
        ('Linear',  VC_LINEAR),
        ('Log',     VC_LOG),
        ('Exp',     VC_EXP),
        ('S-Curve', VC_SCURVE),
        ('Fixed',   VC_FIXED),
    ],
}

def _render_setup_screen(state):
    """Render the Setup page."""
    img = Image.new('RGB', (SCREEN_WIDTH, SCREEN_HEIGHT), color=COLOR_BG)
    draw = ImageDraw.Draw(img)
    
    page_idx = state.setup_page
    
    # ── Title bar ──
    draw.rectangle([0, 0, SCREEN_WIDTH, 18], fill=(30, 30, 50))
    title = "SETUP"
    tw = FONT_SM.getlength(title) if hasattr(FONT_SM, 'getlength') else len(title) * 7
    draw.text(((SCREEN_WIDTH - tw) // 2, 2), title, fill=COLOR_ACCENT, font=FONT_SM)
    
    # ── Upper row labels (page tabs, y=20-38) ──
    for i in range(8):
        x = i * CELL_WIDTH
        draw.line([(x, 20), (x, 38)], fill=COLOR_SEPARATOR)
        if i < len(SETUP_PAGE_NAMES) and SETUP_PAGE_NAMES[i] is not None:
            name = SETUP_PAGE_NAMES[i]
            is_active = (i == page_idx)
            if is_active:
                draw.rectangle([x + 1, 20, x + CELL_WIDTH - 1, 38], fill=(0, 60, 80))
            color = COLOR_ACCENT if is_active else (80, 80, 80)
            tw = FONT_SM.getlength(name) if hasattr(FONT_SM, 'getlength') else len(name) * 6
            tx = x + (CELL_WIDTH - tw) // 2
            draw.text((tx, 23), name, fill=color, font=FONT_SM)
    
    # ── Page content ──
    options = SETUP_PAGE_OPTIONS.get(page_idx, [])
    
    if page_idx == 0:
        # ── Page 0: MIDI Controller — Aftertouch mode ──
        draw.text((20, 50), "Aftertouch Mode", fill=(200, 200, 200), font=FONT_MD)
        at_mode = state.aftertouch_mode
        if at_mode == AT_POLY:
            at_name, desc = "Polyphonic", "Per-note pressure (0xA0)"
        elif at_mode == AT_CHANNEL:
            at_name, desc = "Channel", "Global pressure (0xD0)"
        else:
            at_name, desc = "Off", "Pad pressure ignored"
        draw.text((20, 75), at_name, fill=COLOR_ACCENT, font=FONT_LG)
        draw.text((20, 100), desc, fill=(100, 100, 100), font=FONT_SM)
    
    elif page_idx == 1:
        # ── Page 1: Velocity Curve — graphique par bouton ──
        draw.text((20, 42), "Velocity Curve", fill=(200, 200, 200), font=FONT_MD)
        
        # Draw a curve preview above each of the 5 buttons
        vc_presets = [VC_LINEAR, VC_LOG, VC_EXP, VC_SCURVE, VC_FIXED]
        for idx, vc_val in enumerate(vc_presets):
            x = idx * CELL_WIDTH
            is_selected = (state.velocity_curve == vc_val)
            
            # Graph area (y=60-130, within the cell)
            gx = x + 8
            gy = 62
            gw = CELL_WIDTH - 16
            gh = 65
            
            # Background highlight for selected
            if is_selected:
                draw.rectangle([x + 1, 58, x + CELL_WIDTH - 1, 135], fill=(0, 45, 60))
            
            # Graph border
            draw.rectangle([gx, gy, gx + gw, gy + gh], outline=(60, 60, 60))
            
            # Draw the curve (pass accent_velocity for Fixed mode)
            curve_color = COLOR_ACCENT if is_selected else (80, 80, 80)
            fixed_vel = state.accent_velocity
            _draw_velocity_preview(draw, gx, gy, gw, gh, vc_val, curve_color, fixed_vel)
            
            # Show velocity value on Fixed graph
            if vc_val == VC_FIXED:
                vel_text = str(state.accent_velocity)
                tw = FONT_SM.getlength(vel_text) if hasattr(FONT_SM, 'getlength') else len(vel_text) * 6
                val_color = COLOR_ACCENT if is_selected else (100, 100, 100)
                draw.text((x + (CELL_WIDTH - tw) // 2, gy - 14), vel_text, fill=val_color, font=FONT_SM)
            
            # Separator
            draw.line([(x, 42), (x, 140)], fill=COLOR_SEPARATOR)
    
    elif page_idx == 7:
        # ── Page 7: About ──
        # Bridge version
        draw.text((20, 48), "Push 2 / Nuendo Bridge", fill=(200, 200, 200), font=FONT_MD)
        draw.text((20, 70), f"Bridge  v{BRIDGE_VERSION}", fill=COLOR_ACCENT, font=FONT_LG)
        
        # JS version
        js_ver = state.js_version if state.js_version != "?" else "not connected"
        draw.text((20, 95), f"Script  v{js_ver}", fill=COLOR_ACCENT, font=FONT_MD)
        
        # Links
        draw.text((20, 118), "github.com/mbourque-mix/Push2Nuendo-Bridge", fill=(80, 80, 80), font=FONT_SM)
    
    # ── Lower row labels (y=142-160) ──
    draw.line([(0, 141), (SCREEN_WIDTH, 141)], fill=COLOR_SEPARATOR)
    
    for i in range(8):
        x = i * CELL_WIDTH
        draw.line([(x, 141), (x, SCREEN_HEIGHT)], fill=COLOR_SEPARATOR)
        
        if i < len(options):
            label, value = options[i]
            
            if page_idx == 0:
                is_selected = (state.aftertouch_mode == value)
            elif page_idx == 1:
                is_selected = (state.velocity_curve == value)
            else:
                is_selected = False
            
            if is_selected:
                draw.rectangle([x + 1, 142, x + CELL_WIDTH - 1, SCREEN_HEIGHT - 1],
                              fill=(0, 60, 80))
            
            color = COLOR_ACCENT if is_selected else (100, 100, 100)
            tw = FONT_SM.getlength(label) if hasattr(FONT_SM, 'getlength') else len(label) * 6
            tx = x + (CELL_WIDTH - tw) // 2
            draw.text((tx, 146), label, fill=color, font=FONT_SM)
    
    return _to_push2_frame(img)

def _draw_velocity_preview(draw, x, y, w, h, vc_mode, color=None, fixed_vel=100):
    """Draw a velocity curve preview graph."""
    import math
    if color is None:
        color = COLOR_ACCENT
    
    prev_px, prev_py = None, None
    for i in range(0, w + 1, 2):
        t = i / max(w, 1)
        if vc_mode == VC_LINEAR:
            v = t
        elif vc_mode == VC_LOG:
            v = math.log1p(t * 3) / math.log1p(3)
        elif vc_mode == VC_EXP:
            v = (math.exp(t * 3) - 1) / (math.exp(3) - 1)
        elif vc_mode == VC_SCURVE:
            v = 0.5 * (1 + math.tanh(4 * (t - 0.5)) / math.tanh(2))
        elif vc_mode == VC_FIXED:
            v = fixed_vel / 127.0 if t > 0 else 0
        else:
            v = t
        px = x + i
        py = y + h - int(v * h)
        if prev_px is not None:
            draw.line([(prev_px, prev_py), (px, py)], fill=color, width=1)
        prev_px, prev_py = px, py

# ─────────────────────────────────────────────
# Splash screen
# ─────────────────────────────────────────────

def render_splash_screen():
    """
    Display a splash screen while waiting for Nuendo to connect.
    """
    img = Image.new('RGB', (SCREEN_WIDTH, SCREEN_HEIGHT), color=COLOR_BG)
    draw = ImageDraw.Draw(img)
    
    # Title
    draw.text((SCREEN_WIDTH // 2 - 120, 40),
              "Push 2 / Nuendo Bridge",
              font=FONT_LG, fill=COLOR_ACCENT)
    
    # Subtitle
    draw.text((SCREEN_WIDTH // 2 - 100, 70),
              "Waiting for Nuendo connection...",
              font=FONT_MD, fill=COLOR_TEXT_DIM)
    
    # Instructions
    draw.text((SCREEN_WIDTH // 2 - 90, 100),
              "Make sure IAC ports are active",
              font=FONT_SM, fill=(70, 70, 70))
    
    return _to_push2_frame(img)


def render_disconnect_screen():
    """Displayed when the connection with Nuendo is lost."""
    img = Image.new('RGB', (SCREEN_WIDTH, SCREEN_HEIGHT), color=(25, 10, 10))
    draw = ImageDraw.Draw(img)
    draw.text((SCREEN_WIDTH // 2 - 90, 60),
              "Nuendo connection lost",
              font=FONT_LG, fill=COLOR_WARNING)
    draw.text((SCREEN_WIDTH // 2 - 80, 90),
              "Restart the bridge or check IAC ports",
              font=FONT_SM, fill=COLOR_TEXT_DIM)
    return _to_push2_frame(img)


# ─────────────────────────────────────────────
# Main function : render_frame()
# ─────────────────────────────────────────────

def render_frame(state: AppState, pad_grid=None, cr_state=None):
    """
    Generate a complete frame to send to the Push 2 screen.
    """
    if not state.nuendo_connected:
        return render_splash_screen()
    
    if pad_grid and pad_grid.scale_mode:
        return _render_scale_screen(pad_grid)
    
    if state.accent_held:
        return _render_accent_screen(state)
    
    if state.mode == MODE_CR and cr_state:
        return _render_cr_screen(state, cr_state)
    
    if state.mode == MODE_SETUP:
        return _render_setup_screen(state)
    
    if state.mode == MODE_MIDICC:
        return _render_midicc_screen(state)
    
    if state.mode == MODE_INSERTS:
        return _render_inserts_screen(state)
    
    if state.mode == MODE_SENDS:
        return _render_sends_screen(state)
    
    if state.mode == MODE_DEVICE:
        return _render_device_screen(state)
    
    # Main image
    img = Image.new('RGB', (SCREEN_WIDTH, SCREEN_HEIGHT), color=COLOR_BG)
    draw = ImageDraw.Draw(img)
    
    visible_tracks = state.visible_tracks
    
    for col in range(BANK_SIZE):
        cell_x = col * CELL_WIDTH
        track_abs_index = state.bank_offset + col
        
        # Get the track (or a dummy track if out of bounds)
        if track_abs_index < state.total_tracks and col < len(visible_tracks):
            track = visible_tracks[col]
        else:
            # Empty cell (beyond track count)
            draw.rectangle([cell_x, 0, cell_x + CELL_WIDTH - 1, SCREEN_HEIGHT],
                           fill=(12, 12, 12))
            draw.line([(cell_x, 0), (cell_x, SCREEN_HEIGHT)],
                      fill=COLOR_SEPARATOR)
            continue
        
        is_selected = (track_abs_index == state.selected_track_index)
        
        # Cell background
        if track.is_muted:
            bg = COLOR_BG_MUTED
        elif is_selected:
            bg = COLOR_BG_SELECTED
        else:
            bg = COLOR_BG
        draw.rectangle([cell_x, 0, cell_x + CELL_WIDTH - 1, 141], fill=bg)
        
        # Header (track name)
        _draw_header(draw, cell_x, track, is_selected)
        
        # Content according to mode
        if state.mode == MODE_VOLUME:
            _draw_volume_cell(draw, cell_x, track)
        
        elif state.mode == MODE_PAN:
            _draw_pan_cell(draw, cell_x, track)
        
        elif state.mode == MODE_SENDS:
            _draw_send_cell(draw, cell_x, track, state.current_send)
        
        elif state.mode == MODE_DEVICE:
            # In Device mode, display the 8 Quick Controls
            # of the selected track (not the bank)
            selected = state.selected_track
            if col < len(selected.quick_controls):
                _draw_device_cell(draw, cell_x, selected.quick_controls[col])
        
        elif state.mode == MODE_INSERTS:
            # Display inserts of the selected track
            selected = state.selected_track
            if col < len(selected.inserts):
                insert = selected.inserts[col]
                is_insert_selected = (col == state.selected_insert_slot)
                _draw_insert_cell(draw, cell_x, insert, is_insert_selected)
            else:
                _draw_insert_cell(draw, cell_x, None, False)
        
        elif state.mode == MODE_TRACK:
            selected = state.selected_track
            _draw_track_combined_cell(draw, cell_x, selected, col)
        
        elif state.mode == MODE_OVERVIEW:
            _draw_volume_cell(draw, cell_x, track)
        
        # Vertical separator between cells
        draw.line([(cell_x, 0), (cell_x, 141)], fill=COLOR_SEPARATOR)
    
    # Bottom info bar
    _draw_bottom_bar(draw, state)
    
    # Temporary overlay (ex: touchstrip mode change)
    overlay_text = getattr(state, '_touchstrip_overlay', None)
    overlay_until = getattr(state, '_touchstrip_overlay_until', 0)
    if overlay_text and time.time() < overlay_until:
        # Background in center of screen
        ox = SCREEN_WIDTH // 2 - 100
        oy = 55
        draw.rectangle([ox, oy, ox + 200, oy + 40], fill=(20, 20, 30), outline=(80, 80, 120), width=1)
        draw.text((ox + 10, oy + 4), "TOUCHSTRIP", font=FONT_SM, fill=(120, 120, 160))
        draw.text((ox + 10, oy + 18), overlay_text, font=FONT_MD, fill=(255, 255, 255))
    
    return _to_push2_frame(img)


def _cr_value_to_db(value, max_db=12.0):
    """Converts a normalized value 0-1 to an approximate dB value.
    0 dB = ~0.748 normalized (95/127).
    max_db = max dB at value 127 (12 dB default, 18 for Listen).
    """
    if value <= 0.001:
        return "-inf"
    val_127 = value * 127.0
    if val_127 >= 95:
        db = (val_127 - 95) / 32.0 * max_db
    else:
        ratio = val_127 / 95.0
        if ratio <= 0.001:
            return "-inf"
        import math
        db = 20.0 * math.log10(ratio)
    return f"{db:+.1f}"


def _render_cr_screen(state, cr_state):
    """Display the Control Room mode screen."""
    try:
        img = Image.new('RGB', (SCREEN_WIDTH, SCREEN_HEIGHT), color=COLOR_BG)
        draw = ImageDraw.Draw(img)
        
        page_def = CR_PAGES.get(cr_state.page, {})
        page_name = CR_PAGE_NAMES[cr_state.page] if cr_state.page < len(CR_PAGE_NAMES) else "?"
        
        # Upper button labels (top of screen)
        upper = page_def.get('upper_btns', [])
        for i in range(8):
            cell_x = i * CELL_WIDTH
            if i < len(upper) and upper[i] is not None:
                label, cc, param_id, is_toggle = upper[i]
                is_on = cr_state.get_toggle(param_id) if param_id is not None else False
                color = (0, 200, 200) if is_on else COLOR_TEXT_DIM
                draw.text((cell_x + 4, 2), label, font=FONT_SM, fill=color)
            if i > 0:
                draw.line([(cell_x, 0), (cell_x, 14)], fill=(40, 40, 40))
        
        # Top separator
        draw.line([(0, 16), (SCREEN_WIDTH, 16)], fill=(50, 50, 50))
        
        # Encoders: display values
        encoders = page_def.get('encoders', [])
        for i in range(8):
            cell_x = i * CELL_WIDTH
            
            if i < len(encoders) and encoders[i] is not None:
                label, cc, param_id, max_db = encoders[i]
                value = cr_state.get_value(param_id) if param_id is not None else 0.0
                
                # Label
                draw.text((cell_x + 4, 20), label, font=FONT_SM, fill=COLOR_TEXT_DIM)
                
                # Vertical volume bar
                bar_x = cell_x + 10
                bar_y = 38
                bar_w = CELL_WIDTH - 20
                bar_h = 65
                draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], fill=(30, 30, 30))
                
                # 0 dB marker (at 95/127 = 74.8%)
                zero_y = bar_y + bar_h - int(bar_h * 0.748)
                draw.line([(bar_x, zero_y), (bar_x + bar_w, zero_y)], fill=(80, 80, 80))
                
                fill_h = int(bar_h * value)
                if fill_h > 0:
                    draw.rectangle([bar_x, bar_y + bar_h - fill_h, bar_x + bar_w, bar_y + bar_h], fill=COLOR_ACCENT)
                
                # Value in dB (from Nuendo)
                display_text = cr_state.get_display(param_id) if param_id is not None else ""
                if display_text:
                    draw.text((cell_x + 4, 110), f"{display_text} dB", font=FONT_MD, fill=COLOR_TEXT_MAIN)
                else:
                    db_text = _cr_value_to_db(value, max_db)
                    draw.text((cell_x + 4, 110), f"{db_text} dB", font=FONT_MD, fill=COLOR_TEXT_MAIN)
            
            # Separator
            if i > 0:
                draw.line([(cell_x, 18), (cell_x, 130)], fill=COLOR_SEPARATOR)
        
        # Bottom bar with page navigation
        draw.rectangle([0, 142, SCREEN_WIDTH, SCREEN_HEIGHT], fill=(10, 10, 10))
        draw.line([(0, 142), (SCREEN_WIDTH, 142)], fill=(50, 50, 50))
        
        # Buttons 1-4: action labels
        lower = page_def.get('lower_btns', [])
        for i in range(4):
            cell_x = i * CELL_WIDTH
            if i < len(lower) and lower[i] is not None:
                label = lower[i][0]
                param_id = lower[i][2] if len(lower[i]) >= 3 else None
                if param_id is not None and cr_state.get_toggle(param_id):
                    color = (0, 150, 255)  # Blue = selected
                else:
                    color = COLOR_TEXT_DIM
                draw.text((cell_x + 8, 147), label, font=FONT_SM, fill=color)
        
        # Buttons 5-8: pages
        for i in range(4):
            cell_x = (i + 4) * CELL_WIDTH
            if i < len(CR_PAGE_NAMES):
                if i == cr_state.page:
                    color = (0, 150, 255)  # Blue for active page
                else:
                    color = (255, 165, 0)  # Orange for others
                draw.text((cell_x + 8, 147), CR_PAGE_NAMES[i], font=FONT_SM, fill=color)
        
        return _to_push2_frame(img)
    except Exception as e:
        print(f"  ✗ CR screen error: {e}")
        return None


def _render_accent_screen(state):
    """Display the Accent velocity setting screen."""
    try:
        img = Image.new('RGB', (SCREEN_WIDTH, SCREEN_HEIGHT), color=COLOR_BG)
        draw = ImageDraw.Draw(img)
        
        # Title
        status = "ON" if state.accent_enabled else "OFF"
        draw.text((30, 8), f"ACCENT ({status})", font=FONT_LG, fill=COLOR_ACCENT)
        
        # Label + value
        draw.text((30, 50), "Velocity:", font=FONT_MD, fill=COLOR_TEXT_DIM)
        draw.text((170, 42), str(state.accent_velocity), font=FONT_LG, fill=COLOR_TEXT_MAIN)
        
        # Progress bar
        bar_x = 30
        bar_y = 85
        bar_w = 900
        bar_h = 14
        draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], fill=(40, 40, 40))
        fill_w = int(bar_w * state.accent_velocity / 127)
        draw.rectangle([bar_x, bar_y, bar_x + fill_w, bar_y + bar_h], fill=COLOR_ACCENT)
        
        # Markers
        for marker in [32, 64, 96, 127]:
            mx = bar_x + int(bar_w * marker / 127)
            draw.line([(mx, bar_y + bar_h + 2), (mx, bar_y + bar_h + 6)], fill=COLOR_TEXT_DIM)
            draw.text((mx - 6, bar_y + bar_h + 8), str(marker), font=FONT_SM, fill=COLOR_TEXT_DIM)
        
        # Instruction
        draw.text((30, 125), "Turn encoder 1 to adjust", font=FONT_SM, fill=COLOR_TEXT_DIM)
        
        # Bottom bar
        _draw_bottom_bar(draw, state)
        
        return _to_push2_frame(img)
    except Exception as e:
        print(f"  ✗ Accent screen error: {e}")
        return None


def _render_scale_screen(pad_grid):
    """Display the scale and root note selection screen."""
    from pad_grid import SCALE_NAMES, NOTE_NAMES
    
    img = Image.new('RGB', (SCREEN_WIDTH, SCREEN_HEIGHT), color=(15, 15, 20))
    draw = ImageDraw.Draw(img)
    
    # Title
    draw.text((SCREEN_WIDTH // 2 - 40, 2), "SCALE SELECT",
              font=FONT_MD, fill=COLOR_ACCENT)
    
    # ── Current scale and root note ──
    draw.text((10, 22), pad_grid.scale_name,
              font=FONT_MD, fill=(200, 200, 255))
    draw.text((SCREEN_WIDTH // 2, 22), 
              f"Root: {pad_grid.root_note_name}   Oct: {pad_grid.octave}",
              font=FONT_MD, fill=(100, 150, 255))
    
    # ── Scale grid (matches top pads, rows 0-3) ──
    y_start = 42
    col_width = SCREEN_WIDTH // 8
    
    for i, name in enumerate(SCALE_NAMES):
        c = i % 8
        r = i // 8
        x = 4 + c * col_width
        y = y_start + r * 16
        
        if i == pad_grid.scale_index:
            draw.rectangle([x - 2, y - 1, x + col_width - 6, y + 14], fill=(30, 50, 80))
            draw.text((x, y), _truncate(name, 12), font=FONT_SM, fill=(150, 200, 255))
        else:
            draw.text((x, y), _truncate(name, 12), font=FONT_SM, fill=(100, 100, 100))
    
    # ── Root notes (matches bottom pads, rows 6-7) ──
    draw.text((10, 115), "Root note:", font=FONT_SM, fill=(80, 80, 80))
    note_x = 120
    for i, note in enumerate(NOTE_NAMES):
        x = note_x + i * 58
        if i == pad_grid.root_note:
            draw.text((x, 112), note, font=FONT_MD, fill=(100, 150, 255))
        else:
            draw.text((x, 112), note, font=FONT_MD, fill=(80, 80, 80))
    
    # Bottom bar
    draw.rectangle([0, 143, SCREEN_WIDTH, SCREEN_HEIGHT], fill=(20, 20, 25))
    draw.text((6, 147), "■ SCALE", font=FONT_SM, fill=COLOR_ACCENT)
    draw.text((SCREEN_WIDTH - 200, 147), "Press Scale to exit",
              font=FONT_SM, fill=COLOR_TEXT_DIM)
    
    return _to_push2_frame(img)


# ─────────────────────────────────────────────
# Convert to Push 2 format
# ─────────────────────────────────────────────

def _to_push2_frame(img):
    """
    Converts a PIL RGB image to a BGR565 numpy array
    ready to be sent to Push 2 via push2-python.

    push2-python expects an array of shape (960, 160) in uint16 — i.e.
    960 "rows" of 160 pixels. This is the inverse of the PIL convention
    (width × height), so we transpose after conversion.

    BGR565 format: [b4 b3 b2 b1 b0 | g5 g4 g3 g2 g1 g0 | r4 r3 r2 r1 r0]
    """
    rgb = np.array(img, dtype=np.uint16)   # shape: (160, 960, 3)

    r = rgb[:, :, 0]
    g = rgb[:, :, 1]
    b = rgb[:, :, 2]

    # Encode as BGR565
    bgr565 = (
        ((b >> 3) << 11) |
        ((g >> 2) << 5)  |
        (r >> 3)
    ).astype(np.uint16)                    # shape: (160, 960)

    # Transpose → shape (960, 160) expected by push2-python
    return bgr565.T
