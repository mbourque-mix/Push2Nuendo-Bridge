"""
push2_controller.py — Push 2 Controller

This module links the Push 2 hardware to the rest of the bridge.

It handles:
- Reading encoders (the 8 large rotary knobs)
- Reading mode buttons (Volume, Pan, Device, Track...)
- Reading navigation buttons (◄ ►)
- LED updates to reflect the active state
- Sending frames to the display

The push2-python library handles all low-level work (USB, protocol).
We simply connect events to the right actions here.
"""

import push2_python
import push2_python.constants as Push2Constants
import threading
import time
from state import (
    AppState, BANK_SIZE,
    MODE_VOLUME, MODE_PAN, MODE_SENDS, MODE_DEVICE, MODE_INSERTS, MODE_TRACK, MODE_OVERVIEW, MODE_CR,
    MODE_SETUP, MODE_MIDICC, MODE_BROWSER, MODE_CHANNEL_STRIP, MODE_XY, XY_TRACK_PARAMS,
    AT_POLY, AT_CHANNEL, AT_OFF,
    VC_LINEAR, VC_LOG, VC_EXP, VC_SCURVE, VC_FIXED,
)
from pad_grid import (
    PadGrid, KS_CHROMATIC, KS_NATURALS,
    LAYOUT_64, LAYOUT_KS8, LAYOUT_KS16, LAYOUT_DRUM,
)
from overview import compute_overview_layout, get_pad_color_for_overview
from repeat import NoteRepeat
from control_room import (
    ControlRoomState, CR_PAGES, CR_PAGE_NAMES,
    CR_PAGE_MAIN, CR_PAGE_PHONES, CR_PAGE_CUE, CR_PAGE_SOURCES
)

# ─────────────────────────────────────────────────────────────────────────────
# PUSH 2 BUTTON MAPPING
#
# These names are the actual names defined by push2-python.
# Full list obtained with:
#   python3 -c "import push2_python.constants as c; print([a for a in dir(c) if a.startswith('BUTTON_')])"
# ─────────────────────────────────────────────────────────────────────────────

# Mode buttons — we use the most logical available buttons
# on the Push 2 for each role:
BTN_MODE_VOLUME  = Push2Constants.BUTTON_MIX        # "Mix"    → mode Volume (Shift+Mix = Track)
BTN_MODE_SENDS   = Push2Constants.BUTTON_CLIP       # "Clip"   → mode Sends (Shift+Clip = Pan)
BTN_MODE_NOTE    = Push2Constants.BUTTON_NOTE       # "Note"   → MIDI note grid
BTN_DEVICE       = Push2Constants.BUTTON_DEVICE     # "Device" → mode Device (Quick Controls)
BTN_MODE_INSERTS = Push2Constants.BUTTON_BROWSE     # "Browse" → mode Inserts
BTN_MODE_OVERVIEW = Push2Constants.BUTTON_SESSION   # "Session" → mode Overview

# Bank navigation
BTN_LEFT         = Push2Constants.BUTTON_LEFT       # ◄ left arrow
BTN_RIGHT        = Push2Constants.BUTTON_RIGHT      # ► right arrow
BTN_PAGE_LEFT    = getattr(Push2Constants, 'BUTTON_PAGE_LEFT', 'Page Left')
BTN_PAGE_RIGHT   = getattr(Push2Constants, 'BUTTON_PAGE_RIGHT', 'Page Right')

# Modifier
BTN_SHIFT        = Push2Constants.BUTTON_SHIFT      # Shift

# Undo / Redo
BTN_UNDO         = Push2Constants.BUTTON_UNDO if hasattr(Push2Constants, 'BUTTON_UNDO') else None

# Delete
BTN_DELETE       = getattr(Push2Constants, 'BUTTON_DELETE', 'Delete')

# Quick Mute / Solo
BTN_MUTE         = Push2Constants.BUTTON_MUTE
BTN_SOLO         = Push2Constants.BUTTON_SOLO

# Rescan button (7th lower row button)
BTN_RESCAN       = Push2Constants.BUTTON_LOWER_ROW_7

# Lower row buttons (for Mute/Solo/Monitor/Rec)
BUTTONS_LOWER_ROW = [
    Push2Constants.BUTTON_LOWER_ROW_1,
    Push2Constants.BUTTON_LOWER_ROW_2,
    Push2Constants.BUTTON_LOWER_ROW_3,
    Push2Constants.BUTTON_LOWER_ROW_4,
    Push2Constants.BUTTON_LOWER_ROW_5,
    Push2Constants.BUTTON_LOWER_ROW_6,
    Push2Constants.BUTTON_LOWER_ROW_7,
    Push2Constants.BUTTON_LOWER_ROW_8,
]

# Buttons to change the lower row mode (Monitor / Rec Arm)
# CC 60 and CC 61 on the Push 2
BTN_MONITOR_MODE = Push2Constants.BUTTON_LOWER_ROW_8  # 8th button = placeholder
# Use the actual button names from push2-python
# CC60 = "Stop Clip" (in Ableton), CC61 = non-standard
# Use the physical buttons named in push2-python instead

# Lower row modes
LOWER_MODE_MUTE    = "mute"
LOWER_MODE_SOLO    = "solo"
LOWER_MODE_MONITOR = "monitor"
LOWER_MODE_REC     = "rec"

# Transport
BTN_PLAY          = Push2Constants.BUTTON_PLAY
BTN_STOP          = Push2Constants.BUTTON_STOP  if hasattr(Push2Constants, 'BUTTON_STOP') else None
BTN_RECORD        = Push2Constants.BUTTON_RECORD
BTN_AUTOMATE      = Push2Constants.BUTTON_AUTOMATE if hasattr(Push2Constants, 'BUTTON_AUTOMATE') else None

# Up/Down arrows for sends
BTN_UP            = Push2Constants.BUTTON_UP if hasattr(Push2Constants, 'BUTTON_UP') else None
BTN_DOWN          = Push2Constants.BUTTON_DOWN if hasattr(Push2Constants, 'BUTTON_DOWN') else None

# Scale
BTN_SCALE         = Push2Constants.BUTTON_SCALE if hasattr(Push2Constants, 'BUTTON_SCALE') else None
BTN_OCTAVE_UP     = Push2Constants.BUTTON_OCTAVE_UP if hasattr(Push2Constants, 'BUTTON_OCTAVE_UP') else None
BTN_OCTAVE_DOWN   = Push2Constants.BUTTON_OCTAVE_DOWN if hasattr(Push2Constants, 'BUTTON_OCTAVE_DOWN') else None

# Layout & Metronome
BTN_LAYOUT        = getattr(Push2Constants, 'BUTTON_LAYOUT', getattr(Push2Constants, 'BUTTON_USER', None))
BTN_METRONOME     = Push2Constants.BUTTON_METRONOME if hasattr(Push2Constants, 'BUTTON_METRONOME') else None

# Repeat
BTN_REPEAT        = getattr(Push2Constants, 'BUTTON_REPEAT', 'Repeat')

# Accent
BTN_ACCENT        = getattr(Push2Constants, 'BUTTON_ACCENT', 'Accent')

# Fixed Length (Cycle/Loop)
BTN_FIXED_LENGTH  = getattr(Push2Constants, 'BUTTON_FIXED_LENGTH', 'Fixed Length')

# Add Track
BTN_ADD_TRACK     = getattr(Push2Constants, 'BUTTON_ADD_TRACK', 'Add Track')
BTN_NEW           = getattr(Push2Constants, 'BUTTON_NEW', 'New')

# Duplicate
BTN_DUPLICATE     = getattr(Push2Constants, 'BUTTON_DUPLICATE', 'Duplicate')

# User (for Hold + Master Encoder = Phones)
BTN_USER          = getattr(Push2Constants, 'BUTTON_USER', 'User')

# Select (modifier: Hold + Master Encoder = CR Phones level)
BTN_SELECT        = getattr(Push2Constants, 'BUTTON_SELECT', 'Select')

# Setup button (CC 30, monochrome)
BTN_SETUP         = getattr(Push2Constants, 'BUTTON_SETUP', 'Setup')

# Add Device button (monochrome, for Plugin Browser)
BTN_ADD_DEVICE    = getattr(Push2Constants, 'BUTTON_ADD_DEVICE', 'Add Device')

# "Select" buttons above encoders (upper row)
BUTTONS_UPPER_ROW = [
    Push2Constants.BUTTON_UPPER_ROW_1,
    Push2Constants.BUTTON_UPPER_ROW_2,
    Push2Constants.BUTTON_UPPER_ROW_3,
    Push2Constants.BUTTON_UPPER_ROW_4,
    Push2Constants.BUTTON_UPPER_ROW_5,
    Push2Constants.BUTTON_UPPER_ROW_6,
    Push2Constants.BUTTON_UPPER_ROW_7,
    Push2Constants.BUTTON_UPPER_ROW_8,
]

# Names of the 8 track encoders (ENCODER_TRACK1_ENCODER to ENCODER_TRACK8_ENCODER)
TRACK_ENCODERS = [
    Push2Constants.ENCODER_TRACK1_ENCODER,
    Push2Constants.ENCODER_TRACK2_ENCODER,
    Push2Constants.ENCODER_TRACK3_ENCODER,
    Push2Constants.ENCODER_TRACK4_ENCODER,
    Push2Constants.ENCODER_TRACK5_ENCODER,
    Push2Constants.ENCODER_TRACK6_ENCODER,
    Push2Constants.ENCODER_TRACK7_ENCODER,
    Push2Constants.ENCODER_TRACK8_ENCODER,
]

# ─────────────────────────────────────────────────────────────────────────────
# LED COLORS (Push 2 RGB palette)
#
# Push 2 uses a palette system 1-127.
# Here are some useful colors (default palette values).
# ─────────────────────────────────────────────────────────────────────────────

LED_OFF      = 0    # Off
LED_DIM_GREY = 1    # Dim grey
LED_WHITE    = 3    # White (Push 2 palette)
LED_RED      = 127  # Red
LED_ORANGE   = 9    # Orange
LED_YELLOW   = 13   # Yellow
LED_GREEN    = 26   # Green
LED_CYAN     = 37   # Cyan
LED_BLUE     = 48   # Blue
LED_PURPLE   = 57   # Purple

# Custom palette indices for buttons (initialized at startup)
# WARNING: do not use 0, 21, 37, 45, 122, 124 (reserved for pads)
BTN_DIM      = 110  # Dark grey (inactive buttons)
BTN_WHITE    = 111  # Bright white (selected buttons)
BTN_YELLOW   = 112  # Yellow (Mute)
BTN_BLUE     = 113  # Blue (Solo)
BTN_ORANGE   = 114  # Orange (Monitor)
BTN_RED      = 115  # Red (Rec)

# Colors by mode
MODE_COLORS = {
    MODE_VOLUME:  LED_GREEN,
    MODE_PAN:     LED_ORANGE,
    MODE_SENDS:   LED_PURPLE,
    MODE_DEVICE:  LED_CYAN,
    MODE_INSERTS: LED_BLUE,
    MODE_TRACK:   LED_WHITE,
    MODE_OVERVIEW: LED_PURPLE,
    MODE_BROWSER: LED_BLUE,
    MODE_CHANNEL_STRIP: LED_WHITE,  # Mix button toggled into Channel Strip view
}

# ─────────────────────────────────────────────────────────────────────────────
# Encoder sensitivity
#
# Push 2 encoders send relative deltas (+1 or -1 per notch).
# We multiply by these values to adjust the rate of change.
# ─────────────────────────────────────────────────────────────────────────────

ENCODER_SENSITIVITY_NORMAL = 0.008   # Normal speed (1 notch = 0.8%)
ENCODER_SENSITIVITY_FINE   = 0.001   # Fine speed with Shift (1 notch = 0.1%)


# ── Channel Strip variant routing (Axe B Step 2A) ──
# Each slot's bank zone exposes different params per loaded plugin variant.
# To route encoders and lower-row toggles correctly per variant, we look up
# tables keyed by (cs_page, variant_name).
#
# variant_name = None is the "primary" variant — used as a fallback when the
# loaded plugin has no entry, or when no plugin is loaded yet.
#
# JS sub-page bindings mirror these maps. See Ableton_Push2.js (search for
# bindModuleEncoders/bindModuleToggles for each variant).

_CS_PAGE_TO_MOD_ID = {
    'gate':    0x10,
    'comp':    0x11,
    'tools':   0x12,
    'sat':     0x13,
    'limiter': 0x14,
}

# Encoder index (0..7) → paramId for each (cs_page, variant)
_VARIANT_ENCODER_MAPS = {
    # Gate (single variant)
    ('gate', None):                   [0x01, 0x02, 0x03, 0x04, 0x07, 0x08, None, None],
    ('gate', 'Noise Gate'):           [0x01, 0x02, 0x03, 0x04, 0x07, 0x08, None, None],
    
    # Compressor variants
    ('comp', None):                   [0x01, 0x02, 0x03, 0x04, 0x06, None, None, None],
    ('comp', 'Standard Compressor'):  [0x01, 0x02, 0x03, 0x04, 0x06, None, None, None],
    ('comp', 'Tube Compressor'):      [0x01, 0x02, 0x03, 0x04, 0x06, 0x07, None, None],
    ('comp', 'VintageCompressor'):    [0x01, 0x02, 0x03, 0x05, None, None, None, None],
    
    # Tools variants
    ('tools', None):                  [0x01, 0x03, 0x04, 0x05, 0x06, None, None, None],
    ('tools', 'DeEsser'):             [0x01, 0x03, 0x04, 0x05, 0x06, None, None, None],
    ('tools', 'EnvelopeShaper'):      [0x01, 0x02, 0x04, 0x06, None, None, None, None],
    
    # Saturator variants
    ('sat', None):                    [0x01, 0x02, 0x03, 0x04, 0x07, None, None, None],
    ('sat', 'Magneto II'):            [0x01, 0x02, 0x03, 0x04, 0x07, None, None, None],
    ('sat', 'Tape Saturation'):       [0x01, 0x02, 0x03, 0x07, None, None, None, None],
    ('sat', 'Tube Saturation'):       [0x01, 0x02, 0x03, 0x06, None, None, None, None],
    
    # Limiter variants
    ('limiter', None):                [0x01, 0x04, None, None, None, None, None, None],
    ('limiter', 'Brickwall Limiter'): [0x01, 0x04, None, None, None, None, None, None],
    ('limiter', 'Maximizer'):         [0x01, 0x03, 0x06, None, None, None, None, None],
    ('limiter', 'Standard Limiter'):  [0x01, 0x04, 0x07, None, None, None, None, None],
}

# Active toggle positions (lower row indices) for each (cs_page, variant).
# The actual paramId at each position is wired by the JS sub-page bindings;
# Python just needs to know which positions get a drilldown_toggle note.
_VARIANT_ACTIVE_TOGGLES = {
    ('gate', None):                   {0, 1, 2},
    ('gate', 'Noise Gate'):           {0, 1, 2},
    
    ('comp', None):                   {0, 1},
    ('comp', 'Standard Compressor'):  {0, 1},
    ('comp', 'Tube Compressor'):      {0},
    ('comp', 'VintageCompressor'):    {0, 1},
    
    ('tools', None):                  {0, 1},
    ('tools', 'DeEsser'):             {0, 1},
    ('tools', 'EnvelopeShaper'):      set(),
    
    ('sat', None):                    {0, 1},
    ('sat', 'Magneto II'):            {0, 1},
    ('sat', 'Tape Saturation'):       {0, 1},
    ('sat', 'Tube Saturation'):       set(),  # Tube has no toggle params
    
    ('limiter', None):                {0},
    ('limiter', 'Brickwall Limiter'): {0},
    ('limiter', 'Maximizer'):         set(),
    ('limiter', 'Standard Limiter'):  {0},
}

# DA encoder setup for CS sub-page variants with extended parameters (not in bank zone).
# Maps (cs_page, variant) → (da_slot_idx, [8 param_indices])
# da_slot_idx: 16-20 (DA_STRIP_SLOT_OFFSET + strip slot 0..4)
# param_indices: index into the DA-enumerated param list (-1 = unused position)
# Variant lists for strip slot switching via DA Plugin Manager.
# Maps cs_page → (da_slot, ordered list of variant names).
# The ORDER must mirror Ableton_Push2.js STRIP_VARIANTS exactly — the index is
# the wire protocol value sent to JS.
_VARIANT_SWITCH_OPTIONS = {
    'gate':    (16, ['Noise Gate']),
    'comp':    (17, ['Standard Compressor', 'Tube Compressor', 'VintageCompressor']),
    'tools':   (18, ['DeEsser', 'EnvelopeShaper']),
    'sat':     (19, ['Magneto II', 'Tape Saturation', 'Tube Saturation']),
    'limiter': (20, ['Brickwall Limiter', 'Maximizer', 'Standard Limiter']),
}


# Footer toggle positions that use DA flip instead of the bank-zone binding path.
# Use this for params where setTypeToggle fails — e.g. VintageCompressor Att-Mode
# triggers a Cubase bank-zone refresh that invalidates the toggle binding.
# Maps (cs_page, variant, lower_row_idx) → (da_slot, da_param_idx)
_VARIANT_DA_TOGGLES = {
    ('comp', 'VintageCompressor', 0): (17, 1),  # Punch (Att-Mode) — DA tag 4218
    # DeEsser Diff (DA idx 6, tag 4244) on footer position 2.
    # Listed under both 'tools' (standard layout) and 'sat' (custom layouts where
    # DeEsser sits at the saturator slot position).
    ('tools', 'DeEsser', 2): (18, 6),
    ('sat',   'DeEsser', 2): (19, 6),
    # Standard Compressor: SoftKnee (idx=8) at footer position 2.
    ('comp', 'Standard Compressor', 2): (17, 8),
    # Magneto II: Dual (idx=1) and OverSampling (idx=5) are binary extended params.
    # Listed for both 'sat' (standard) and 'limiter' (custom layouts).
    ('sat',     'Magneto II', 2): (19, 1),  # Dual
    ('sat',     'Magneto II', 3): (19, 5),  # OverSampling
    ('limiter', 'Magneto II', 2): (20, 1),
    ('limiter', 'Magneto II', 3): (20, 5),
    # Tape Saturation: OverSampling (idx=6) only extended param.
    ('sat',     'Tape Saturation', 2): (19, 6),
    ('limiter', 'Tape Saturation', 2): (20, 6),
    # Brickwall Limiter: Link (idx=4) and Oversample (idx=5) are binary extended.
    ('limiter', 'Brickwall Limiter', 1): (20, 4),  # Link at footer pos 1
    ('limiter', 'Brickwall Limiter', 2): (20, 5),  # Oversample at footer pos 2
    # Maximizer: SoftClipper (idx=0) and Modern Mode (idx=2) binary extended.
    ('limiter', 'Maximizer', 0): (20, 0),  # SoftClipper
    ('limiter', 'Maximizer', 1): (20, 2),  # Modern Mode

    # EQ Band On is handled dynamically in the lower-row handler (acts on the
    # currently selected band) — no fixed entries here.
}


_VARIANT_DA_ENC_SETUP = {
    # Maps (cs_page, variant) → list of 8 DA param indices (use -1 for unused).
    # The DA slot is resolved at runtime from cs_page via _CS_PAGE_TO_MOD_ID.
    # Use this to surface params that are NOT exposed by the bank zone, or to
    # benefit from DA's reliable display-value feedback.

    # Noise Gate: bank zone has 6 encoders; Hold + Analysis are extended params
    # only reachable via DA. Bypass/SCOn/SCMonitor remain footer toggles via
    # the binding path.
    ('gate', 'Noise Gate'): [0, 1, 2, 3, 12, 13, 5, 6],
    # enc: Threshold, Range, Attack, Release, FilterFreq, Q-Factor, Hold, Analysis

    # VintageCompressor: Ratio (idx=5) and Mix (idx=6) are absent from bank zone.
    # Attack Mode (idx=1) and Auto Release (idx=4) are binary — kept as footer toggles.
    ('comp', 'VintageCompressor'): [0, 2, 3, 7, 5, 6, -1, -1],
    # enc: InputGain, AttackTime, ReleaseTime, OutputGain, Ratio, Mix, –, –

    # Standard Compressor: DryMix (idx=11, parallel comp) and Hold (idx=5)
    # are the most useful extended params beyond the bank zone.
    ('comp', 'Standard Compressor'): [0, 1, 2, 3, 6, 11, 5, -1],
    # enc: Threshold, Ratio, Attack, Release, MakeUp, DryMix, Hold, –

    # Tube Compressor: Character (idx=1) gives the tube color knob, High Ratio
    # (idx=3) is the dual-band high-frequency ratio. Both absent from bank zone.
    ('comp', 'Tube Compressor'): [0, 1, 2, 7, 4, 5, 8, 3],
    # enc: Drive, Character, InputGain, OutputGain, Attack, Release, Mix, HighRatio

    # Maximizer: Release + Recover (Modern-mode timing) absent from bank zone.
    ('limiter', 'Maximizer'): [1, 6, 5, 3, 4, -1, -1, -1],
    # enc: Optimize, Output, Mix, Release, Recover, –, –, –

    # Channel EQ: EQ-Eight style with band selector. The actual indices are
    # computed at runtime by _eq_da_encoder_indices(selected_band) because they
    # depend on which band is selected. This sentinel just signals "EQ has DA
    # encoder setup" so other lookup paths work.
    # enc layout: [Sel(-1), Type, Freq, Q, Gain, HC(-1), LC(-1), PreGain(-1)]
    ('eq', 'EQ'): [-1, -1, -1, -1, -1, -1, -1, -1],

    # Tube Saturation: OverSampling (idx=4) is the only param beyond the bank zone.
    # Listed under both 'sat' (standard layout) and 'limiter' (some user setups
    # place Tube Saturation at the Limiter slot position).
    ('sat',     'Tube Saturation'): [0, 1, 2, 3, 4, -1, -1, -1],
    ('limiter', 'Tube Saturation'): [0, 1, 2, 3, 4, -1, -1, -1],
    # enc: Drive, LF, HF, Output, OverSampling, –, –, –

    # DeEsser: SCFreq (idx=9) and SCQ (idx=10) are side-chain filter controls
    # not exposed in the bank zone. Diff is added as a footer toggle below.
    # Listed under both 'tools' (standard) and 'sat' (some custom strip layouts
    # place DeEsser at the Saturator slot position).
    ('tools', 'DeEsser'): [1, 0, 2, 3, 4, -1, 9, 10],
    ('sat',   'DeEsser'): [1, 0, 2, 3, 4, -1, 9, 10],
    # enc: Threshold, Reduction, Release, LowFreq, HighFreq, –, SCFreq, SCQ
}


class Push2Controller:
    """
    Push 2 Controller.
    
    Usage :
        controller = Push2Controller(state, nuendo_link, on_frame_needed)
        controller.start()
        ...
        controller.stop()
    """

    def __init__(self, state: AppState, nuendo_link, on_encoder_moved=None):
        """
        state          : shared application state
        nuendo_link    : NuendoLink instance (to send changes)
        on_encoder_moved : optional callback for testing
        """
        self.state           = state
        self.nuendo_link     = nuendo_link
        self.on_encoder_moved = on_encoder_moved
        
        self.push            = None
        self._running        = False
        self._display_thread = None
        self.pad_grid        = PadGrid()
        self.note_repeat     = NoteRepeat()
        self.cr_state        = ControlRoomState()
        self._insert_scan_version = 0
        self._upper_row_press_time = {}  # {button_name: timestamp}
        self._upper_row_last_press = {}  # {button_name: timestamp} for double press detection
        self._lower_row_press_time = {}  # {button_name: timestamp}
        self._lower_row_handled = {}     # {button_name: bool}
        self._lower_row_press_id = {}    # {button_name: int} — incremented each press to cancel stale timers

        # Layout button long-press (keyswitch config) + keyswitch latch tracking
        self._layout_press_active = False  # True while a non-shift Layout press is held
        self._layout_long_fired = False    # True once the long-press action fired
        self._layout_press_id = 0          # generation counter to cancel stale timers
        self._ks_held_note = None          # MIDI note currently sounding from the KS section (mono)
        self._ks_held_ksi = None           # KS index currently sounding, or None

        # XY pad (MODE_XY): pressed-pad pressures + smoothed centroid reference
        self._xy_pressures = {}            # {(row, col): pressure} for currently-touched pads
        self._xy_centroid = None           # last smoothed (cx, cy) centroid, or None when lifted
        self._xy_last_sent = (None, None)  # last integer (x, y) CC values sent

        # Callback for initial scan when Nuendo connects
        self.nuendo_link._on_connected_callback = lambda: self._initial_bank_refresh()
        
        # Callback for auto bank switch
        self.nuendo_link._on_bank_switch_needed = lambda new_bank: self._auto_switch_bank(new_bank)
        
        # Callback for touchstrip LEDs in volume mode
        self.nuendo_link._touchstrip_led_callback = lambda val: self._update_touchstrip_leds(val)
        
        # Callback for LED update when selection changes
        self.nuendo_link._on_selection_changed = lambda: self._update_all_leds()

        # Always-on callback so strip DA param completions can apply encoder setup
        self.nuendo_link._on_da_params_ready = self._on_da_params_ready
        # Add Device on a non-instrument track falls back to the insert browser
        self.nuendo_link._on_browser_no_instrument = self._browser_fallback_to_inserts

    # ─────────────────────────────────────────
    # Start / stop
    # ─────────────────────────────────────────

    def start(self):
        """
        Initialize the Push 2 connection and start threads.
        Returns True if successful.
        """
        try:
            self.push = push2_python.Push2(use_user_midi_port=False)
            print("  ✓ Push 2 found (USB)")
        except Exception as e:
            print(f"  ✗ Push 2 not found : {e}")
            print("    → Check that Push 2 is connected via USB")
            print("    → Check that libusb is installed")
            print("    → Check that Ableton Live is not running")
            return False

        try:
            self.push.configure_midi_out()
        except Exception as e:
            print(f"  ⚠ MIDI OUT first attempt : {e}")

        for attempt in range(30):
            if self.push.midi_is_configured():
                break
            time.sleep(0.1)
            try:
                if self.push.midi_in_port is None:
                    self.push.configure_midi_in()
                if self.push.midi_out_port is None:
                    self.push.configure_midi_out()
            except Exception:
                pass

        if not self.push.midi_is_configured():
            print("  ✗ MIDI Push 2 not found")
            return False

        print("  ✓ Push 2 MIDI configured")

        self._register_callbacks()
        self._update_all_leds()
        self._update_pad_colors()
        self._configure_touchstrip_mode()
        self._configure_aftertouch()
        self._setup_button_palette()
        self._load_plugin_mappings()
        
        # Register callback for playback notes
        self.nuendo_link._note_display_callback = self._on_playback_note
        self.nuendo_link._cr_state = self.cr_state
        self._playback_notes = set()  # Currently playing notes

        self._running = True
        self._display_thread = threading.Thread(
            target=self._display_loop, daemon=True
        )
        self._display_thread.start()

        return True

    def stop(self):
        """Cleanly stop the controller."""
        self._running = False
        if self.push:
            try:
                self._restore_default_palette()
                for btn in [BTN_MODE_VOLUME, BTN_MODE_SENDS, BTN_MODE_NOTE,
                            BTN_DEVICE, BTN_MODE_INSERTS, BTN_MODE_OVERVIEW, BTN_LEFT, BTN_RIGHT]:
                    self.push.buttons.set_button_color(btn, LED_OFF)
            except Exception:
                pass

    # ─────────────────────────────────────────
    # Callback registration
    # ─────────────────────────────────────────

    def _register_callbacks(self):
        """
        Connect response functions to Push 2 events.

        In push2-python, callbacks are declared with decorators
        at the MODULE level (push2_python.on_encoder_rotated), not on the object.
        The function always receives `push` as first argument.
        """
        # ── Encoders ──
        @push2_python.on_encoder_rotated()
        def on_encoder(push, encoder_name, increment):
            self._handle_encoder(encoder_name, increment)

        # ── Encoder touched ──
        @push2_python.on_encoder_touched()
        def on_encoder_touched(push, encoder_name):
            self._handle_encoder_touch(encoder_name)

        # ── Button pressed ──
        @push2_python.on_button_pressed()
        def on_button_pressed(push, button_name):
            self._handle_button_press(button_name)

        # ── Button released ──
        @push2_python.on_button_released()
        def on_button_released(push, button_name):
            self._handle_button_release(button_name)

        # ── Pad pressed ──
        @push2_python.on_pad_pressed()
        def on_pad_pressed(push, pad_n, pad_ij, velocity):
            self._handle_pad_press(pad_n, pad_ij, velocity)

        # ── Pad released ──
        @push2_python.on_pad_released()
        def on_pad_released(push, pad_n, pad_ij, velocity):
            self._handle_pad_release(pad_n, pad_ij, velocity)

        # ── Pad aftertouch ──
        @push2_python.on_pad_aftertouch()
        def on_pad_aftertouch(push, pad_n, pad_ij, velocity):
            self._handle_pad_aftertouch(pad_n, pad_ij, velocity)

        # ── Touchstrip ──
        @push2_python.on_touchstrip()
        def on_touchstrip(push, value):
            self._handle_touchstrip(value)

    # ─────────────────────────────────────────
    # Encoder handling
    # ─────────────────────────────────────────

    def _handle_encoder(self, encoder_name, increment):
        """
        Called when the user rotates an encoder.

        encoder_name : ex. 'ENCODER_TRACK1_ENCODER', 'ENCODER_TRACK2_ENCODER'...
        increment    : +1 (clockwise) or -1 (counter-clockwise), can be larger if turned fast
        """
        # Find the index 0-7 from the encoder name
        if encoder_name not in TRACK_ENCODERS:
            if 'swing' in encoder_name.lower():
                # Swing Encoder (top left) = AI Knob → CC 2 (was CC 64 ≤ 1.0.5,
                # which collided with the Send-Enable button for track 5 and
                # toggled Send 1 on/off whenever the encoder was turned).
                if increment > 0:
                    midi_val = min(63, abs(increment))
                else:
                    midi_val = 64 + min(63, abs(increment))
                self.nuendo_link.send_cc(2, midi_val)
            elif 'tempo' in encoder_name.lower():
                # Tempo Encoder (CC 14) = Note Repeat BPM when active
                if self.note_repeat.enabled:
                    self.note_repeat.tempo += increment * 1.0
                    self.note_repeat.tempo = max(40.0, min(300.0, self.note_repeat.tempo))
                    self._sync_repeat_state()
            elif 'master' in encoder_name.lower():
                # Master Encoder (top right) controls CR Main or Phones volume.
                # Default target is Main (or Phones if inverted in Setup); holding
                # User/Select swaps to the other. want_phones = default XOR modifier.
                if increment > 0:
                    midi_val = min(63, abs(increment))
                else:
                    midi_val = 64 + min(63, abs(increment))
                modifier = self.state.user_held or getattr(self.state, 'select_held', False)
                phones_default = getattr(self.state, 'cr_phones_default', False)
                want_phones = (phones_default != modifier)
                if want_phones:
                    self.nuendo_link.send_cc(77, midi_val)  # Phones level
                else:
                    self.nuendo_link.send_cc(79, midi_val)  # Main level
            return
        
        encoder_index = TRACK_ENCODERS.index(encoder_name)

        # Keyswitch config screen: encoders edit the keyswitch notes
        if self.pad_grid.ks_edit:
            self._handle_ks_edit_encoder(encoder_index, increment)
            return

        # When Accent is held, the first encoder adjusts velocity
        if self.state.accent_held:
            if encoder_index == 0:
                self.state.accent_velocity = max(1, min(127, self.state.accent_velocity + increment))
                # If Fixed curve is active, re-apply it with the new velocity
                if self.state.velocity_curve == VC_FIXED:
                    self._apply_velocity_curve()
            return
        
        # Setup mode: encoder 5 (index 4) adjusts fixed velocity on Vel Curve page
        if self.state.mode == MODE_SETUP and self.state.setup_page == 1:
            if encoder_index == 4:  # 5th encoder, above "Fixed" button
                self.state.accent_velocity = max(1, min(127, self.state.accent_velocity + increment))
                if self.state.velocity_curve == VC_FIXED:
                    self._apply_velocity_curve()
            return
        
        # MIDI CC mode: encoders adjust CC value or CC number
        if self.state.mode == MODE_MIDICC:
            if self.state.cc_edit_mode:
                # Edit mode: encoder changes CC number
                cc = self.state.cc_numbers[encoder_index]
                cc = max(0, min(127, cc + increment))
                self.state.cc_numbers[encoder_index] = cc
            else:
                # Normal mode: encoder changes CC value (sent immediately)
                old_val = self.state.cc_values[encoder_index]
                new_val = max(0, min(127, old_val + increment))
                self.state.cc_values[encoder_index] = new_val
                self.nuendo_link.send_midi_cc_to_notes(
                    self.state.cc_numbers[encoder_index], new_val)
            return
        
        # XY pad mode: Enc1/2 pick the X/Y item (within its category), Enc3/4 = feel
        if self.state.mode == MODE_XY:
            st = self.state
            if encoder_index == 0:                 # Enc1 = X param
                if st.xy_cat_x == 'cc':
                    st.xy_cc_x = max(0, min(127, st.xy_cc_x + increment))
                else:
                    st.xy_track_param_x = max(0, min(len(XY_TRACK_PARAMS) - 1,
                                                     st.xy_track_param_x + increment))
            elif encoder_index == 1:               # Enc2 = Y param
                if st.xy_cat_y == 'cc':
                    st.xy_cc_y = max(0, min(127, st.xy_cc_y + increment))
                else:
                    st.xy_track_param_y = max(0, min(len(XY_TRACK_PARAMS) - 1,
                                                     st.xy_track_param_y + increment))
            elif encoder_index == 3:               # Enc4 = Sensitivity
                st.xy_sensitivity = max(0.1, min(4.0, st.xy_sensitivity + increment * 0.05))
            elif encoder_index == 4:               # Enc5 = Smooth
                st.xy_smooth = max(0.0, min(0.9, st.xy_smooth + increment * 0.05))
            return

        # Control Room mode: redirect encoders to CR CCs
        if self.state.mode == MODE_CR:
            page_def = CR_PAGES.get(self.cr_state.page, {})
            encoders = page_def.get('encoders', [])
            if encoder_index < len(encoders) and encoders[encoder_index] is not None:
                _, cc, _, _ = encoders[encoder_index]
                if increment > 0:
                    midi_val = min(63, abs(increment))
                else:
                    midi_val = 64 + min(63, abs(increment))
                self.nuendo_link.send_cc_ch6(cc, midi_val)
            return
        
        # Sensitivity based on Shift
        sensitivity = (ENCODER_SENSITIVITY_FINE if self.state.shift_held
                       else ENCODER_SENSITIVITY_NORMAL)
        
        # Delta = how much to change the value (between -1.0 and +1.0)
        delta = increment * sensitivity
        
        # Get the current value
        current_val = self.state.get_encoder_value_for_mode(encoder_index)
        
        # Calculate the new value (clamped between 0.0 and 1.0)
        new_val = max(0.0, min(1.0, current_val + delta))
        
        # Update state AND send to Nuendo
        state = self.state
        mode  = state.mode
        
        abs_track_index = state.bank_offset + encoder_index
        
        if mode == MODE_VOLUME:
            if abs_track_index < len(state.tracks):
                state.tracks[abs_track_index].volume = new_val
                state.tracks[abs_track_index].volume_db = _to_db(new_val)
                # Protect against feedback glitch for 200ms
                state.tracks[abs_track_index]._vol_touched_until = time.time() + 0.2
            self.nuendo_link.send_volume_change(encoder_index, new_val)
        
        elif mode == MODE_PAN:
            # Convert 0.0-1.0 to -1.0 to +1.0 for pan
            pan_val = (new_val * 2.0) - 1.0
            if abs_track_index < len(state.tracks):
                state.tracks[abs_track_index].pan = pan_val
            self.nuendo_link.send_pan_change(encoder_index, pan_val)
        
        elif mode == MODE_SENDS:
            # Send CC on channel 3 for selected track send levels
            if increment > 0:
                midi_val = min(63, abs(increment))
            else:
                midi_val = 64 + min(63, abs(increment))
            self.nuendo_link.send_cc_ch3(20 + encoder_index, midi_val)
            return  # Feedback comes from JS via SysEx 0x19
        
        elif mode == MODE_CHANNEL_STRIP:
            # Channel Strip encoder routing depends on the current sub-page
            # AND the loaded plugin variant for multi-variant slots.
            #
            # Overview: encoder 8 (idx 7) = PreGain delta
            # Variant slots: each variant has its own encoder→paramId map
            # (matches JS sub-page bindings). Look up via (cs_page, variant).
            cs_page = getattr(state, 'cs_page', 'overview')
            if cs_page == 'overview':
                if encoder_index == 7:
                    self.nuendo_link.send_strip_param_delta(0x00, 0x00, increment)
                return

            # EQ page Enc 6/7/8 → PreFilter LC Freq / HC Freq / PreGain (binding path)
            if cs_page == 'eq':
                if encoder_index == 5:
                    self.nuendo_link.send_strip_param_delta(0x00, 0x05, increment)  # LC Freq
                    return
                if encoder_index == 6:
                    self.nuendo_link.send_strip_param_delta(0x00, 0x02, increment)  # HC Freq
                    return
                if encoder_index == 7:
                    self.nuendo_link.send_strip_param_delta(0x00, 0x00, increment)  # PreGain
                    return

            # EQ band selector (Enc 1): no MIDI — change internal selection,
            # re-arm DA encoders so Enc 2-5 control the new band's params.
            # Accumulate raw encoder ticks (Push 2 sends many per turn) and only
            # advance one band per ENC_BAND_STEP ticks for a controllable feel.
            if cs_page == 'eq' and encoder_index == 0:
                ENC_BAND_STEP = 12
                accum = getattr(state, '_eq_band_accum', 0) + increment
                steps = int(accum / ENC_BAND_STEP) if accum >= 0 else -int(-accum / ENC_BAND_STEP)
                if steps != 0:
                    new_band = max(0, min(3, state.eq_selected_band + steps))
                    accum -= steps * ENC_BAND_STEP
                    if new_band != state.eq_selected_band:
                        state.eq_selected_band = new_band
                        self._apply_cs_strip_da_setup('eq', 'EQ')
                        print(f"  EQ band selected: {new_band + 1}")
                state._eq_band_accum = accum
                return

            # DA encoder path: takes priority and also enables pages without a
            # binding-path mod_id (e.g. EQ page where mod_id is the section 0x01).
            if getattr(state, 'cs_strip_da_active', False):
                if increment > 0:
                    midi_val = min(63, abs(increment))
                else:
                    midi_val = 64 + min(63, abs(increment))
                self.nuendo_link.send_da_encoder_value(encoder_index, midi_val)
                return

            # Resolve the slot's mod_id and current variant for binding-path
            mod_id = _CS_PAGE_TO_MOD_ID.get(cs_page)
            if mod_id is None:
                return  # EQ etc. — no binding-path slot, no DA setup applied
            slot = state.channel_strip.slots.get(mod_id)
            variant = slot.plugin_name if (slot and slot.plugin_name) else None

            # Pick the encoder paramId map for this (page, variant).
            # Fall back to the page's primary variant (None key) if the
            # current plugin doesn't have a custom map.
            enc_map = _VARIANT_ENCODER_MAPS.get((cs_page, variant))
            if enc_map is None:
                enc_map = _VARIANT_ENCODER_MAPS.get((cs_page, None))
            if enc_map is None:
                return
            
            if 0 <= encoder_index < len(enc_map):
                pid = enc_map[encoder_index]
                if pid is not None:
                    self.nuendo_link.send_slot_param_delta(
                        mod_id, pid, increment, encoder_index=encoder_index)
            return  # No fader/state update for strip params; feedback via SysEx 0x32
        
        elif mode == MODE_DEVICE:
            selected = state.selected_track
            if encoder_index < len(selected.quick_controls):
                selected.quick_controls[encoder_index].value = new_val
            self.nuendo_link.send_quick_control_change(encoder_index, new_val)
        
        elif mode == MODE_INSERTS and state.insert_params_mode:
            if getattr(self.nuendo_link, '_da_mapping_active', False) and state.active_mapping:
                # Mapping active: send relative encoder to DA via channel 9
                if increment > 0:
                    midi_val = min(63, abs(increment))
                else:
                    midi_val = 64 + min(63, abs(increment))
                self.nuendo_link.send_da_encoder_value(encoder_index, midi_val)
            else:
                # No mapping: send CC on channel 2 for insert parameters
                if increment > 0:
                    midi_val = min(63, abs(increment))
                else:
                    midi_val = 64 + min(63, abs(increment))
                self.nuendo_link.send_cc_ch2(20 + encoder_index, midi_val)
            return  # Feedback comes from JS
        
        elif mode == MODE_BROWSER and state.browser_phase == "collection_select":
            # Collection picker: encoder 1 scrolls through collections
            if encoder_index == 0 or encoder_index == 1:
                total = len(state.browser_collections)
                if total > 0:
                    state.browser_coll_scroll += increment
                    state.browser_coll_scroll = max(0, min(total - 1, state.browser_coll_scroll))
            return
        
        elif mode == MODE_BROWSER and state.browser_phase == "plugin_list":
            # Browser mode: encoders scroll the plugin list
            total = len(state.browser_plugins)
            if total == 0:
                return
            if encoder_index == 0:
                # Encoder 1: page scroll (8 per notch)
                state.browser_scroll += increment * 8
                # Snap to multiples of 8
                state.browser_scroll = (state.browser_scroll // 8) * 8
                max_scroll = max(0, ((total - 1) // 8) * 8)
                state.browser_scroll = max(0, min(max_scroll, state.browser_scroll))
                # Keep selection within visible range
                if state.browser_selected < state.browser_scroll:
                    state.browser_selected = state.browser_scroll
                elif state.browser_selected >= state.browser_scroll + 8:
                    state.browser_selected = state.browser_scroll
            elif encoder_index == 1:
                # Encoder 2: fine scroll — move highlight only, page when hitting edge
                state.browser_selected += increment
                state.browser_selected = max(0, min(total - 1, state.browser_selected))
                # If selection goes out of visible range, jump to next/prev page
                if state.browser_selected < state.browser_scroll:
                    state.browser_scroll = (state.browser_selected // 8) * 8
                elif state.browser_selected >= state.browser_scroll + 8:
                    state.browser_scroll = (state.browser_selected // 8) * 8
            else:
                return
            return
        
        elif mode == MODE_TRACK:
            # Combined mode: all encoders control the selected track
            selected = state.selected_track
            sel_in_bank = state.selected_track_index - state.bank_offset
            if sel_in_bank < 0 or sel_in_bank >= 8:
                return  # Selected track outside visible bank
            
            if encoder_index == 0:
                # Volume
                selected.volume = new_val
                selected.volume_db = _to_db(new_val)
                self.nuendo_link.send_volume_change(sel_in_bank, new_val)
            elif encoder_index == 1:
                # Pan
                pan_val = (new_val * 2.0) - 1.0
                selected.pan = pan_val
                self.nuendo_link.send_pan_change(sel_in_bank, pan_val)
            elif encoder_index >= 2 and encoder_index <= 7:
                # Sends 1-6 — CC 48-55 routes to sendVars[currentSendIndex]
                # Temporarily change currentSendIndex via CC 19
                send_idx = encoder_index - 2
                # Send the send index change + the value
                self.nuendo_link.send_cc(19, send_idx)  # Change send index in the JS
                import time as _t; _t.sleep(0.01)
                if send_idx < len(selected.sends):
                    selected.sends[send_idx] = new_val
                self.nuendo_link.send_send_change(sel_in_bank, new_val)

    # ─────────────────────────────────────────
    # Button handling
    # ─────────────────────────────────────────

    def _handle_encoder_touch(self, encoder_name):
        """Called when the user touches an encoder."""
        if not self.state.shift_held:
            return
        if 'master' in encoder_name.lower():
            # Shift + touch Master Encoder = reset Control Room Main to exact 0 dB.
            # The JS button on CC 78 fires its handler only when the value CHANGES
            # (and the API may coalesce identical CCs), so a fixed value would
            # only work once. Alternate between two non-zero values (both pass the
            # JS "value > 0" guard) so every Shift+Touch produces a fresh change.
            self._cr_reset_toggle = 126 if getattr(self, '_cr_reset_toggle', 127) != 126 else 127
            self.nuendo_link.send_cc(78, self._cr_reset_toggle)
    
    def _handle_button_press(self, button_name):
        """Called when the user presses a button."""
        state = self.state
        
        # ── Shift ──
        if button_name == BTN_SHIFT:
            state.shift_held = True
            try:
                self.push.buttons.set_button_color(BTN_SHIFT, LED_DIM_GREY)
            except Exception:
                pass
            return
        
        # ── Keyswitch config screen: intercept lower row + arrows ──
        if self.pad_grid.ks_edit:
            if self._handle_ks_edit_button(button_name):
                return

        # ── XY pad: upper row disabled; lower 1/2 toggle the X/Y category ──
        if state.mode == MODE_XY:
            if button_name in BUTTONS_UPPER_ROW:
                return
            if button_name in BUTTONS_LOWER_ROW:
                idx = BUTTONS_LOWER_ROW.index(button_name)
                if idx == 0:
                    state.xy_cat_x = 'cc' if state.xy_cat_x == 'track' else 'track'
                    self._update_lower_row_leds()
                    return
                if idx == 1:
                    state.xy_cat_y = 'cc' if state.xy_cat_y == 'track' else 'track'
                    self._update_lower_row_leds()
                    return
                if 4 <= idx <= 7:
                    # Mute / Solo / Monitor / Rec on the selected track (like QC page)
                    self._toggle_selected_track_function(idx - 4)
                    return
                return

        # ── User (toggle Control Room mode) ──
        if button_name == BTN_USER:
            state.user_held = True
            if state.mode == MODE_CR:
                # Exit CR mode
                self._set_mode(MODE_VOLUME)
            else:
                self._set_mode(MODE_CR)
                self.cr_state.page = CR_PAGE_MAIN
                self._update_cr_leds()
            return

        # ── Select (modifier: Select + Master Encoder = CR Phones level) ──
        if button_name == BTN_SELECT:
            state.select_held = True
            return

        # ── Setup (toggle Setup page) ──
        if button_name == BTN_SETUP:
            if state.shift_held:
                # Shift+Setup = trigger DirectAccess diagnostic
                print("  → Triggering DA diagnostic...")
                self.nuendo_link.send_cc(15, 127)
                time.sleep(0.02)
                self.nuendo_link.send_cc(15, 0)
                return
            if state.mode == MODE_SETUP:
                self._set_mode(MODE_VOLUME)
            else:
                self._set_mode(MODE_SETUP)
                state.setup_page = 0
            self._update_all_leds()
            return
        
        # ── Undo / Redo ──
        if BTN_UNDO and button_name == BTN_UNDO:
            if state.shift_held:
                self.nuendo_link.send_cc(55, 127)  # Redo
            else:
                self.nuendo_link.send_cc(54, 127)  # Undo
            return
        
        # ── Scale ──
        if BTN_SCALE and button_name == BTN_SCALE:
            self.pad_grid.scale_mode = not self.pad_grid.scale_mode
            try:
                if self.pad_grid.scale_mode:
                    self.push.buttons.set_button_color(BTN_SCALE, LED_CYAN)
                else:
                    self.push.buttons.set_button_color(BTN_SCALE, LED_DIM_GREY)
            except Exception:
                pass
            self._update_pad_colors()
            return
        
        # ── Octave Up/Down ──
        if BTN_OCTAVE_UP and button_name == BTN_OCTAVE_UP:
            self.pad_grid.octave_up()
            self._update_pad_colors()
            return
        if BTN_OCTAVE_DOWN and button_name == BTN_OCTAVE_DOWN:
            self.pad_grid.octave_down()
            self._update_pad_colors()
            return
        
        # ── Layout (cycle note layouts; Shift = touchstrip; long-press = KS config) ──
        if BTN_LAYOUT and button_name == BTN_LAYOUT:
            if state.shift_held:
                modes = ["pitchbend", "modwheel", "volume"]
                current_idx = modes.index(self.state.touchstrip_mode) if self.state.touchstrip_mode in modes else 0
                self.state.touchstrip_mode = modes[(current_idx + 1) % len(modes)]
                self._configure_touchstrip_mode()
                print(f"  Touchstrip mode: {self.state.touchstrip_mode}")
                labels = {"pitchbend": "PITCH BEND", "modwheel": "MOD WHEEL", "volume": "VOLUME FADER"}
                self.state._touchstrip_overlay = labels[self.state.touchstrip_mode]
                self.state._touchstrip_overlay_until = time.time() + 2.0
                return
            # Non-shift: short press cycles layout, long press opens KS config.
            # A press id cancels stale long-press timers (so a fast double-click
            # does not let a previous press's timer fire the KS config).
            self._layout_press_active = True
            self._layout_long_fired = False
            self._layout_press_id += 1
            my_id = self._layout_press_id
            import threading
            def _layout_long_press(pid=my_id):
                time.sleep(0.5)
                if (self._layout_press_active and self._layout_press_id == pid
                        and self.pad_grid.is_keyswitch_layout
                        and self.state.mode != MODE_XY):
                    self._layout_long_fired = True
                    self.pad_grid.ks_edit = not self.pad_grid.ks_edit
                    if self.pad_grid.ks_edit:
                        self.pad_grid.ks_edit_page = 0
                    self._update_pad_colors()
                    self._update_ks_edit_leds()
            threading.Thread(target=_layout_long_press, daemon=True).start()
            return
        
        # ── Metronome ──
        if BTN_METRONOME and button_name == BTN_METRONOME:
            self.nuendo_link.send_cc(58, 127)
            time.sleep(0.01)
            self.nuendo_link.send_cc(58, 0)
            return
        
        # ── Note Repeat ──
        if button_name == BTN_REPEAT:
            self.note_repeat.enabled = not self.note_repeat.enabled
            if not self.note_repeat.enabled:
                self.note_repeat.stop_all(self.nuendo_link.send_note_off)
            self._sync_repeat_state()
            self._update_repeat_leds()
            return
        
        # ── Subdivision buttons (CC 36-43 on the Push) ──
        for subdiv_btn_name in ['1/4', '1/4t', '1/8', '1/8t', '1/16', '1/16t', '1/32', '1/32t']:
            if button_name == subdiv_btn_name:
                idx = ['1/4', '1/4t', '1/8', '1/8t', '1/16', '1/16t', '1/32', '1/32t'].index(subdiv_btn_name)
                self.note_repeat.set_subdivision(idx)
                self._sync_repeat_state()
                self._update_repeat_leds()
                return
        
        # ── Accent ──
        if button_name == BTN_ACCENT:
            state.accent_enabled = not state.accent_enabled
            state.accent_held = True
            self._update_accent_led()
            return
        
        # ── Fixed Length (Cycle/Loop) ──
        if button_name == BTN_FIXED_LENGTH:
            self.nuendo_link.send_cc(53, 127)
            return
        
        # ── Add Track ──
        if button_name == BTN_ADD_TRACK:
            self.nuendo_link.send_cc(72, 127)
            return
        
        # ── New Track Version ──
        if button_name == BTN_NEW:
            self.nuendo_link.send_cc(71, 127)
            return
        
        # ── Duplicate ──
        if button_name == BTN_DUPLICATE:
            if state.shift_held:
                self.nuendo_link.send_cc(70, 127)  # Duplicate Track Version
            else:
                self.nuendo_link.send_cc(69, 127)  # Duplicate Track
            return
        
        # ── Delete ──
        if button_name == BTN_DELETE:
            if state.shift_held:
                self.nuendo_link.send_cc(16, 127)  # Remove Selected Tracks
            else:
                self.nuendo_link.send_cc(76, 127)  # Delete (clip)
            return
        
        # ── Touchstrip mode (Shift + touchstrip button = alternate) ──
        
        # ── Sends Up/Down ──
        if BTN_UP and button_name == BTN_UP:
            if state.mode == MODE_SENDS:
                self.nuendo_link.send_cc(47, 127)  # Prev send
            return
        if BTN_DOWN and button_name == BTN_DOWN:
            if state.mode == MODE_SENDS:
                self.nuendo_link.send_cc(46, 127)  # Next send
            return
        
        # ── Transport ──
        if button_name == BTN_PLAY:
            if getattr(state, 'is_playing', False):
                self.nuendo_link.send_cc(51, 127)  # Stop
            else:
                self.nuendo_link.send_cc(50, 127)  # Play
            return
        if button_name == BTN_RECORD:
            self.nuendo_link.send_cc(52, 127)
            return
        if BTN_AUTOMATE and button_name == BTN_AUTOMATE:
            # Cycle: Off → Read → Read+Write → Write → Off
            track = state.selected_track
            r = track.automation_read
            w = track.automation_write
            
            if not r and not w:
                # Off → Read
                self.nuendo_link.send_cc(56, 127)
            elif r and not w:
                # Read → Read+Write
                self.nuendo_link.send_cc(57, 127)
            elif r and w:
                # Read+Write → Write only (toggle read off)
                self.nuendo_link.send_cc(56, 127)
            elif not r and w:
                # Write → Off (toggle write off)
                self.nuendo_link.send_cc(57, 127)
            return
        
        # ── Bank navigation (or track navigation in Inserts/Sends mode) ──
        if button_name == BTN_LEFT:
            if state.mode == MODE_INSERTS and state.insert_params_mode:
                if getattr(self.nuendo_link, '_da_mapping_active', False) and state.active_mapping:
                    # Mapping active: navigate mapping pages
                    page_idx = getattr(self, '_current_mapping_page', 0)
                    if page_idx > 0:
                        page_idx -= 1
                        self._current_mapping_page = page_idx
                        pages = state.active_mapping.get("pages", [])
                        self._apply_mapping_page(page_idx, pages)
                        self._update_nav_leds()
                else:
                    # No mapping: use viewer parameter bank navigation
                    self.nuendo_link.send_cc_ch2(3, 127)
                    time.sleep(0.01)
                    self.nuendo_link.send_cc_ch2(3, 0)
                return
            if state.mode == MODE_INSERTS and not state.insert_params_mode and state.shift_held:
                # Shift+Left in insert list mode: bank left (8-15 → 0-7)
                if state.insert_bank_offset > 0:
                    state.insert_bank_offset = 0
                    self._update_upper_row_leds()
                    self._update_lower_row_leds()
                    self._update_nav_leds()
                return
            if state.mode in (MODE_INSERTS, MODE_SENDS, MODE_DEVICE, MODE_XY):
                if state.selected_track_index > 0:
                    new_idx = state.selected_track_index - 1
                    need_bank = new_idx < state.bank_offset
                    current_mode = state.mode
                    state.selected_track_index = new_idx
                    for j, track in enumerate(state.tracks):
                        track.is_selected = (j == new_idx)
                    if need_bank:
                        state.bank_offset = max(0, state.bank_offset - BANK_SIZE)
                    
                    import threading
                    def _nav_left():
                        if need_bank:
                            self.nuendo_link.send_cc(9, 127)
                            time.sleep(0.02)
                            self.nuendo_link.send_cc(9, 0)
                            time.sleep(0.2)
                        rel = state.selected_track_index - state.bank_offset
                        self.nuendo_link.send_select_track(rel)
                        self.nuendo_link._ignore_selection_until = time.time() + 5.0
                        time.sleep(0.5)
                        if current_mode == MODE_INSERTS:
                            state.insert_bank_offset = 0
                            self._scan_inserts()
                        self._update_upper_row_leds()
                        self._update_lower_row_leds()
                        self._update_nav_leds()
                    threading.Thread(target=_nav_left, daemon=True).start()
                return
            # Shift+Left in Volume/Pan: nudge bank by 1 track
            if state.shift_held and state.mode in (MODE_VOLUME, MODE_PAN):
                if state.bank_offset > 0:
                    state.bank_offset -= 1
                    self.nuendo_link.send_cc(39, 127)
                    time.sleep(0.02)
                    self.nuendo_link.send_cc(39, 0)
                    self.nuendo_link._ignore_selection_until = time.time() + 2.0
                self._update_nav_leds()
                return
            if state.bank_offset > 0:
                state.bank_offset = max(0, state.bank_offset - BANK_SIZE)
                self.nuendo_link.send_cc(9, 127)
                time.sleep(0.02)
                self.nuendo_link.send_cc(9, 0)
                self.nuendo_link._ignore_selection_until = time.time() + 2.0
            self._update_nav_leds()
            return
        
        if button_name == BTN_RIGHT:
            if state.mode == MODE_INSERTS and state.insert_params_mode:
                if getattr(self.nuendo_link, '_da_mapping_active', False) and state.active_mapping:
                    # Mapping active: navigate mapping pages
                    page_idx = getattr(self, '_current_mapping_page', 0)
                    pages = state.active_mapping.get("pages", [])
                    if page_idx < len(pages) - 1:
                        page_idx += 1
                        self._current_mapping_page = page_idx
                        self._apply_mapping_page(page_idx, pages)
                        self._update_nav_leds()
                else:
                    # No mapping: use viewer parameter bank navigation
                    self.nuendo_link.send_cc_ch2(2, 127)
                    time.sleep(0.01)
                    self.nuendo_link.send_cc_ch2(2, 0)
                return
            if state.mode == MODE_INSERTS and not state.insert_params_mode and state.shift_held:
                # Shift+Right in insert list mode: bank right (0-7 → 8-15)
                if state.insert_bank_offset == 0:
                    state.insert_bank_offset = 8
                    self._update_upper_row_leds()
                    self._update_lower_row_leds()
                    self._update_nav_leds()
                return
            if state.mode in (MODE_INSERTS, MODE_SENDS, MODE_DEVICE, MODE_XY):
                if state.selected_track_index < state.total_tracks - 1:
                    new_idx = state.selected_track_index + 1
                    current_mode = state.mode
                    state.selected_track_index = new_idx
                    for j, track in enumerate(state.tracks):
                        track.is_selected = (j == new_idx)
                    need_bank = new_idx >= state.bank_offset + BANK_SIZE
                    if need_bank:
                        state.bank_offset += BANK_SIZE
                    
                    import threading
                    def _nav_right():
                        if need_bank:
                            self.nuendo_link.send_cc(8, 127)
                            time.sleep(0.02)
                            self.nuendo_link.send_cc(8, 0)
                            time.sleep(0.2)
                        rel = state.selected_track_index - state.bank_offset
                        self.nuendo_link.send_select_track(rel)
                        self.nuendo_link._ignore_selection_until = time.time() + 5.0
                        time.sleep(0.5)
                        if current_mode == MODE_INSERTS:
                            state.insert_bank_offset = 0
                            self._scan_inserts()
                        self._update_upper_row_leds()
                        self._update_lower_row_leds()
                        self._update_nav_leds()
                    threading.Thread(target=_nav_right, daemon=True).start()
                return
            # Shift+Right in Volume/Pan: nudge bank by 1 track
            if state.shift_held and state.mode in (MODE_VOLUME, MODE_PAN):
                if state.bank_offset + BANK_SIZE < state.total_tracks:
                    state.bank_offset += 1
                    self.nuendo_link.send_cc(38, 127)
                    time.sleep(0.02)
                    self.nuendo_link.send_cc(38, 0)
                    self.nuendo_link._ignore_selection_until = time.time() + 2.0
                self._update_nav_leds()
                return
            max_offset = max(0, (state.total_tracks - 1) // BANK_SIZE) * BANK_SIZE
            if state.bank_offset < max_offset:
                state.bank_offset += BANK_SIZE
                self.nuendo_link.send_cc(8, 127)
                time.sleep(0.02)
                self.nuendo_link.send_cc(8, 0)
                self.nuendo_link._ignore_selection_until = time.time() + 2.0
            self._update_nav_leds()
            return
        
        # ── Mode buttons ──
        if button_name == BTN_MODE_VOLUME:
            if state.shift_held:
                # Shift+Mix → Track view (combined Vol+Pan+Sends on selected)
                self._set_mode(MODE_TRACK)
            elif state.mode == MODE_VOLUME:
                # Already on the 8-track mix → drill into Channel Strip overview
                self._set_cs_page("overview")
                self._set_mode(MODE_CHANNEL_STRIP)
            elif state.mode == MODE_CHANNEL_STRIP:
                # In Channel Strip → back out to the 8-track mix
                # (regardless of whether we were on overview or a drill-down sub-page)
                self._set_mode(MODE_VOLUME)
            else:
                # Coming from any other mode → land on the 8-track mix
                self._set_mode(MODE_VOLUME)
            return
        
        if button_name == BTN_MODE_SENDS:
            # Clip button cycles Sends <-> Pan (Pan used to be Shift+Clip), the
            # same way the Mix button cycles Volume <-> Channel Strip.
            if state.mode == MODE_SENDS:
                # On Sends → Pan
                self._set_mode(MODE_PAN)
            else:
                # From Pan or any other mode → Sends
                self._set_mode(MODE_SENDS)
                # Force refresh of names de sends by re-selecting the track
                import threading
                def _refresh_sends():
                    rel = state.selected_track_index - state.bank_offset
                    if 0 <= rel < 8:
                        self.nuendo_link.send_select_track(rel)
                        self.nuendo_link._ignore_selection_until = time.time() + 5.0
                    time.sleep(0.3)
                    self._update_upper_row_leds()
                    self._update_lower_row_leds()
                threading.Thread(target=_refresh_sends, daemon=True).start()
            return
        
        if button_name == BTN_MODE_NOTE:
            if state.shift_held:
                # Shift+Note = MIDI CC page
                if state.mode == MODE_MIDICC:
                    self._set_mode(MODE_VOLUME)
                else:
                    self._set_mode(MODE_MIDICC)
                    state.cc_edit_mode = False
                return
            # Return to MIDI note pads (exit Overview / MIDI CC / XY if active)
            if state.mode in (MODE_OVERVIEW, MODE_MIDICC, MODE_XY):
                self._set_mode(MODE_VOLUME)
            self._update_pad_colors()
            return
        
        if button_name == BTN_DEVICE:
            self._set_mode(MODE_DEVICE)
            # Force refresh of QC names by re-selecting the track
            import threading
            def _refresh_qc():
                rel = state.selected_track_index - state.bank_offset
                if 0 <= rel < 8:
                    self.nuendo_link.send_select_track(rel)
                    self.nuendo_link._ignore_selection_until = time.time() + 5.0
                time.sleep(0.3)
            threading.Thread(target=_refresh_qc, daemon=True).start()
            return
        
        if button_name == BTN_MODE_INSERTS:
            if state.mode == MODE_BROWSER:
                # Browse pressed in browser mode → cancel, return to inserts
                self._set_mode(MODE_INSERTS)
                self._scan_inserts()
                return
            if state.mode != MODE_INSERTS:
                self._set_mode(MODE_INSERTS)
            state.selected_insert_slot = 0
            state.insert_bank_offset = 0
            self.nuendo_link._insert_current_slot = 0
            self._scan_inserts()
            return
        
        # ── Add Device → Plugin Browser ──
        if button_name == BTN_ADD_DEVICE:
            if state.mode == MODE_BROWSER:
                # Already in browser → cancel, back to where we came from
                if state.browser_instrument:
                    self._set_mode(state.browser_prev_mode)
                else:
                    self._set_mode(MODE_INSERTS)
                    self._scan_inserts()
            elif state.shift_held:
                # Shift+Add Device → INSERT browser (audio effects, pick a slot)
                state.browser_prev_mode = state.mode
                state.browser_instrument = False
                state.browser_phase = "slot_select"
                state.insert_bank_offset = 0
                self._set_mode(MODE_BROWSER)
                if not self.nuendo_link._da_inserts_ready:
                    self._scan_inserts()
            else:
                # Add Device → INSTRUMENT browser for the selected Instrument
                # track. There is a single instrument slot, so skip slot select
                # and jump straight to the plugin list (collection 0 = Default).
                state.browser_prev_mode = state.mode
                state.browser_instrument = True
                state.browser_phase = "plugin_list"
                state.browser_scroll = 0
                state.browser_selected = 0
                state.browser_collection_index = 0
                state.browser_list_ready = False
                self._set_mode(MODE_BROWSER)
                self.nuendo_link.request_da_plugin_list(0, instrument=True)
            return
        
        # ── Overview mode ──
        if button_name == BTN_MODE_OVERVIEW:
            # Session = XY pad (Overview mode disabled for now)
            if state.mode == MODE_XY:
                self._set_mode(MODE_VOLUME)
            else:
                self._set_mode(MODE_XY)
                self._xy_pressures = {}
                self._xy_centroid = None
                self._xy_last_sent = (None, None)
            self._update_pad_colors()
            return
        
        # ── Page ◄/► for Overview pagination ──
        if state.mode == MODE_OVERVIEW:
            if BTN_PAGE_LEFT and button_name == BTN_PAGE_LEFT:
                if state.overview_page > 0:
                    state.overview_page -= 1
                    self._update_overview_pads()
                return
            if BTN_PAGE_RIGHT and button_name == BTN_PAGE_RIGHT:
                _, _, total_rows = compute_overview_layout(state.tracks, state.total_tracks, state.overview_page)
                max_pages = (total_rows + 7) // 8
                if state.overview_page < max_pages - 1:
                    state.overview_page += 1
                    self._update_overview_pads()
                return
        
        # (Rescan moved to the Setup page, lower row 8.)

        # ── Mode MIDI CC : intercepter les boutons ──
        if state.mode == MODE_MIDICC:
            # Upper row → toggle CC edit mode per channel
            for i, btn in enumerate(BUTTONS_UPPER_ROW):
                if button_name == btn:
                    state.cc_edit_mode = not state.cc_edit_mode
                    self._update_all_leds()
                    return
            
            # Lower row → toggle CC value 0/127 (for on/off CCs like sustain)
            for i, btn in enumerate(BUTTONS_LOWER_ROW):
                if button_name == btn:
                    if state.cc_values[i] > 0:
                        state.cc_values[i] = 0
                    else:
                        state.cc_values[i] = 127
                    self.nuendo_link.send_midi_cc_to_notes(state.cc_numbers[i], state.cc_values[i])
                    self._update_lower_row_leds()
                    return
            return
        
        # ── Mode Setup : intercepter les boutons ──
        if state.mode == MODE_SETUP:
            SETUP_PAGES = ['MIDI Ctrl', 'Vel Curve', 'CR Knob', None, None, None, None, 'About']
            
            # Upper row → select setup page
            for i, btn in enumerate(BUTTONS_UPPER_ROW):
                if button_name == btn:
                    if i < len(SETUP_PAGES) and SETUP_PAGES[i] is not None:
                        state.setup_page = i
                        self._update_all_leds()
                    return
            
            # Lower row → change settings on the current page
            for i, btn in enumerate(BUTTONS_LOWER_ROW):
                if button_name == btn:
                    if i == 7:
                        # Rescan tracks (available on every Setup page)
                        for t in state.tracks:
                            t.name = f"Track {t.index + 1}"
                            t.color = (150, 150, 150)
                        self._full_scan()
                        self._update_all_leds()
                        return
                    if state.setup_page == 0:
                        # Page 0: MIDI Controller — Aftertouch mode (buttons 1-3)
                        if i == 0:
                            state.aftertouch_mode = AT_POLY
                            self._apply_aftertouch_mode()
                        elif i == 1:
                            state.aftertouch_mode = AT_CHANNEL
                            self._apply_aftertouch_mode()
                        elif i == 2:
                            state.aftertouch_mode = AT_OFF
                            self._apply_aftertouch_mode()
                    elif state.setup_page == 1:
                        # Page 1: Velocity Curve (buttons 1-5)
                        VC_LIST = [VC_LINEAR, VC_LOG, VC_EXP, VC_SCURVE, VC_FIXED]
                        if i < len(VC_LIST):
                            state.velocity_curve = VC_LIST[i]
                            self._apply_velocity_curve()
                    elif state.setup_page == 2:
                        # Page 2: CR Knob default (button 1 = Main, 2 = Phones)
                        if i == 0:
                            state.cr_phones_default = False
                        elif i == 1:
                            state.cr_phones_default = True
                    self._update_all_leds()
                    return
            return
        
        # ── Mode Control Room : intercepter les boutons ──
        if state.mode == MODE_CR:
            # Params that don't receive JS feedback when operated from Push
            # (exclusive selects vs true toggles)
            SELECT_PARAMS = {
                12, 13,             # Mon A, Mon B
                17, 18, 19, 20,     # Main Cue 1-4
                42, 43, 44, 45,     # Phones Cue 1-4
            }
            # Exclusive groups: selecting one deselects the others
            EXCLUSIVE_GROUPS = {
                12: {12, 13},       # Mon A/B
                13: {12, 13},
                17: {17, 18, 19, 20},  # Main Cue 1-4
                18: {17, 18, 19, 20},
                19: {17, 18, 19, 20},
                20: {17, 18, 19, 20},
                42: {42, 43, 44, 45},  # Phones Cue 1-4
                43: {42, 43, 44, 45},
                44: {42, 43, 44, 45},
                45: {42, 43, 44, 45},
            }
            # Mon A/B: always one selected (no deselection)
            ALWAYS_ONE = {12, 13}
            
            def _do_select(param_id):
                """Handle exclusive selection."""
                group = EXCLUSIVE_GROUPS.get(param_id, {param_id})
                was_on = self.cr_state.get_toggle(param_id)
                if param_id in ALWAYS_ONE and was_on:
                    return  # Already selected, don't deselect
                for p in group:
                    self.cr_state.set_toggle(p, p == param_id and not was_on)
                self._update_cr_leds()
            
            # Upper row → actions CR
            for i, btn in enumerate(BUTTONS_UPPER_ROW):
                if button_name == btn:
                    page_def = CR_PAGES.get(self.cr_state.page, {})
                    upper = page_def.get('upper_btns', [])
                    if i < len(upper) and upper[i] is not None:
                        label, cc, param_id, is_toggle = upper[i]
                        self.nuendo_link.send_cc_ch6(cc, 127)
                        if param_id in SELECT_PARAMS:
                            _do_select(param_id)
                    return
            
            # Lower row → CR page navigation (buttons 5-8) or CR actions (buttons 1-4)
            for i, btn in enumerate(BUTTONS_LOWER_ROW):
                if button_name == btn:
                    page_def = CR_PAGES.get(self.cr_state.page, {})
                    lower = page_def.get('lower_btns', [])
                    # Buttons 1-4: CR actions (cue select etc.)
                    if i < 4 and i < len(lower) and lower[i] is not None:
                        cc = lower[i][1]
                        param_id = lower[i][2] if len(lower[i]) >= 3 else None
                        self.nuendo_link.send_cc_ch6(cc, 127)
                        if param_id in SELECT_PARAMS:
                            _do_select(param_id)
                    # Buttons 5-8: page navigation
                    elif i >= 4 and (i - 4) < len(CR_PAGE_NAMES):
                        self.cr_state.page = i - 4
                        self._update_cr_leds()
                    return
            return
        
        # ── Channel Strip mode: drill-in nav (upper) + bypass toggles (lower) ──
        if state.mode == MODE_CHANNEL_STRIP and state.cs_page == "overview":
            # Upper row 1-6 → enter drill-down page for that module
            # Upper row 7   → toggle PreFilter section bypass
            # Upper row 8   → no-op (reserved for future)
            for i, btn in enumerate(BUTTONS_UPPER_ROW):
                if button_name == btn:
                    if i < 6:
                        target_page = ["gate", "comp", "eq", "tools", "sat", "limiter"][i]
                        self._set_cs_page(target_page)
                        print(f"  CS drill-in: {target_page}")
                    elif i == 6:
                        # PreFilter section bypass — link reads cached value and sends inverse
                        self.nuendo_link.send_strip_param_toggle(0x00, 0x7F)
                    return
            
            # Lower row 1-6 → toggle bypass of corresponding module
            #   1=Gate, 2=Comp, 3=EQ section, 4=Tools, 5=Sat, 6=Limiter
            # Lower row 7   → toggle Phase Switch
            # Lower row 8   → no-op
            for i, btn in enumerate(BUTTONS_LOWER_ROW):
                if button_name == btn:
                    if i == 0:    # Gate slot.mOn
                        self.nuendo_link.send_strip_param_toggle(0x10, 0x00)
                    elif i == 1:  # Compressor slot.mOn
                        self.nuendo_link.send_strip_param_toggle(0x11, 0x00)
                    elif i == 2:  # ChannelEQ section bypass via DA flip
                        # The binding-path Note 9/3 (eq.mBypass setTypeToggle)
                        # is unreliable on some Cubase versions; DA flip works.
                        da_slot = self._resolve_da_slot_for_variant('EQ')
                        if da_slot >= 0:
                            self.nuendo_link.send_da_param_flip(da_slot, 0)
                    elif i == 3:  # Tools slot.mOn
                        self.nuendo_link.send_strip_param_toggle(0x12, 0x00)
                    elif i == 4:  # Saturator slot.mOn
                        self.nuendo_link.send_strip_param_toggle(0x13, 0x00)
                    elif i == 5:  # Limiter slot.mOn
                        self.nuendo_link.send_strip_param_toggle(0x14, 0x00)
                    elif i == 6:  # PreFilter Phase Switch
                        self.nuendo_link.send_strip_param_toggle(0x00, 0x01)
                    elif i == 7:  # Toggle Edit Channel Settings window
                        self.nuendo_link.toggle_edit_channel_settings()
                    return
            return
        
        # ── Channel Strip drill-down upper row ──
        # Layout (all CS sub-pages):
        #   Upper 1 = inactive (just displays the module name)
        #   Upper 2 = module On/Off (slot.mOn for strip slots, section bypass for EQ)
        #   Upper 3-4-5 = variant choice (when applicable — limited by API)
        #   Upper 6, 7 = unassigned
        #   Upper 8 = back to overview
        if state.mode == MODE_CHANNEL_STRIP and state.cs_page != "overview":
            for i, btn in enumerate(BUTTONS_UPPER_ROW):
                if button_name == btn and i == 0:
                    # Inactive — module name label only
                    return
                if button_name == btn and i == 1:
                    # Upper 2 → module Bypass.
                    # EQ section: DA flip on the Bypass param (DA idx 0,
                    # tag 4204) — the binding-path Note 9/3 seems unreliable
                    # for eq.mBypass on certain Cubase versions.
                    # Strip slots: toggle slot.mOn via binding path (works fine).
                    if state.cs_page == 'eq':
                        da_slot = self._resolve_da_slot_for_variant('EQ')
                        if da_slot >= 0:
                            self.nuendo_link.send_da_param_flip(da_slot, 0)
                            print(f"  EQ section bypass toggle (DA slot {da_slot} idx 0)")
                    else:
                        mod_id = _CS_PAGE_TO_MOD_ID.get(state.cs_page)
                        if mod_id is not None:
                            self.nuendo_link.send_strip_param_toggle(mod_id, 0x00)
                            print(f"  CS toggle on/off: {state.cs_page}")
                    return
                if button_name == btn and 2 <= i <= 4:
                    # Variant switch from Push is NOT supported by the MIDI Remote API
                    # for strip slots — silently ignore. Only log for pages that
                    # have multiple variants (so EQ etc. don't print misleading msg).
                    if state.cs_page in _VARIANT_SWITCH_OPTIONS:
                        print(f"  Variant switch from Push not supported; "
                              f"change in Nuendo's plugin slot menu.")
                    return
                if button_name == btn and i == 7:
                    # Upper 8 → back to overview
                    self._set_cs_page("overview")
                    print(f"  CS back to overview")
                    return
            # Lower row → drill-down toggles. JS Buttons at notes 9/120..127
            # have bindings per sub-page; bridge just sends the note. Each
            # sub-page's specific param mapping is on the JS side.
            for i, btn in enumerate(BUTTONS_LOWER_ROW):
                if button_name == btn:
                    # Look up active toggle positions for the current
                    # (cs_page, variant) — mirror of the JS sub-page bindings.
                    variant = self._cs_page_variant(state.cs_page)

                    # Lower 8 (universal on all CS sub-pages) → toggle the
                    # Edit Channel Settings window for the selected channel.
                    if i == 7:
                        self.nuendo_link.toggle_edit_channel_settings()
                        return

                    # DA-based toggle overrides the binding path (workaround for
                    # params that trigger Cubase bank-zone refresh on change).
                    # EQ page-specific lower-row toggles:
                    #   0 = selected band On/Off (dynamic via DA)
                    #   4 = PreFilter Bypass, 5 = LC On, 6 = HC On
                    if state.cs_page == 'eq':
                        if i == 0:
                            sel = self.state.eq_selected_band
                            on_idx = 5 + sel * 6  # DA param idx for Band N On
                            da_slot = self._resolve_da_slot_for_variant('EQ')
                            if da_slot >= 0:
                                self.nuendo_link.send_da_param_flip(da_slot, on_idx)
                                print(f"  EQ Band {sel + 1} On toggle (DA idx {on_idx})")
                            return
                        if i == 4:
                            self.nuendo_link.send_strip_param_toggle(0x00, 0x7F)  # PreFilter Bypass
                            return
                        if i == 5:
                            self.nuendo_link.send_strip_param_toggle(0x00, 0x06)  # LC On
                            return
                        if i == 6:
                            self.nuendo_link.send_strip_param_toggle(0x00, 0x03)  # HC On
                            return

                    da_toggle = _VARIANT_DA_TOGGLES.get((state.cs_page, variant, i))
                    if da_toggle is not None:
                        _, param_idx = da_toggle  # hardcoded da_slot ignored — resolve dynamically
                        resolved_slot = self._resolve_da_slot_for_variant(variant)
                        if resolved_slot < 0:
                            resolved_slot = da_toggle[0]  # fall back to hardcoded
                        self.nuendo_link.send_da_param_flip(resolved_slot, param_idx)
                        # Re-activate the sub-page so any subsequent bank-zone
                        # refresh (triggered by the plugin's value change) doesn't
                        # leave the JS sub-page in a stale/inactive state.
                        import threading as _t
                        _t.Timer(0.1, lambda p=state.cs_page:
                                 self.nuendo_link.activate_subpage(p)).start()
                        return

                    active = _VARIANT_ACTIVE_TOGGLES.get((state.cs_page, variant))
                    if active is None:
                        active = _VARIANT_ACTIVE_TOGGLES.get((state.cs_page, None), set())
                    if i in active:
                        self.nuendo_link.send_drilldown_toggle(i)
                    return
            return
        
        # ── Device mode: intercept buttons ──
        if state.mode == MODE_DEVICE:
            # Lower row: button 1 = Open Instrument UI, buttons 5-8 = Mute/Solo/Mon/Rec
            for i, btn in enumerate(BUTTONS_LOWER_ROW):
                if button_name == btn:
                    if i == 0:
                        # Open/close instrument UI of the selected track
                        rel = state.selected_track_index - state.bank_offset
                        if 0 <= rel < 8:
                            self.nuendo_link.send_note(80 + rel, 127)
                            time.sleep(0.01)
                            self.nuendo_link.send_note(80 + rel, 0)
                            print(f"  Instrument UI toggle (Device mode)")
                    elif 4 <= i <= 7:
                        self._toggle_selected_track_function(i - 4)
                    return
            return
        
        # ── Sends mode: intercept buttons ──
        if state.mode == MODE_SENDS:
            # Upper row → toggle send on/off (Note 90+i)
            for i, btn in enumerate(BUTTONS_UPPER_ROW):
                if button_name == btn:
                    self.nuendo_link.send_note(90 + i, 127)
                    time.sleep(0.01)
                    self.nuendo_link.send_note(90 + i, 0)
                    return
            
            # Lower row → toggle pre/post (Note 100+i)
            for i, btn in enumerate(BUTTONS_LOWER_ROW):
                if button_name == btn:
                    self.nuendo_link.send_note(100 + i, 127)
                    time.sleep(0.01)
                    self.nuendo_link.send_note(100 + i, 0)
                    return
            return
        
        # ── Browser mode: intercept buttons ──
        if state.mode == MODE_BROWSER:
            # ◄► arrows: switch insert bank (slot_select) or do nothing (plugin_list)
            if button_name == BTN_LEFT:
                if state.browser_phase == "slot_select" and state.insert_bank_offset > 0:
                    state.insert_bank_offset = 0
                return
            if button_name == BTN_RIGHT:
                if state.browser_phase == "slot_select" and state.insert_bank_offset == 0:
                    state.insert_bank_offset = 8
                return
            
            if state.browser_phase == "slot_select":
                # Upper row → select slot, go to plugin list
                for i, btn in enumerate(BUTTONS_UPPER_ROW):
                    if button_name == btn:
                        abs_slot = state.insert_bank_offset + i
                        state.browser_target_slot = abs_slot
                        state.browser_phase = "plugin_list"
                        state.browser_scroll = 0
                        state.browser_selected = 0
                        # Request plugin list if not already loaded
                        if not state.browser_list_ready:
                            self.nuendo_link.request_da_plugin_list(
                                state.browser_collection_index)
                        print(f"  Browser: selected slot {abs_slot + 1}, browsing plugins")
                        self._update_upper_row_leds()
                        self._update_lower_row_leds()
                        return
                
                # Lower row → button 8 = cancel
                for i, btn in enumerate(BUTTONS_LOWER_ROW):
                    if button_name == btn:
                        if i == 7:
                            self._set_mode(MODE_INSERTS)
                            self._scan_inserts()
                        return
            
            elif state.browser_phase == "plugin_list":
                # Upper row → load plugin from that column
                for i, btn in enumerate(BUTTONS_UPPER_ROW):
                    if button_name == btn:
                        plugin_idx = state.browser_scroll + i
                        if plugin_idx < len(state.browser_plugins):
                            plugin = state.browser_plugins[plugin_idx]
                            if plugin:
                                self._browser_load_plugin(
                                    state.browser_target_slot,
                                    plugin_idx,
                                    state.browser_collection_index)
                        return
                
                # Lower row
                for i, btn in enumerate(BUTTONS_LOWER_ROW):
                    if button_name == btn:
                        if i == 0:
                            # Button 1 = open collection picker
                            state.browser_phase = "collection_select"
                            state.browser_coll_scroll = state.browser_collection_index
                            state.browser_collections_ready = False
                            self.nuendo_link.request_da_collection_info(
                                instrument=state.browser_instrument)
                            self._update_upper_row_leds()
                            self._update_lower_row_leds()
                        elif i == 7:
                            # Last button = back. Instrument mode has no slot
                            # selection, so exit the browser entirely.
                            if state.browser_instrument:
                                self._set_mode(state.browser_prev_mode)
                            else:
                                state.browser_phase = "slot_select"
                                self._update_upper_row_leds()
                                self._update_lower_row_leds()
                        return
            
            elif state.browser_phase == "collection_select":
                # Upper row or lower row button 1 = confirm selection
                confirmed = False
                for i, btn in enumerate(BUTTONS_UPPER_ROW):
                    if button_name == btn:
                        confirmed = True
                        break
                if not confirmed:
                    for i, btn in enumerate(BUTTONS_LOWER_ROW):
                        if button_name == btn:
                            if i == 0:
                                confirmed = True
                            elif i == 7:
                                # Back to plugin list (cancel)
                                state.browser_phase = "plugin_list"
                                self._update_upper_row_leds()
                                self._update_lower_row_leds()
                                return
                            break
                
                if confirmed and state.browser_collections_ready:
                    selected_coll = state.browser_coll_scroll
                    if 0 <= selected_coll < len(state.browser_collections):
                        coll = state.browser_collections[selected_coll]
                        state.browser_collection_index = coll['index']
                        state.browser_phase = "plugin_list"
                        state.browser_scroll = 0
                        state.browser_selected = 0
                        state.browser_list_ready = False
                        self.nuendo_link.request_da_plugin_list(
                            coll['index'], instrument=state.browser_instrument)
                        print(f"  Browser: Selected collection \"{coll['name']}\" ({coll['count']} plugins)")
                        self._update_upper_row_leds()
                        self._update_lower_row_leds()
                return
            
            return
        
        # ── Inserts mode: intercept buttons ──
        if state.mode == MODE_INSERTS:
            names = state.current_insert_names
            ibo = state.insert_bank_offset  # 0 or 8
            
            # Upper row
            for i, btn in enumerate(BUTTONS_UPPER_ROW):
                if button_name == btn:
                    if state.insert_params_mode:
                        # In parameters mode, upper row = back to list
                        state.insert_params_mode = False
                        self.nuendo_link._da_mapping_active = False
                        self.state.active_mapping = None
                        self._update_upper_row_leds()
                        self._update_lower_row_leds()
                    else:
                        abs_slot = ibo + i
                        if abs_slot < len(names) and names[abs_slot]:
                            # Record timestamp for long press detection
                            self._upper_row_press_time[button_name] = time.time()
                            
                            # Long press timer: open UI without entering params
                            import threading
                            def _inserts_long_press(btn_name=button_name, slot=abs_slot):
                                time.sleep(0.5)
                                if btn_name in self._upper_row_press_time and self._upper_row_press_time[btn_name] > 0:
                                    # Long press: open plugin UI only
                                    self._insert_action(slot, 'edit')
                                    print(f"  Long press: Open insert UI slot {slot}")
                                    self._upper_row_press_time[btn_name] = -1  # mark handled
                            threading.Thread(target=_inserts_long_press, daemon=True).start()
                    return
            
            # Lower row
            for i, btn in enumerate(BUTTONS_LOWER_ROW):
                if button_name == btn:
                    if state.insert_params_mode:
                        # In parameters mode:
                        # Buttons 1 = Open/Close UI, 2 = Bypass, 3 = Deactivate
                        # Buttons 5-8 = Mute/Solo/Mon/Rec on selected track
                        if i == 0:
                            slot = state.selected_insert_slot
                            self._insert_action(slot, 'edit')
                        elif i == 1:
                            slot = state.selected_insert_slot
                            self._insert_action(slot, 'bypass')
                        elif i == 2:
                            slot = state.selected_insert_slot
                            self._insert_action(slot, 'deactivate')
                        elif 4 <= i <= 7:
                            self._toggle_selected_track_function(i - 4)
                    else:
                        # List view: all 8 buttons = bypass per slot
                        abs_slot = ibo + i
                        if abs_slot < len(names) and names[abs_slot]:
                            self._insert_action(abs_slot, 'bypass')
                    return
            
            # Browse → re-scan (refresh after adding insert)
            if button_name == BTN_MODE_INSERTS:
                self._scan_inserts()
                return
            
            return
        
        # ── Mode buttons Mute/Monitor (CC 60) ──
        if button_name == Push2Constants.BUTTON_MUTE:
            if state.shift_held:
                if state.lower_mode == LOWER_MODE_MONITOR:
                    # Shift+Mute in Monitor mode = Clear all monitors (all tracks)
                    if self.nuendo_link._da_available:
                        # DirectAccess path: JS clears all monitors instantly
                        self.nuendo_link.send_cc(66, 127)
                        time.sleep(0.02)
                        self.nuendo_link.send_cc(66, 0)
                        self.nuendo_link._vu_ignore_until = time.time() + 3.0
                    else:
                        # Fallback: iterate banks via CC 8/9
                        import threading
                        def _clear_all_monitors():
                            current_bank = self.state.bank_offset
                            current_bank_idx = current_bank // 8
                            num_banks = (self.state.total_tracks + 7) // 8
                            for _ in range(current_bank_idx):
                                self.nuendo_link.send_cc(9, 127)
                                time.sleep(0.02)
                                self.nuendo_link.send_cc(9, 0)
                                time.sleep(0.08)
                            self.state.bank_offset = 0
                            time.sleep(0.1)
                            for bank_idx in range(num_banks):
                                for t in range(8):
                                    abs_idx = bank_idx * 8 + t
                                    if abs_idx < len(self.state.tracks):
                                        self.state.tracks[abs_idx].is_monitored = False
                                        self.nuendo_link.send_monitor_toggle(t, False)
                                if bank_idx < num_banks - 1:
                                    self.nuendo_link.send_cc(8, 127)
                                    time.sleep(0.02)
                                    self.nuendo_link.send_cc(8, 0)
                                    time.sleep(0.08)
                            target_bank_idx = current_bank // 8
                            current_pos = num_banks - 1
                            for _ in range(current_pos - target_bank_idx):
                                self.nuendo_link.send_cc(9, 127)
                                time.sleep(0.02)
                                self.nuendo_link.send_cc(9, 0)
                                time.sleep(0.08)
                            self.state.bank_offset = current_bank
                            self._update_lower_row_leds()
                        threading.Thread(target=_clear_all_monitors, daemon=True).start()
                else:
                    # Shift+Mute = Deactivate All Mute States
                    self.nuendo_link.send_cc(75, 127)
                    time.sleep(0.05)
                    self.nuendo_link.send_cc(75, 0)
                return
            if state.lower_mode == LOWER_MODE_MUTE:
                state.lower_mode = LOWER_MODE_MONITOR
            else:
                state.lower_mode = LOWER_MODE_MUTE
            self._update_lower_row_leds()
            return
        
        # ── Mode buttons Solo/Rec (CC 61) ──
        if button_name == Push2Constants.BUTTON_SOLO:
            if state.shift_held:
                if state.lower_mode == LOWER_MODE_REC:
                    # Shift+Solo in Rec mode = Clear all rec arms (all tracks)
                    if self.nuendo_link._da_available:
                        # DirectAccess path: JS clears all rec arms instantly
                        self.nuendo_link.send_cc(67, 127)
                        time.sleep(0.02)
                        self.nuendo_link.send_cc(67, 0)
                        self.nuendo_link._vu_ignore_until = time.time() + 3.0
                    else:
                        # Fallback: iterate banks via CC 8/9
                        import threading
                        def _clear_all_rec():
                            current_bank = self.state.bank_offset
                            current_bank_idx = current_bank // 8
                            num_banks = (self.state.total_tracks + 7) // 8
                            for _ in range(current_bank_idx):
                                self.nuendo_link.send_cc(9, 127)
                                time.sleep(0.02)
                                self.nuendo_link.send_cc(9, 0)
                                time.sleep(0.08)
                            self.state.bank_offset = 0
                            time.sleep(0.1)
                            for bank_idx in range(num_banks):
                                for t in range(8):
                                    abs_idx = bank_idx * 8 + t
                                    if abs_idx < len(self.state.tracks):
                                        self.state.tracks[abs_idx].is_armed = False
                                        self.nuendo_link.send_rec_toggle(t, False)
                                if bank_idx < num_banks - 1:
                                    self.nuendo_link.send_cc(8, 127)
                                    time.sleep(0.02)
                                    self.nuendo_link.send_cc(8, 0)
                                    time.sleep(0.08)
                            target_bank_idx = current_bank // 8
                            current_pos = num_banks - 1
                            for _ in range(current_pos - target_bank_idx):
                                self.nuendo_link.send_cc(9, 127)
                                time.sleep(0.02)
                                self.nuendo_link.send_cc(9, 0)
                                time.sleep(0.08)
                            self.state.bank_offset = current_bank
                            self._update_lower_row_leds()
                        threading.Thread(target=_clear_all_rec, daemon=True).start()
                else:
                    # Shift+Solo = Deactivate All Solo States
                    self.nuendo_link.send_cc(74, 127)
                    time.sleep(0.05)
                    self.nuendo_link.send_cc(74, 0)
                return
            if state.lower_mode == LOWER_MODE_SOLO:
                state.lower_mode = LOWER_MODE_REC
            else:
                state.lower_mode = LOWER_MODE_SOLO
            self._update_lower_row_leds()
            return
        
        # ── Lower row buttons (1-8): Mute/Solo (short), Monitor/Rec (long press) ──
        for i, btn in enumerate(BUTTONS_LOWER_ROW):
            if button_name == btn:
                track_in_bank = i
                abs_index = state.bank_offset + i
                if abs_index >= state.total_tracks:
                    return
                
                # Record press time for long press detection
                self._lower_row_press_time[button_name] = time.time()
                self._lower_row_handled[button_name] = False
                press_id = self._lower_row_press_id.get(button_name, 0) + 1
                self._lower_row_press_id[button_name] = press_id
                
                # Launch long press timer
                import threading
                def _lower_long_press(btn_name=button_name, idx=i, my_id=press_id):
                    time.sleep(0.5)
                    # Only act if this press is still the current one (not superseded by a new press)
                    if self._lower_row_press_id.get(btn_name, 0) != my_id:
                        return
                    # If still pressed and not yet handled
                    if btn_name in self._lower_row_press_time and not self._lower_row_handled.get(btn_name, True):
                        self._lower_row_handled[btn_name] = True
                        abs_idx = self.state.bank_offset + idx
                        if abs_idx < self.state.total_tracks:
                            trk = self.state.tracks[abs_idx]
                            mode = self.state.lower_mode
                            if mode == LOWER_MODE_MUTE:
                                # Long press in Mute mode = Monitor toggle
                                trk.is_monitored = not trk.is_monitored
                                self.nuendo_link.send_monitor_toggle(idx, trk.is_monitored)
                            elif mode == LOWER_MODE_SOLO:
                                # Long press in Solo mode = Rec Arm toggle
                                trk.is_armed = not trk.is_armed
                                self.nuendo_link.send_rec_toggle(idx, trk.is_armed)
                            elif mode == LOWER_MODE_MONITOR:
                                # Long press in Monitor mode = Mute toggle
                                trk.is_muted = not trk.is_muted
                                self.nuendo_link.send_mute_toggle(idx, trk.is_muted)
                            elif mode == LOWER_MODE_REC:
                                # Long press in Rec mode = Solo toggle
                                trk.is_solo = not trk.is_solo
                                self.nuendo_link.send_solo_toggle(idx, trk.is_solo)
                            self._update_lower_row_leds()
                threading.Thread(target=_lower_long_press, daemon=True).start()
                return
        
        # ── Track selection buttons (upper row) ──
        for i, btn in enumerate(BUTTONS_UPPER_ROW):
            if button_name == btn:
                abs_index = state.bank_offset + i
                
                # Shift + upper row button = toggle Edit Channel Settings window
                # for the track at this bank position (Clear Clip removed — clip
                # auto-clears, the shortcut is repurposed here).
                if state.shift_held and abs_index < state.total_tracks:
                    self.nuendo_link.send_note(70 + i, 127)
                    time.sleep(0.01)
                    self.nuendo_link.send_note(70 + i, 0)
                    print(f"  Shift+Upper: Edit Channel Settings track {abs_index}")
                    return
                
                now = time.time()
                
                # Double press detection in Volume/Pan/Track modes
                if state.mode in (MODE_VOLUME, MODE_PAN, MODE_TRACK):
                    last = self._upper_row_last_press.get(button_name, 0)
                    if now - last < 0.4:  # double press within 400ms
                        # Toggle Edit Channel Settings
                        if abs_index < state.total_tracks:
                            self.nuendo_link.send_note(70 + i, 127)
                            time.sleep(0.01)
                            self.nuendo_link.send_note(70 + i, 0)
                            print(f"  Double press: Edit Channel Settings track {abs_index}")
                        self._upper_row_last_press[button_name] = 0
                        return
                self._upper_row_last_press[button_name] = now
                
                # Record timestamp for long press detection
                self._upper_row_press_time[button_name] = now
                
                # Timer for long press : open instrument UI after 1.0s
                if state.mode not in (MODE_INSERTS, MODE_CR, MODE_SENDS):
                    import threading
                    def _long_press_check(btn_name=button_name, idx=i):
                        time.sleep(1.0)
                        # Check that the button is still pressed
                        if btn_name in self._upper_row_press_time and self._upper_row_press_time[btn_name] > 0:
                            abs_idx = self.state.bank_offset + idx
                            if abs_idx < self.state.total_tracks:
                                self.nuendo_link.send_note(80 + idx, 127)
                                time.sleep(0.01)
                                self.nuendo_link.send_note(80 + idx, 0)
                                print(f"  Long press: Instrument UI toggle track {abs_idx}")
                            # Mark as handled so release doesn't act
                            self._upper_row_press_time[btn_name] = -1
                    threading.Thread(target=_long_press_check, daemon=True).start()
                
                # Immediate track selection
                if abs_index < state.total_tracks:
                    state.selected_track_index = abs_index
                    for j, track in enumerate(state.tracks):
                        track.is_selected = (j == abs_index)
                    self.nuendo_link.send_select_track(i)
                    self.nuendo_link._ignore_selection_until = time.time() + 5.0
                    self._update_upper_row_leds()
                return
        
        # Debug: unhandled button
        print(f"  Unhandled button: '{button_name}'")


    def _handle_button_release(self, button_name):
        """Called when the user releases a button."""
        if button_name == BTN_SHIFT:
            self.state.shift_held = False
            try:
                self.push.buttons.set_button_color(BTN_SHIFT, LED_OFF)
            except Exception:
                pass
        if button_name == BTN_ACCENT:
            self.state.accent_held = False
        if button_name == BTN_USER:
            self.state.user_held = False
        if button_name == BTN_SELECT:
            self.state.select_held = False

        # XY pad: upper row is disabled
        if self.state.mode == MODE_XY and button_name in BUTTONS_UPPER_ROW:
            return

        # ── Layout button release: short press = cycle layout / close KS config ──
        if BTN_LAYOUT and button_name == BTN_LAYOUT and self._layout_press_active:
            self._layout_press_active = False
            if self._layout_long_fired:
                self._layout_long_fired = False
                return
            # Short press
            if self.state.mode == MODE_XY:
                # In XY mode the pads are the XY surface — Layout returns to note pads
                self._set_mode(MODE_VOLUME)
            elif self.pad_grid.ks_edit:
                self.pad_grid.ks_edit = False
            else:
                self._release_ks_latch()
                self.pad_grid.cycle_layout()
                self.state.drum_mode = self.pad_grid.drum_mode  # keep state in sync
            self._set_button_led(BTN_LAYOUT, self.pad_grid.note_layout != LAYOUT_64)
            self._update_pad_colors()
            self._update_ks_edit_leds()
            return

        # Long press on upper row: clean up tracking
        if button_name in self._upper_row_press_time:
            was_long_press = (self._upper_row_press_time[button_name] < 0)
            self._upper_row_press_time.pop(button_name)
            
            # Short press in Inserts mode = enter params
            if not was_long_press and self.state.mode == MODE_INSERTS and not self.state.insert_params_mode:
                for i, btn in enumerate(BUTTONS_UPPER_ROW):
                    if button_name == btn:
                        names = self.state.current_insert_names
                        abs_slot = self.state.insert_bank_offset + i
                        if abs_slot < len(names) and names[abs_slot]:
                            self.state.selected_insert_slot = abs_slot
                            self.state.insert_param_names = [''] * 8
                            self.state.insert_param_values = [''] * 8
                            # Check if a plugin mapping exists
                            self._check_insert_mapping(names[abs_slot])
                            # If mapping found, request DA param enumeration
                            if self.state.active_mapping and getattr(self.nuendo_link, '_da_available', False):
                                self.nuendo_link._da_mapping_active = True
                                self.nuendo_link._on_da_params_ready = self._on_da_params_ready
                                self._current_mapping_page = 0
                                self.nuendo_link.request_da_plugin_params(abs_slot)
                            else:
                                self.nuendo_link._da_mapping_active = False
                            if self.state.shift_held:
                                self._insert_action(abs_slot, 'params_and_edit')
                            else:
                                self._insert_action(abs_slot, 'params')
                            self.state.insert_params_mode = True
                            self._update_upper_row_leds()
                            self._update_lower_row_leds()
                        break
        
        # Lower row release: short press = mute/solo action
        if button_name in self._lower_row_press_time:
            self._lower_row_press_time.pop(button_name)
            if not self._lower_row_handled.get(button_name, True):
                # Not handled by long press → short press action
                self._lower_row_handled[button_name] = True
                for i, btn in enumerate(BUTTONS_LOWER_ROW):
                    if button_name == btn:
                        abs_index = self.state.bank_offset + i
                        if abs_index < self.state.total_tracks:
                            track = self.state.tracks[abs_index]
                            mode = self.state.lower_mode
                            if mode == LOWER_MODE_MUTE:
                                track.is_muted = not track.is_muted
                                self.nuendo_link.send_mute_toggle(i, track.is_muted)
                            elif mode == LOWER_MODE_SOLO:
                                track.is_solo = not track.is_solo
                                self.nuendo_link.send_solo_toggle(i, track.is_solo)
                            elif mode == LOWER_MODE_MONITOR:
                                track.is_monitored = not track.is_monitored
                                self.nuendo_link.send_monitor_toggle(i, track.is_monitored)
                            elif mode == LOWER_MODE_REC:
                                track.is_armed = not track.is_armed
                                self.nuendo_link.send_rec_toggle(i, track.is_armed)
                            self._update_lower_row_leds()
                        break

    # ─────────────────────────────────────────
    # Keyswitch config screen + latch
    # ─────────────────────────────────────────

    def _handle_ks_edit_button(self, button_name):
        """Handle lower-row + arrow buttons while the KS config screen is open.

        Returns True if the button was consumed.
        """
        pg = self.pad_grid
        if button_name in BUTTONS_LOWER_ROW:
            idx = BUTTONS_LOWER_ROW.index(button_name)
            if idx == 0:                       # Chromatic
                pg.set_ks_mode(KS_CHROMATIC)
            elif idx == 1:                     # Naturals
                pg.set_ks_mode(KS_NATURALS)
            elif idx == 3:                     # Latch toggle
                if not pg.toggle_ks_latch():
                    self._release_ks_latch()
            elif idx == 6:                     # Reset overrides
                pg.reset_ks()
            elif idx == 7:                     # Done — close config
                pg.ks_edit = False
            self._update_pad_colors()
            self._update_ks_edit_leds()
            return True
        if button_name in (BTN_LEFT, BTN_RIGHT) and pg.note_layout == LAYOUT_KS16:
            pg.ks_edit_page = 1 - pg.ks_edit_page
            return True
        return False

    def _handle_ks_edit_encoder(self, encoder_index, increment):
        """Edit keyswitch notes from the config screen.

        Encoder for KS #0 sets the start note (regenerates, clears overrides);
        the others set a per-pad override. Paginated for ks16 via ks_edit_page.
        """
        pg = self.pad_grid
        ks_index = pg.ks_edit_page * 8 + encoder_index
        if ks_index >= pg.ks_count():
            return
        if ks_index == 0:
            pg.set_ks_start(pg.ks_start_note + increment)
        else:
            current = pg.ks_effective_notes()[ks_index]
            pg.set_ks_override(ks_index, current + increment)
        self._update_pad_colors()

    def _handle_ks_press(self, ksi, row, col, velocity):
        """Keyswitch press — the KS section is monophonic (one note at a time).

        Momentary: pressing a new KS releases the one currently sounding
        (last-note priority); release sends note-off.
        Latch: the note stays held until the same pad (toggle) or another
        pad (radio) is pressed.
        """
        pg = self.pad_grid
        note = pg.pad_to_note(row, col)
        if note < 0:
            return
        if self.state.accent_enabled:
            velocity = self.state.accent_velocity

        same = (self._ks_held_ksi == ksi)

        # Release whatever KS note is currently sounding (monophonic section)
        if self._ks_held_note is not None:
            self.nuendo_link.send_note_off(self._ks_held_note)
            if self._ks_held_ksi is not None:
                pr, pc = pg._ks_pad_position(self._ks_held_ksi)
                pg.pad_pressed[pr][pc] = False
            self._ks_held_note = None
            self._ks_held_ksi = None
            pg.ks_latched_index = None

        # Latch + re-press of the same pad = leave it off (toggle release)
        if not (pg.ks_latch and same):
            self.nuendo_link.send_note_on(note, velocity)
            self._ks_held_note = note
            self._ks_held_ksi = ksi
            if pg.ks_latch:
                pg.ks_latched_index = ksi
            else:
                pg.pad_pressed[row][col] = True

        self._update_pad_colors()

    def _handle_ks_release(self, ksi, row, col):
        """Keyswitch release. Latch keeps the note; momentary sends note-off."""
        pg = self.pad_grid
        if pg.ks_latch:
            return  # latched: note stays held until re-selected
        # Momentary: release only the pad that is actually sounding
        if self._ks_held_ksi == ksi and self._ks_held_note is not None:
            self.nuendo_link.send_note_off(self._ks_held_note)
            self._ks_held_note = None
            self._ks_held_ksi = None
        pg.pad_pressed[row][col] = False
        self._update_pad_colors()

    def _release_ks_latch(self):
        """Send note-off for any held KS note and clear the held/latch state."""
        if self._ks_held_note is not None:
            try:
                self.nuendo_link.send_note_off(self._ks_held_note)
            except Exception:
                pass
        if self._ks_held_ksi is not None:
            try:
                pr, pc = self.pad_grid._ks_pad_position(self._ks_held_ksi)
                self.pad_grid.pad_pressed[pr][pc] = False
            except Exception:
                pass
        self._ks_held_note = None
        self._ks_held_ksi = None
        self.pad_grid.ks_latched_index = None

    def _update_ks_edit_leds(self):
        """Refresh the lower-row LEDs (delegates to the single LED updater so the
        KS config buttons stay consistent and are not overwritten by the loop)."""
        self._update_lower_row_leds()

    # ─────────────────────────────────────────
    # XY pad (MODE_XY) — relative input, absolute CC output
    # ─────────────────────────────────────────

    def _xy_update(self, event, row, col, pressure):
        """Track pressed-pad pressures and reprocess the centroid on each event."""
        if event == 'press':
            self._xy_pressures[(row, col)] = max(1, int(pressure))
        elif event == 'after':
            if (row, col) in self._xy_pressures:
                self._xy_pressures[(row, col)] = max(1, int(pressure))
        elif event == 'release':
            self._xy_pressures.pop((row, col), None)
        self._xy_process()

    def _xy_process(self):
        """Compute the pressure-weighted centroid and feed its delta into the
        per-axis accumulators (relative). Output is sent as absolute CC."""
        st = self.state
        if not self._xy_pressures:
            # Finger lifted: drop the reference so the next touch causes no jump.
            self._xy_centroid = None
            return
        total = sum(self._xy_pressures.values())
        if total <= 0:
            return
        cx = sum(c * p for (r, c), p in self._xy_pressures.items()) / total
        cy = sum(r * p for (r, c), p in self._xy_pressures.items()) / total

        if self._xy_centroid is None:
            # First contact = reference point only (no movement, no jump).
            self._xy_centroid = (cx, cy)
            return

        # Smooth the centroid (low-pass) to tame pressure jitter.
        a = max(0.0, min(0.9, st.xy_smooth))
        scx = self._xy_centroid[0] * a + cx * (1 - a)
        scy = self._xy_centroid[1] * a + cy * (1 - a)

        dx = scx - self._xy_centroid[0]
        dy = self._xy_centroid[1] - scy   # invert Y: moving up increases the value
        self._xy_centroid = (scx, scy)

        scale = (127.0 / 7.0) * max(0.1, st.xy_sensitivity)
        st.xy_val_x = max(0.0, min(127.0, st.xy_val_x + dx * scale))
        st.xy_val_y = max(0.0, min(127.0, st.xy_val_y + dy * scale))
        self._xy_send()

    def _xy_send(self):
        """Route the current X/Y accumulators to their assigned targets (on change)."""
        st = self.state
        ix = int(round(st.xy_val_x))
        iy = int(round(st.xy_val_y))
        lx, ly = self._xy_last_sent
        if ix != lx:
            self._xy_route_axis(st.xy_cat_x, st.xy_track_param_x, st.xy_cc_x, ix)
        if iy != ly:
            self._xy_route_axis(st.xy_cat_y, st.xy_track_param_y, st.xy_cc_y, iy)
        self._xy_last_sent = (ix, iy)
        self._update_pad_colors()

    def _xy_route_axis(self, category, track_param, cc_num, value):
        """Send one axis value (0-127) to its assigned target on the selected track."""
        st = self.state
        if category == 'cc':
            self.nuendo_link.send_midi_cc_to_notes(cc_num, value)
            return
        # Track parameter (selected track). Volume/Pan are addressed by bank slot.
        slot = st.selected_track_index - st.bank_offset
        norm = value / 127.0
        if track_param == 0:        # Volume
            if 0 <= slot < 8:
                self.nuendo_link.send_volume_change(slot, norm)
        elif track_param == 1:      # Pan
            if 0 <= slot < 8:
                self.nuendo_link.send_pan_change(slot, norm * 2.0 - 1.0)
        else:                       # QC1-8 (index 2..9 -> qc 0..7)
            self.nuendo_link.send_quick_control_change(track_param - 2, norm)

    def xy_axis_label(self, axis):
        """Human label for an axis assignment, e.g. 'Volume', 'QC3', 'CC16'."""
        st = self.state
        cat = st.xy_cat_x if axis == 'x' else st.xy_cat_y
        if cat == 'cc':
            return f"CC{st.xy_cc_x if axis == 'x' else st.xy_cc_y}"
        idx = st.xy_track_param_x if axis == 'x' else st.xy_track_param_y
        return XY_TRACK_PARAMS[idx]

    def _update_xy_pads(self):
        """Light a crosshair at the current X/Y position."""
        from pad_grid import PAD_OFF, PAD_GREEN, PAD_CYAN
        st = self.state
        tx = int(round(st.xy_val_x / 127.0 * 7))
        ty = 7 - int(round(st.xy_val_y / 127.0 * 7))   # row (0=top, 7=bottom)
        for row in range(8):
            for col in range(8):
                if row == ty and col == tx:
                    color = PAD_GREEN
                elif row == ty or col == tx:
                    color = PAD_CYAN
                else:
                    color = PAD_OFF
                try:
                    pad_note = 36 + (7 - row) * 8 + col
                    self._send_midi_to_push([0x90, pad_note, color])
                except Exception:
                    pass

    # ─────────────────────────────────────────
    # Pad handling
    # ─────────────────────────────────────────

    def _handle_pad_press(self, pad_n, pad_ij, velocity):
        """Called when a pad is pressed."""
        row, col = pad_ij
        if row is None:
            return

        if self.state.mode == MODE_XY:
            self._xy_update('press', row, col, velocity)
            return

        if self.pad_grid.scale_mode:
            self._handle_scale_pad(row, col)
            return
        
        # In Overview mode, pads control mute/solo/rec/monitor
        if self.state.mode == MODE_OVERVIEW:
            self._handle_overview_pad(row, col)
            return

        # Keyswitch section is monophonic (latch or momentary): handle separately
        if self.pad_grid.is_keyswitch_layout:
            ksi = self.pad_grid._ks_index_for_pad(row, col)
            if ksi is not None:
                self._handle_ks_press(ksi, row, col, velocity)
                return

        self.pad_grid.pad_pressed[row][col] = True
        
        # Send Note On to Nuendo
        midi_note = self.pad_grid.pad_to_note(row, col)
        if midi_note < 0:
            return  # Inactive pad (outside drum zone)
        
        # Accent: fixed velocity if enabled
        if self.state.accent_enabled:
            velocity = self.state.accent_velocity
        
        self.nuendo_link.send_note_on(midi_note, velocity)
        
        # Note Repeat: start repeating if enabled
        if self.note_repeat.enabled:
            self.note_repeat.note_on(
                midi_note, velocity,
                self.nuendo_link.send_note_on,
                self.nuendo_link.send_note_off
            )
        
        # Light in green all pads with the same MIDI note
        from pad_grid import PAD_GREEN
        for r in range(8):
            for c in range(8):
                if self.pad_grid.note_map[r][c] == midi_note:
                    try:
                        pad_n2 = 36 + (7 - r) * 8 + c
                        self._send_midi_to_push([0x90, pad_n2, PAD_GREEN])
                    except Exception:
                        pass

    def _handle_pad_release(self, pad_n, pad_ij, velocity):
        """Called when a pad is released."""
        row, col = pad_ij
        if row is None:
            return

        if self.state.mode == MODE_XY:
            self._xy_update('release', row, col, velocity)
            return

        if self.pad_grid.scale_mode:
            return
        
        if self.state.mode == MODE_OVERVIEW:
            return

        # Keyswitch section: monophonic release (latch keeps the note held)
        if self.pad_grid.is_keyswitch_layout:
            ksi = self.pad_grid._ks_index_for_pad(row, col)
            if ksi is not None:
                self._handle_ks_release(ksi, row, col)
                return

        self.pad_grid.pad_pressed[row][col] = False

        # Send Note Off to Nuendo
        midi_note = self.pad_grid.pad_to_note(row, col)
        if midi_note < 0:
            return  # Inactive pad
        self.nuendo_link.send_note_off(midi_note)
        
        # Note Repeat: stop repeating
        if self.note_repeat.enabled:
            self.note_repeat.note_off(midi_note, self.nuendo_link.send_note_off)
        
        # Restore color of all pads with the same MIDI note
        for r in range(8):
            for c in range(8):
                if self.pad_grid.note_map[r][c] == midi_note:
                    # Check that no other pad with this note is still pressed
                    still_pressed = any(
                        self.pad_grid.pad_pressed[r2][c2]
                        for r2 in range(8) for c2 in range(8)
                        if self.pad_grid.note_map[r2][c2] == midi_note
                    )
                    if not still_pressed:
                        try:
                            color = self.pad_grid.get_pad_color(r, c)
                            pad_n2 = 36 + (7 - r) * 8 + c
                            self._send_midi_to_push([0x90, pad_n2, color])
                        except Exception:
                            pass

    def _handle_pad_aftertouch(self, pad_n, pad_ij, velocity):
        """Called when pad pressure changes (aftertouch).
        
        Push 2 hardware always sends polyphonic AT (0xA0).
        We convert based on aftertouch_mode:
        - poly: forward as-is (0xA0 per note)
        - channel: send max pressure across all pads as 0xD0
        - off: ignore
        """
        row, col = pad_ij
        if row is None:
            return
        if self.state.mode == MODE_XY:
            self._xy_update('after', row, col, velocity)
            return
        if self.state.aftertouch_mode == AT_OFF:
            return
        if self.state.mode == MODE_OVERVIEW or self.pad_grid.scale_mode:
            return
        midi_note = self.pad_grid.pad_to_note(row, col)
        if midi_note < 0:
            return
        if self.state.aftertouch_mode == AT_CHANNEL:
            # Track per-pad pressure and send the max as channel AT
            if not hasattr(self, '_pad_pressures'):
                self._pad_pressures = {}
            if velocity > 0:
                self._pad_pressures[pad_n] = velocity
            else:
                self._pad_pressures.pop(pad_n, None)
            max_pressure = max(self._pad_pressures.values()) if self._pad_pressures else 0
            self.nuendo_link.send_channel_aftertouch(max_pressure)
        else:
            self.nuendo_link.send_aftertouch(midi_note, velocity)
        if self.note_repeat.enabled and velocity > 0:
            self.note_repeat.update_velocity(midi_note, velocity)

    def _on_playback_note(self, note, is_on):
        """Called when Nuendo plays a note. Lights up/turns off pads."""
        if self.state.mode == MODE_OVERVIEW or self.pad_grid.scale_mode:
            return
        if not self.push:
            return
        
        if is_on:
            self._playback_notes.add(note)
        else:
            self._playback_notes.discard(note)
        
        from pad_grid import PAD_CYAN
        for r in range(8):
            for c in range(8):
                if self.pad_grid.note_map[r][c] == note:
                    pad_note = 36 + (7 - r) * 8 + c
                    # Don't overwrite a pad pressed by the user
                    if self.pad_grid.pad_pressed[r][c]:
                        continue
                    try:
                        if is_on:
                            self._send_midi_to_push([0x90, pad_note, PAD_CYAN])
                        else:
                            color = self.pad_grid.get_pad_color(r, c)
                            self._send_midi_to_push([0x90, pad_note, color])
                    except Exception:
                        pass

    def _handle_scale_pad(self, row, col):
        """Handle pad presses in Scale mode.
        
        push2-python: row 0 = top of Push, row 7 = bottom
        - Rows 0-3 (top): scale selection
        - Rows 6-7 (bottom): root note selection (12 notes on 2 rows)
        """
        from pad_grid import SCALE_NAMES
        
        if row <= 3:
            # Top rows: scales
            scale_idx = row * 8 + col
            if scale_idx < len(SCALE_NAMES):
                self.pad_grid.set_scale(scale_idx)
        elif row == 6:
            # Second to last row: notes C to G# (0-7)
            if col < 8:
                self.pad_grid.set_root(col)
        elif row == 7:
            # Last row: notes A to B (8-11)
            if col < 4:
                self.pad_grid.set_root(8 + col)
        
        self._update_pad_colors()

    def _update_pad_colors(self):
        """Update all pad colors."""
        # Keep the Mix-footer note range in sync with the current pad layout.
        try:
            self.state.pad_note_range = self.pad_grid.note_range_label()
        except Exception:
            pass
        if not self.push or not self.push.midi_is_configured():
            return
        
        # In Overview mode, pads are handled by _update_overview_pads
        if self.state.mode == MODE_OVERVIEW:
            self._update_overview_pads()
            return

        if self.state.mode == MODE_XY:
            self._update_xy_pads()
            return

        if self.pad_grid.scale_mode:
            self._update_scale_mode_pads()
            return
        
        colors = self.pad_grid.get_all_pad_colors()
        for row in range(8):
            for col in range(8):
                try:
                    # Push 2 pads are controlled via Note On
                    # on the Live Port MIDI channel
                    # Note = 36 + row * 8 + col, velocity = color
                    pad_note = 36 + (7 - row) * 8 + col
                    color = colors[row][col]
                    self._send_midi_to_push([0x90, pad_note, color])
                except Exception:
                    pass

    def _update_scale_mode_pads(self):
        """Display the scale selector on the pads."""
        from pad_grid import SCALE_NAMES, NOTE_NAMES, PAD_OFF, PAD_WHITE, PAD_BLUE, PAD_CYAN
        
        for row in range(8):
            for col in range(8):
                color = PAD_OFF
                
                if row <= 3:
                    # Top rows: scales
                    scale_idx = row * 8 + col
                    if scale_idx < len(SCALE_NAMES):
                        if scale_idx == self.pad_grid.scale_index:
                            color = PAD_CYAN
                        else:
                            color = PAD_WHITE
                elif row == 6:
                    # Second to last row: notes C to G# (0-7)
                    if col < 8:
                        if col == self.pad_grid.root_note:
                            color = PAD_BLUE
                        else:
                            color = PAD_WHITE
                elif row == 7:
                    # Last row: notes A to B (8-11)
                    if col < 4:
                        if (8 + col) == self.pad_grid.root_note:
                            color = PAD_BLUE
                        else:
                            color = PAD_WHITE
                
                try:
                    pad_note = 36 + (7 - row) * 8 + col
                    self._send_midi_to_push([0x90, pad_note, color])
                except Exception:
                    pass

    # ─────────────────────────────────────────
    # Mode Overview
    # ─────────────────────────────────────────

    def _handle_overview_pad(self, row, col):
        """Handle a pad press in Overview mode.
        
        - Select held + pad = select track (and optionally navigate bank)
        - Otherwise: Mute/Solo/Mon/Rec toggle via DA (any track) or fallback (bank only)
        """
        state = self.state
        pad_map, _, _ = compute_overview_layout(state.tracks, state.total_tracks, state.overview_page)
        
        track_idx = pad_map.get((row, col))
        if track_idx is None:
            return
        
        track = state.tracks[track_idx]
        target_bank = (track_idx // BANK_SIZE) * BANK_SIZE
        track_in_bank = track_idx - target_bank
        
        # Select held = select track (Shift + pad)
        if state.shift_held:
            state.selected_track_index = track_idx
            for j, t in enumerate(state.tracks):
                t.is_selected = (j == track_idx)
            # Navigate bank if needed
            if target_bank != state.bank_offset:
                banks_diff = (target_bank - state.bank_offset) // BANK_SIZE
                cc = 8 if banks_diff > 0 else 9
                import threading
                def _navigate(diff=abs(banks_diff)):
                    for _ in range(diff):
                        self.nuendo_link.send_cc(cc, 127)
                        time.sleep(0.02)
                        self.nuendo_link.send_cc(cc, 0)
                        time.sleep(0.08)
                    self.state.bank_offset = target_bank
                threading.Thread(target=_navigate, daemon=True).start()
            else:
                self.nuendo_link.send_select_track(track_in_bank)
                self.nuendo_link._ignore_selection_until = time.time() + 5.0
            self._update_overview_pads()
            return
        
        # Toggle Mute/Solo/Mon/Rec
        mode = state.lower_mode
        
        # Try DA for any track (instantaneous, no bank constraint)
        if self.nuendo_link._da_available:
            # Send DA toggle command via SysEx
            # CC 16 = DA toggle, value encodes: track_idx in high bits, function in low bits
            # Instead, send a SysEx with track_idx and function
            da_func = {'mute': 0, 'solo': 1, 'monitor': 2, 'rec': 3}.get(mode, 0)
            self.nuendo_link.send_da_toggle(track_idx, da_func)
            # Update local state
            if mode == LOWER_MODE_MUTE:
                track.is_muted = not track.is_muted
            elif mode == LOWER_MODE_SOLO:
                track.is_solo = not track.is_solo
            elif mode == LOWER_MODE_MONITOR:
                track.is_monitored = not track.is_monitored
            elif mode == LOWER_MODE_REC:
                track.is_armed = not track.is_armed
        else:
            # Fallback: only works for tracks in the current bank
            if target_bank != state.bank_offset:
                return
            if mode == LOWER_MODE_MUTE:
                track.is_muted = not track.is_muted
                self.nuendo_link.send_mute_toggle(track_in_bank, track.is_muted)
            elif mode == LOWER_MODE_SOLO:
                track.is_solo = not track.is_solo
                self.nuendo_link.send_solo_toggle(track_in_bank, track.is_solo)
            elif mode == LOWER_MODE_MONITOR:
                track.is_monitored = not track.is_monitored
                self.nuendo_link.send_monitor_toggle(track_in_bank, track.is_monitored)
            elif mode == LOWER_MODE_REC:
                track.is_armed = not track.is_armed
                self.nuendo_link.send_rec_toggle(track_in_bank, track.is_armed)
        
        self._update_overview_pads()

    def _update_overview_pads(self):
        """Update pad colors in Overview mode using custom palette entries."""
        if not self.push or self.state.mode != MODE_OVERVIEW:
            return
        
        state = self.state
        pad_map, _, total_rows = compute_overview_layout(state.tracks, state.total_tracks, state.overview_page)
        
        any_solo = any(t.is_solo for t in state.tracks if t.name)
        blink_on = getattr(self, '_overview_blink_phase', True)
        
        # Use palette indices 1-64, skipping reserved standard colors
        _reserved = {0, 21, 37, 45, 122, 124, 110, 111, 112, 113, 114, 115, 116, 117}
        palette_idx = 1
        
        for row in range(8):
            for col in range(8):
                track_idx = pad_map.get((row, col))
                pad_note = 36 + (7 - row) * 8 + col
                
                if track_idx is None:
                    self._send_midi_to_push([0x90, pad_note, 0])
                    continue
                
                # Find next non-reserved palette index
                while palette_idx in _reserved:
                    palette_idx += 1
                
                track = state.tracks[track_idx]
                r, g, b = track.color
                should_blink = False
                
                if r == 150 and g == 150 and b == 150:
                    r, g, b = 80, 80, 80
                
                if track.is_armed:
                    r, g, b = 255, 0, 0
                    should_blink = True
                elif track.is_monitored:
                    should_blink = True
                elif track.is_muted:
                    r, g, b = r // 4, g // 4, b // 4
                elif any_solo:
                    if track.is_solo:
                        r = min(255, int(r * 1.4))
                        g = min(255, int(g * 1.4))
                        b = min(255, int(b * 1.4))
                    else:
                        r, g, b = r // 4, g // 4, b // 4
                
                if should_blink and not blink_on:
                    self._send_midi_to_push([0x90, pad_note, 0])
                else:
                    self._set_palette_entry(palette_idx, r, g, b)
                    self._send_midi_to_push([0x90, pad_note, palette_idx])
                
                palette_idx += 1
        
        # Flush palette
        self._send_midi_to_push([0xF0, 0x00, 0x21, 0x1D, 0x01, 0x01, 0x05, 0xF7])

    def _set_palette_entry(self, index, r, g, b):
        """Program an RGB palette entry for Push 2."""
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))
        
        if not hasattr(self, '_modified_palette'):
            self._modified_palette = set()
        self._modified_palette.add(index)
        
        self._send_midi_to_push([
            0xF0, 0x00, 0x21, 0x1D, 0x01, 0x01, 0x03,
            index & 0x7F,
            r & 0x7F, (r >> 7) & 0x01,
            g & 0x7F, (g >> 7) & 0x01,
            b & 0x7F, (b >> 7) & 0x01,
            0x00, 0x00,
            0xF7
        ])

    # ─────────────────────────────────────────
    # Touchstrip
    # ─────────────────────────────────────────

    def _handle_touchstrip(self, value):
        """Handle the Push 2 touchstrip.
        
        value: -8192 to +8191 (signed, center=0)
        In modwheel mode: ignores physical return to center.
        In volume mode: controls the volume of the selected track.
        """
        now = time.time()
        
        if self.state.touchstrip_mode == "volume":
            # Map -8192..+8191 → 0.0..1.0
            normalized = (value + 8192) / 16383.0
            normalized = max(0.0, min(1.0, normalized))
            
            # Update state
            state = self.state
            sel = state.selected_track
            if sel:
                sel.volume = normalized
                sel.volume_db = _to_db(normalized)
            
            # Send to Nuendo
            rel = state.selected_track_index - state.bank_offset
            if 0 <= rel < 8:
                self.nuendo_link.send_volume_change(rel, normalized)
            return
        
        elif self.state.touchstrip_mode == "modwheel":
            cc_val = min(127, max(0, int((value + 8192) * 127 / 16383)))
            port = self.nuendo_link._midi_notes_out or self.nuendo_link._midi_out
            if port and self.nuendo_link._running:
                port.send_message([0xB0, 1, cc_val])
        else:
            pb = value + 8192
            pb = max(0, min(16383, pb))
            lsb = pb & 0x7F
            msb = (pb >> 7) & 0x7F
            port = self.nuendo_link._midi_notes_out or self.nuendo_link._midi_out
            if port and self.nuendo_link._running:
                port.send_message([0xE0, lsb, msb])

    def _setup_button_palette(self):
        """Initialize palette entries for button and pad colors."""
        palette = {
            # Buttons
            BTN_DIM:    (40, 40, 40),       # Dark grey
            BTN_WHITE:  (255, 255, 255),     # Bright white
            BTN_YELLOW: (255, 220, 0),       # Yellow (Mute)
            BTN_BLUE:   (0, 80, 255),        # Blue (Solo)
            BTN_ORANGE: (255, 140, 0),       # Orange (Monitor)
            BTN_RED:    (255, 0, 0),         # Red (Rec)
            # Pads
            122:        (255, 255, 255),     # PAD_WHITE
            124:        (60, 60, 60),        # PAD_WHITE_DIM
            45:         (0, 0, 255),         # PAD_BLUE (root note)
            21:         (0, 255, 0),         # PAD_GREEN (pad pressed)
            37:         (0, 200, 200),       # PAD_CYAN
            117:        (30, 30, 30),        # PAD_BLACK (chromatic accidentals)
            116:        (160, 50, 200),      # PAD_PURPLE (root in chromatic mode)
        }
        for idx, (r, g, b) in palette.items():
            self._set_palette_entry(idx, r, g, b)
        # Apply palette
        self._send_midi_to_push([0xF0, 0x00, 0x21, 0x1D, 0x01, 0x01, 0x05, 0xF7])
        print("  ✓ Button/pad palette initialized")

    def _configure_touchstrip_mode(self):
        """Configure the touchstrip physical mode via SysEx.
        
        Config bits (from the Push 2 MIDI Interface doc):
        bit 0: LEDs controlled by (0=Push, 1=Host)
        bit 1: Host sends (0=Values, 1=Sysex) 
        bit 2: Values sent as (0=PitchBend, 1=ModWheel)
        bit 3: LEDs show (0=Bar, 1=Point)
        bit 4: Bar starts at (0=Bottom, 1=Center)
        bit 5: Do autoreturn (0=No, 1=Yes)
        bit 6: Autoreturn to (0=Bottom, 1=Center)
        """
        if not self.push:
            return
        if self.state.touchstrip_mode == "pitchbend":
            # Pitchbend: Point, autoreturn to center, push controls LEDs
            config = 0b1111000  # = 0x78
        else:
            # Modwheel/Volume: Bar from bottom, no autoreturn, push controls LEDs
            config = 0b0000000  # = 0x00
        self._send_midi_to_push([0xF0, 0x00, 0x21, 0x1D, 0x01, 0x01, 0x17, config, 0xF7])

    def _update_touchstrip_leds(self, value):
        """Update touchstrip LEDs for volume mode (currently disabled)."""
        pass

    def _configure_aftertouch(self):
        """Configure Push 2 for polyphonic aftertouch.
        
        SysEx: F0 00 21 1D 01 01 1E <mode> F7
        mode 0x00 = channel aftertouch
        mode 0x01 = polyphonic (key) aftertouch
        """
        if not self.push:
            return
        self._apply_aftertouch_mode()

    def _apply_aftertouch_mode(self):
        """Apply the current aftertouch mode setting.
        
        The Push 2 hardware is always kept in polyphonic mode (0x01).
        Conversion to channel AT or suppression is done in _handle_pad_aftertouch.
        This avoids issues with push2-python not receiving channel AT callbacks.
        """
        if not self.push:
            return
        # Always keep Push 2 in poly mode — conversion happens in software
        self._send_midi_to_push([0xF0, 0x00, 0x21, 0x1D, 0x01, 0x01, 0x1E, 0x01, 0xF7])
        mode = self.state.aftertouch_mode
        if mode == AT_POLY:
            print("  Aftertouch → Polyphonic")
        elif mode == AT_CHANNEL:
            print("  Aftertouch → Channel (converted from poly)")
        elif mode == AT_OFF:
            print("  Aftertouch → Off")

    def _toggle_selected_track_function(self, function_index):
        """Toggle Mute/Solo/Mon/Rec on the selected track.
        
        function_index: 0=Mute, 1=Solo, 2=Monitor, 3=Rec
        Used by Device and Inserts modes on lower row buttons 5-8.
        """
        state = self.state
        sel = state.selected_track_index
        if sel < 0 or sel >= len(state.tracks):
            return
        track = state.tracks[sel]
        rel = sel - state.bank_offset
        if rel < 0 or rel >= 8:
            return
        
        if function_index == 0:  # Mute
            track.is_muted = not track.is_muted
            self.nuendo_link.send_mute_toggle(rel, track.is_muted)
        elif function_index == 1:  # Solo
            track.is_solo = not track.is_solo
            self.nuendo_link.send_solo_toggle(rel, track.is_solo)
        elif function_index == 2:  # Monitor
            track.is_monitored = not track.is_monitored
            self.nuendo_link.send_monitor_toggle(rel, track.is_monitored)
        elif function_index == 3:  # Rec
            track.is_armed = not track.is_armed
            self.nuendo_link.send_rec_toggle(rel, track.is_armed)
        self._update_lower_row_leds()

    def _apply_velocity_curve(self):
        """Apply the current velocity curve preset to the Push 2 pads."""
        if not self.push:
            return
        import math
        mode = self.state.velocity_curve
        fixed_vel = self.state.accent_velocity  # synced with Accent
        curve = []
        for i in range(128):
            t = i / 127.0  # normalized 0..1
            if mode == VC_LINEAR:
                v = t
            elif mode == VC_LOG:
                v = math.log1p(t * 3) / math.log1p(3)
            elif mode == VC_EXP:
                v = (math.exp(t * 3) - 1) / (math.exp(3) - 1)
            elif mode == VC_SCURVE:
                v = 0.5 * (1 + math.tanh(4 * (t - 0.5)) / math.tanh(2))
            elif mode == VC_FIXED:
                v = fixed_vel / 127.0 if i > 0 else 0
            else:
                v = t
            curve.append(max(0, min(127, int(v * 127))))
        curve[0] = 0  # ensure 0→0
        try:
            self.push.pads.set_velocity_curve(curve)
            if mode == VC_FIXED:
                print(f"  Velocity curve → {mode} (vel={fixed_vel})")
            else:
                print(f"  Velocity curve → {mode}")
        except Exception as e:
            print(f"  Velocity curve error: {e}")

    # ─────────────────────────────────────────
    # Sending MIDI to Push
    # ─────────────────────────────────────────

    def _send_midi_to_push(self, msg):
        """Send a MIDI message to Push 2 to control LEDs/pads."""
        if not self.push:
            return
        try:
            import mido
            if msg[0] == 0xF0:
                # SysEx — mido.Message doesn't handle from_bytes for SysEx
                # Use the MIDI port directly
                sysex_data = msg[1:-1]  # Strip F0 and F7
                midi_msg = mido.Message('sysex', data=sysex_data)
            else:
                midi_msg = mido.Message.from_bytes(msg)
            self.push.send_midi_to_push(midi_msg)
        except Exception:
            pass

    def _set_button_led(self, button_name, on):
        """Turn on or off the LED of a monochrome button."""
        self._set_mono_led(button_name, 127 if on else 0)
    
    def _set_mono_led(self, button_name, value):
        """Control the LED of a monochrome button.
        
        Push 2 values: 0=off, 1=dim, 4=lit, 127=lit
        """
        try:
            for cc, info in self.push.buttons.button_map.items():
                if info.get('Name') == button_name:
                    self._send_midi_to_push([0xB0, cc, value])
                    return
        except Exception:
            pass

    # ─────────────────────────────────────────
    # Mode switching
    # ─────────────────────────────────────────

    def _set_mode(self, new_mode):
        """Change the active mode and update LEDs."""
        old_mode = self.state.mode
        self.state.mode = new_mode
        self.state.insert_params_mode = False  # Always reset when changing mode
        # Leaving Channel Strip: clear the CS-DA ownership flag so the insert
        # viewer's 0x16/0x17 param feedback is no longer suppressed (the two
        # share insert_param_names/values).
        if old_mode == MODE_CHANNEL_STRIP and new_mode != MODE_CHANNEL_STRIP:
            self.state.cs_strip_da_active = False
        self.nuendo_link._da_mapping_active = False
        self.state.active_mapping = None
        self.nuendo_link.send_mode_change(new_mode)
        # Ignore VU peak clips briefly after mode change to avoid false triggers
        self.nuendo_link._vu_ignore_until = time.time() + 3.0
        self._update_all_leds()
        
        if new_mode == MODE_OVERVIEW:
            self.state.overview_page = 0
        elif old_mode == MODE_OVERVIEW:
            self._restore_default_palette()
            self._update_pad_colors()
    
    def _set_cs_page(self, new_page):
        """
        Change the active Channel Strip sub-page and notify the JS side so
        encoder write bindings switch to the right module's params.

        Sends a note-on (channel 9, note 100..106) via activate_subpage; the
        JS Phase 1d activator buttons trigger the sub-page's mActivate action
        which re-routes the 8 encoder Knobs' bindings.

        On drill-in to a strip slot page, triggers DA strip exploration if not
        yet done so that bypass/edit and extended param access are available.
        """
        if self.state.cs_page == new_page:
            return
        self.state.cs_page = new_page
        self.nuendo_link.activate_subpage(new_page)
        self._update_upper_row_leds()
        self._update_lower_row_leds()

        if new_page == 'overview':
            self.state.cs_strip_da_active = False
        else:
            # Apply DA encoder setup when strip is already explored and variant has DA params.
            # If not explored yet, trigger exploration; DA setup will be applied after
            # auto-enum completes via _on_da_params_ready.
            variant = self._cs_page_variant(new_page)
            if getattr(self.nuendo_link, '_da_strip_explored', False):
                self._apply_cs_strip_da_setup(new_page, variant)
            else:
                self.state.cs_strip_da_active = False
                self.nuendo_link.request_da_strip_exploration()
            # Variant switching needs insert collections (strip slots expose 0)
            # — ensure inserts are also explored so the UID fallback works.
            if not getattr(self.nuendo_link, '_da_inserts_ready', False):
                self.nuendo_link.request_da_insert_exploration()
    
    def _cs_page_variant(self, cs_page):
        """Resolve the variant name used as a lookup key for a CS sub-page.

        For strip-slot pages (gate/comp/tools/sat/limiter), reads the loaded
        plugin name from the binding-path slot. The EQ page is a special case:
        it's a section in the binding path but appears as a strip slot in the
        DA tree with plugin_name='EQ' — we return 'EQ' directly.
        """
        if cs_page == 'eq':
            return 'EQ'
        mod_id = _CS_PAGE_TO_MOD_ID.get(cs_page)
        if mod_id is None:
            return None
        slot = self.state.channel_strip.slots.get(mod_id)
        return slot.plugin_name if (slot and slot.plugin_name) else None

    def _resolve_da_slot_for_variant(self, variant):
        """Find the actual DA strip slot index that currently hosts the given
        variant plugin. Custom strip layouts can put e.g. DeEsser at the
        Saturator physical position, so the binding-path mod_id doesn't always
        match the DA tree's slot index. Returns DA slot (16-20) or -1 if not found.
        """
        if not variant:
            return -1
        cache = getattr(self.nuendo_link, '_da_strip_slot_cache', []) or []
        for entry in cache:
            if entry and entry.get('plugin_name') == variant:
                strip_si = entry.get('slot_index', -1)
                if 0 <= strip_si <= 5:
                    return 16 + strip_si
        return -1

    def _eq_da_encoder_indices(self, band_idx_0based):
        """Compute the 8 DA param indices for the EQ page given the selected band.

        DA enum for the ChannelEQ slot:
          Band N (1-based): On=5+(N-1)*6, Type=6+(N-1)*6, Gain=7+(N-1)*6,
                            Freq=8+(N-1)*6, Q=9+(N-1)*6

        Encoder layout (Ableton EQ-Eight style):
          0 = band selector (no DA, handled in encoder handler)
          1 = Type, 2 = Freq, 3 = Q, 4 = Gain (for selected band)
          5 = HC Freq, 6 = LC Freq, 7 = PreGain (PreFilter — Phase 2, not yet)
        """
        b = max(0, min(3, band_idx_0based))
        base = b * 6
        type_idx = 6 + base
        gain_idx = 7 + base
        freq_idx = 8 + base
        q_idx    = 9 + base
        return [-1, type_idx, freq_idx, q_idx, gain_idx, -1, -1, -1]

    def _apply_cs_strip_da_setup(self, cs_page, variant):
        """Configure DA encoders for a CS sub-page variant that has extended DA params.

        Returns True if DA setup was applied and cs_strip_da_active set, False otherwise.
        """
        # EQ uses dynamic param indices that depend on the selected band.
        if cs_page == 'eq':
            param_indices = self._eq_da_encoder_indices(self.state.eq_selected_band)
        else:
            param_indices = _VARIANT_DA_ENC_SETUP.get((cs_page, variant))
        if param_indices is None:
            self.state.cs_strip_da_active = False
            return False

        # Resolve the actual DA slot by scanning the strip cache for the variant
        # (handles custom Cubase strip layouts where the binding-path mod_id
        # doesn't match the DA tree position).
        da_slot = self._resolve_da_slot_for_variant(variant)
        if da_slot < 0:
            # Fall back to standard mapping if not found in cache yet
            mod_id = _CS_PAGE_TO_MOD_ID.get(cs_page)
            if mod_id is None or not (0x10 <= mod_id <= 0x14):
                self.state.cs_strip_da_active = False
                return False
            da_slot = 16 + (mod_id - 0x10)
        strip_si = da_slot - getattr(self.nuendo_link, 'DA_STRIP_SLOT_OFFSET', 16)
        da_params = getattr(self.nuendo_link, '_da_strip_params', {}).get(strip_si, {})

        names = [''] * 8
        for enc_i, pidx in enumerate(param_indices):
            if pidx >= 0:
                info = da_params.get(pidx)
                if info:
                    names[enc_i] = info.get('name', '')

        # EQ page: Enc 1 = band selector, Enc 6-8 = PreFilter LC/HC/PreGain (binding path).
        # Populate names manually since these encs have no DA tag.
        if cs_page == 'eq':
            names[0] = "BAND"
            names[5] = "LC Freq"
            names[6] = "HC Freq"
            names[7] = "PreGain"

        self.state.insert_param_names = names
        self.state.insert_param_values = [''] * 8
        if cs_page == 'eq':
            self.state.insert_param_values[0] = str(self.state.eq_selected_band + 1)
        self.state.cs_strip_da_active = True

        self.nuendo_link.send_da_encoder_setup(da_slot, param_indices)
        named = [n for n in names if n]
        print(f"  ✓ CS strip DA: {variant} [{', '.join(named)}]")
        return True

    def _restore_default_palette(self):
        """Restore Push 2 palette by resetting the Push."""
        if not self.push:
            return
        try:
            # Reset modified entries to black
            # then let push2_python restore its colors
            for idx in getattr(self, '_modified_palette', set()):
                self._send_midi_to_push([
                    0xF0, 0x00, 0x21, 0x1D, 0x01, 0x01, 0x03,
                    idx & 0x7F, 0, 0, 0, 0, 0, 0, 0, 0, 0xF7
                ])
            self._modified_palette = set()
            # Reapply to force a refresh
            self._send_midi_to_push([
                0xF0, 0x00, 0x21, 0x1D, 0x01, 0x01, 0x05, 0xF7
            ])
        except Exception:
            pass

    # ─────────────────────────────────────────
    # LED management
    # ─────────────────────────────────────────

    def _update_all_leds(self):
        """Update all LEDs based on state."""
        if not self.push or not self.push.midi_is_configured():
            return
        self._update_mode_leds()
        self._update_nav_leds()
        if self.state.mode == MODE_CR:
            self._update_cr_leds()
        else:
            self._update_upper_row_leds()
            self._update_lower_row_leds()
        self._update_repeat_leds()
        self._update_accent_led()

        # Utility buttons
        try:
            self.push.buttons.set_button_color(BTN_SHIFT, LED_DIM_GREY)
            if BTN_UNDO:
                self.push.buttons.set_button_color(BTN_UNDO, LED_DIM_GREY)
            if BTN_SCALE:
                color = LED_CYAN if self.pad_grid.scale_mode else LED_DIM_GREY
                self.push.buttons.set_button_color(BTN_SCALE, color)
            
            # Note: always dim lit
            self.push.buttons.set_button_color(BTN_MODE_NOTE, LED_DIM_GREY)
            
            # Layout (CC 31, monochrome): always bright
            self._send_midi_to_push([0xB0, 31, 127])
            
            # Octave Up/Down (CC 55/54, monochrome): off in Overview, bright otherwise
            if self.state.mode == MODE_OVERVIEW:
                self._send_midi_to_push([0xB0, 55, 0])
                self._send_midi_to_push([0xB0, 54, 0])
            else:
                self._send_midi_to_push([0xB0, 55, 127])
                self._send_midi_to_push([0xB0, 54, 127])
            
            # Page Left/Right (monochrome): bright in Overview, off otherwise
            self._set_mono_led(BTN_PAGE_LEFT, 127 if self.state.mode == MODE_OVERVIEW else 0)
            self._set_mono_led(BTN_PAGE_RIGHT, 127 if self.state.mode == MODE_OVERVIEW else 0)
            
            # Play (CC 85, colored): white when stopped, green or purple when playing
            if self.state.is_playing:
                if getattr(self.state, 'cycle_active', False):
                    self._send_midi_to_push([0xB0, 85, 26])  # Purple (loop)
                else:
                    self._send_midi_to_push([0xB0, 85, 21])  # Green (playing)
            else:
                self._send_midi_to_push([0xB0, 85, BTN_WHITE])
            
            # Rec (CC 86, colored): orange=idle, blink red=armed, solid red=recording
            self._update_rec_led()
            
            self._update_automate_led()
            # Metronome (monochrome)
            if BTN_METRONOME:
                self._set_mono_led(BTN_METRONOME, 127 if self.state.metronome_on else 0)
            
            # Fixed Length / Cycle (CC 90, monochrome)
            self._send_midi_to_push([0xB0, 90, 127 if self.state.cycle_active else 0])
            
            # Add Track (CC 53, monochrome) : lit at all times
            self._send_midi_to_push([0xB0, 53, 127])
            
            # Duplicate (CC 88, monochrome) : lit at all times
            self._send_midi_to_push([0xB0, 88, 127])
            
            # New (CC 87, monochrome) : lit (New Track Version)
            self._send_midi_to_push([0xB0, 87, 127])
            
            # User (CC 59, monochrome) : lit at all times
            self._send_midi_to_push([0xB0, 59, 127])
            
            # Delete (CC 118, monochrome) : lit at all times
            self._send_midi_to_push([0xB0, 118, 127])
            
            # Setup (CC 30, monochrome) : bright when in Setup mode
            self._send_midi_to_push([0xB0, 30, 127 if self.state.mode == MODE_SETUP else 40])
            
            # Add Device (monochrome) : lit at all times
            self._set_mono_led(BTN_ADD_DEVICE, 127)

            # Select (monochrome) : lit at all times — it modifies the Master
            # Encoder (CR Main <-> Phones), so keep it visibly available.
            self._set_mono_led(BTN_SELECT, 127)
        except Exception:
            pass

    def _update_mode_leds(self):
        """Light the active mode button, turn off others."""
        if not self.push:
            return
        
        mode = self.state.mode
        buttons_modes = {
            BTN_MODE_VOLUME:  [MODE_VOLUME, MODE_TRACK, MODE_CHANNEL_STRIP],
            BTN_MODE_SENDS:   [MODE_SENDS, MODE_PAN],
            BTN_DEVICE:       [MODE_DEVICE],
            BTN_MODE_INSERTS: [MODE_INSERTS, MODE_BROWSER],
            BTN_MODE_OVERVIEW: [MODE_OVERVIEW],
            BTN_MODE_NOTE:    [MODE_MIDICC],
        }
        
        for btn, modes in buttons_modes.items():
            if mode in modes:
                self.push.buttons.set_button_color(btn, MODE_COLORS.get(mode, LED_WHITE))
            else:
                self.push.buttons.set_button_color(btn, LED_DIM_GREY)

    def _update_nav_leds(self):
        """LEDs for the ◄ ► navigation buttons."""
        if not self.push:
            return
        
        state = self.state
        
        # When in insert params mode with a mapping, show page navigation
        if state.mode == MODE_INSERTS and state.insert_params_mode:
            if getattr(self.nuendo_link, '_da_mapping_active', False) and state.active_mapping:
                page_idx = getattr(self, '_current_mapping_page', 0)
                pages = state.active_mapping.get("pages", [])
                left_color = LED_WHITE if page_idx > 0 else LED_DIM_GREY
                right_color = LED_WHITE if page_idx < len(pages) - 1 else LED_DIM_GREY
                self.push.buttons.set_button_color(BTN_LEFT, left_color)
                self.push.buttons.set_button_color(BTN_RIGHT, right_color)
                return
        
        left_color  = LED_WHITE if state.can_go_bank_left() else LED_DIM_GREY
        right_color = LED_WHITE if state.can_go_bank_right() else LED_DIM_GREY
        
        self.push.buttons.set_button_color(BTN_LEFT, left_color)
        self.push.buttons.set_button_color(BTN_RIGHT, right_color)

    def _update_upper_row_leds(self):
        """Upper row LEDs (CC 102-109)."""
        if not self.push:
            return

        state = self.state

        # ── XY pad: upper row disabled (all off) ──
        if state.mode == MODE_XY:
            for i in range(8):
                try:
                    self._send_midi_to_push([0xB0, 102 + i, LED_OFF])
                except Exception:
                    pass
            return

        # ── Setup mode: upper row = page tabs ──
        if state.mode == MODE_SETUP:
            SETUP_PAGES = ['MIDI Ctrl', 'Vel Curve', 'CR Knob', None, None, None, None, 'About']
            for i in range(8):
                cc = 102 + i
                try:
                    if i < len(SETUP_PAGES) and SETUP_PAGES[i] is not None:
                        color = BTN_WHITE if i == state.setup_page else BTN_DIM
                    else:
                        color = LED_OFF
                    self._send_midi_to_push([0xB0, cc, color])
                except Exception:
                    pass
            return
        
        # ── MIDI CC mode: upper row = edit mode indicator ──
        if state.mode == MODE_MIDICC:
            for i in range(8):
                cc = 102 + i
                try:
                    self._send_midi_to_push([0xB0, cc, BTN_WHITE if state.cc_edit_mode else BTN_DIM])
                except Exception:
                    pass
            return
        
        # ── Sends mode: upper row = send on/off ──
        if state.mode == MODE_SENDS:
            for i in range(8):
                cc = 102 + i
                try:
                    if state.send_on[i]:
                        self._send_midi_to_push([0xB0, cc, BTN_WHITE])
                    elif state.send_names[i]:
                        self._send_midi_to_push([0xB0, cc, BTN_DIM])
                    else:
                        self._send_midi_to_push([0xB0, cc, LED_OFF])
                except Exception:
                    pass
            return
        
        # ── Inserts mode: upper row ──
        if state.mode == MODE_INSERTS:
            if state.insert_params_mode:
                # Parameters mode: all buttons = BACK (dim except first = white)
                for i in range(8):
                    cc = 102 + i
                    try:
                        self._send_midi_to_push([0xB0, cc, BTN_WHITE if i == 0 else BTN_DIM])
                    except Exception:
                        pass
            else:
                # List view: slots with plugin = white
                ibo = state.insert_bank_offset
                for i in range(8):
                    cc = 102 + i
                    try:
                        abs_slot = ibo + i
                        name = state.current_insert_names[abs_slot] if abs_slot < len(state.current_insert_names) else ''
                        if name:
                            self._send_midi_to_push([0xB0, cc, BTN_WHITE])
                        else:
                            self._send_midi_to_push([0xB0, cc, LED_OFF])
                    except Exception:
                        pass
            return
        
        # ── Channel Strip mode: upper row OFF (drill-in nav, not state) ──
        if state.mode == MODE_CHANNEL_STRIP:
            for i in range(8):
                try:
                    self._send_midi_to_push([0xB0, 102 + i, LED_OFF])
                except Exception:
                    pass
            return

        # ── Browser mode: upper row ──
        if state.mode == MODE_BROWSER:
            if state.browser_phase == "slot_select":
                # All 8 slots are selectable
                for i in range(8):
                    cc = 102 + i
                    try:
                        self._send_midi_to_push([0xB0, cc, BTN_WHITE])
                    except Exception:
                        pass
            elif state.browser_phase == "plugin_list":
                # Light buttons for visible plugins
                total = len(state.browser_plugins)
                for i in range(8):
                    cc = 102 + i
                    try:
                        plugin_idx = state.browser_scroll + i
                        if plugin_idx < total:
                            self._send_midi_to_push([0xB0, cc, BTN_WHITE])
                        else:
                            self._send_midi_to_push([0xB0, cc, LED_OFF])
                    except Exception:
                        pass
            return
        
        for i in range(8):
            abs_index = state.bank_offset + i
            cc = 102 + i
            try:
                if abs_index >= state.total_tracks:
                    self._send_midi_to_push([0xB0, cc, LED_OFF])
                elif state.mode == MODE_SENDS:
                    track = state.tracks[abs_index]
                    send_on = track.send_enabled[state.current_send]
                    self._send_midi_to_push([0xB0, cc, BTN_WHITE if send_on else BTN_DIM])
                elif abs_index == state.selected_track_index:
                    self._send_midi_to_push([0xB0, cc, BTN_WHITE])
                else:
                    self._send_midi_to_push([0xB0, cc, BTN_DIM])
            except Exception:
                pass

    # ─────────────────────────────────────────
    # LED management (continued)
    # ─────────────────────────────────────────

    def _update_cr_leds(self):
        """Update Control Room mode LEDs."""
        if not self.push or self.state.mode != MODE_CR:
            return
        
        page_def = CR_PAGES.get(self.cr_state.page, {})
        
        # Upper row (CC 102-109)
        upper = page_def.get('upper_btns', [])
        for i in range(8):
            cc = 102 + i
            if i < len(upper) and upper[i] is not None:
                label, btn_cc, param_id, is_toggle = upper[i]
                if param_id is not None and self.cr_state.get_toggle(param_id):
                    self._send_midi_to_push([0xB0, cc, BTN_WHITE])
                else:
                    self._send_midi_to_push([0xB0, cc, BTN_DIM])
            else:
                self._send_midi_to_push([0xB0, cc, LED_OFF])
        
        # Lower row (CC 20-27)
        lower = page_def.get('lower_btns', [])
        for i in range(8):
            cc = 20 + i
            if i < 4:
                if i < len(lower) and lower[i] is not None:
                    param_id = lower[i][2] if len(lower[i]) >= 3 else None
                    if param_id is not None and self.cr_state.get_toggle(param_id):
                        self._send_midi_to_push([0xB0, cc, BTN_WHITE])
                    else:
                        self._send_midi_to_push([0xB0, cc, BTN_DIM])
                else:
                    self._send_midi_to_push([0xB0, cc, LED_OFF])
            else:
                page_idx = i - 4
                if page_idx < len(CR_PAGE_NAMES):
                    if page_idx == self.cr_state.page:
                        self._send_midi_to_push([0xB0, cc, BTN_WHITE])
                    else:
                        self._send_midi_to_push([0xB0, cc, BTN_DIM])
                else:
                    self._send_midi_to_push([0xB0, cc, LED_OFF])

    def _update_rec_led(self):
        """Update Record button LED: orange=idle, blink red=armed, solid red=recording."""
        if not self.push:
            return
        try:
            if self.state.is_recording:
                # Solid red when recording
                self._send_midi_to_push([0xB0, 86, LED_RED])
            elif any(t.is_armed for t in self.state.tracks if t.name):
                # Blink red when armed but not recording
                phase = getattr(self, '_rec_blink_phase', False)
                self._send_midi_to_push([0xB0, 86, LED_RED if phase else LED_DIM_GREY])
            else:
                # Orange when idle
                self._send_midi_to_push([0xB0, 86, LED_ORANGE])
        except Exception:
            pass

    def _update_automate_led(self):
        """Update Automate button LED (CC 89) from the SELECTED track only.

        Write → red, Read → green, neither → white. (The API only reports
        automation mode for the current bank, so a reliable project-wide
        indicator isn't possible — we keep it to the selected track.)
        """
        if not (self.push and BTN_AUTOMATE):
            return
        try:
            sel = self.state.selected_track
            if sel and sel.automation_write:
                self._send_midi_to_push([0xB0, 89, 4])     # Red
            elif sel and sel.automation_read:
                self._send_midi_to_push([0xB0, 89, 21])    # Green
            else:
                self._send_midi_to_push([0xB0, 89, BTN_WHITE])
        except Exception:
            pass

    def _update_accent_led(self):
        """Update Accent button LED."""
        if not self.push:
            return
        try:
            self._set_mono_led(BTN_ACCENT, 127 if self.state.accent_enabled else 1)
        except Exception:
            pass

    def _update_repeat_leds(self):
        """Update Repeat mode LEDs."""
        if not self.push:
            return
        try:
            # Repeat button: always lit, bright if active, dim otherwise
            self._set_mono_led(BTN_REPEAT, 127 if self.note_repeat.enabled else 40)
            
            # Subdivision buttons (CC 36-43)
            for i in range(8):
                if self.note_repeat.enabled:
                    if i == self.note_repeat.subdivision_index:
                        self._send_midi_to_push([0xB0, 36 + i, LED_CYAN])
                    else:
                        self._send_midi_to_push([0xB0, 36 + i, LED_DIM_GREY])
                else:
                    self._send_midi_to_push([0xB0, 36 + i, 0])
        except Exception:
            pass
    
    def _sync_repeat_state(self):
        """Sync NoteRepeat data to state for display."""
        self.state.repeat_enabled = self.note_repeat.enabled
        self.state.repeat_tempo = self.note_repeat.tempo
        self.state.repeat_subdivision = self.note_repeat.subdivision_name

    def _update_mute_solo_leds(self):
        """Update Mute and Solo button LEDs based on active mode."""
        if not self.push:
            return
        try:
            mode = self.state.lower_mode
            # Mute (CC 60): green default, purple in Monitor mode
            if mode == LOWER_MODE_MONITOR:
                self._send_midi_to_push([0xB0, 60, LED_PURPLE])
            else:
                self._send_midi_to_push([0xB0, 60, LED_GREEN])
            # Solo (CC 61): green default, red in Rec mode
            if mode == LOWER_MODE_REC:
                self._send_midi_to_push([0xB0, 61, 4])  # 4 = red in the palette
            else:
                self._send_midi_to_push([0xB0, 61, LED_GREEN])
        except Exception:
            pass

    def _update_lower_row_leds(self):
        """Lower row LEDs based on mode (mute/solo/monitor/rec)."""
        if not self.push:
            return

        state = self.state

        # ── XY pad: lower 1/2 = X/Y category (track=white, cc=yellow); 5-8 = M/S/Mon/R ──
        if state.mode == MODE_XY:
            sel = state.selected_track_index
            track = state.tracks[sel] if 0 <= sel < len(state.tracks) else None
            colors = [LED_OFF] * 8
            colors[0] = BTN_YELLOW if state.xy_cat_x == 'cc' else BTN_WHITE
            colors[1] = BTN_YELLOW if state.xy_cat_y == 'cc' else BTN_WHITE
            if track:
                colors[4] = BTN_YELLOW if track.is_muted else BTN_DIM
                colors[5] = BTN_BLUE if track.is_solo else BTN_DIM
                colors[6] = BTN_ORANGE if track.is_monitored else BTN_DIM
                colors[7] = BTN_RED if track.is_armed else BTN_DIM
            for i in range(8):
                try:
                    self._send_midi_to_push([0xB0, 20 + i, colors[i]])
                except Exception:
                    pass
            return

        # ── Keyswitch config screen: lower row = config buttons ──
        if self.pad_grid.ks_edit:
            pg = self.pad_grid
            colors = [LED_OFF] * 8
            colors[0] = BTN_WHITE if pg.ks_mode == KS_CHROMATIC else BTN_DIM  # Chromatic
            colors[1] = BTN_WHITE if pg.ks_mode == KS_NATURALS else BTN_DIM   # Naturals
            colors[3] = LED_ORANGE if pg.ks_latch else BTN_DIM                # Latch
            colors[6] = BTN_DIM   # Reset
            colors[7] = BTN_DIM   # Done
            for i in range(8):
                try:
                    self._send_midi_to_push([0xB0, 20 + i, colors[i]])
                except Exception:
                    pass
            return

        # ── Setup mode: lower row = option buttons ──
        if state.mode == MODE_SETUP:
            AT_OPTIONS = [AT_POLY, AT_CHANNEL, AT_OFF]
            VC_OPTIONS = [VC_LINEAR, VC_LOG, VC_EXP, VC_SCURVE, VC_FIXED]
            for i in range(8):
                cc = 20 + i
                try:
                    if i == 7:
                        self._send_midi_to_push([0xB0, cc, BTN_DIM])  # Rescan (all pages)
                    elif state.setup_page == 0:
                        if i < 3:
                            is_sel = (state.aftertouch_mode == AT_OPTIONS[i])
                            self._send_midi_to_push([0xB0, cc, BTN_WHITE if is_sel else BTN_DIM])
                        else:
                            self._send_midi_to_push([0xB0, cc, LED_OFF])
                    elif state.setup_page == 1:
                        if i < len(VC_OPTIONS):
                            is_sel = (state.velocity_curve == VC_OPTIONS[i])
                            self._send_midi_to_push([0xB0, cc, BTN_WHITE if is_sel else BTN_DIM])
                        else:
                            self._send_midi_to_push([0xB0, cc, LED_OFF])
                    elif state.setup_page == 2:
                        # CR Knob default: button 1 = Main, button 2 = Phones
                        phones_default = getattr(state, 'cr_phones_default', False)
                        if i == 0:
                            self._send_midi_to_push([0xB0, cc, BTN_WHITE if not phones_default else BTN_DIM])
                        elif i == 1:
                            self._send_midi_to_push([0xB0, cc, BTN_WHITE if phones_default else BTN_DIM])
                        else:
                            self._send_midi_to_push([0xB0, cc, LED_OFF])
                    else:
                        self._send_midi_to_push([0xB0, cc, LED_OFF])
                except Exception:
                    pass
            return
        
        # ── Channel Strip drill-down: lower row mirrors footer pill states
        # (set by the renderer each frame in state.cs_footer_pill_states) ──
        if state.mode == MODE_CHANNEL_STRIP and state.cs_page != 'overview':
            pill_states = getattr(state, 'cs_footer_pill_states', [None] * 8)
            for i in range(8):
                cc = 20 + i
                try:
                    s = pill_states[i] if i < len(pill_states) else None
                    if s is None:
                        self._send_midi_to_push([0xB0, cc, LED_OFF])
                    else:
                        self._send_midi_to_push([0xB0, cc, BTN_WHITE if s else BTN_DIM])
                except Exception:
                    pass
            return

        # ── Channel Strip overview: lower row mirrors section bypass state ──
        if state.mode == MODE_CHANNEL_STRIP and state.cs_page == 'overview':
            cs = state.channel_strip
            # Compute the "ON" state for each lower-row position
            #   0 = Gate, 1 = Comp, 2 = EQ, 3 = Tools, 4 = Sat, 5 = Limiter
            #   6 = Phase, 7 = unused
            def _slot_active(mod_id):
                slot = cs.slots.get(mod_id)
                if slot is None or not slot.plugin_name:
                    return False
                return not slot.bypassed

            eq_bypass_val = cs.eq.get(0x7F, {}).get('value', 0)
            eq_bypass_disp = cs.eq.get(0x7F, {}).get('display', '')
            # Cross-check via DA mirror (more reliable for EQ section bypass)
            eq_bypass_da = state.da_strip_toggle_values.get(('EQ', 0), None)
            if eq_bypass_da is not None:
                eq_active = eq_bypass_da < 0.5
            else:
                eq_active = not ((eq_bypass_disp == 'On') or (eq_bypass_val >= 64))

            phase_val = cs.prefilter.get(0x01, {}).get('value', 0)
            phase_disp = cs.prefilter.get(0x01, {}).get('display', '')
            phase_on = (phase_disp == 'On') or (phase_val >= 64)

            editor_open = bool(getattr(state, 'editor_open', False))
            # Lower 1-6 = Bypass indicators: lit AMBER when the section is
            # BYPASSED (matches the on-screen pills + Nuendo's bypass button).
            # Lower 7 = Phase On/Off (white when on). Lower 8 = Edit (white).
            bypassed = [
                not _slot_active(0x10),  # Gate
                not _slot_active(0x11),  # Comp
                not eq_active,           # EQ
                not _slot_active(0x12),  # Tools
                not _slot_active(0x13),  # Sat
                not _slot_active(0x14),  # Limiter
            ]
            for i in range(6):
                cc = 20 + i
                try:
                    self._send_midi_to_push(
                        [0xB0, cc, BTN_YELLOW if bypassed[i] else BTN_DIM])
                except Exception:
                    pass
            try:
                self._send_midi_to_push(
                    [0xB0, 26, BTN_WHITE if phase_on else BTN_DIM])      # Lower 7
                self._send_midi_to_push(
                    [0xB0, 27, BTN_WHITE if editor_open else BTN_DIM])   # Lower 8
            except Exception:
                pass
            return

        # ── MIDI CC mode: lower row = toggle on/off ──
        if state.mode == MODE_MIDICC:
            for i in range(8):
                cc = 20 + i
                try:
                    if state.cc_values[i] > 0:
                        self._send_midi_to_push([0xB0, cc, BTN_WHITE])
                    else:
                        self._send_midi_to_push([0xB0, cc, BTN_DIM])
                except Exception:
                    pass
            return
        
        # ── Device mode: button 1 = OPEN UI, buttons 5-8 = M/S/Mon/R ──
        if state.mode == MODE_DEVICE:
            sel = state.selected_track_index
            track = state.tracks[sel] if 0 <= sel < len(state.tracks) else None
            for i in range(8):
                cc = 20 + i
                try:
                    if i == 0:
                        self._send_midi_to_push([0xB0, cc, BTN_WHITE])
                    elif i == 4 and track:
                        self._send_midi_to_push([0xB0, cc, BTN_YELLOW if track.is_muted else BTN_DIM])
                    elif i == 5 and track:
                        self._send_midi_to_push([0xB0, cc, BTN_BLUE if track.is_solo else BTN_DIM])
                    elif i == 6 and track:
                        self._send_midi_to_push([0xB0, cc, BTN_ORANGE if track.is_monitored else BTN_DIM])
                    elif i == 7 and track:
                        self._send_midi_to_push([0xB0, cc, BTN_RED if track.is_armed else BTN_DIM])
                    else:
                        self._send_midi_to_push([0xB0, cc, LED_OFF])
                except Exception:
                    pass
            return
        
        # ── Sends mode: LEDs = pre/post ──
        if state.mode == MODE_SENDS:
            for i in range(8):
                cc = 20 + i
                try:
                    if not state.send_names[i]:
                        self._send_midi_to_push([0xB0, cc, LED_OFF])
                    elif state.send_prepost[i]:
                        self._send_midi_to_push([0xB0, cc, BTN_BLUE])   # Pre-fader
                    else:
                        self._send_midi_to_push([0xB0, cc, BTN_ORANGE]) # Post-fader
                except Exception:
                    pass
            return
        
        # ── Inserts mode: LEDs = bypass state or actions in params mode ──
        if state.mode == MODE_INSERTS:
            sel = state.selected_track_index
            track = state.tracks[sel] if 0 <= sel < len(state.tracks) else None
            if state.insert_params_mode:
                # Parameters mode: action buttons 1-3, then M/S/Mon/R on 5-8
                slot = state.selected_insert_slot
                is_active = state.current_insert_active[slot] if slot < len(state.current_insert_active) else False
                for i in range(8):
                    cc = 20 + i
                    try:
                        if i == 0:
                            self._send_midi_to_push([0xB0, cc, BTN_WHITE])   # OPEN UI
                        elif i == 1:
                            self._send_midi_to_push([0xB0, cc, BTN_BLUE if is_active else BTN_ORANGE])  # BYPASS
                        elif i == 2:
                            self._send_midi_to_push([0xB0, cc, BTN_RED])     # DEACTIVATE
                        elif i == 4 and track:
                            self._send_midi_to_push([0xB0, cc, BTN_YELLOW if track.is_muted else BTN_DIM])
                        elif i == 5 and track:
                            self._send_midi_to_push([0xB0, cc, BTN_BLUE if track.is_solo else BTN_DIM])
                        elif i == 6 and track:
                            self._send_midi_to_push([0xB0, cc, BTN_ORANGE if track.is_monitored else BTN_DIM])
                        elif i == 7 and track:
                            self._send_midi_to_push([0xB0, cc, BTN_RED if track.is_armed else BTN_DIM])
                        else:
                            self._send_midi_to_push([0xB0, cc, LED_OFF])
                    except Exception:
                        pass
            else:
                # List view: bypass on all 8 slots
                ibo = state.insert_bank_offset
                for i in range(8):
                    cc = 20 + i
                    try:
                        abs_slot = ibo + i
                        name = state.current_insert_names[abs_slot] if abs_slot < len(state.current_insert_names) else ''
                        active = state.current_insert_active[abs_slot] if abs_slot < len(state.current_insert_active) else False
                        if not name:
                            self._send_midi_to_push([0xB0, cc, LED_OFF])
                        elif active:
                            self._send_midi_to_push([0xB0, cc, BTN_BLUE])
                        else:
                            self._send_midi_to_push([0xB0, cc, BTN_DIM])
                    except Exception:
                        pass
            return
        
        # ── Browser mode: LEDs ──
        if state.mode == MODE_BROWSER:
            for i in range(8):
                cc = 20 + i
                try:
                    if state.browser_phase == "slot_select":
                        if i == 7:
                            self._send_midi_to_push([0xB0, cc, BTN_RED])
                        else:
                            self._send_midi_to_push([0xB0, cc, LED_OFF])
                    elif state.browser_phase == "plugin_list":
                        if i == 0:
                            # Collection cycle button
                            self._send_midi_to_push([0xB0, cc, BTN_YELLOW])
                        elif i == 7:
                            # Back button
                            self._send_midi_to_push([0xB0, cc, BTN_RED])
                        else:
                            self._send_midi_to_push([0xB0, cc, LED_OFF])
                except Exception:
                    pass
            return
        
        mode = state.lower_mode
        
        # LED for the Mute (CC 60) and Solo (CC 61) buttons
        # Mute/Mon share the same button, Solo/Rec too
        try:
            if mode == LOWER_MODE_MUTE:
                self._send_midi_to_push([0xB0, 60, BTN_YELLOW])
            elif mode == LOWER_MODE_MONITOR:
                self._send_midi_to_push([0xB0, 60, BTN_ORANGE])
            else:
                self._send_midi_to_push([0xB0, 60, BTN_DIM])
            
            if mode == LOWER_MODE_SOLO:
                self._send_midi_to_push([0xB0, 61, BTN_BLUE])
            elif mode == LOWER_MODE_REC:
                self._send_midi_to_push([0xB0, 61, BTN_RED])
            else:
                self._send_midi_to_push([0xB0, 61, BTN_DIM])
        except Exception:
            pass
        
        # LEDs for the 8 lower buttons (CC 20-27)
        # Color reflects the active mode
        MODE_BTN_COLORS = {
            LOWER_MODE_MUTE: BTN_YELLOW,
            LOWER_MODE_SOLO: BTN_BLUE,
            LOWER_MODE_MONITOR: BTN_ORANGE,
            LOWER_MODE_REC: BTN_RED,
        }
        active_color = MODE_BTN_COLORS.get(mode, BTN_DIM)
        
        for i in range(8):
            abs_index = state.bank_offset + i
            cc = 20 + i
            try:
                if abs_index >= state.total_tracks:
                    self._send_midi_to_push([0xB0, cc, LED_OFF])
                    continue
                
                track = state.tracks[abs_index]
                
                if mode == LOWER_MODE_MUTE:
                    is_active = track.is_muted
                elif mode == LOWER_MODE_SOLO:
                    is_active = track.is_solo
                elif mode == LOWER_MODE_MONITOR:
                    is_active = track.is_monitored
                elif mode == LOWER_MODE_REC:
                    is_active = track.is_armed
                else:
                    is_active = False
                
                self._send_midi_to_push([0xB0, cc, active_color if is_active else BTN_DIM])
            except Exception:
                pass

    # ─────────────────────────────────────────
    # Display thread (continued)
    # ─────────────────────────────────────────

    def _display_loop(self):
        """
        Display loop: generate and send a frame every ~33ms (~30 fps).
        Also periodically check that MIDI is still configured.
        """
        from renderer import render_frame

        TARGET_FPS        = 30
        FRAME_TIME        = 1.0 / TARGET_FPS
        midi_check_ticks  = 0
        _frame_count      = 0
        _display_ok       = True
        _display_retry    = 0

        while self._running:
            frame_start = time.time()

            try:
                # Check/reconfigure MIDI every ~30 frames (≈1 second)
                midi_check_ticks += 1
                if midi_check_ticks >= 30:
                    midi_check_ticks = 0
                    if not self.push.midi_is_configured():
                        self.push.configure_midi()
                    self._update_all_leds()
                    
                    # If display was failing, try to reinitialize USB
                    if not _display_ok:
                        _display_retry += 1
                        if _display_retry % 3 == 0:  # Every ~3 seconds
                            print(f"  ⟳ Retrying Push 2 display connection...")
                            try:
                                self.push.display.configure_display()
                                _display_ok = True
                                _frame_count = 0
                                print("  ✓ Push 2 display reconnected!")
                            except Exception:
                                pass
                
                # Blink for Overview mode (~2Hz)
                if self.state.mode == MODE_OVERVIEW:
                    if not hasattr(self, '_overview_blink_counter'):
                        self._overview_blink_counter = 0
                    self._overview_blink_counter += 1
                    if self._overview_blink_counter >= 8:  # ~4Hz at 30fps
                        self._overview_blink_counter = 0
                        self._overview_blink_phase = not getattr(self, '_overview_blink_phase', True)
                        self._update_overview_pads()

                # Blink for Record button (~2Hz) when armed
                if not hasattr(self, '_rec_blink_counter'):
                    self._rec_blink_counter = 0
                self._rec_blink_counter += 1
                if self._rec_blink_counter >= 15:  # ~2Hz at 30fps
                    self._rec_blink_counter = 0
                    self._rec_blink_phase = not getattr(self, '_rec_blink_phase', False)
                    if not self.state.is_recording and any(
                            t.is_armed for t in self.state.tracks if t.name):
                        self._update_rec_led()

                if _display_ok:
                    frame = render_frame(self.state, self.pad_grid, self.cr_state)
                    self.push.display.display_frame(
                        frame,
                        input_format=push2_python.constants.FRAME_FORMAT_BGR565
                    )
                    _frame_count += 1
                    if _frame_count == 1:
                        print("  ✓ First frame sent to Push 2 display")

                # Update LEDs AFTER render so any state computed by the
                # renderer (e.g. state.cs_footer_pill_states) is already fresh.
                if getattr(self.nuendo_link, '_leds_dirty', False):
                    self.nuendo_link._leds_dirty = False
                    self._update_all_leds()
            except Exception as e:
                _frame_count += 1
                if _display_ok:
                    print(f"  ✗ Display error: {e}")
                    _display_ok = False
                    _display_retry = 0

            elapsed    = time.time() - frame_start
            sleep_time = FRAME_TIME - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _auto_switch_bank(self, new_bank):
        """Update bank_offset without sending CC (Nuendo may scroll on its own)."""
        if getattr(self, '_switching', False):
            return
        self.state.bank_offset = new_bank
        self._update_nav_leds()
        self._update_upper_row_leds()

    def _insert_action(self, target_slot, action):
        """Execute an action on an insert slot."""
        import threading
        
        # Bypass lock: prevent concurrent bypass actions
        if not hasattr(self, '_bypass_lock'):
            self._bypass_lock = threading.Lock()
        
        def _do():
            if action == 'bypass':
                # ── Try DirectAccess bypass (instant) ──
                is_active = self.state.current_insert_active[target_slot]
                want_bypass = is_active  # Active → bypass ON; Bypassed → bypass OFF
                if self.nuendo_link.send_da_bypass(target_slot, want_bypass):
                    print(f"  Bypass {'ON' if want_bypass else 'OFF'} slot {target_slot} [DA]")
                    return
                
                # ── Fallback: viewer-based bypass (slow) ──
                # Only one bypass at a time — drop if busy
                if not self._bypass_lock.acquire(blocking=False):
                    return
                try:
                    self.nuendo_link._bypass_navigating = True
                    # 1. Reset main viewer to slot 0
                    self.nuendo_link.send_cc(89, 127)
                    time.sleep(0.01)
                    self.nuendo_link.send_cc(89, 0)
                    time.sleep(0.15)
                    # 2. Advance to target slot (same timing as edit action)
                    for _ in range(target_slot):
                        self.nuendo_link.send_cc(1, 127)
                        time.sleep(0.01)
                        self.nuendo_link.send_cc(1, 0)
                        time.sleep(0.15)
                    # 3. Settling delay — let the binding sync with the new slot
                    time.sleep(0.15)
                    self.nuendo_link._bypass_navigating = False
                    # 4. Set bypass: 127 = bypass ON, 0 = bypass OFF
                    if is_active:
                        self.nuendo_link.send_cc_ch4(20, 127)
                    else:
                        self.nuendo_link.send_cc_ch4(20, 0)
                    print(f"  Bypass {'ON' if is_active else 'OFF'} slot {target_slot} [viewer]")
                finally:
                    self.nuendo_link._bypass_navigating = False
                    self._bypass_lock.release()
            elif action == 'edit':
                # Open/close plugin UI via viewer navigation
                # (DA "Edit" param is read-only state, can't trigger UI open)
                self.nuendo_link.send_cc(89, 127)  # Reset
                time.sleep(0.01)
                self.nuendo_link.send_cc(89, 0)
                time.sleep(0.15)
                for _ in range(target_slot):
                    self.nuendo_link.send_cc(1, 127)  # Next
                    time.sleep(0.01)
                    self.nuendo_link.send_cc(1, 0)
                    time.sleep(0.15)
                time.sleep(0.1)
                self.nuendo_link.send_cc(99, 127)
                time.sleep(0.01)
                self.nuendo_link.send_cc(99, 0)
                print(f"  Edit toggle slot {target_slot}")
            elif action == 'params':
                # Navigate the main viewer to the correct slot (parameters follow)
                self.nuendo_link.send_cc(89, 127)
                time.sleep(0.01)
                self.nuendo_link.send_cc(89, 0)
                time.sleep(0.15)
                for _ in range(target_slot):
                    self.nuendo_link.send_cc(1, 127)
                    time.sleep(0.01)
                    self.nuendo_link.send_cc(1, 0)
                    time.sleep(0.15)
                print(f"  Params mode slot {target_slot}")
            elif action == 'params_and_edit':
                # Navigate + open UI (viewer-based)
                self.nuendo_link.send_cc(89, 127)
                time.sleep(0.01)
                self.nuendo_link.send_cc(89, 0)
                time.sleep(0.15)
                for _ in range(target_slot):
                    self.nuendo_link.send_cc(1, 127)
                    time.sleep(0.01)
                    self.nuendo_link.send_cc(1, 0)
                    time.sleep(0.15)
                time.sleep(0.1)
                self.nuendo_link.send_cc(99, 127)
                time.sleep(0.01)
                self.nuendo_link.send_cc(99, 0)
                print(f"  Params+Edit slot {target_slot}")
            elif action == 'deactivate':
                # Toggle mOn via CC 4 channel 2
                # Main viewer must be at the correct slot
                self.nuendo_link.send_cc(89, 127)
                time.sleep(0.01)
                self.nuendo_link.send_cc(89, 0)
                time.sleep(0.15)
                for _ in range(target_slot):
                    self.nuendo_link.send_cc(1, 127)
                    time.sleep(0.01)
                    self.nuendo_link.send_cc(1, 0)
                    time.sleep(0.15)
                time.sleep(0.1)
                self.nuendo_link.send_cc_ch2(4, 127)
                time.sleep(0.01)
                self.nuendo_link.send_cc_ch2(4, 0)
                print(f"  Deactivate toggle slot {target_slot}")
            
            self.state.selected_insert_slot = target_slot
        
        threading.Thread(target=_do, daemon=True).start()

    def _navigate_insert_to(self, target_slot):
        """Navigate the insert viewer to a specific slot."""
        current = self.state.selected_insert_slot
        self.state.selected_insert_slot = target_slot
        
        if target_slot == 0:
            # Reset to first slot
            self.nuendo_link.send_cc(89, 127)
            time.sleep(0.01)
            self.nuendo_link.send_cc(89, 0)
        elif target_slot != current:
            # Reset first, then advance
            self.nuendo_link.send_cc(89, 127)
            time.sleep(0.01)
            self.nuendo_link.send_cc(89, 0)
            time.sleep(0.05)
            for _ in range(target_slot):
                self.nuendo_link.send_cc(1, 127)
                time.sleep(0.01)
                self.nuendo_link.send_cc(1, 0)
                time.sleep(0.05)

    def _browser_fallback_to_inserts(self):
        """Called when Add Device opened the instrument browser but the selected
        track has no instrument slot — switch to the insert browser instead."""
        state = self.state
        if state.mode != MODE_BROWSER or not getattr(state, 'browser_instrument', False):
            return
        print("  Browser: no instrument slot — falling back to inserts")
        state.browser_instrument = False
        state.browser_phase = "slot_select"
        state.insert_bank_offset = 0
        if not self.nuendo_link._da_inserts_ready:
            self._scan_inserts()
        self._update_upper_row_leds()
        self._update_lower_row_leds()

    def _browser_load_plugin(self, target_slot, entry_index, collection_index):
        """Load a plugin from the browser — into an insert slot, or as the
        selected Instrument track's instrument when in instrument mode."""
        state = self.state
        plugin = state.browser_plugins[entry_index] if entry_index < len(state.browser_plugins) else None
        if not plugin:
            return

        instrument = getattr(state, 'browser_instrument', False)
        where = "as instrument" if instrument else f"into slot {target_slot + 1}"
        print(f"  Browser: Loading \"{plugin['name']}\" {where}...")

        # Send load command to JS via CC sequence on ch8
        success = self.nuendo_link.send_da_load_plugin(
            target_slot, entry_index, collection_index, instrument=instrument)

        if success:
            import threading
            def _after_load():
                time.sleep(1.0)  # Wait for Nuendo to load the plugin
                if instrument:
                    # Instrument loaded — return to where we came from.
                    self._set_mode(state.browser_prev_mode)
                else:
                    self._set_mode(MODE_INSERTS)
                    state.selected_insert_slot = target_slot
                    state.insert_bank_offset = 0 if target_slot < 8 else 8
                    self._scan_inserts()
                print(f"  Browser: \"{plugin['name']}\" loaded ✓")
            threading.Thread(target=_after_load, daemon=True).start()
        else:
            print(f"  Browser: Load failed — DA not available")

    def _browser_cycle_collection(self):
        """Cycle to the next plugin collection and reload the list."""
        state = self.state
        coll_count = state.browser_collection_count
        if coll_count <= 1:
            # Only one collection (or unknown), nothing to cycle
            return
        next_idx = (state.browser_collection_index + 1) % coll_count
        state.browser_collection_index = next_idx
        state.browser_scroll = 0
        state.browser_selected = 0
        state.browser_list_ready = False
        self.nuendo_link.request_da_plugin_list(next_idx)
        print(f"  Browser: Switching to collection {next_idx}/{coll_count}")

    def _browser_clear_slot(self, slot_index):
        """Attempt to clear (remove plugin from) an insert slot."""
        print(f"  Browser: Clearing slot {slot_index + 1}...")
        success = self.nuendo_link.send_da_clear_slot(slot_index)
        if success:
            import threading
            def _after_clear():
                time.sleep(0.5)
                self._scan_inserts()
            threading.Thread(target=_after_clear, daemon=True).start()
        else:
            print(f"  Browser: Clear failed — DA not available")

    def _scan_inserts(self):
        """Scan 16 inserts — uses DirectAccess if available, otherwise viewer navigation."""
        import threading
        
        # ── Try DirectAccess first (instant) ──
        if getattr(self.nuendo_link, '_da_available', False):
            self.nuendo_link.request_da_insert_exploration()
            print("  Inserts: DA exploration requested (instant)")
            return
        
        # ── Fallback: viewer-based scan (slow) ──
        self._insert_scan_version += 1
        my_version = self._insert_scan_version
        
        def _scan():
            # Reset names
            self.state.current_insert_names = [''] * 16
            self.state.current_insert_active = [False] * 16
            
            track_name = self.state.selected_track.name if self.state.selected_track else '?'
            print(f"  Inserts: scan v{my_version} (track='{track_name}') [viewer-based]")
            
            # Reset to slot 0
            self.nuendo_link.send_cc(89, 127)
            time.sleep(0.01)
            self.nuendo_link.send_cc(89, 0)
            time.sleep(0.3)
            
            for slot in range(1, 16):
                if my_version != self._insert_scan_version:
                    print(f"  Inserts: scan cancelled")
                    return
                self.nuendo_link.send_cc(1, 127)
                time.sleep(0.01)
                self.nuendo_link.send_cc(1, 0)
                time.sleep(0.3)
            
            if my_version != self._insert_scan_version:
                return
            
            # Return to slot 0
            self.nuendo_link.send_cc(89, 127)
            time.sleep(0.01)
            self.nuendo_link.send_cc(89, 0)
            time.sleep(0.1)
            self.state.selected_insert_slot = 0
            
            scanned_names = list(self.state.current_insert_names)
            page1 = scanned_names[:8]
            page2 = scanned_names[8:16]
            print(f"  ✓ Inserts scan v{my_version}: {page1}")
            if any(page2):
                print(f"    Page 2: {page2}")
            
            if my_version != self._insert_scan_version:
                return
            
            # Restore scanned names
            self.state.current_insert_names = scanned_names
            
            self._update_lower_row_leds()
            self._update_upper_row_leds()
        
        threading.Thread(target=_scan, daemon=True).start()

    def _initial_bank_refresh(self):
        """Initial refresh: loads names/colors for the current bank."""
        import threading
        
        def _refresh():
            print("  Bank refresh: starting")
            # Round-trip to force JS to send names/colors
            self.nuendo_link.send_cc(8, 127)
            time.sleep(0.01)
            self.nuendo_link.send_cc(8, 0)
            time.sleep(0.05)
            self.nuendo_link.send_cc(9, 127)
            time.sleep(0.01)
            self.nuendo_link.send_cc(9, 0)
            time.sleep(0.1)
            self._update_all_leds()
            print("  ✓ Bank refresh complete")
        
        threading.Thread(target=_refresh, daemon=True).start()

    def _full_scan(self, num_banks=8):
        """Scan multi-banks.
        
        Names and colors arrive automatically via mOnTitleChange
        and mOnColorChange on the Volume knobs of the bank zone.
        """
        import threading
        
        original_offset = self.state.bank_offset
        
        def _scan_thread():
            print(f"  Scan: starting ({num_banks} banks)")
            self.nuendo_link._ignore_selection_until = time.time() + 60.0
            self.nuendo_link._scanning = True
            
            self.nuendo_link._scan_returning = True
            while self.state.bank_offset > 0:
                self.nuendo_link.send_cc(9, 127)
                time.sleep(0.01)
                self.nuendo_link.send_cc(9, 0)
                self.state.bank_offset -= BANK_SIZE
                time.sleep(0.01)
            self.state.bank_offset = 0
            self.nuendo_link._scan_returning = False
            time.sleep(0.06)
            
            # Force a refresh of bank 0: go to bank 1 then come back
            self.nuendo_link.send_cc(8, 127)
            time.sleep(0.01)
            self.nuendo_link.send_cc(8, 0)
            time.sleep(0.02)
            self.nuendo_link.send_cc(9, 127)
            time.sleep(0.01)
            self.nuendo_link.send_cc(9, 0)
            time.sleep(0.06)
            
            for bank in range(num_banks):
                if bank > 0:
                    self.nuendo_link.send_cc(8, 127)
                    time.sleep(0.01)
                    self.nuendo_link.send_cc(8, 0)
                    time.sleep(0.01)
                    self.state.bank_offset = bank * BANK_SIZE
                else:
                    self.state.bank_offset = 0
                time.sleep(0.04)
            
            self.nuendo_link._scan_returning = True
            for _ in range(num_banks + 2):
                self.nuendo_link.send_cc(9, 127)
                time.sleep(0.01)
                self.nuendo_link.send_cc(9, 0)
                time.sleep(0.01)
            
            target = original_offset // BANK_SIZE
            for _ in range(target):
                self.nuendo_link.send_cc(8, 127)
                time.sleep(0.01)
                self.nuendo_link.send_cc(8, 0)
                time.sleep(0.01)
            
            time.sleep(0.1)
            self.state.bank_offset = original_offset
            self.nuendo_link._scan_returning = False
            
            sel_in_bank = self.state.selected_track_index - original_offset
            if 0 <= sel_in_bank < 8:
                self.nuendo_link.send_select_track(sel_in_bank)
            
            # Stop the mute/solo filter BEFORE the final bank right/left
            # to receive the real states of the current bank
            self.nuendo_link._scanning = False
            
            time.sleep(0.04)
            self.nuendo_link.send_cc(8, 127)
            time.sleep(0.01)
            self.nuendo_link.send_cc(8, 0)
            time.sleep(0.04)
            self.nuendo_link.send_cc(9, 127)
            time.sleep(0.01)
            self.nuendo_link.send_cc(9, 0)
            time.sleep(0.04)
            
            self.nuendo_link._ignore_selection_until = time.time() + 2.0
            print(f"  ✓ Scan complete")
        
        threading.Thread(target=_scan_thread, daemon=True).start()

    def _load_plugin_mappings(self):
        """Load all plugin mappings from ~/.push2bridge/mappings/."""
        from pathlib import Path
        import json
        
        mappings_dir = Path.home() / ".push2bridge" / "mappings"
        if not mappings_dir.exists():
            print("  No plugin mappings found")
            return
        
        count = 0
        for f in mappings_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                plugin_name = data.get("plugin", f.stem)
                self.state.plugin_mappings[plugin_name] = data
                count += 1
            except (json.JSONDecodeError, IOError):
                pass
        
        if count > 0:
            print(f"  ✓ Loaded {count} plugin mapping(s)")

    def _check_insert_mapping(self, plugin_name):
        """Check if a mapping exists for the given plugin and activate it.
        
        Matching strategy (in order):
        1. Exact match
        2. Case-insensitive exact match
        3. Nuendo name starts with mapping name (catches "Pro-Q 4 Mono" → "Pro-Q 4")
        4. Mapping name starts with Nuendo name (catches truncated names)
        5. Substring match (one contains the other)
        """
        mappings = self.state.plugin_mappings
        if not mappings:
            self.state.active_mapping = None
            return None
        
        # 1. Exact match
        mapping = mappings.get(plugin_name)
        if mapping:
            self.state.active_mapping = mapping
            pages = mapping.get("pages", [])
            print(f"  ✓ Mapping found for '{plugin_name}': {len(pages)} page(s)")
            return mapping
        
        # 2-5. Fuzzy matching
        plugin_lower = plugin_name.lower().strip()
        best_match = None
        best_name = None
        
        for name, m in mappings.items():
            name_lower = name.lower().strip()
            
            # 2. Case-insensitive exact
            if name_lower == plugin_lower:
                best_match = m
                best_name = name
                break
            
            # 3. Nuendo name starts with mapping name (most common: "Pro-Q 4 Mono" → "Pro-Q 4")
            if plugin_lower.startswith(name_lower) and len(name_lower) >= 4:
                if not best_match or len(name) > len(best_name):  # prefer longest match
                    best_match = m
                    best_name = name
            
            # 4. Mapping name starts with Nuendo name
            elif name_lower.startswith(plugin_lower) and len(plugin_lower) >= 4:
                if not best_match or len(name) > len(best_name):
                    best_match = m
                    best_name = name
            
            # 5. Substring (one contains the other)
            elif (name_lower in plugin_lower or plugin_lower in name_lower) and len(min(name_lower, plugin_lower, key=len)) >= 4:
                if not best_match:
                    best_match = m
                    best_name = name
        
        self.state.active_mapping = best_match
        if best_match:
            pages = best_match.get("pages", [])
            if best_name != plugin_name:
                print(f"  ✓ Mapping found for '{plugin_name}' (matched '{best_name}'): {len(pages)} page(s)")
            else:
                print(f"  ✓ Mapping found for '{plugin_name}': {len(pages)} page(s)")
        else:
            available = list(mappings.keys())[:5]
            suffix = f" (+{len(mappings)-5} more)" if len(mappings) > 5 else ""
            print(f"  ✗ No mapping for '{plugin_name}' — available: {available}{suffix}")
        return best_match

    def _on_da_params_ready(self, slot_index):
        """Called when DA param enumeration is complete for any slot."""
        # Strip slot DA (16-20): apply CS encoder setup when the matching slot is done
        da_strip_offset = getattr(self.nuendo_link, 'DA_STRIP_SLOT_OFFSET', 16)
        if slot_index >= da_strip_offset:
            cs_page = getattr(self.state, 'cs_page', 'overview')
            if cs_page != 'overview':
                variant = self._cs_page_variant(cs_page)
                # Only apply if there's a DA setup for this (page, variant) AND
                # the completed DA slot matches the dynamically resolved one.
                if _VARIANT_DA_ENC_SETUP.get((cs_page, variant)) is not None:
                    expected_da_slot = self._resolve_da_slot_for_variant(variant)
                    if expected_da_slot == slot_index:
                        self._apply_cs_strip_da_setup(cs_page, variant)
            return

        import json
        from pathlib import Path

        mapping = self.state.active_mapping
        if not mapping:
            return
        
        da_params = getattr(self.nuendo_link, '_da_plugin_params', {})
        if not da_params:
            print("  ✗ DA params empty — cannot apply mapping")
            return
        
        # Load pedalboard cache
        cache_file = Path.home() / ".push2bridge" / "plugin_cache.json"
        pb_params = []
        if cache_file.exists():
            try:
                cache = json.loads(cache_file.read_text())
                plugin_name = mapping.get("plugin", "")
                pb_plugin = cache.get(plugin_name, {})
                pb_params = pb_plugin.get("parameters", [])
            except (json.JSONDecodeError, IOError):
                pass
        
        if not pb_params:
            print(f"  ✗ No pedalboard cache — using direct index")
            self._param_pb_to_da = {i: i for i in range(len(da_params))}
        else:
            self._param_pb_to_da = {}
            
            # Build DA index list for searching
            da_list = [(idx, info['name']) for idx, info in da_params.items()]
            matched_da = set()  # prevent double-matching
            
            for p in pb_params:
                pb_idx = p['index']
                pb_name = (p.get('name') or '').strip()
                pb_label = (p.get('label') or '').strip()
                
                # Convert snake_case to words: 'band_1_frequency' → ['band', '1', 'frequency']
                pb_words = pb_name.lower().replace('_', ' ').split()
                
                # Strategy 1: exact name match (normalized)
                pb_norm = pb_name.lower().replace('_', ' ').strip()
                for da_idx, da_name in da_list:
                    if da_idx in matched_da:
                        continue
                    if da_name.lower().strip() == pb_norm:
                        self._param_pb_to_da[pb_idx] = da_idx
                        matched_da.add(da_idx)
                        break
                else:
                    # Strategy 2: fuzzy word match — all pb words must appear in DA name
                    if len(pb_words) >= 2:
                        best_da = None
                        best_len = 999
                        for da_idx, da_name in da_list:
                            if da_idx in matched_da:
                                continue
                            da_lower = da_name.lower()
                            if all(w in da_lower for w in pb_words):
                                # Prefer shortest DA name (tightest match)
                                if len(da_name) < best_len:
                                    best_da = da_idx
                                    best_len = len(da_name)
                        if best_da is not None:
                            self._param_pb_to_da[pb_idx] = best_da
                            matched_da.add(best_da)
            
            matched = len(self._param_pb_to_da)
            total_pb = len(pb_params)
            print(f"  Param matching: {matched}/{total_pb} matched")
            
            if matched > 0:
                # Show a few examples
                examples = []
                for pb_idx, da_idx in list(self._param_pb_to_da.items())[:3]:
                    pb_p = next((p for p in pb_params if p['index'] == pb_idx), None)
                    da_name = da_params[da_idx]['name'] if da_idx in da_params else '?'
                    pb_n = pb_p['name'] if pb_p else '?'
                    examples.append(f"'{pb_n}' → '{da_name}'")
                print(f"    Examples: {', '.join(examples)}")
            
            if total_pb > 0 and matched / total_pb < 0.1:
                # Very poor matching — show diagnostic
                print(f"  ⚠ Very poor matching — check parameter names")
                print(f"    Pedalboard (first 3): {[p.get('name','') for p in pb_params[:3]]}")
                print(f"    DA (first 3): {[da_params[i]['name'] for i in sorted(da_params.keys())[:3]]}")
        
        # Apply the first mapping page
        pages = mapping.get("pages", [])
        if pages:
            self._apply_mapping_page(0, pages, da_params)

    @staticmethod
    def _normalize_param_name(name):
        """Normalize a parameter name for matching."""
        return name.lower().strip() if name else ''

    def _apply_mapping_page(self, page_idx, pages, da_params=None):
        """Apply a specific mapping page to the Push display and configure encoders."""
        if page_idx >= len(pages):
            return
        
        if da_params is None:
            da_params = getattr(self.nuendo_link, '_da_plugin_params', {})
        
        page = pages[page_idx]
        param_indices = page.get("params", [])
        labels = page.get("labels", [])
        
        names = [''] * 8
        values = [''] * 8
        da_indices_for_encoders = [-1] * 8
        
        for enc in range(8):
            if enc >= len(param_indices):
                break
            pb_idx = param_indices[enc]
            if pb_idx is None or pb_idx < 0:
                continue
            
            # Convert pedalboard index to DA index
            da_idx = getattr(self, '_param_pb_to_da', {}).get(pb_idx)
            if da_idx is None:
                names[enc] = f"P{pb_idx} ?"
                continue
            
            da_info = da_params.get(da_idx)
            if not da_info:
                continue
            
            da_indices_for_encoders[enc] = da_idx
            
            # Use custom label if defined, otherwise DA param name
            if enc < len(labels) and labels[enc]:
                names[enc] = labels[enc]
            else:
                names[enc] = da_info['name']
            
            # Display value
            val = da_info.get('value', 0.0)
            values[enc] = f"{val:.2f}"
        
        self.state.insert_param_names = names
        self.state.insert_param_values = values
        
        # Configure JS encoders to control the mapped DA params
        slot = self.state.selected_insert_slot
        self.nuendo_link.send_da_encoder_setup(slot, da_indices_for_encoders)
        
        page_name = page.get("name", "")
        page_label = f" '{page_name}'" if page_name else ""
        print(f"  ✓ Mapping page {page_idx + 1}{page_label} applied: {[n for n in names if n]}")


# ─────────────────────────────────────────────
# Utility (duplicated from nuendo_link to avoid circular import)
# ─────────────────────────────────────────────

def _to_db(normalized_volume):
    import math
    if normalized_volume <= 0.0:
        return float('-inf')
    ratio = normalized_volume / 0.75
    if ratio <= 0:
        return -96.0
    return round(20.0 * math.log10(ratio), 1)
