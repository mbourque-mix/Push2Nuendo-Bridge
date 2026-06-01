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

import math
import numpy as np
import time
from PIL import Image, ImageDraw, ImageFont
from state import (
    MODE_VOLUME, MODE_PAN, MODE_SENDS, MODE_DEVICE, MODE_INSERTS, MODE_TRACK, MODE_OVERVIEW, MODE_CR,
    MODE_SETUP, MODE_MIDICC, MODE_BROWSER, MODE_CHANNEL_STRIP, MODE_XY, XY_TRACK_PARAMS,
    AT_POLY, AT_CHANNEL, AT_OFF,
    VC_LINEAR, VC_LOG, VC_EXP, VC_SCURVE, VC_FIXED,
    BRIDGE_VERSION, BANK_SIZE, AppState,
    STRIP_MOD_GATE, STRIP_MOD_COMPRESSOR, STRIP_MOD_TOOLS,
    STRIP_MOD_SATURATOR, STRIP_MOD_LIMITER,
)
from control_room import (
    CR_PAGES, CR_PAGE_NAMES, CR_PAGE_MAIN, ControlRoomState, PARAM_MAIN_LEVEL
)

# ─────────────────────────────────────────────
# Screen dimensions
# ─────────────────────────────────────────────

SCREEN_WIDTH  = 960
SCREEN_HEIGHT = 160

# Channel Strip section colors (match the Nuendo GUI).
CS_SECTION_COLORS = {
    'gate':    (210, 165, 70),    # yellow-ochre
    'comp':    (110, 140, 215),   # blue
    'eq':      (95, 180, 220),    # light blue
    'tools':   (120, 185, 100),   # green
    'sat':     (220, 140, 80),    # orange
    'limiter': (210, 90, 75),     # red
}
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

def _resource_path(*parts):
    """
    Resolve a path to a bundled resource.

    Works both when running from source and when frozen by PyInstaller
    (which extracts data files to ``sys._MEIPASS``). Returns ``None`` if the
    resource cannot be located.
    """
    import os
    import sys

    candidates = []
    # 1. PyInstaller one-file/one-dir extraction dir
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(os.path.join(meipass, *parts))
    # 2. Alongside this source file (dev mode: src/assets/fonts/...)
    here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(here, *parts))
    # 3. Project-root relative fallback
    candidates.append(os.path.join(here, "..", *parts))

    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def _bundled_font(filename, size):
    """
    Load a font that ships with the app first (so the Push display looks
    identical on every OS, including a frozen .exe where no system fonts
    are guaranteed). Falls back to the system-installed font of the same
    name, then to PIL's built-in bitmap font.
    """
    path = _resource_path("assets", "fonts", filename)
    if path:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            pass
    try:
        return ImageFont.truetype(filename, size)  # system-installed
    except (IOError, OSError):
        return None


def _load_fonts():
    """
    Load fonts. Prefers the fonts bundled with the app, then system fonts,
    otherwise falls back to PIL default font.
    """
    font_large  = _bundled_font("DejaVuSansMono.ttf", 14)
    font_medium = _bundled_font("DejaVuSansMono.ttf", 11)
    font_small  = _bundled_font("DejaVuSansMono.ttf", 9)
    if font_large is None or font_medium is None or font_small is None:
        # Fall back to PIL built-in font (always available)
        _def = ImageFont.load_default()
        font_large  = font_large  or _def
        font_medium = font_medium or _def
        font_small  = font_small  or _def

    # Try bold variants for headers / section names
    font_medium_bold = _bundled_font("DejaVuSansMono-Bold.ttf", 11) or font_medium
    font_small_bold  = _bundled_font("DejaVuSansMono-Bold.ttf", 9)  or font_small
    font_large_bold  = _bundled_font("DejaVuSansMono-Bold.ttf", 14) or font_large

    return (font_large, font_medium, font_small,
            font_medium_bold, font_small_bold, font_large_bold)


FONT_LG, FONT_MD, FONT_SM, FONT_MD_BOLD, FONT_SM_BOLD, FONT_LG_BOLD = _load_fonts()


def _text_color_for_bg(bg_color):
    """Return white or dark text color based on background luminance."""
    r, g, b = bg_color
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return (0, 0, 0) if luminance > 140 else (255, 255, 255)


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
    
    # Track name — adaptive text color based on background
    name = _abbreviate(track.name, 16)
    text_color = _text_color_for_bg(header_color)
    
    # State indicators: M (mute), S (solo), ● (record)
    indicators = []
    if track.is_muted:
        indicators.append(("M", (220, 200, 0)))      # Yellow
    if track.is_solo:
        indicators.append(("S", (0, 100, 220)))       # Blue
    if track.is_armed:
        indicators.append(("●", (220, 40, 40)))       # Red
    
    draw.text((cell_x + 4, 4), name, font=FONT_SM if len(name) > 10 else FONT_MD_BOLD, fill=text_color)
    if indicators:
        ix = cell_x + CELL_WIDTH - 6 * len(indicators) - 2
        for char, icolor in indicators:
            draw.text((ix, 4), char, font=FONT_SM, fill=icolor)
            ix += 6


def _draw_status_icon(draw, x, y, w, h, symbol, active_color, is_active):
    """Pro Tools-style status icon: rounded rect with a symbol inside.
    
    `symbol` can be:
      - a single character (e.g. "S", "M") — drawn as bold text
      - "rec_circle" — drawn as a filled circle (classic REC look)
      - "speaker"    — drawn as a small speaker shape
    
    Active: filled with `active_color`; symbol in black (for shapes) / white (for letters).
    Inactive: dim grey background, symbol in dim grey.
    """
    if is_active:
        bg_color = active_color
        shape_fg = (10, 10, 10)         # Black for shapes (REC circle, speaker)
        text_fg  = (255, 255, 255)      # White for letters
    else:
        bg_color = (38, 38, 38)
        shape_fg = (95, 95, 95)
        text_fg  = (95, 95, 95)
    
    draw.rounded_rectangle([x, y, x + w - 1, y + h - 1], radius=3, fill=bg_color)
    
    if symbol == "rec_circle":
        # Filled circle in the center (~6px radius for 21px-tall icons)
        cx = x + w // 2
        cy = y + h // 2
        r = max(3, min(w, h) // 4)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=shape_fg)
    
    elif symbol == "speaker":
        # Simple speaker icon: a square 'box' on the left, triangular 'cone' on the right
        cx = x + w // 2
        cy = y + h // 2
        bx = cx - 6
        by = cy - 3
        bw = 4
        bh = 6
        draw.rectangle([bx, by, bx + bw, by + bh], fill=shape_fg)
        draw.polygon([
            (bx + bw, by),
            (bx + bw, by + bh),
            (bx + bw + 5, cy + 5),
            (bx + bw + 5, cy - 5),
        ], fill=shape_fg)
    
    else:
        # Single character (letter)
        bbox = draw.textbbox((0, 0), symbol, font=FONT_MD_BOLD)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        tx = x + (w - tw) // 2
        ty = y + (h - th) // 2 - 2  # Slight upward visual adjust
        draw.text((tx, ty), symbol, font=FONT_MD_BOLD, fill=text_fg)


def _draw_automation_chip(draw, x, y, w, h, letter, color, is_active):
    """Small badge to the right of S/M icons indicating automation Read/Write state.
    
    Hidden when inactive. When active: small rounded rect with letter inside.
    """
    if not is_active:
        return
    draw.rounded_rectangle([x, y, x + w - 1, y + h - 1], radius=2, fill=color)
    bbox = draw.textbbox((0, 0), letter, font=FONT_SM)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = x + (w - tw) // 2
    ty = y + (h - th) // 2 - 2
    draw.text((tx, ty), letter, font=FONT_SM, fill=(255, 255, 255))


def _draw_fader_with_vu(draw, x, y, w, h, volume_value, vu_value, peak_clipped, volume_db):
    """Vertical fader with VU meter integrated inside the rail.
    
    The rail is wide enough (14px) for the VU to fill from bottom to vu_value level.
    The fader cap (volume position) sits centered on the rail, slightly wider than it
    for the 'handle' look (24px), and turns red (COLOR_WARNING) above 0 dB.
    
    Reference ticks at -6, -12, -18, -24 dB are drawn on the sides of the rail.
    Unity (0 dB) gets a brighter line across the full fader width.
    Peak clipping shows as a red blink frame around the rail.
    """
    rail_w = 14
    rail_x = x + (w - rail_w) // 2
    rail_x_end = rail_x + rail_w
    rail_center = rail_x + rail_w // 2
    
    # ── Rail background ──
    draw.rectangle([rail_x, y, rail_x_end, y + h], fill=(22, 22, 22))
    
    # ── VU meter inside the rail (logarithmic scale) ──
    import math
    if vu_value > 0:
        vu_db = 20 * math.log10(max(vu_value, 0.0001))
        vu_disp = max(0.0, min(1.0, (vu_db + 60) / 60))  # -60 dB → 0 dB
    else:
        vu_disp = 0.0
    
    vu_h = int(h * vu_disp)
    if vu_h > 0:
        for y_px in range(vu_h):
            y_pos = y + h - y_px - 1
            pct = y_px / h
            if pct < 0.65:
                c = (30, 180, 30)    # Green
            elif pct < 0.85:
                c = (200, 200, 30)   # Yellow
            else:
                c = (220, 40, 40)    # Red
            draw.line([(rail_x + 1, y_pos), (rail_x_end - 2, y_pos)], fill=c)
    
    # ── Peak clipped: red blink frame ──
    if peak_clipped:
        import time
        blink = int(time.time() * 4) % 2 == 0  # ~4Hz
        border = (255, 0, 0) if blink else (100, 0, 0)
        draw.rectangle([rail_x - 1, y - 1, rail_x_end + 1, y + h + 1],
                       outline=border, width=1)
    
    # ── Reference ticks on either side of the rail ──
    # Positions roughly correspond to -6, -12, -18, -24 dB on Nuendo's CC fader taper
    for ref_pos in [0.559, 0.369, 0.250, 0.129]:
        ty = y + h - int(ref_pos * h)
        draw.line([(rail_x - 4, ty), (rail_x - 1, ty)], fill=(70, 70, 70))
        draw.line([(rail_x_end + 1, ty), (rail_x_end + 4, ty)], fill=(70, 70, 70))
    
    # ── Unity line at 0 dB (75.1% from bottom on Nuendo's taper) ──
    unity_y = y + h - int(0.751 * h)
    draw.line([(x + 2, unity_y), (x + w - 3, unity_y)], fill=(140, 140, 140))
    
    # ── Fader cap (centered on rail, slightly wider than it for the 'handle' look) ──
    cap_y = y + h - int(volume_value * h)
    cap_h = 6
    cap_w = 24
    cap_x = rail_center - cap_w // 2
    cap_x_end = rail_center + cap_w // 2
    cap_color = COLOR_WARNING if volume_db > 0.1 else (210, 210, 210)
    draw.rectangle([cap_x, cap_y - cap_h // 2,
                    cap_x_end, cap_y + cap_h // 2],
                   fill=cap_color)
    # Center groove on the cap (gives it the "physical fader handle" look)
    draw.line([(cap_x + 2, cap_y), (cap_x_end - 2, cap_y)],
              fill=(40, 40, 40))


def _draw_volume_cell(draw, cell_x, track):
    """Draw a cell in Volume mode.
    
    Layout:
      Header (y=0..21)            track color + name + M/S/●
      Body (y=26..124)
        Status icons   (x+4..x+32)  4 stacked: REC circle, Speaker, S, M
        R/W chips      (x+34..x+45) 'r' beside S (auto-read); 'W' beside M (auto-write)
        Fader+VU       (x+48..x+116)  shifted right; rail with VU; narrow centered cap
      dB readout (y=128..142)
    """
    body_y_start = 26
    body_y_end = 124
    
    # ── Status icons column (left): REC circle, Speaker, S, M ──
    icon_x = cell_x + 4
    icon_w = 28
    icon_h = 21
    icon_gap = 3
    
    icons = [
        ("rec_circle", (220, 40, 40),  track.is_armed),       # Red — Rec armed
        ("speaker",    (220, 140, 0),  track.is_monitored),   # Orange — Input monitor
        ("S",          (0, 100, 220),  track.is_solo),        # Blue — Solo
        ("M",          (220, 200, 0),  track.is_muted),       # Yellow — Mute
    ]
    
    for j, (sym, color, active) in enumerate(icons):
        iy = body_y_start + j * (icon_h + icon_gap)
        _draw_status_icon(draw, icon_x, iy, icon_w, icon_h, sym, color, active)
    
    # ── Read/Write automation chips (right of S and M icons) ──
    chip_x = cell_x + 34
    chip_w = 12
    chip_h = 14
    s_y = body_y_start + 2 * (icon_h + icon_gap)  # Solo icon top
    m_y = body_y_start + 3 * (icon_h + icon_gap)  # Mute icon top
    chip_y_offset = (icon_h - chip_h) // 2        # Center chip vertically with icon
    
    _draw_automation_chip(draw, chip_x, s_y + chip_y_offset, chip_w, chip_h,
                          "r", (40, 170, 90),  track.automation_read)   # Green
    _draw_automation_chip(draw, chip_x, m_y + chip_y_offset, chip_w, chip_h,
                          "W", (200, 60, 60),  track.automation_write)  # Red
    
    # ── Fader with embedded VU (right column, shifted to make room for chips) ──
    fader_x = cell_x + 48
    fader_w = CELL_WIDTH - 48 - 4  # leave 4px right padding
    fader_y = body_y_start
    fader_h = body_y_end - body_y_start
    
    _draw_fader_with_vu(
        draw, fader_x, fader_y, fader_w, fader_h,
        volume_value=track.volume,
        vu_value=track.vu_meter,
        peak_clipped=track.peak_clipped,
        volume_db=track.volume_db,
    )
    
    # ── dB readout (below body) ──
    if hasattr(track, 'volume_display') and track.volume_display:
        db_text = track.volume_display
    elif track.volume > 0:
        db_text = f"{track.volume_db:+.1f}"
    else:
        db_text = "-∞"
    draw.text((cell_x + 4, 128), db_text, font=FONT_MD, fill=COLOR_TEXT_MAIN)


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
        ibo = getattr(state, 'insert_bank_offset', 0)  # 0 or 8
        page_label = "1-8" if ibo == 0 else "9-16"
        
        # Title at top
        track_name = selected.name if selected else "---"
        r, g, b = selected.color if selected else (150, 150, 150)
        title_bg = (min(r, 150), min(g, 150), min(b, 150))
        draw.rectangle([0, 0, SCREEN_WIDTH, 21], fill=title_bg)
        draw.text((8, 3), f"◄  {track_name}  ·  INSERTS {page_label}  ►", font=FONT_MD_BOLD, fill=_text_color_for_bg(title_bg))
        
        # 8 columns = 8 slots (offset by insert_bank_offset)
        for col in range(8):
            cell_x = col * CELL_WIDTH
            abs_slot = ibo + col
            
            # Separator
            if col > 0:
                draw.line([(cell_x, 22), (cell_x, 141)], fill=COLOR_SEPARATOR)
            
            name = names[abs_slot] if abs_slot < len(names) else ''
            is_active = active[abs_slot] if abs_slot < len(active) else False
            is_sel = (abs_slot == state.selected_insert_slot)
            
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
            draw.text((cell_x + 4, 26), f"#{abs_slot + 1}", font=FONT_SM, fill=COLOR_TEXT_DIM)
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
        
        # Button labels: bypass on all 8 visible slots
        for col in range(8):
            cell_x = col * CELL_WIDTH
            abs_slot = ibo + col
            name = names[abs_slot] if abs_slot < len(names) else ''
            if name:
                is_active = active[abs_slot] if abs_slot < len(active) else False
                bypass_color = (0, 160, 80) if is_active else (200, 120, 0)
                draw.text((cell_x + 4, 147), "BYPASS", font=FONT_SM, fill=bypass_color)
        
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
        title_bg = (min(r, 150), min(g, 150), min(b, 150))
        draw.rectangle([0, 0, SCREEN_WIDTH, 21], fill=title_bg)
        title = f"◄ {plugin_name} ►"
        title_text_color = _text_color_for_bg(title_bg)
        draw.text((8, 3), title, font=FONT_MD_BOLD, fill=title_text_color)
        # Mapping indicator
        if state.active_mapping:
            draw.text((SCREEN_WIDTH - 110, 5), "★ MAPPED", font=FONT_SM, fill=(0, 255, 160))
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


def _render_browser_screen(state):
    """Browser mode: slot selection, plugin list, or collection picker."""
    try:
        if state.browser_phase == "plugin_list":
            return _render_browser_plugin_list(state)
        elif state.browser_phase == "collection_select":
            return _render_browser_collection_select(state)
        return _render_browser_slot_select(state)
    except Exception as e:
        print(f"  ✗ Browser screen error: {e}")
        return _render_empty_frame()


def _render_browser_collection_select(state):
    """Browser: collection picker — select which collection to browse."""
    img = Image.new('RGB', (SCREEN_WIDTH, SCREEN_HEIGHT), color=COLOR_BG)
    draw = ImageDraw.Draw(img)
    
    # Title bar
    draw.rectangle([0, 0, SCREEN_WIDTH, 21], fill=(20, 50, 80))
    draw.text((8, 3), "SELECT COLLECTION", font=FONT_MD_BOLD, fill=(255, 255, 255))
    
    collections = state.browser_collections
    
    if not state.browser_collections_ready or len(collections) == 0:
        draw.text((SCREEN_WIDTH // 2 - 50, 70), "Loading...", font=FONT_LG, fill=COLOR_TEXT_DIM)
        return _to_push2_frame(img)
    
    selected = state.browser_coll_scroll
    total = len(collections)
    
    # Render collection list (vertically, max ~7 visible)
    y_start = 28
    line_height = 16
    max_visible = 7
    
    # Calculate scroll offset to keep selected item visible
    scroll_offset = 0
    if selected >= max_visible:
        scroll_offset = selected - max_visible + 1
    
    for i in range(max_visible):
        idx = scroll_offset + i
        if idx >= total:
            break
        
        coll = collections[idx]
        y = y_start + i * line_height
        is_sel = (idx == selected)
        
        if is_sel:
            # Highlight bar
            draw.rectangle([4, y - 1, SCREEN_WIDTH - 4, y + line_height - 2],
                           fill=(25, 45, 70))
            draw.rectangle([4, y - 1, SCREEN_WIDTH - 4, y + line_height - 2],
                           outline=(0, 150, 220), width=1)
        
        # Collection name
        name = coll['name'] or f"Collection {idx}"
        name_color = (255, 255, 255) if is_sel else COLOR_TEXT_MAIN
        draw.text((12, y), name, font=FONT_MD_BOLD if is_sel else FONT_MD, fill=name_color)
        
        # Plugin count
        count_text = f"{coll['count']} plugins"
        count_color = (0, 180, 220) if is_sel else COLOR_TEXT_DIM
        draw.text((SCREEN_WIDTH - 120, y), count_text, font=FONT_SM, fill=count_color)
        
        # Active indicator
        if idx == state.browser_collection_index:
            draw.text((SCREEN_WIDTH - 30, y), "●", font=FONT_SM, fill=(0, 200, 80))
    
    # Scroll indicator
    if total > max_visible:
        draw.text((SCREEN_WIDTH - 30, 3), f"{selected + 1}/{total}", font=FONT_SM, fill=(180, 180, 180))
    
    # Bottom bar
    draw.rectangle([0, 142, SCREEN_WIDTH, SCREEN_HEIGHT], fill=(10, 10, 10))
    draw.line([(0, 142), (SCREEN_WIDTH, 142)], fill=(50, 50, 50))
    draw.text((6, 147), "SELECT", font=FONT_SM, fill=(0, 200, 120))
    draw.text((200, 147), "Enc: Browse", font=FONT_SM, fill=COLOR_TEXT_DIM)
    draw.text((7 * CELL_WIDTH + 8, 147), "BACK", font=FONT_SM, fill=(200, 100, 100))
    
    return _to_push2_frame(img)


def _render_browser_slot_select(state):
    """Browser Phase 1: select which insert slot to load into."""
    img = Image.new('RGB', (SCREEN_WIDTH, SCREEN_HEIGHT), color=COLOR_BG)
    draw = ImageDraw.Draw(img)
    
    selected = state.selected_track
    track_name = selected.name if selected else "---"
    r, g, b = selected.color if selected else (150, 150, 150)
    ibo = state.insert_bank_offset  # 0 or 8
    page_label = "1-8" if ibo == 0 else "9-16"
    
    # Title bar
    draw.rectangle([0, 0, SCREEN_WIDTH, 21], fill=(20, 50, 80))
    draw.text((8, 3), f"ADD DEVICE  ·  {track_name}  ·  Slots {page_label}",
              font=FONT_MD, fill=(255, 255, 255))
    
    names = state.current_insert_names
    active = state.current_insert_active
    
    for col in range(8):
        cell_x = col * CELL_WIDTH
        abs_slot = ibo + col
        
        if col > 0:
            draw.line([(cell_x, 22), (cell_x, 141)], fill=COLOR_SEPARATOR)
        
        name = names[abs_slot] if abs_slot < len(names) else ''
        
        # Slot number
        draw.text((cell_x + 4, 26), f"Slot {abs_slot + 1}", font=FONT_SM, fill=COLOR_TEXT_DIM)
        
        if name:
            # Occupied slot — show plugin name
            is_act = active[abs_slot] if abs_slot < len(active) else False
            
            lines = []
            n = name
            while n:
                lines.append(n[:11])
                n = n[11:]
            y = 50
            for line in lines[:3]:
                draw.text((cell_x + 4, y), line, font=FONT_MD, fill=COLOR_TEXT_MAIN)
                y += 16
            
            # Active/bypassed indicator
            if is_act:
                draw.ellipse([cell_x + 4, 112, cell_x + 14, 122], fill=(0, 200, 80))
                draw.text((cell_x + 18, 112), "ON", font=FONT_SM, fill=(0, 200, 80))
            else:
                draw.ellipse([cell_x + 4, 112, cell_x + 14, 122], fill=(200, 120, 0))
                draw.text((cell_x + 18, 112), "BYP", font=FONT_SM, fill=(200, 120, 0))
        else:
            # Empty slot — invite to add
            draw.text((cell_x + 14, 65), "Empty", font=FONT_MD, fill=(60, 60, 60))
            draw.text((cell_x + 16, 85), "▲ Add", font=FONT_SM, fill=(80, 120, 160))
    
    # Bottom bar
    draw.rectangle([0, 142, SCREEN_WIDTH, SCREEN_HEIGHT], fill=(10, 10, 10))
    draw.line([(0, 142), (SCREEN_WIDTH, 142)], fill=(50, 50, 50))
    draw.text((6, 147), "SELECT SLOT", font=FONT_SM, fill=(0, 180, 220))
    draw.text((7 * CELL_WIDTH + 8, 147), "CANCEL", font=FONT_SM, fill=(200, 100, 100))
    draw.text((SCREEN_WIDTH - 80, 3), "◄► SLOTS", font=FONT_SM, fill=(180, 180, 180))
    
    return _to_push2_frame(img)


def _render_browser_plugin_list(state):
    """Browser Phase 2: scrollable plugin list."""
    img = Image.new('RGB', (SCREEN_WIDTH, SCREEN_HEIGHT), color=COLOR_BG)
    draw = ImageDraw.Draw(img)
    
    slot_num = state.browser_target_slot + 1
    coll_name = state.browser_collection_name or "Plugins"
    total = len(state.browser_plugins)
    
    # Title bar
    draw.rectangle([0, 0, SCREEN_WIDTH, 21], fill=(20, 50, 80))
    title = f"SLOT {slot_num}  ·  {coll_name}  ({total})"
    draw.text((8, 3), title, font=FONT_MD, fill=(255, 255, 255))
    
    # Show position indicator
    if total > 0:
        pos_text = f"{state.browser_scroll + 1}-{min(state.browser_scroll + 8, total)}/{total}"
        draw.text((SCREEN_WIDTH - 100, 5), pos_text, font=FONT_SM, fill=(180, 180, 180))
    
    if not state.browser_list_ready or total == 0:
        draw.text((SCREEN_WIDTH // 2 - 50, 70), "Loading...", font=FONT_LG, fill=COLOR_TEXT_DIM)
        return _to_push2_frame(img)
    
    # 8 columns = 8 visible plugins
    scroll = state.browser_scroll
    
    for col in range(8):
        cell_x = col * CELL_WIDTH
        plugin_idx = scroll + col
        
        if col > 0:
            draw.line([(cell_x, 22), (cell_x, 141)], fill=COLOR_SEPARATOR)
        
        if plugin_idx >= total:
            continue
        
        plugin = state.browser_plugins[plugin_idx]
        if not plugin:
            continue
        
        is_selected = (plugin_idx == state.browser_selected)
        
        # Background for selected plugin
        if is_selected:
            draw.rectangle([cell_x + 1, 24, cell_x + CELL_WIDTH - 2, 140],
                           fill=(25, 40, 60))
            draw.rectangle([cell_x + 1, 24, cell_x + CELL_WIDTH - 2, 140],
                           outline=(0, 150, 220), width=1)
        
        # Plugin name (2-3 lines)
        name = plugin['name']
        lines = []
        while name:
            lines.append(name[:11])
            name = name[11:]
        y = 30
        name_color = (255, 255, 255) if is_selected else COLOR_TEXT_MAIN
        for line in lines[:3]:
            draw.text((cell_x + 4, y), line, font=FONT_MD, fill=name_color)
            y += 16
        
        # Vendor
        vendor = plugin.get('vendor', '')
        if vendor:
            draw.text((cell_x + 4, 90), _truncate(vendor, 12), font=FONT_SM,
                       fill=(120, 160, 200) if is_selected else COLOR_TEXT_DIM)
        
        # Category (extract after "Fx|")
        sub_cat = plugin.get('sub_categories', '')
        cat_short = sub_cat.split('|')[-1] if '|' in sub_cat else sub_cat
        if cat_short:
            draw.text((cell_x + 4, 108), _truncate(cat_short, 12), font=FONT_SM,
                       fill=(100, 180, 100) if is_selected else (70, 100, 70))
        
        # "LOAD" label for upper row button
        draw.text((cell_x + CELL_WIDTH // 2 - 14, 126), "LOAD", font=FONT_SM,
                   fill=(0, 180, 120) if is_selected else (60, 80, 60))
    
    # Bottom bar
    draw.rectangle([0, 142, SCREEN_WIDTH, SCREEN_HEIGHT], fill=(10, 10, 10))
    draw.line([(0, 142), (SCREEN_WIDTH, 142)], fill=(50, 50, 50))
    draw.text((6, 147), "COLL ►", font=FONT_SM, fill=(220, 160, 0))
    draw.text((200, 147), "Enc1: Page  Enc2: Fine", font=FONT_SM, fill=COLOR_TEXT_DIM)
    
    # Cancel label on last lower button
    draw.text((7 * CELL_WIDTH + 8, 147), "BACK", font=FONT_SM, fill=(200, 100, 100))
    
    return _to_push2_frame(img)


def _render_device_screen(state):
    """Dedicated screen for Device: 8 Quick Controls of the selected track."""
    try:
        img = Image.new('RGB', (SCREEN_WIDTH, SCREEN_HEIGHT), color=COLOR_BG)
        draw = ImageDraw.Draw(img)
        
        selected = state.selected_track
        track_name = selected.name if selected else "---"
        r, g, b = selected.color if selected else (150, 150, 150)
        
        # Title at top
        title_bg = (min(r, 150), min(g, 150), min(b, 150))
        draw.rectangle([0, 0, SCREEN_WIDTH, 21], fill=title_bg)
        draw.text((8, 3), f"◄  {track_name}  ·  QUICK CONTROLS  ►", font=FONT_MD_BOLD, fill=_text_color_for_bg(title_bg))
        
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
        title_bg = (min(r, 150), min(g, 150), min(b, 150))
        draw.rectangle([0, 0, SCREEN_WIDTH, 21], fill=title_bg)
        draw.text((8, 3), f"◄  {track_name}  ·  SENDS  ►", font=FONT_MD_BOLD, fill=_text_color_for_bg(title_bg))
        
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

def _draw_bottom_bar(draw, state, cr_state=None):
    """
    Draw an info bar at the bottom of the screen (y = 142 to 160).
    Display: active mode, bank, Nuendo connection.
    cr_state (optional): when given, the Mix page also shows the Control Room
    Main level (volume) in the footer.
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

    # Pad MIDI note range (Mix page only)
    if state.mode == MODE_VOLUME:
        note_range = getattr(state, 'pad_note_range', '')
        if note_range:
            draw.text((172, 147), f"♪ {note_range}", font=FONT_SM, fill=(120, 170, 130))
    
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

    # Control Room Main level (Mix page only) — prefer Nuendo's dB display,
    # fall back to a value-derived estimate.
    if state.mode == MODE_VOLUME and cr_state is not None:
        cr_disp = cr_state.get_display(PARAM_MAIN_LEVEL)
        if not cr_disp:
            cr_val = cr_state.get_value(PARAM_MAIN_LEVEL)
            if cr_val:
                cr_disp = _cr_value_to_db(cr_val, 12.0)
        if cr_disp:
            draw.text((700, 147), f"CR {cr_disp} dB", font=FONT_SM, fill=(150, 180, 220))

    # Connection status (right side)
    if state.nuendo_connected:
        draw.text((SCREEN_WIDTH - 90, 147), "● NUENDO", font=FONT_SM,
                  fill=(0, 200, 80))
    else:
        draw.text((SCREEN_WIDTH - 110, 147), "○ WAITING", font=FONT_SM,
                  fill=COLOR_WARNING)
    


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

def _xy_axis_label(state, axis):
    """Human label for an XY axis assignment, e.g. 'Volume', 'QC3', 'CC16'."""
    cat = state.xy_cat_x if axis == 'x' else state.xy_cat_y
    if cat == 'cc':
        return f"CC{state.xy_cc_x if axis == 'x' else state.xy_cc_y}"
    idx = state.xy_track_param_x if axis == 'x' else state.xy_track_param_y
    return XY_TRACK_PARAMS[idx]


def _render_xy_screen(state):
    """XY pad screen: selected-track header + X/Y assignments and live values."""
    img = Image.new('RGB', (SCREEN_WIDTH, SCREEN_HEIGHT), color=COLOR_BG)
    draw = ImageDraw.Draw(img)

    sel = state.selected_track
    track_name = sel.name if sel else "---"
    tcol = sel.color if sel else (90, 90, 90)
    hdr = (min(tcol[0], 180), min(tcol[1], 180), min(tcol[2], 180))

    # Header — selected track (like other modes)
    draw.rectangle([0, 0, SCREEN_WIDTH, 21], fill=hdr)
    draw.text((8, 3), f"XY  -  {track_name}", font=FONT_MD, fill=_text_color_for_bg(hdr))

    cw = SCREEN_WIDTH // 8
    def col(i):
        return i * cw + 8

    x_lbl = _xy_axis_label(state, 'x')
    y_lbl = _xy_axis_label(state, 'y')
    cat_x = "CC" if state.xy_cat_x == 'cc' else "Track"
    cat_y = "CC" if state.xy_cat_y == 'cc' else "Track"

    # Encoder-aligned columns: Enc1=X, Enc2=Y, Enc4=Sens, Enc5=Smooth
    draw.text((col(0), 28), "X param", font=FONT_SM, fill=(120, 160, 220))
    draw.text((col(0), 42), x_lbl, font=FONT_MD, fill=(180, 210, 255))
    draw.text((col(0), 64), f"{int(round(state.xy_val_x))}", font=FONT_LG_BOLD, fill=(255, 255, 255))
    draw.text((col(0), 92), f"({cat_x})", font=FONT_SM, fill=(120, 120, 140))

    draw.text((col(1), 28), "Y param", font=FONT_SM, fill=(120, 220, 170))
    draw.text((col(1), 42), y_lbl, font=FONT_MD, fill=(180, 255, 210))
    draw.text((col(1), 64), f"{int(round(state.xy_val_y))}", font=FONT_LG_BOLD, fill=(255, 255, 255))
    draw.text((col(1), 92), f"({cat_y})", font=FONT_SM, fill=(120, 120, 140))

    draw.text((col(3), 28), "Sens", font=FONT_SM, fill=(150, 150, 170))
    draw.text((col(3), 42), f"{state.xy_sensitivity:.2f}", font=FONT_MD, fill=(220, 220, 230))
    draw.text((col(4), 28), "Smooth", font=FONT_SM, fill=(150, 150, 170))
    draw.text((col(4), 42), f"{state.xy_smooth:.2f}", font=FONT_MD, fill=(220, 220, 230))

    draw.text((col(0), 118), "Lower 1/2: switch X/Y between Track params and MIDI CC",
              font=FONT_SM, fill=(110, 110, 130))

    # Footer — lower-row labels (1/2 = X/Y category, 5-8 = M/S/Mon/Rec, lit when active)
    draw.rectangle([0, 143, SCREEN_WIDTH, SCREEN_HEIGHT], fill=(22, 22, 28))
    draw.text((col(0), 147), f"X:{cat_x}", font=FONT_SM, fill=(150, 200, 255))
    draw.text((col(1), 147), f"Y:{cat_y}", font=FONT_SM, fill=(150, 255, 200))
    foot = [
        (4, "MUTE", (255, 200, 0),  bool(sel and sel.is_muted)),
        (5, "SOLO", (90, 150, 255), bool(sel and sel.is_solo)),
        (6, "MON",  (255, 150, 0),  bool(sel and sel.is_monitored)),
        (7, "REC",  (255, 70, 70),  bool(sel and sel.is_armed)),
    ]
    for i, label, on_color, is_on in foot:
        draw.text((col(i), 147), label, font=FONT_SM, fill=on_color if is_on else (110, 110, 130))

    return _to_push2_frame(img)


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

    # Rescan action on lower row 8 (available on every Setup page)
    rx = 7 * CELL_WIDTH
    rtw = FONT_SM.getlength("RESCAN") if hasattr(FONT_SM, 'getlength') else 36
    draw.text((rx + (CELL_WIDTH - rtw) // 2, 146), "RESCAN", fill=(150, 150, 150), font=FONT_SM)

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
# Channel Strip overview screen (v1.0.4)
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# Footer pill helper — single-line label centered in a slim pill.
# Pill colour conveys state (green = on, gray = off); no ON/OFF text needed.
# ─────────────────────────────────────────────────────────────────────────────

def _draw_footer_pill(draw, fx, footer_top, cell_w, footer_h, label, is_on,
                      on_color=(0, 180, 0)):
    # on_color lets callers pick the lit colour (default green; the Edit
    # button uses white to match Nuendo's window-open indication).
    pill_color = on_color if is_on else (60, 60, 60)
    draw.rectangle([fx + 4, footer_top + 2,
                    fx + cell_w - 4, footer_top + footer_h - 4],
                   fill=pill_color, outline=(30, 30, 30), width=1)
    if not label:
        return
    label_short = label if len(label) <= 12 else label[:11] + '…'
    bbox = draw.textbbox((0, 0), label_short, font=FONT_SM)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    # Center label vertically inside the pill
    pill_h_avail = footer_h - 6
    y_text = footer_top + 2 + (pill_h_avail - th) // 2 - 1
    text_fill = _text_color_for_bg(pill_color)
    draw.text((fx + (cell_w - tw) // 2, y_text),
              label_short, font=FONT_SM, fill=text_fill)


# ─────────────────────────────────────────────────────────────────────────────
# EQ page helpers — parse display strings, compute filter magnitudes, render curve
# ─────────────────────────────────────────────────────────────────────────────

def _parse_freq_hz(display):
    """Parse '30.0 Hz', '1.5 kHz', '12.0 kHz' → float Hz, or None."""
    if not display:
        return None
    s = display.strip().lower().replace(' ', '')
    try:
        if s.endswith('khz'):
            return float(s[:-3]) * 1000.0
        if s.endswith('hz'):
            return float(s[:-2])
        return float(s)
    except (ValueError, TypeError):
        return None


def _parse_db(display):
    """Parse '0.0 dB', '-3.5 dB' → float dB, or None."""
    if not display:
        return None
    s = display.strip().lower().replace(' ', '')
    try:
        if s.endswith('db'):
            s = s[:-2]
        return float(s)
    except (ValueError, TypeError):
        return None


def _parse_q(display):
    """Parse '0.71' → float, or None."""
    if not display:
        return None
    try:
        return float(display.strip())
    except (ValueError, TypeError):
        return None


def _peak_db(f, f0, gain_db, q):
    """Bell/peak filter magnitude approximation."""
    if f0 <= 0 or f <= 0 or q <= 0:
        return 0.0
    ratio = f / f0
    dev = q * (ratio - 1.0 / ratio)
    return gain_db / (1.0 + dev * dev)


def _low_shelf_db(f, f0, gain_db):
    """Low shelf magnitude — full gain below f0/2, zero above 2*f0."""
    if f0 <= 0 or f <= 0:
        return 0.0
    x = math.log2(f / f0)
    return gain_db / (1.0 + math.exp(x * 2.0))


def _high_shelf_db(f, f0, gain_db):
    """High shelf magnitude — zero below f0/2, full gain above 2*f0."""
    if f0 <= 0 or f <= 0:
        return 0.0
    x = math.log2(f / f0)
    return gain_db / (1.0 + math.exp(-x * 2.0))


def _low_cut_db(f, f0, slope_db_oct=24):
    """Low-cut (high-pass) filter: 0 dB above f0, slope rolloff below."""
    if f0 <= 0 or f <= 0:
        return -60.0
    if f >= f0:
        return 0.0
    return max(-60.0, -slope_db_oct * math.log2(f0 / f))


def _high_cut_db(f, f0, slope_db_oct=24):
    """High-cut (low-pass) filter: 0 dB below f0, slope rolloff above."""
    if f0 <= 0 or f <= 0:
        return -60.0
    if f <= f0:
        return 0.0
    return max(-60.0, -slope_db_oct * math.log2(f / f0))


def _norm_to_freq_hz(norm):
    """Cubase EQ freq mapping (20 Hz → 20 kHz log scale)."""
    n = max(0.0, min(1.0, norm))
    return 20.0 * (1000.0 ** n)


def _norm_to_db(norm):
    """Cubase EQ gain mapping (−24 dB → +24 dB linear, centered at 0.5)."""
    n = max(0.0, min(1.0, norm))
    return (n - 0.5) * 48.0


def _norm_to_q(norm):
    """Cubase EQ Q mapping (~0.5 → ~12, log-like)."""
    n = max(0.0, min(1.0, norm))
    return 0.5 * (24.0 ** n)


def _norm_to_eq_type(norm, band_idx):
    """Map normalized Type value to a name. Band 0/3 have Cut/Shelf/Peak,
    Band 1/2 are always Peak."""
    if band_idx in (1, 2):
        return 'peak'
    n = max(0.0, min(1.0, norm))
    # Approximation — Cubase actual mapping may have more discrete steps
    if n < 0.33:
        return 'cut'
    if n < 0.67:
        return 'shelf'
    return 'peak'


def _collect_eq_data(state):
    """Gather all 4 EQ bands + PreFilter HC/LC params for the curve renderer.

    Pulls fresh display strings for the SELECTED band from
    state.insert_param_values[1..4]; estimates other bands' values from the
    normalized cache in state.da_strip_toggle_values[('EQ', param_idx)].

    Returns a dict, or None if no EQ data is available.
    """
    selected = getattr(state, 'eq_selected_band', 0)
    toggle_mirror = getattr(state, 'da_strip_toggle_values', {}) or {}

    # Sanity: do we have any EQ data at all?
    if not any(k[0] == 'EQ' for k in toggle_mirror.keys()):
        return None

    ipv = getattr(state, 'insert_param_values', []) or []

    band_cache = getattr(state, 'eq_band_cache', None)
    if band_cache is None or len(band_cache) < 4:
        state.eq_band_cache = [{}, {}, {}, {}]
        band_cache = state.eq_band_cache

    bands = []
    for band_idx in range(4):
        base = band_idx * 6
        on_idx   = 5 + base
        type_idx = 6 + base
        gain_idx = 7 + base
        freq_idx = 8 + base
        q_idx    = 9 + base
        cache_entry = band_cache[band_idx]

        # Fresh display for selected band only.
        if band_idx == selected and len(ipv) >= 5:
            type_disp = ipv[1] or ''
            freq_disp = ipv[2] or ''
            q_disp    = ipv[3] or ''
            gain_disp = ipv[4] or ''
            freq = _parse_freq_hz(freq_disp)
            gain = _parse_db(gain_disp)
            q    = _parse_q(q_disp)
            type_str = type_disp.lower() if type_disp else None
            # Stash freshly parsed values into the per-band cache so the
            # curve stays stable when the user later switches selection.
            if freq is not None: cache_entry['freq'] = freq
            if gain is not None: cache_entry['gain'] = gain
            if q is not None:    cache_entry['q'] = q
            if type_str:         cache_entry['type'] = type_str
        else:
            freq = cache_entry.get('freq')
            gain = cache_entry.get('gain')
            q    = cache_entry.get('q')
            type_str = cache_entry.get('type')

        # Final fallback: estimate from normalized cache when nothing is known.
        if freq is None:
            freq = _norm_to_freq_hz(toggle_mirror.get(('EQ', freq_idx), 0.5))
        if gain is None:
            gain = _norm_to_db(toggle_mirror.get(('EQ', gain_idx), 0.5))
        if q is None:
            q = _norm_to_q(toggle_mirror.get(('EQ', q_idx), 0.5))
        if not type_str:
            type_str = _norm_to_eq_type(
                toggle_mirror.get(('EQ', type_idx), 0.5), band_idx)

        on_val = toggle_mirror.get(('EQ', on_idx), 0.0)

        bands.append({
            'on':   on_val >= 0.5,
            'type': type_str,
            'freq': freq,
            'gain': gain,
            'q':    q,
        })

    # PreFilter — read directly from state.channel_strip.prefilter
    pf = state.channel_strip.prefilter
    lc_disp = pf.get(0x05, {}).get('display', '')
    hc_disp = pf.get(0x02, {}).get('display', '')
    lc_val  = pf.get(0x06, {}).get('value', 0)
    hc_val  = pf.get(0x03, {}).get('value', 0)
    pregain_disp = pf.get(0x00, {}).get('display', '')

    return {
        'bands':     bands,
        'selected':  selected,
        'lc_on':     lc_val >= 64,
        'lc_freq':   _parse_freq_hz(lc_disp),
        'hc_on':     hc_val >= 64,
        'hc_freq':   _parse_freq_hz(hc_disp),
        'pregain':   _parse_db(pregain_disp) or 0.0,
    }


def _render_eq_curve(draw, x_left, y_top, width, height, eq):
    """Draw the EQ magnitude curve into the given rect.

    Combines PreGain + PreFilter HC/LC + 4 EQ bands. Each band's filter type
    is determined from the display string ('peak', 'shelf', 'cut') + band
    index (band 0-1 → low side, band 2-3 → high side for shelf/cut).
    """
    if eq is None:
        return

    N = max(width // 3, 80)  # number of curve sample points
    log_min = math.log10(20.0)
    log_max = math.log10(20000.0)
    db_range = 24.0  # ±24 dB → top to bottom (matches Cubase EQ gain range)

    points = []
    for i in range(N):
        x_frac = i / (N - 1)
        freq = 10 ** (log_min + (log_max - log_min) * x_frac)

        # PreGain is upstream gain staging — it shifts the whole signal but
        # doesn't reshape the spectrum, so we exclude it from the curve.
        mag = 0.0

        # PreFilter cuts
        if eq.get('lc_on') and eq.get('lc_freq'):
            mag += _low_cut_db(freq, eq['lc_freq'])
        if eq.get('hc_on') and eq.get('hc_freq'):
            mag += _high_cut_db(freq, eq['hc_freq'])

        # EQ bands
        for band_idx, band in enumerate(eq['bands']):
            if not band['on'] or band['freq'] is None:
                continue
            t = band['type']
            if 'peak' in t:
                mag += _peak_db(freq, band['freq'], band['gain'], band['q'])
            elif 'shelf' in t:
                if band_idx <= 1:
                    mag += _low_shelf_db(freq, band['freq'], band['gain'])
                else:
                    mag += _high_shelf_db(freq, band['freq'], band['gain'])
            elif 'cut' in t:
                if band_idx <= 1:
                    mag += _low_cut_db(freq, band['freq'])
                else:
                    mag += _high_cut_db(freq, band['freq'])
            else:
                # Default to peak
                mag += _peak_db(freq, band['freq'], band['gain'], band['q'])

        x_px = x_left + int(round(x_frac * (width - 1)))
        y_frac = (db_range - mag) / (2 * db_range)
        y_frac = max(0.0, min(1.0, y_frac))
        y_px = y_top + int(round(y_frac * (height - 1)))
        points.append((x_px, y_px))

    # 0 dB reference line
    y_mid = y_top + height // 2
    draw.line([(x_left, y_mid), (x_left + width - 1, y_mid)],
              fill=(50, 50, 50), width=1)

    # Curve polyline (cyan/teal like Ableton)
    if len(points) > 1:
        draw.line(points, fill=(0, 200, 220), width=2)

    # Vertical tick for the selected band
    sel = eq['selected']
    if 0 <= sel < len(eq['bands']) and eq['bands'][sel]['freq']:
        sf = eq['bands'][sel]['freq']
        if 20 <= sf <= 20000:
            sx_frac = (math.log10(sf) - log_min) / (log_max - log_min)
            sx_px = x_left + int(round(sx_frac * (width - 1)))
            draw.line([(sx_px, y_top), (sx_px, y_top + height - 1)],
                      fill=(0, 200, 100), width=1)

    # Per-band markers: numbered circle at (freq, gain).
    #   active   → white-filled circle, grey digit
    #   inactive → grey outline circle, grey digit
    R = 8
    for band_idx, band in enumerate(eq['bands']):
        bf = band.get('freq')
        if bf is None or not (20 <= bf <= 20000):
            continue
        bx_frac = (math.log10(bf) - log_min) / (log_max - log_min)
        bx = x_left + int(round(bx_frac * (width - 1)))
        # Cut filters have no meaningful gain → anchor on the 0 dB line.
        t = band.get('type', '')
        if 'cut' in t:
            by = y_mid
        else:
            g = band.get('gain', 0.0) or 0.0
            gy_frac = (db_range - g) / (2 * db_range)
            gy_frac = max(0.0, min(1.0, gy_frac))
            by = y_top + int(round(gy_frac * (height - 1)))
        # Clamp the circle fully inside the canvas
        bx = max(x_left + R, min(x_left + width - 1 - R, bx))
        by = max(y_top + R, min(y_top + height - 1 - R, by))

        active = bool(band.get('on'))
        if active:
            draw.ellipse([bx - R, by - R, bx + R, by + R],
                         fill=(255, 255, 255), outline=(255, 255, 255))
            digit_color = (90, 90, 90)
        else:
            draw.ellipse([bx - R, by - R, bx + R, by + R],
                         outline=(120, 120, 120), width=1)
            digit_color = (120, 120, 120)

        dch = str(band_idx + 1)
        dbbox = draw.textbbox((0, 0), dch, font=FONT_SM_BOLD)
        dw = dbbox[2] - dbbox[0]
        dh = dbbox[3] - dbbox[1]
        draw.text((bx - dw // 2, by - dh // 2 - 1),
                  dch, font=FONT_SM_BOLD, fill=digit_color)


def _render_channel_strip_screen(state):
    """
    Channel Strip overview of the selected track.
    
    Layout (8 columns of 120px each):
      Col 1: Gate         (variant + on/off)
      Col 2: Comp         (variant + on/off)
      Col 3: EQ           (4 bands status)
      Col 4: Tools        (variant + on/off)
      Col 5: Sat          (variant + on/off)
      Col 6: Limiter      (variant + on/off)
      Col 7: Phase        (PreFilter Phase Switch on/off)
      Col 8: PreGain      (PreFilter Gain value)
    
    From Matthieu's plan:
      - Upper row buttons 1-6 = enter that module's drill-down page
      - Lower row buttons 1-6 = toggle module on/off
      - Encoders 7-8 = adjust Phase / PreGain
    
    This is a first-pass overview; the per-module drill-down pages come later.
    """
    img = Image.new('RGB', (SCREEN_WIDTH, SCREEN_HEIGHT), color=COLOR_BG)
    draw = ImageDraw.Draw(img)
    
    cs = state.channel_strip
    selected = state.selected_track
    
    # ── Header (track name + mode label) ──
    track_color = selected.color if selected.color else (60, 60, 60)
    draw.rectangle([0, 0, SCREEN_WIDTH, 22], fill=track_color)
    header_text_color = _text_color_for_bg(track_color)
    draw.text((6, 4), f"CHANNEL STRIP — {selected.name}",
              fill=header_text_color, font=FONT_MD_BOLD)
    
    # ── 8 column cells ──
    columns = [
        ('slot',  'Gate',    STRIP_MOD_GATE),
        ('slot',  'Comp',    STRIP_MOD_COMPRESSOR),
        ('eq',    'EQ',      None),
        ('slot',  'Tools',   STRIP_MOD_TOOLS),
        ('slot',  'Sat',     STRIP_MOD_SATURATOR),
        ('slot',  'Limiter', STRIP_MOD_LIMITER),
        ('pf',    'Phase',   0x01),  # PreFilter PhaseSwitch
        ('pf',    'PreGain', 0x00),  # PreFilter Gain
    ]
    
    section_colors = CS_SECTION_COLORS
    # Map column index → section key for colouring
    col_section_key = ['gate', 'comp', 'eq', 'tools', 'sat', 'limiter', None, None]
    # Capture each section's active state for the footer pills (Lower 1-6).
    col_active = [True] * 8

    for col_idx, (kind, label, key) in enumerate(columns):
        x = col_idx * CELL_WIDTH
        sect = col_section_key[col_idx]
        col = section_colors.get(sect) if sect else None

        # Cell separator on the right
        draw.line([(x + CELL_WIDTH - 1, 24), (x + CELL_WIDTH - 1, SCREEN_HEIGHT)],
                  fill=COLOR_SEPARATOR)

        # Decide on/off state (drives the colour intensity)
        is_active = True
        empty = False
        if kind == 'slot':
            slot = cs.slots.get(key)
            empty = (slot is None or not slot.plugin_name)
            is_active = (not empty) and (not slot.bypassed) if slot else False
        elif kind == 'eq':
            # Prefer DA mirror (the overview lower-row 3 toggles via DA flip,
            # which updates state.da_strip_toggle_values[('EQ', 0)]).
            bypass_da = state.da_strip_toggle_values.get(('EQ', 0), None)
            if bypass_da is not None:
                bypassed = bypass_da >= 0.5
            else:
                bypass_val = cs.eq.get(0x7F, {}).get('value', 0)
                bypass_disp = cs.eq.get(0x7F, {}).get('display', '')
                bypassed = (bypass_disp == 'On') or (bypass_val >= 64)
            is_active = not bypassed

        col_active[col_idx] = is_active

        # Section bar (Cubase-style coloured banner across most of the cell).
        # Colour brightness reflects active/bypassed state.
        if col is not None:
            band_top = 26
            band_bot = 116
            if is_active:
                fill_col = col
            else:
                # Darken when bypassed (~25% brightness)
                fill_col = tuple(int(c * 0.25) for c in col)
            draw.rectangle([x + 4, band_top, x + CELL_WIDTH - 6, band_bot],
                           fill=fill_col)
            text_col = _text_color_for_bg(fill_col)
            # Section name — bold, centred-ish in the band
            bbox = draw.textbbox((0, 0), label, font=FONT_LG_BOLD)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text((x + (CELL_WIDTH - tw) // 2, band_top + 6),
                      label, fill=text_col, font=FONT_LG_BOLD)

            # Variant / status under the name (where applicable)
            if kind == 'slot' and slot is not None:
                variant_text = slot.plugin_name if slot.plugin_name else "—"
                if len(variant_text) > 14:
                    variant_text = variant_text[:13] + '…'
                bbox = draw.textbbox((0, 0), variant_text, font=FONT_SM)
                tw = bbox[2] - bbox[0]
                draw.text((x + (CELL_WIDTH - tw) // 2, band_top + 38),
                          variant_text, fill=text_col, font=FONT_SM)
            elif kind == 'eq':
                active_bands = sum(
                    1 for band_idx in range(1, 5)
                    if cs.eq.get((band_idx * 0x10) + 0x04, {}).get('display') == 'On'
                )
                txt = f"{active_bands}/4 bands"
                bbox = draw.textbbox((0, 0), txt, font=FONT_SM)
                tw = bbox[2] - bbox[0]
                draw.text((x + (CELL_WIDTH - tw) // 2, band_top + 38),
                          txt, fill=text_col, font=FONT_SM)
        else:
            # Phase / PreGain cells — no colour band, just label + value
            draw.text((x + 6, 28), label, fill=COLOR_TEXT_MAIN, font=FONT_MD_BOLD)
            if kind == 'pf':
                param = cs.prefilter.get(key, {})
                display = param.get('display', '—')
                if len(display) > 12:
                    display = display[:11] + '…'
                color = COLOR_TEXT_MAIN
                if label == 'Phase':
                    is_on = (display == 'On')
                    color = COLOR_TEXT_MAIN if is_on else COLOR_TEXT_DIM
                draw.text((x + 6, 60), display, fill=color, font=FONT_MD)

    # ── Lower-row button labels footer (overview) ──
    # Lower 1-6 = bypass each section (Gate..Limiter), Lower 7 = Phase On/Off,
    # Lower 8 = Edit Channel Settings window.
    if state.cs_page == "overview":
        f_top = SCREEN_HEIGHT - 22
        phase_val  = cs.prefilter.get(0x01, {}).get('value', 0)
        phase_disp = cs.prefilter.get(0x01, {}).get('display', '')
        phase_on   = (phase_disp == 'On') or (phase_val >= 64)
        eo = bool(getattr(state, 'editor_open', False))

        # (label, lit?, on_color). Bypass pills are lit AMBER when the section
        # is BYPASSED (engaged) — matching Nuendo's bypass indicator. Phase is
        # a normal On/Off (green when on). Edit is white when window open.
        AMBER = (240, 200, 0)
        footer_defs = [
            ('Bypass', not col_active[0], AMBER),  # Lower 1 — Gate
            ('Bypass', not col_active[1], AMBER),  # Lower 2 — Comp
            ('Bypass', not col_active[2], AMBER),  # Lower 3 — EQ
            ('Bypass', not col_active[3], AMBER),  # Lower 4 — Tools
            ('Bypass', not col_active[4], AMBER),  # Lower 5 — Sat
            ('Bypass', not col_active[5], AMBER),  # Lower 6 — Limiter
            ('On/Off', phase_on,          (0, 180, 0)),   # Lower 7 — Phase
            ('Edit',   eo,                (255, 255, 255)),  # Lower 8 — Settings
        ]
        for fi, (flbl, fon, on_col) in enumerate(footer_defs):
            fx = fi * CELL_WIDTH
            pill_col = on_col if fon else (60, 60, 60)
            draw.rectangle([fx + 4, f_top + 2, fx + CELL_WIDTH - 4,
                            SCREEN_HEIGHT - 4],
                           fill=pill_col, outline=(30, 30, 30), width=1)
            bbox = draw.textbbox((0, 0), flbl, font=FONT_SM)
            tw = bbox[2] - bbox[0]
            draw.text((fx + (CELL_WIDTH - tw) // 2, f_top + 5),
                      flbl, font=FONT_SM, fill=_text_color_for_bg(pill_col))

    # Drill-down rendering
    if state.cs_page != "overview":
        page_labels = {
            "gate": "GATE",
            "comp": "COMPRESSOR",
            "eq": "CHANNEL EQ",
            "tools": "TOOLS",
            "sat": "SATURATOR",
            "limiter": "LIMITER",
        }
        page_to_modid = {
            "gate": 0x10,
            "comp": 0x11,
            "eq":   0x01,   # ChannelEQ section (binding-path mod 0x01)
            "tools": 0x12,
            "sat": 0x13,
            "limiter": 0x14,
        }
        
        # Per-page layout: which paramId goes in each cell position (top row,
        # indexed by encoder 0..7) and footer position (bottom row, indexed
        # by lower button 0..7). null entries are left blank.
        # Per-variant layouts: which paramId goes in each cell position
        # (top row, encoder 0..7) and footer position (lower button 0..7).
        # Lookup key is (cs_page, variant_name). variant_name=None is the
        # primary fallback.
        #
        # `toggle_labels` overrides Cubase's API names with the in-GUI labels
        # (e.g. Gate's paramId 0x06 is API-named "side chain on/off" but the
        # plugin GUI labels its behavior as "Activate Filter").
        variant_layouts = {
            # ── Gate (single variant) ──
            ('gate', None): {
                'encoders': [0x01, 0x02, 0x03, 0x04, 0x07, 0x08, None, None],
                'toggles':  [0x0E, 0x06, 0x05, None, None, None, None, None],
                'toggle_labels': {
                    0x0E: 'Listen Filter',
                    0x06: 'Activate Filter',
                    0x05: 'Auto Release',
                },
            },
            # ── Comp variants ──
            ('comp', 'Standard Compressor'): {
                'encoders': [0x01, 0x02, 0x03, 0x04, 0x06, None, None, None],
                'toggles':  [0x05, 0x07, None, None, None, None, None, None],
                'toggle_labels': {
                    0x05: 'Auto Release',
                    0x07: 'Auto MakeUp',
                },
                'da_toggles': {2: ('SoftKnee', 8)},
            },
            ('comp', 'Tube Compressor'): {
                'encoders': [0x01, 0x02, 0x03, 0x04, 0x06, 0x07, None, None],
                'toggles':  [0x05, None, None, None, None, None, None, None],
                'toggle_labels': {
                    0x05: 'Auto Release',
                },
            },
            ('comp', 'VintageCompressor'): {
                'encoders': [0x01, 0x02, 0x03, 0x05, None, None, None, None],
                'toggles':  [0x04, 0x06, None, None, None, None, None, None],
                'toggle_labels': {
                    0x04: 'Punch',          # API: "Att-Mode"
                    0x06: 'Auto Release',   # API: "Au-Release"
                },
            },
            # ── Tools variants ──
            ('tools', 'DeEsser'): {
                'encoders': [0x01, 0x03, 0x04, 0x05, 0x06, None, None, None],
                'toggles':  [0x02, 0x07, None, None, None, None, None, None],
                'toggle_labels': {
                    0x02: 'Auto Threshold',
                    0x07: 'Solo',
                },
                # DA-based footer toggles: {footer_pos: (label, da_param_idx)}
                # Strip slot is resolved at runtime from cs_page's mod_id.
                'da_toggles': {2: ('Diff', 6)},
            },
            # Custom layout: DeEsser may sit at the Saturator slot position.
            ('sat', 'DeEsser'): {
                'encoders': [0x01, 0x03, 0x04, 0x05, 0x06, None, None, None],
                'toggles':  [0x02, 0x07, None, None, None, None, None, None],
                'toggle_labels': {
                    0x02: 'Auto Threshold',
                    0x07: 'Solo',
                },
                'da_toggles': {2: ('Diff', 6)},
            },
            ('tools', 'EnvelopeShaper'): {
                'encoders': [0x01, 0x02, 0x04, 0x06, None, None, None, None],
                'toggles':  [None, None, None, None, None, None, None, None],
                'toggle_labels': {},
            },
            # ── Sat variants ──
            ('sat', 'Magneto II'): {
                'encoders': [0x01, 0x02, 0x03, 0x04, 0x07, None, None, None],
                'toggles':  [0x05, 0x06, None, None, None, None, None, None],
                'toggle_labels': {
                    0x05: 'HF On',
                    0x06: 'Solo',
                },
                'da_toggles': {2: ('Dual', 1), 3: ('Oversample', 5)},
            },
            # Custom layout: Magneto II at Limiter slot position.
            ('limiter', 'Magneto II'): {
                'encoders': [0x01, 0x02, 0x03, 0x04, 0x07, None, None, None],
                'toggles':  [0x05, 0x06, None, None, None, None, None, None],
                'toggle_labels': {
                    0x05: 'HF On',
                    0x06: 'Solo',
                },
                'da_toggles': {2: ('Dual', 1), 3: ('Oversample', 5)},
            },
            ('sat', 'Tape Saturation'): {
                'encoders': [0x01, 0x02, 0x03, 0x07, None, None, None, None],
                'toggles':  [0x05, 0x06, None, None, None, None, None, None],
                'toggle_labels': {
                    0x05: 'Dual',
                    0x06: 'Auto Gain',
                },
                'da_toggles': {2: ('Oversample', 6)},
            },
            # Custom layout: Tape Saturation at Limiter slot.
            ('limiter', 'Tape Saturation'): {
                'encoders': [0x01, 0x02, 0x03, 0x07, None, None, None, None],
                'toggles':  [0x05, 0x06, None, None, None, None, None, None],
                'toggle_labels': {
                    0x05: 'Dual',
                    0x06: 'Auto Gain',
                },
                'da_toggles': {2: ('Oversample', 6)},
            },
            ('sat', 'Tube Saturation'): {
                'encoders': [0x01, 0x02, 0x03, 0x06, None, None, None, None],
                'toggles':  [None, None, None, None, None, None, None, None],
                'toggle_labels': {},
            },
            # Custom layout: Tube Saturation at Limiter slot.
            ('limiter', 'Tube Saturation'): {
                'encoders': [0x01, 0x02, 0x03, 0x06, None, None, None, None],
                'toggles':  [None, None, None, None, None, None, None, None],
                'toggle_labels': {},
            },
            # ── Channel EQ (single-variant) ──
            # The encoder grid is fully driven by DA (cs_strip_da_active=True).
            # da_toggles puts band 1-4 On/Off on footer positions 0-3.
            ('eq', 'EQ'): {
                'encoders': [None, None, None, None, None, None, None, None],
                'toggles':  [None, None, None, None, None, None, None, None],
                'toggle_labels': {},
                # Band On at footer pos 0 acts on the SELECTED band; its DA
                # param index is dynamic, so the renderer handles it via a
                # custom branch (see eq_band_on_footer below) — not via da_toggles.
                'da_toggles': {},
                # Binding-path toggles at footer pos 5-7 (PreFilter LC/HC/Bypass).
                # Format: {pos: (mod_id, param_id, label, invert_for_on)}
                # invert_for_on=True means the param is a "bypass" flag → ON pill
                # when value is 0 (not bypassed).
                # Pos 7 is now the universal "Edit" (Channel Settings) button
                # on all CS pages — PreFilter Bypass moved to pos 4.
                'binding_toggles': {
                    4: (0x00, 0x7F, 'PreFilt',  True),
                    5: (0x00, 0x06, 'LC On',    False),
                    6: (0x00, 0x03, 'HC On',    False),
                },
                # Binding-path encoders at cell 5-7 (PreFilter LC Freq, HC Freq, PreGain).
                # Format: {cell_idx: (mod_id, param_id)}
                'binding_encoders': {
                    5: (0x00, 0x05),
                    6: (0x00, 0x02),
                    7: (0x00, 0x00),
                },
            },

            # ── Limit variants ──
            ('limiter', 'Brickwall Limiter'): {
                'encoders': [0x01, 0x04, None, None, None, None, None, None],
                'toggles':  [0x05, None, None, None, None, None, None, None],
                'toggle_labels': {
                    0x05: 'Auto Release',
                },
                'da_toggles': {1: ('Link', 4), 2: ('Oversample', 5)},
            },
            ('limiter', 'Maximizer'): {
                'encoders': [0x01, 0x03, 0x06, None, None, None, None, None],
                'toggles':  [None, None, None, None, None, None, None, None],
                'toggle_labels': {},
                'da_toggles': {0: ('SoftClip', 0), 1: ('Modern', 2)},
            },
            ('limiter', 'Standard Limiter'): {
                'encoders': [0x01, 0x04, 0x07, None, None, None, None, None],
                'toggles':  [0x05, None, None, None, None, None, None, None],
                'toggle_labels': {
                    0x05: 'Auto Release',
                },
            },
        }
        # Primary variant fallbacks (used when a slot has no plugin yet)
        variant_layouts[('comp', None)]    = variant_layouts[('comp', 'Standard Compressor')]
        variant_layouts[('tools', None)]   = variant_layouts[('tools', 'DeEsser')]
        variant_layouts[('sat', None)]     = variant_layouts[('sat', 'Magneto II')]
        variant_layouts[('limiter', None)] = variant_layouts[('limiter', 'Brickwall Limiter')]
        variant_layouts[('eq', None)]      = variant_layouts[('eq', 'EQ')]
        
        # Resolve the active layout for the current page + variant
        page_layouts = {}
        if state.cs_page in page_to_modid:
            mod_id_for_page = page_to_modid[state.cs_page]
            slot_for_page = state.channel_strip.slots.get(mod_id_for_page)
            variant_name = (slot_for_page.plugin_name
                            if (slot_for_page and slot_for_page.plugin_name)
                            else None)
            layout = variant_layouts.get((state.cs_page, variant_name))
            if layout is None:
                layout = variant_layouts.get((state.cs_page, None))
            if layout is not None:
                page_layouts[state.cs_page] = layout
        
        if state.cs_page in page_to_modid and state.cs_page in page_layouts:
            mod_id = page_to_modid[state.cs_page]
            slot = state.channel_strip.slots.get(mod_id)
            layout = page_layouts[state.cs_page]
            
            # Full overlay so the overview underneath doesn't bleed through
            img = Image.new('RGB', (SCREEN_WIDTH, SCREEN_HEIGHT), color=COLOR_BG)
            draw = ImageDraw.Draw(img)
            
            # Standard header (page label + Back hint) is now merged into the
            # chip strip below (col 0 = module name, col 7 = Back), so we no
            # longer draw a separate header line — this frees vertical space.

            # ── Header chip strip (upper row 3-4-5 variants, 7 Edit, 8 On/Off) ──
            _CS_VARIANT_NAMES = {
                'comp':    ['Standard Compressor', 'Tube Compressor', 'VintageCompressor'],
                'tools':   ['DeEsser', 'EnvelopeShaper'],
                'sat':     ['Magneto II', 'Tape Saturation', 'Tube Saturation'],
                'limiter': ['Brickwall Limiter', 'Maximizer', 'Standard Limiter'],
            }
            variant_names = _CS_VARIANT_NAMES.get(state.cs_page, [])
            cell_w = SCREEN_WIDTH // 8
            # Chip strip moved up to y=4-26 (header is gone) so cells get
            # more vertical room.
            chip_y_top = 4
            chip_y_bot = 26

            def _draw_chip(col, label, is_active, dim=False, accent='green'):
                # accent: 'green' (variant active) or 'yellow' (bypass engaged,
                # matches Nuendo's amber bypass indicator).
                cx = col * cell_w
                if is_active and accent == 'yellow':
                    fill, outline = (120, 95, 0), (220, 180, 0)
                elif is_active:
                    fill, outline = (0, 110, 55), (0, 200, 100)
                elif dim:
                    fill, outline = (35, 35, 35), (60, 60, 60)
                else:
                    fill, outline = (40, 40, 40), (80, 80, 80)
                draw.rectangle([cx + 4, chip_y_top, cx + cell_w - 4, chip_y_bot - 2],
                               fill=fill, outline=outline, width=1)
                text_color = COLOR_TEXT_MAIN if is_active else COLOR_TEXT_DIM
                short = label if len(label) <= 14 else label[:13] + '…'
                bbox = draw.textbbox((0, 0), short, font=FONT_SM)
                tw = bbox[2] - bbox[0]
                draw.text((cx + (cell_w - tw) // 2, chip_y_top + 4),
                          short, font=FONT_SM, fill=text_color)

            # ── Chip strip layout (new upper-row mapping) ──
            #   col 0: module name (Upper 1, inactive label)
            #   col 1: ON/OFF chip (Upper 2)
            #   cols 2-4: variant chips (Upper 3-4-5)
            #   col 7: [Back] label (Upper 8)
            current_variant = slot.plugin_name if (slot and slot.plugin_name) else None

            # Resolve the section/module on-off state once for the page
            if state.cs_page == 'eq':
                # Read EQ Bypass via the DA toggle mirror (DA idx 0 = Bypass,
                # tag 4204). Binding-path state.channel_strip.eq[0x7F] is also
                # populated but the DA path is more reliable since we toggle
                # via DA flip on Upper 2.
                bypass_val_norm = state.da_strip_toggle_values.get(('EQ', 0), 0.0)
                bypassed = bypass_val_norm >= 0.5
                # Cross-check the binding-path state (in case JS hasn't
                # responded yet); fallback to it when DA mirror is unset.
                if ('EQ', 0) not in state.da_strip_toggle_values:
                    eq_dict = state.channel_strip.eq
                    bypass_val  = eq_dict.get(0x7F, {}).get('value', 0)
                    bypass_disp = eq_dict.get(0x7F, {}).get('display', '')
                    bypassed = (bypass_disp == 'On') or (bypass_val >= 0.5)
                is_on_state = not bypassed   # ON when NOT bypassed
            else:
                on_mod_id = page_to_modid.get(state.cs_page)
                on_slot = (state.channel_strip.slots.get(on_mod_id)
                           if on_mod_id is not None else None)
                on_val  = on_slot.params.get(0x00, {}).get('value', 0)   if on_slot else 0
                on_disp = on_slot.params.get(0x00, {}).get('display', '') if on_slot else ''
                is_on_state = (on_disp == 'On') or (on_val >= 0.5)

            if state.cs_page != 'eq':
                # Col 0: module name with section-coloured background pill.
                page_label_full = page_labels.get(state.cs_page, state.cs_page.upper())
                short = (page_label_full if len(page_label_full) <= 13
                         else page_label_full[:12] + '…')
                sect_color = CS_SECTION_COLORS.get(state.cs_page)
                if sect_color:
                    draw.rectangle([4, chip_y_top, cell_w - 4, chip_y_bot - 2],
                                   fill=sect_color, outline=sect_color, width=1)
                    text_col = _text_color_for_bg(sect_color)
                else:
                    text_col = COLOR_TEXT_MAIN
                bbox = draw.textbbox((0, 0), short, font=FONT_SM_BOLD)
                tw = bbox[2] - bbox[0]
                draw.text(((cell_w - tw) // 2, chip_y_top + 4),
                          short, font=FONT_SM_BOLD, fill=text_col)

                # Col 1: "Bypass" chip — amber/lit when bypass is ENGAGED
                # (section NOT active), matching Nuendo's bypass indicator.
                _draw_chip(1, 'Bypass', not is_on_state, accent='yellow')

                # Cols 2-4: variant chips
                for vi, vname in enumerate(variant_names[:3]):
                    _draw_chip(vi + 2, vname, vname == current_variant)

                # Col 7: Back label (no chip background)
                back_lbl = '[Back]'
                bbox = draw.textbbox((0, 0), back_lbl, font=FONT_SM)
                tw = bbox[2] - bbox[0]
                draw.text((7 * cell_w + (cell_w - tw) // 2, chip_y_top + 4),
                          back_lbl, font=FONT_SM, fill=COLOR_TEXT_DIM)
            else:
                # ── EQ thin upper-row label strip (no header on EQ page) ──
                page_label_full = page_labels.get('eq', 'EQ')
                upper_labels = [
                    page_label_full,    # Upper 1: module name (inactive)
                    'Bypass',           # Upper 2: section bypass toggle
                    '', '', '',         # Upper 3-5: no variants for EQ
                    '', '',             # Upper 6-7: unassigned
                    'Back',             # Upper 8
                ]
                # Upper 1 = module name with section colour background
                sect_color = CS_SECTION_COLORS.get('eq')
                if sect_color:
                    draw.rectangle([4, 0, cell_w - 4, 11],
                                   fill=sect_color, outline=sect_color, width=1)
                for ui, lbl in enumerate(upper_labels):
                    if not lbl:
                        continue
                    ux = ui * cell_w
                    if ui == 0 and sect_color:
                        color = _text_color_for_bg(sect_color)
                    elif ui == 1:
                        # Bypass: amber/lit when ENGAGED (section bypassed)
                        color = (240, 200, 0) if not is_on_state else COLOR_TEXT_DIM
                    else:
                        color = COLOR_TEXT_DIM
                    # Module name (Upper 1) in bold to match section banners
                    fnt = FONT_SM_BOLD if ui == 0 else FONT_SM
                    bbox = draw.textbbox((0, 0), lbl, font=fnt)
                    tw = bbox[2] - bbox[0]
                    draw.text((ux + (cell_w - tw) // 2, 0),
                              lbl, font=fnt, fill=color)

            # ── Layout dimensions ──
            # Header: 0..26
            # Chip strip: 28..50
            # Main cells: 52..(SCREEN_HEIGHT - footer_h - 4)
            # Footer: (SCREEN_HEIGHT - footer_h)..(SCREEN_HEIGHT - 4)
            # EQ page: cells are COMPACT (top half of main area) and the
            # EQ curve fills the bottom half.
            # Slimmer footer (was 36) — the ON/OFF text below the pill label is
            # redundant since the pill colour already conveys the state.
            footer_h = 22
            is_eq_page = (state.cs_page == 'eq')
            if is_eq_page:
                # EQ page: thin upper-row label strip at y=0..11, compact cells
                # below, then curve. Footer at the bottom.
                cells_top = 12
                cells_bot = 38
                eq_curve_top = 40
                eq_curve_bot = SCREEN_HEIGHT - footer_h - 4
            else:
                # Chip strip y=4..26, cells y=28..(footer-4)
                cells_top = 28
                cells_bot = SCREEN_HEIGHT - footer_h - 4
            
            # ── Main cells (one per encoder position) ──
            # EQ page uses compact cells (label + value on 2 short lines) to
            # leave room for the EQ curve below.
            compact = is_eq_page
            name_y_off = 2 if compact else 22
            value_y_off = 14 if compact else 50
            value_font = FONT_SM if compact else FONT_MD
            for ci in range(8):
                paramId = layout['encoders'][ci]
                cx = ci * cell_w
                # Cell border (always drawn, dim for empty cells)
                if getattr(state, 'cs_strip_da_active', False):
                    da_names = getattr(state, 'insert_param_names', [])
                    _has_da = bool(da_names[ci]) if ci < len(da_names) else False
                    border_color = (50, 50, 50) if _has_da else (35, 35, 35)
                    badge_color  = COLOR_TEXT_DIM if _has_da else (60, 60, 60)
                else:
                    border_color = (50, 50, 50) if paramId else (35, 35, 35)
                    badge_color  = COLOR_TEXT_DIM if paramId else (60, 60, 60)
                # EQ band selector (Enc 1) gets a distinctive green border.
                if state.cs_page == 'eq' and ci == 0:
                    border_color = (0, 200, 100)
                draw.rectangle([cx + 2, cells_top, cx + cell_w - 2, cells_bot],
                               outline=border_color, width=1)
                # Encoder number badge top-left (skipped on compact cells)
                if not compact:
                    draw.text((cx + 6, cells_top + 4), f"{ci+1}",
                              font=FONT_SM, fill=badge_color)
                # DA encoder override: show names/values from DA when active
                if getattr(state, 'cs_strip_da_active', False):
                    da_names = getattr(state, 'insert_param_names', [])
                    da_vals  = getattr(state, 'insert_param_values', [])
                    name    = da_names[ci] if ci < len(da_names) else ''
                    display = da_vals[ci]  if ci < len(da_vals)  else ''
                    # Binding-path override for specific cells (e.g. EQ page
                    # cells 5-7 reading PreFilter values from mod 0x00).
                    be = layout.get('binding_encoders', {}).get(ci)
                    if be is not None:
                        bm, bp = be
                        if bm == 0x00:
                            pdata = state.channel_strip.prefilter.get(bp, {})
                        elif bm == 0x01:
                            pdata = state.channel_strip.eq.get(bp, {})
                        else:
                            bslot = state.channel_strip.slots.get(bm)
                            pdata = bslot.params.get(bp, {}) if bslot else {}
                        bdisp = pdata.get('display', '')
                        if bdisp:
                            display = bdisp
                    if name:
                        name_short = name if len(name) <= 13 else name[:12] + '…'
                        draw.text((cx + 6, cells_top + name_y_off), name_short,
                                  font=FONT_SM, fill=COLOR_TEXT_DIM)
                    # Band selector cell: draw "1 2 3 4" with selected highlighted
                    if is_eq_page and ci == 0:
                        sel = getattr(state, 'eq_selected_band', 0)
                        bands_str = '1 2 3 4'
                        char_x = cx + 8
                        for bi in range(4):
                            tag = str(bi + 1)
                            color = (0, 220, 120) if bi == sel else COLOR_TEXT_DIM
                            draw.text((char_x, cells_top + value_y_off), tag,
                                      font=value_font, fill=color)
                            bbox = draw.textbbox((0, 0), tag + ' ', font=value_font)
                            char_x += bbox[2] - bbox[0] + 4
                    elif display:
                        disp_short = display if len(display) <= 11 else display[:10] + '…'
                        bbox = draw.textbbox((0, 0), disp_short, font=value_font)
                        tw = bbox[2] - bbox[0]
                        draw.text((cx + (cell_w - tw) // 2, cells_top + value_y_off),
                                  disp_short, font=value_font, fill=COLOR_TEXT_MAIN)
                    continue

                if paramId is None or slot is None:
                    continue
                pdata = slot.params.get(paramId, {})
                name = pdata.get('name', '')
                display = pdata.get('display', '')
                # Param name top of cell
                if name:
                    name_short = name if len(name) <= 13 else name[:12] + '…'
                    draw.text((cx + 6, cells_top + name_y_off), name_short,
                              font=FONT_SM, fill=COLOR_TEXT_DIM)
                # Display value center, larger
                if display:
                    disp_short = display if len(display) <= 11 else display[:10] + '…'
                    bbox = draw.textbbox((0, 0), disp_short, font=value_font)
                    tw = bbox[2] - bbox[0]
                    draw.text((cx + (cell_w - tw) // 2, cells_top + value_y_off),
                              disp_short, font=value_font, fill=COLOR_TEXT_MAIN)

            # ── EQ curve canvas (only on EQ page) ──
            if is_eq_page:
                # Background rectangle
                draw.rectangle([8, eq_curve_top, SCREEN_WIDTH - 8, eq_curve_bot],
                               outline=(40, 40, 40), width=1, fill=(15, 15, 18))
                # Guard the curve computation: a transient bad value (mid-drag
                # feedback, partial state snapshot) must not crash the frame.
                try:
                    eq_data = _collect_eq_data(state)
                    if eq_data is not None:
                        _render_eq_curve(draw, 10, eq_curve_top + 2,
                                         SCREEN_WIDTH - 20,
                                         eq_curve_bot - eq_curve_top - 4,
                                         eq_data)
                except Exception:
                    pass  # skip curve this frame, retry next
            
            # ── Footer (one segment per lower row button) ──
            # Separator line between cells and footer
            sep_y = cells_bot + 2
            draw.line([(0, sep_y), (SCREEN_WIDTH, sep_y)], fill=(40, 40, 40), width=1)
            footer_top = SCREEN_HEIGHT - footer_h
            toggle_labels = layout.get('toggle_labels', {})
            da_toggles = layout.get('da_toggles', {})  # {pos: (label, da_param_idx)}
            binding_toggles = layout.get('binding_toggles', {})  # {pos: (mod_id, param_id, label, invert)}
            # DA values keyed by plugin name (current variant), so custom strip
            # layouts where mod_id ≠ DA slot position still work correctly.
            _current_variant = slot.plugin_name if (slot and slot.plugin_name) else None
            # Reset all positions; renderer will set the ones that have a pill.
            state.cs_footer_pill_states = [None] * 8
            for fi in range(8):
                paramId = layout['toggles'][fi]
                fx = fi * cell_w
                # Pos 7 (universal) → "Edit" button: toggles the Channel
                # Settings window. Lit white when the window is open.
                if fi == 7:
                    eo = bool(getattr(state, 'editor_open', False))
                    state.cs_footer_pill_states[fi] = eo
                    _draw_footer_pill(draw, fx, footer_top, cell_w, footer_h,
                                      'Edit', eo, on_color=(255, 255, 255))
                    continue
                # EQ-specific dynamic Band On pill at footer pos 0
                if state.cs_page == 'eq' and fi == 0:
                    sel = getattr(state, 'eq_selected_band', 0)
                    on_idx = 5 + sel * 6
                    val = state.da_strip_toggle_values.get(('EQ', on_idx), 0.0)
                    is_band_on = val >= 0.5
                    state.cs_footer_pill_states[fi] = is_band_on
                    _draw_footer_pill(draw, fx, footer_top, cell_w, footer_h,
                                      f"B{sel + 1} On", is_band_on)
                    continue
                # Binding-path toggle on a non-default mod_id (e.g. EQ page
                # PreFilter HC/LC/Bypass on the EQ page that points to mod 0x01).
                if fi in binding_toggles:
                    bm, bp, blabel, binvert = binding_toggles[fi]
                    # Resolve store: PreFilter (0x00) and ChannelEQ (0x01) have
                    # their own dicts, strip slots (0x10+) are under .slots.
                    if bm == 0x00:
                        bpdata = state.channel_strip.prefilter.get(bp, {})
                    elif bm == 0x01:
                        bpdata = state.channel_strip.eq.get(bp, {})
                    else:
                        bslot = state.channel_strip.slots.get(bm)
                        bpdata = bslot.params.get(bp, {}) if bslot else {}
                    bdisp = bpdata.get('display', '')
                    bvalue = bpdata.get('value', 0)
                    if bdisp == 'On':
                        is_on_bp = True
                    elif bdisp == 'Off':
                        is_on_bp = False
                    else:
                        is_on_bp = bvalue >= 0.5
                    if binvert:
                        is_on_bp = not is_on_bp
                    state.cs_footer_pill_states[fi] = is_on_bp
                    _draw_footer_pill(draw, fx, footer_top, cell_w, footer_h,
                                      blabel, is_on_bp)
                    continue
                # DA-based toggle (overrides any None paramId at this position)
                if fi in da_toggles and _current_variant:
                    da_label, da_idx = da_toggles[fi]
                    val = state.da_strip_toggle_values.get((_current_variant, da_idx), 0.0)
                    is_on_da = val >= 0.5
                    state.cs_footer_pill_states[fi] = is_on_da
                    _draw_footer_pill(draw, fx, footer_top, cell_w, footer_h,
                                      da_label, is_on_da)
                    continue
                if paramId is None or slot is None:
                    continue
                pdata = slot.params.get(paramId, {})
                # Display label: page layout's override wins over API name, so
                # we can rename Cubase's short/cryptic names to match what the
                # user sees in the plugin GUI.
                name = toggle_labels.get(paramId) or pdata.get('name', '')
                display = pdata.get('display', '')
                # Toggle state: prefer the "On"/"Off" string from SysEx 0x32, but
                # fall back to the numeric value (SysEx 0x31) for binary params
                # where Cubase doesn't fire mOnDisplayValueChange.
                if display == 'On':
                    is_on = True
                elif display == 'Off':
                    is_on = False
                else:
                    is_on = pdata.get('value', 0) >= 0.5
                if name:
                    state.cs_footer_pill_states[fi] = is_on
                    _draw_footer_pill(draw, fx, footer_top, cell_w, footer_h,
                                      name, is_on)
        else:
            # EQ + any future page that doesn't have a layout yet: placeholder.
            overlay = Image.new('RGBA', (SCREEN_WIDTH, SCREEN_HEIGHT),
                                (0, 0, 0, 200))
            img = Image.alpha_composite(img.convert('RGBA'),
                                        overlay).convert('RGB')
            draw = ImageDraw.Draw(img)
            label = page_labels.get(state.cs_page, state.cs_page.upper())
            bbox = draw.textbbox((0, 0), label, font=FONT_LG)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text(((SCREEN_WIDTH - tw) // 2, (SCREEN_HEIGHT - th) // 2 - 20),
                      label, font=FONT_LG, fill=(255, 255, 255))
            hint = "Drill-down page — coming soon. Press [1] above to return."
            bbox = draw.textbbox((0, 0), hint, font=FONT_SM)
            tw = bbox[2] - bbox[0]
            draw.text(((SCREEN_WIDTH - tw) // 2, SCREEN_HEIGHT - 30),
                      hint, font=FONT_SM, fill=(180, 180, 180))
    
    return _to_push2_frame(img)


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
    draw.text((SCREEN_WIDTH // 2 - 110, 100),
              "Load the MIDI Remote script in Nuendo",
              font=FONT_SM, fill=(70, 70, 70))
    
    return _to_push2_frame(img)


def render_disconnect_screen():
    """Displayed when the connection with Nuendo is lost."""
    img = Image.new('RGB', (SCREEN_WIDTH, SCREEN_HEIGHT), color=(25, 10, 10))
    draw = ImageDraw.Draw(img)
    draw.text((SCREEN_WIDTH // 2 - 90, 60),
              "Nuendo connection lost",
              font=FONT_LG, fill=COLOR_WARNING)
    draw.text((SCREEN_WIDTH // 2 - 100, 90),
              "Restart the bridge or reload the script",
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

    if pad_grid and getattr(pad_grid, 'ks_edit', False):
        return _render_ks_edit_screen(pad_grid)

    if state.accent_held:
        return _render_accent_screen(state)
    
    if state.mode == MODE_CR and cr_state:
        return _render_cr_screen(state, cr_state)
    
    if state.mode == MODE_SETUP:
        return _render_setup_screen(state)
    
    if state.mode == MODE_MIDICC:
        return _render_midicc_screen(state)

    if state.mode == MODE_XY:
        return _render_xy_screen(state)

    if state.mode == MODE_BROWSER:
        return _render_browser_screen(state)
    
    if state.mode == MODE_INSERTS:
        return _render_inserts_screen(state)
    
    if state.mode == MODE_SENDS:
        return _render_sends_screen(state)
    
    if state.mode == MODE_DEVICE:
        return _render_device_screen(state)
    
    if state.mode == MODE_CHANNEL_STRIP:
        return _render_channel_strip_screen(state)
    
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
    _draw_bottom_bar(draw, state, cr_state)
    
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


def _render_ks_edit_screen(pad_grid):
    """Display the keyswitch configuration screen (long-press Layout)."""
    from pad_grid import midi_note_name, KS_CHROMATIC, KS_NATURALS, LAYOUT_KS16

    ORANGE = (255, 150, 0)
    ORANGE_DIM = (120, 70, 0)

    img = Image.new('RGB', (SCREEN_WIDTH, SCREEN_HEIGHT), color=(15, 15, 20))
    draw = ImageDraw.Draw(img)

    count = pad_grid.ks_count()
    notes = pad_grid.ks_effective_notes()
    page = pad_grid.ks_edit_page if pad_grid.note_layout == LAYOUT_KS16 else 0
    base = page * 8

    # ── Title + status line ──
    draw.text((8, 2), "KEYSWITCH CONFIG", font=FONT_MD, fill=ORANGE)
    mode_txt = "Chromatic" if pad_grid.ks_mode == KS_CHROMATIC else "Naturals"
    latch_txt = "Latch ON" if pad_grid.ks_latch else "Latch off"
    status = f"{count} keys   {mode_txt}   {latch_txt}"
    if pad_grid.note_layout == LAYOUT_KS16:
        status += f"   Page {page + 1}/2"
    draw.text((SCREEN_WIDTH - 360, 4), status, font=FONT_SM, fill=(150, 150, 170))

    # ── Encoder cells: one per encoder (8), showing the keyswitch note ──
    col_w = SCREEN_WIDTH // 8
    cell_top = 26
    cell_bot = 132
    for c in range(8):
        ks_index = base + c
        x = c * col_w
        if ks_index >= count:
            continue
        note = notes[ks_index]
        is_start = (ks_index == 0)
        is_override = ks_index in pad_grid.ks_overrides

        # cell frame
        draw.rectangle([x + 3, cell_top, x + col_w - 3, cell_bot],
                       outline=(45, 45, 55), width=1)
        # KS number (1-based), with markers
        label = f"KS{ks_index + 1}"
        if is_start:
            label += "*"            # start note
        draw.text((x + 10, cell_top + 4), label, font=FONT_SM,
                  fill=ORANGE if not is_override else (255, 210, 120))
        # note name (big)
        name = midi_note_name(note)
        draw.text((x + 10, cell_top + 30), name, font=FONT_LG_BOLD,
                  fill=(255, 255, 255) if not is_override else (255, 210, 120))
        # markers legend per cell
        if is_start:
            draw.text((x + 10, cell_bot - 22), "start", font=FONT_SM, fill=(110, 110, 130))
        elif is_override:
            draw.text((x + 10, cell_bot - 22), "set", font=FONT_SM, fill=(150, 110, 60))

    # ── Bottom bar: lower-row button labels ──
    draw.rectangle([0, 138, SCREEN_WIDTH, SCREEN_HEIGHT], fill=(22, 22, 28))
    labels = ["Chromatic", "Naturals", "", "Latch", "", "", "Reset", "Done"]
    for i, lbl in enumerate(labels):
        if not lbl:
            continue
        x = i * col_w + 8
        active = ((i == 0 and pad_grid.ks_mode == KS_CHROMATIC) or
                  (i == 1 and pad_grid.ks_mode == KS_NATURALS) or
                  (i == 3 and pad_grid.ks_latch))
        color = ORANGE if active else (130, 130, 145)
        draw.text((x, 144), lbl, font=FONT_SM, fill=color)

    return _to_push2_frame(img)


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
