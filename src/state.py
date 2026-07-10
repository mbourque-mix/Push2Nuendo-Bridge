"""
state.py — Shared application state

This file contains all data the bridge needs to know
at all times: tracks, their values, the active mode, etc.

This is the bridge's central state. All other modules
read and write here.
"""

# ─────────────────────────────────────────────
# Constants — Push 2 display modes
# ─────────────────────────────────────────────

MODE_VOLUME  = "volume"   # Encoders control volume
MODE_PAN     = "pan"      # Encoders control pan
MODE_SENDS   = "sends"    # Encoders control sends
MODE_DEVICE  = "device"   # Encoders control Quick Controls / plugin parameters
MODE_INSERTS = "inserts"  # Displays the insert list for the current track
MODE_TRACK   = "track"    # Combined mode: Vol+Pan+Sends on the selected track
MODE_CR      = "controlroom"  # Control Room mode
MODE_SETUP   = "setup"    # Setup page (aftertouch mode, etc.)
MODE_MIDICC  = "midicc"   # MIDI CC controller page
MODE_BROWSER = "browser"  # Plugin browser (load plugins into insert slots)
MODE_CHANNEL_STRIP = "channel_strip"  # Channel Strip view of the selected track
MODE_XY      = "xy"       # XY pad: 64 pads control 2 assignable params (relative)

# XY pad — selectable selected-track parameters (index order matters)
XY_TRACK_PARAMS = ["Volume", "Pan", "QC1", "QC2", "QC3", "QC4", "QC5", "QC6", "QC7", "QC8"]

# Channel Strip sub-pages (used when mode == MODE_CHANNEL_STRIP)
CS_PAGE_OVERVIEW = "overview"
CS_PAGE_GATE = "gate"
CS_PAGE_COMP = "comp"
CS_PAGE_EQ = "eq"
CS_PAGE_TOOLS = "tools"
CS_PAGE_SAT = "sat"
CS_PAGE_LIMITER = "limiter"

# Bridge version
BRIDGE_VERSION = "1.0.7"

# Aftertouch modes
AT_POLY    = "poly"       # Polyphonic aftertouch (per-note)
AT_CHANNEL = "channel"    # Channel aftertouch (global)
AT_OFF     = "off"        # No aftertouch

# Velocity curve presets
VC_LINEAR  = "linear"
VC_LOG     = "log"       # Logarithmic (more sensitive at low velocities)
VC_EXP     = "exp"       # Exponential (more sensitive at high velocities)
VC_SCURVE  = "s-curve"   # S-curve (compressed extremes, expanded middle)
VC_FIXED   = "fixed"     # Fixed velocity (always 100)

# Footswitch / pedal actions (Push 2 has two pedal jacks: jack 1 = CC 64,
# jack 2 = CC 69). Each pedal is assigned one of these, with an optional invert.
FS_SUSTAIN  = "sustain"    # Pass CC 64 (sustain) through to the instrument
FS_PLAYSTOP = "playstop"   # Toggle Play / Stop
FS_PLAY     = "play"       # Start playback
FS_STOP     = "stop"       # Stop playback
FS_RECORD   = "record"     # Record
FS_RECSTOP  = "recstop"    # Toggle Record / Stop (start recording, then stop)
FS_EXPRESSION = "expression"  # Continuous controller: send the pedal's 0-127
                              # position as a CC to the instrument (CC selectable)
FS_OFF      = "off"        # Do nothing
# (label, value) order shown on the Setup pedal pages (lower-row buttons 1-7).
# 'Stop' (FS_STOP) was dropped to make room for 'Expr'; the Play/Stop and
# Rec/Stop toggles still stop the transport. FS_STOP stays defined so any
# previously-saved 'stop' assignment keeps working (see _handle_footswitch).
FS_OPTIONS = [
    ("Sustain", FS_SUSTAIN),
    ("Play/Stop", FS_PLAYSTOP),
    ("Play", FS_PLAY),
    ("Expr", FS_EXPRESSION),
    ("Rec", FS_RECORD),
    ("Rec/Stop", FS_RECSTOP),
    ("Off", FS_OFF),
]
# Default CC an expression pedal sends to the instrument (11 = Expression)
FS_EXPRESSION_DEFAULT_CC = 11
# Expression pedal destinations: (label, value). 'cc' = MIDI CC to the
# instrument; the others drive Nuendo directly through existing bridge paths.
FS_EXPR_TARGETS = [
    ("MIDI CC", "cc"),
    ("Volume", "volume"),       # selected track volume
    ("QC", "qc"),               # selected track Quick Control 1-8
    ("Send", "send"),           # selected track, currently active send slot
    ("AI Knob", "ai"),          # value under the mouse (mValueUnderMouse)
]
# Pedal jack -> the MIDI CC the Push emits for that jack
FS_PEDAL_CC = {1: 64, 2: 69}

# ── Key Commands ─────────────────────────────────────────────────────────────
# The 8 note-value buttons (CC 36-43) double as user-assignable Key Command
# slots when Note Repeat is OFF. There are KC_NUM_PAGES pages, navigated with
# Page Left / Right, giving KC_NUM_PAGES x KC_NUM_SLOTS distinct triggers. Each
# (page, slot) emits a unique CC on a dedicated channel; the JS MIDI Remote
# script exposes those as UNASSIGNED buttons so the user maps each one to any
# Nuendo Key Command in the Mapping Assistant. We only persist labels + a
# per-page colour for the Push display/LEDs (the actual command lives in Nuendo).
KC_NUM_PAGES = 8
KC_NUM_SLOTS = 8
KC_MIDI_CHANNEL = 12          # 0-indexed (MIDI channel 13, status 0xBC); collision-free
KC_LONG_PRESS_SEC = 0.4       # hold this long on a slot to open the legend overlay
# Selectable button colours (name -> Push 2 button LED palette INDEX). These
# indices address the Push's *factory* palette, verified against real hardware
# (they differ from push2-python's DEFAULT_COLOR_PALETTE, which is not what the
# device actually renders). White (index 53) is reserved for Note Repeat, so it
# is intentionally NOT offered here.
#   Confirmed on hardware: 3=coral/salmon, 9=yellow, 13=green, 26=fuchsia,
#   37=cyan, 48=blue, 53=white, 127=red.  purple(22) is still an estimate.
KC_COLORS = [
    ("red", 127), ("coral", 3), ("yellow", 9), ("green", 13),
    ("cyan", 37), ("blue", 48), ("purple", 22), ("fuchsia", 26),
]
KC_COLOR_MAP = dict(KC_COLORS)
KC_LED_WHITE = 53             # confirmed white index for the note-value buttons
# Default colour for each page (one per page, in palette order)
KC_DEFAULT_PAGE_COLORS = [name for name, _ in KC_COLORS]

# Note-value buttons, ordered TOP → BOTTOM to match the labels printed on the
# Push. Slot 0 = top button. Each entry is (physical label, the CC the Push
# emits for that button): CC 36='1/4' (bottom) … CC 43='1/32t' (top).
KC_SLOT_BUTTONS = [
    ('1/32t', 43), ('1/32', 42), ('1/16t', 41), ('1/16', 40),
    ('1/8t', 39),  ('1/8', 38),  ('1/4t', 37),  ('1/4', 36),
]
KC_BUTTON_NAME_TO_SLOT = {name: i for i, (name, cc) in enumerate(KC_SLOT_BUTTONS)}
KC_SLOT_TO_CC = [cc for name, cc in KC_SLOT_BUTTONS]  # physical CC per slot index

def kc_slot_cc(page, slot):
    """The unique CC number a given (page, slot) emits on KC_MIDI_CHANNEL."""
    return page * KC_NUM_SLOTS + slot

def make_default_key_commands():
    """Fresh in-memory KC config: KC_NUM_PAGES pages, each with a colour and
    KC_NUM_SLOTS empty slots ({'command': str, 'label': str})."""
    return [
        {'color': KC_DEFAULT_PAGE_COLORS[p % len(KC_DEFAULT_PAGE_COLORS)],
         'slots': [{'command': '', 'label': ''} for _ in range(KC_NUM_SLOTS)]}
        for p in range(KC_NUM_PAGES)
    ]

def kc_slot_display_label(slot):
    """Label shown on the Push for a slot: short label overrides, else the
    command text, else '' (caller renders a positional placeholder)."""
    if not isinstance(slot, dict):
        return ''
    return (slot.get('label') or slot.get('command') or '').strip()

# ── Expand menus (long-press New / Duplicate / Mute / Play / Record) ────────
# A long-press opens an on-screen menu on the lower-row buttons; it stays until
# another display mode is selected. Entry = (label, kind, payload):
#   kind 'js'  → payload = index into EXPAND_JS_COMMANDS (fired via wire ch 14
#                = 0xBD, CC = index; the JS holds the matching makeCommandBinding
#                table — KEEP BOTH TABLES IN SYNC)
#   kind 'cc'  → payload = channel-0 CC pulsed 127/0 (existing bridge paths)
EXPAND_JS_COMMANDS = [
    ('TrackVersions', 'New Version'),            # 0
    ('Audio', 'Events to Part'),                 # 1
    ('Edit', 'To Real Copy'),                    # 2
    ('Render in Place', 'Render'),               # 3
    ('Edit', 'Group'),                           # 4
    ('Transport', 'Insert Marker'),              # 5
    ('Audio', 'Bounce'),                         # 6
    ('Edit', 'Duplicate'),                       # 7
    ('Edit', 'Repeat'),                          # 8
    ('Edit', 'Fill Loop'),                       # 9
    ('Mixer', 'Bypass: Sends'),                  # 10
    ('Mixer', 'Bypass: Inserts'),                # 11
    ('Mixer', 'Bypass: Channel Strip'),          # 12
    ('Mixer', 'Bypass: EQs'),                    # 13
    ('Transport', 'Audio Record Mode'),          # 14
    ('Transport', 'MIDI Record Mode'),           # 15
    ('Transport', 'MIDI Cycle Record Mode'),     # 16
    ('Transport', 'Global Retrospective Record'),# 17
    ('Transport', 'Auto Punch In'),              # 18
    ('Transport', 'Auto Punch Out'),             # 19
    ('Transport', 'Use Pre-roll'),               # 20
    ('Transport', 'Sync Punch To Cycle'),        # 21
    ('Transport', 'Play Selection Range'),       # 22
    ('Transport', 'Play Selection Solo'),        # 23
    ('Transport', 'Play from Selection Start'),  # 24
    ('Transport', 'Play until Selection End'),   # 25
    ('Transport', 'Play until Next Marker'),     # 26
    ('Transport', 'Loop Selection'),             # 27
    ('Transport', 'Shuttle Play 2x'),            # 28
    ('Transport', 'Shuttle Play 1/2x'),          # 29
    ('Transport', 'Start Mode'),                 # 30
    ('Transport', 'Set Left Locator'),           # 31
    ('Transport', 'Activate Return to Start Position'),  # 32
    ('Transport', 'Play until Selection Start'), # 33
    ('Transport', 'Play from Selection End'),    # 34
    ('Transport', 'Set Right Locator'),          # 35
    ('Transport', 'Loop Selection Solo'),        # 36
    ('Transport', 'StartStop Preview'),          # 37
    ('Transport', 'Use Post-roll'),              # 38
]
# Menu = (title, lower_row_entries, upper_row_entries) — each row up to 8.
# Entry kinds: 'js' = one command (index into EXPAND_JS_COMMANDS), 'cc' =
# channel-0 CC pulse (existing bridge paths).
EXPAND_MENUS = {
    'new': ('NEW', [
        ('Track Vers.', 'js', 0), ('Events>Part', 'js', 1), ('Real Copy', 'js', 2),
        ('Render', 'js', 3), ('Group', 'js', 4), ('Marker', 'js', 5),
        ('Bounce', 'js', 6),
    ], []),
    'duplicate': ('DUPLICATE', [
        ('Dup Track', 'cc', 69), ('Dup Version', 'cc', 70), ('Dup Clip', 'js', 7),
        ('Repeat', 'js', 8), ('Fill Loop', 'js', 9),
    ], []),
    'mute': ('MUTE / BYPASS', [
        # NOTE: the Mixer::Bypass commands only act when the MixConsole window
        # is FOCUSED in Nuendo (Nuendo limitation, documented in the guide).
        ('Unmute All', 'cc', 75), ('Byp Sends', 'js', 10),
        ('Byp Inserts', 'js', 11), ('Byp Strip', 'js', 12),
        ('Byp EQs', 'js', 13),
    ], []),
    'record': ('RECORD MODES', [
        ('Audio Mode', 'js', 14), ('MIDI Mode', 'js', 15), ('MIDI Cycle', 'js', 16),
        ('Retro Rec', 'js', 17), ('Punch In', 'js', 18), ('Punch Out', 'js', 19),
        ('Punch=Cycle', 'js', 21),
    ], [  # upper row — roll options together
        ('Pre-roll', 'js', 20), ('Post-roll', 'js', 38),
    ]),
    'play': ('PLAY MODES', [
        ('Play Sel', 'js', 22), ('Sel Solo', 'js', 23), ('From Start', 'js', 24),
        ('Until End', 'js', 25), ('To Marker', 'js', 26),
        ('Shuttle 2x', 'js', 28), ('Shuttle .5x', 'js', 29),
    ], [  # upper row — start modes; locators side by side (6-7)
        ('Start Mode', 'js', 30), ('Auto RTZ', 'js', 32), ('Until Start', 'js', 33),
        ('From End', 'js', 34), ('Preview', 'js', 37),
        ('Set L Loc', 'js', 31), ('Set R Loc', 'js', 35),
    ]),
    'loop': ('LOOP', [
        ('Loop Sel', 'js', 27), ('Loop Sel Solo', 'js', 36),
    ], []),
}

# Number of tracks displayed simultaneously (= number of encoders)
BANK_SIZE = 8


class TrackInfo:
    """
    Represents a Nuendo track with all its values.
    
    Nuendo sends us this information via MIDI loopback.
    The bridge stores them here and the renderer displays them on screen.
    """

    def __init__(self, index):
        self.index = index          # Track position (0, 1, 2...)
        self.name = f"Track {index + 1}"  # Name displayed on screen
        # True once Nuendo has actually sent a name for this slot. Cells that
        # were never populated (banked past the last visible track) render blank
        # instead of the "Track NN" placeholder, so the end of the project reads
        # as empty rather than as random ghost tracks.
        self.populated = False
        
        # Track color (RGB, as in Nuendo)
        # Default: grey, will be updated by Nuendo
        self.color = (150, 150, 150)
        
        # Volume: 0.0 to 1.0 (1.0 = 0 dB)
        self.volume = 99.0 / 127.0  # 0 dB = CC 99
        self.volume_db = 0.0        # dB version for display
        self.volume_display = ""    # Display text from Nuendo (ex: "-6.0 dB")
        
        # Pan: -1.0 (left) to +1.0 (right), 0.0 = center
        self.pan = 0.0
        
        # Sends: list of 8 values (0.0 to 1.0)
        self.sends = [0.0] * 8
        self.send_names = [f"Send {i+1}" for i in range(8)]
        
        # Quick Controls: 8 assignable parameters in Nuendo
        self.quick_controls = [QuickControl(i) for i in range(8)]
        
        # Inserts: list of plug-ins on this track (max 16)
        self.inserts = []
        
        # Track selected in Nuendo ?
        self.is_selected = False
        
        # Track muted ?
        self.is_muted = False
        
        # Track in solo ?
        self.is_solo = False
        
        # Track armed for recording ?
        self.is_armed = False
        
        # Track in monitor mode ?
        self.is_monitored = False
        
        # Automation
        self.automation_read = False
        self.automation_write = False
        
        # Send enable (8 sends)
        self.send_enabled = [True] * 8
        
        # Send pre/post (8 sends): True = pre-fader, False = post-fader
        self.send_pre_post = [False] * 8
        
        # Send display values (8 sends)
        self.send_display = [''] * 8
        
        # VU meter (0.0 to 1.0)
        self.vu_meter = 0.0
        self.peak_clipped = False  # True when VU exceeded threshold

    def __repr__(self):
        return f"<Track {self.index}: '{self.name}' vol={self.volume:.2f} pan={self.pan:.2f}>"


class QuickControl:
    """One of the 8 Quick Controls on a Nuendo track."""

    def __init__(self, index):
        self.index = index
        self.name = f"QC {index + 1}"   # Will be updated by Nuendo
        self.value = 0.0                  # 0.0 to 1.0
        self.display_value = "---"        # Display text (ex: "-6.0 dB")
        self.min_val = 0.0
        self.max_val = 1.0


class InsertInfo:
    """An insert plug-in on a track."""

    def __init__(self, slot, name="", is_active=True):
        self.slot = slot            # Position in the chain (0-15)
        self.name = name            # Plug-in name (ex: "Pro-Q 3")
        self.is_active = is_active  # Active or bypassed
        self.parameters = []        # Plugin parameters (if available)

    def __repr__(self):
        status = "ON" if self.is_active else "OFF"
        return f"<Insert {self.slot}: {self.name} [{status}]>"


# ─────────────────────────────────────────────
# Channel Strip state (v1.0.4)
# Holds the selected track's PreFilter, ChannelEQ, and 5 strip slots.
# ─────────────────────────────────────────────

# Module IDs (matching SysEx 0x30/0x31/0x32/0x33 protocol from JS)
STRIP_MOD_PREFILTER  = 0x00
STRIP_MOD_CHANNEL_EQ = 0x01
STRIP_MOD_GATE       = 0x10
STRIP_MOD_COMPRESSOR = 0x11
STRIP_MOD_TOOLS      = 0x12
STRIP_MOD_SATURATOR  = 0x13
STRIP_MOD_LIMITER    = 0x14

STRIP_SLOT_MOD_IDS = (STRIP_MOD_GATE, STRIP_MOD_COMPRESSOR, STRIP_MOD_TOOLS,
                      STRIP_MOD_SATURATOR, STRIP_MOD_LIMITER)


class StripSlotState:
    """
    One Channel Strip slot (Gate / Compressor / Tools / Saturator / Limiter).
    
    The current variant ('VintageCompressor', 'EnvelopeShaper', etc.) determines
    which parameters live in the bank zone. params is keyed by paramId from the
    JS side: 0x01..0x08 are bank parameters; 0x00 is reserved for slot.mOn but
    we mirror its on/off into the dedicated `on` field for convenience. paramId
    0x7E is the slot's mBypass — separate from mOn since they represent different
    things in the API: mOn = "is the slot active in the chain", mBypass = "is the
    slot bypassed". The renderer's effective ON indicator is `on AND NOT bypassed`.
    """
    def __init__(self, mod_id, label):
        self.mod_id = mod_id
        self.label = label              # 'Gate' / 'Compressor' / etc.
        self.plugin_name = ''           # e.g. 'VintageCompressor'
        self.on = False                 # mirror of slot.mOn display ("Activate Plug-in")
        self.bypassed = False           # mirror of slot.mBypass display ("Bypass Plug-in")
        # paramId int → {'name': str, 'display': str}
        self.params = {}
    
    def __repr__(self):
        state = 'BYP' if self.bypassed else ('ON' if self.on else 'OFF')
        return (f"<Strip {self.label} {self.plugin_name or '<empty>'} "
                f"{state} {len(self.params)}params>")


class ChannelStripState:
    """
    Aggregate state of the selected track's channel strip:
      - PreFilter  (8 params, paramId 0x00..0x07)
      - ChannelEQ  (4 bands × 5 params, paramIds 0x10..0x44)
      - 5 strip slots (Gate/Comp/Tools/Sat/Limiter), each with up to 8 params
    
    The update_*() methods return True ONLY when the value actually changed —
    callers use this for dedup so the renderer is only refreshed on real changes
    rather than on every Nuendo callback fire (which can repeat 4-10× per change).
    """
    def __init__(self):
        # PreFilter — paramId 0x00..0x07 → {'name', 'display'}
        self.prefilter = {}
        
        # ChannelEQ — paramId (band*0x10 + offset) → {'name', 'display'}
        # Layout: band1 = 0x10..0x14, band2 = 0x20..0x24, etc.
        # Within a band: 0=Freq, 1=Gain, 2=Q, 3=Type, 4=On
        self.eq = {}
        
        # 5 strip slots, indexed by mod_id
        self.slots = {
            STRIP_MOD_GATE:       StripSlotState(STRIP_MOD_GATE,       'Gate'),
            STRIP_MOD_COMPRESSOR: StripSlotState(STRIP_MOD_COMPRESSOR, 'Comp'),
            STRIP_MOD_TOOLS:      StripSlotState(STRIP_MOD_TOOLS,      'Tools'),
            STRIP_MOD_SATURATOR:  StripSlotState(STRIP_MOD_SATURATOR,  'Sat'),
            STRIP_MOD_LIMITER:    StripSlotState(STRIP_MOD_LIMITER,    'Limit'),
        }
    
    def _store_for(self, mod_id):
        """Returns the dict that holds params for this module, or None."""
        if mod_id == STRIP_MOD_PREFILTER:
            return self.prefilter
        if mod_id == STRIP_MOD_CHANNEL_EQ:
            return self.eq
        if mod_id in self.slots:
            return self.slots[mod_id].params
        return None
    
    def update_announce(self, mod_id, param_id, name):
        """
        Store the parameter name (announce). Returns True if changed.
        
        The JS sends names as 'PluginName:ParamName' (e.g. 'Noise Gate:Threshold').
        We strip the plugin prefix here so renderers can use a clean param name.
        For strip slots, paramId 0x00 is the slot's .mOn — its announce contains
        the variant name, which we ignore (variant comes via update_plugin()).
        """
        # slot.mOn announce is just '<variant>:On' — we get variant from 0x33 instead
        if mod_id in self.slots and param_id == 0x00:
            return False
        
        store = self._store_for(mod_id)
        if store is None:
            return False
        
        # Strip the plugin/section prefix from 'Section:Param'
        cleaned = name.split(':', 1)[1] if ':' in name else name
        
        existing = store.setdefault(param_id, {})
        if existing.get('name') == cleaned:
            return False
        existing['name'] = cleaned
        return True
    
    def update_display(self, mod_id, param_id, display):
        """
        Store the parameter display value. Returns True if changed.
        
        Special-cases for strip slots:
          - paramId 0x00 (slot.mOn): mirror into slot.on bool ("Activate Plug-in")
          - paramId 0x7E (slot.mBypass): mirror into slot.bypassed bool ("Bypass Plug-in")
        
        The renderer's effective ON indicator combines both: green when
        slot.on AND NOT slot.bypassed.
        """
        # slot.mOn display = 'On' / 'Off' → mirror into slot.on
        if mod_id in self.slots and param_id == 0x00:
            new_on = (display == 'On')
            slot = self.slots[mod_id]
            if slot.on == new_on:
                return False
            slot.on = new_on
            return True
        
        # slot.mBypass display → mirror into slot.bypassed
        # Steinberg typically shows "On" when bypass is engaged ("Bypass: On" = bypassed),
        # but be lenient: any non-Off / non-empty string treated as bypassed.
        if mod_id in self.slots and param_id == 0x7E:
            # 'On' = bypass active = slot bypassed
            new_byp = (display == 'On')
            slot = self.slots[mod_id]
            if slot.bypassed == new_byp:
                return False
            slot.bypassed = new_byp
            return True
        
        store = self._store_for(mod_id)
        if store is None:
            return False
        
        existing = store.setdefault(param_id, {})
        if existing.get('display') == display:
            return False
        existing['display'] = display
        return True
    
    def update_plugin(self, mod_id, plugin_name):
        """
        Store the loaded plugin/variant name for a strip slot. Returns True if
        changed. When the variant changes, the slot's params dict is cleared
        because the new plugin will have entirely different parameters.
        """
        if mod_id not in self.slots:
            return False
        slot = self.slots[mod_id]
        if slot.plugin_name == plugin_name:
            return False
        slot.plugin_name = plugin_name
        # Variant changed — old param names/values are stale; new ones will arrive
        slot.params.clear()
        return True
    
    def update_value(self, mod_id, param_id, val127):
        """
        Store the raw 0-127 value for a parameter (received via SysEx 0x31).
        Returns True if changed. This cache lets the bridge compute deltas
        and toggles without round-tripping through Nuendo.
        
        For slot.mOn (paramId 0x00 of slot mods), also mirrors into slot.on bool.
        """
        # slot.mOn is treated specially — also keep the bool in sync
        if mod_id in self.slots and param_id == 0x00:
            new_on = (val127 >= 64)
            slot = self.slots[mod_id]
            changed = (slot.on != new_on)
            slot.on = new_on
            # Also store in params dict for uniform get_value access
            slot.params.setdefault(0x00, {})['value'] = val127
            return changed
        
        store = self._store_for(mod_id)
        if store is None:
            return False
        existing = store.setdefault(param_id, {})
        if existing.get('value') == val127:
            return False
        existing['value'] = val127
        return True
    
    def get_value(self, mod_id, param_id):
        """
        Return the cached 0-127 value for a parameter, or None if unknown.
        Used by the bridge to compute relative deltas and toggle inversions
        before sending an absolute value back to Nuendo.
        """
        # slot.mOn — derive from the bool if no explicit value cached
        if mod_id in self.slots and param_id == 0x00:
            slot = self.slots[mod_id]
            cached = slot.params.get(0x00, {}).get('value')
            if cached is not None:
                return cached
            return 127 if slot.on else 0
        store = self._store_for(mod_id)
        if store is None:
            return None
        return store.get(param_id, {}).get('value')


class AppState:
    """
    Global application state.
    
    A single instance of this type exists throughout the program.
    All modules share the same instance.
    """

    def __init__(self):
        # ── Active mode ──
        self.mode = MODE_VOLUME
        
        # ── Bank navigation ──
        # Which 'page' of 8 tracks is displayed?
        # bank_offset = 0 → tracks 1-8
        # bank_offset = 8 → tracks 9-16, etc.
        self.bank_offset = 0
        # Dynamically-learned last reachable bank offset (end of the VISIBLE
        # project). None = not yet known / unlimited. Set by the end-of-project
        # detection in nuendo_link (0x11 no-movement); reset on scan/reconnect.
        self.bank_offset_cap = None

        # ── Tracks ──
        # Pre-allocate 128 tracks. They will be updated by Nuendo.
        self.tracks = [TrackInfo(i) for i in range(128)]
        self.total_tracks = 128  # Will be updated by scan
        
        # ── Selected track ──
        self.selected_track_index = 0
        
        # ── Sends mode ──
        # Which send is currently displayed? (0 = Send 1, 1 = Send 2, etc.)
        self.current_send = 0
        
        # ── Inserts mode ──
        # Which insert is selected for Device control?
        self.selected_insert_slot = 0
        # Insert bank: 0 = slots 0-7, 8 = slots 8-15
        self.insert_bank_offset = 0
        
        # ── Current track inserts (filled by JS) ──
        self.current_insert_names = [''] * 16
        self.current_insert_active = [False] * 16
        
        # ── Focused insert plugin parameters ──
        self.insert_param_names = [''] * 8
        self.insert_param_values = [''] * 8
        self.insert_params_mode = False

        # ── Edit Channel Settings window state (for the selected channel) ──
        self.editor_open = False

        # ── EQ page state ──
        self.eq_selected_band = 0  # 0-based (0=Band1, 3=Band4)
        # Cache of last-parsed per-band params so the curve stays stable when
        # switching bands (we only get fresh display strings for the selected
        # band; other bands use the most recent parse stored here).
        self.eq_band_cache = [{}, {}, {}, {}]

        # ── Channel Strip footer pill states (one bool per position 0-7) ──
        # Populated by the renderer each frame; read by _update_lower_row_leds
        # so the lower-row LEDs reflect the same on/off state as the on-screen
        # pills (Band on/off, HC/LC on, PreFilter bypass, etc.).
        # None means "no toggle at this position" → LED off.
        self.cs_footer_pill_states = [None] * 8

        # ── DA strip param mirror (for renderer display of DA-based toggles) ──
        # Keyed by (plugin_name, da_param_idx) → float value. Populated by
        # nuendo_link on SysEx 0x29 + 0x39. plugin_name is used as key (not
        # strip_si) so custom strip layouts work without remapping.
        self.da_strip_toggle_values = {}
        
        # ── Selected track sends ──
        self.send_names = [''] * 8          # Destination names
        self.send_levels = [''] * 8         # Level display values
        self.send_on = [False] * 8          # On/Off
        self.send_prepost = [False] * 8     # False=post-fader, True=pre-fader
        
        # ── Connection with Nuendo ──
        self.nuendo_connected = False
        
        # ── Encoders ──
        # Current value of each encoder (used for deltas)
        self.encoder_values = [0.5] * BANK_SIZE
        
        # ── Shift ──
        # Is the Shift button held?
        self.shift_held = False
        self.user_held = False
        self.select_held = False  # Select + Master Encoder = CR Phones level
        self.master_held = False  # Master held = momentarily show the Navigation help screen
        self.nav_active = False   # Navigation D-pads overlay the grid; independent of the
                                  # screen mode (mix pages keep the D-pads — only Note/Scale/
                                  # Session restore the normal pads)
        # 🎰 Vegas mode (undocumented easter egg, toggled by Shift+Master)
        self.vegas_mode = False
        self.vegas_phase = 0
        # When True, the Master Encoder controls CR Phones by default and the
        # Select modifier gives CR Main (Setup → CR Knob page inverts this).
        self.cr_phones_default = False
        
        # ── Lower row button mode (Mute/Solo/Monitor/Rec) ──
        self.lower_mode = "mute"
        
        # ── Transport ──
        self.is_playing = False
        self.is_recording = False
        self.tempo_display = ""
        self.position_display = ""
        self.beats_display = ""
        self.metronome_on = False
        self.cycle_active = False
        
        # ── Control Room ──
        self.cr_volume_display = ""
        
        # ── Touchstrip ──
        self.touchstrip_mode = "pitchbend"  # "pitchbend" or "modwheel"
        
        # ── Drum mode ──
        self.drum_mode = False  # True = 4x4 drum layout
        
        # ── Setup page ──
        self.setup_page = 0         # 0 = MIDI Controller, future pages...
        self.aftertouch_mode = AT_POLY  # default: polyphonic aftertouch
        self.velocity_curve = VC_LINEAR  # default: linear velocity

        # ── Footswitch / pedals (jack 1 = CC 64, jack 2 = CC 69) ──
        # Per pedal: {'action': FS_*, 'invert': bool, 'cc': int}. 'cc' is the
        # destination CC used only when action == FS_EXPRESSION. Persisted to
        # settings.json alongside the other Setup options.
        self.footswitch = {
            1: {'action': FS_SUSTAIN,  'invert': False, 'cc': FS_EXPRESSION_DEFAULT_CC,
                'target': 'cc', 'qc_idx': 0, 'send_idx': 0},  # jack 1 (CC 64)
            2: {'action': FS_PLAYSTOP, 'invert': False, 'cc': FS_EXPRESSION_DEFAULT_CC,
                'target': 'cc', 'qc_idx': 0, 'send_idx': 0},  # jack 2 (CC 69)
        }
        # Expression-pedal calibration in progress: None, or
        # {'pedal': 1|2, 'live': [ring, tip], 'min': [..], 'max': [..]} (raw ADC)
        self.pedal_cal = None
        
        # Pad note range label for the Mix footer (e.g. "C1-G5"), updated by the controller
        self.pad_note_range = ""

        # Expand menu overlay: None, or a key of EXPAND_MENUS ('new', 'mute', …)
        self.expand_menu = None

        # ── Key Commands (note-value buttons CC 36-43, active when Repeat off) ──
        self.kc_page = 0                 # current page index (0..KC_NUM_PAGES-1)
        self.kc_legend_active = False    # True while the on-screen legend overlay is shown
        self.key_commands = make_default_key_commands()  # loaded from keycommands.json

        # ── XY pad (Shift+Device) ──
        # Each axis targets either a selected-track parameter or a raw MIDI CC.
        self.xy_cat_x = "track"      # 'track' or 'cc'
        self.xy_cat_y = "track"
        self.xy_track_param_x = 0    # index into XY_TRACK_PARAMS (0=Vol,1=Pan,2-9=QC1-8)
        self.xy_track_param_y = 1    # default Pan
        self.xy_cc_x = 16            # raw CC number when category == 'cc'
        self.xy_cc_y = 17
        self.xy_val_x = 64.0         # current X value accumulator (0-127, float)
        self.xy_val_y = 64.0         # current Y value accumulator (0-127, float)
        self.xy_sensitivity = 1.0    # delta scale (0.1-4.0): <1 finer, >1 faster
        self.xy_smooth = 0.5         # centroid smoothing 0..0.9 (higher = smoother)

        # ── MIDI CC page ──
        self.cc_numbers = [1, 2, 7, 8, 10, 11, 64, 65]  # default CC assignments
        self.cc_values = [0] * 8       # current CC values (0-127) — encoder position
        self.cc_edit_mode = False      # True = encoders change CC number instead of value
        self.cc_nuendo_values = [-1] * 8  # last known value from Nuendo (-1 = unknown)
        
        # ── Version info ──
        self.js_version = "?"         # will be set by JS via SysEx
        
        # ── Plugin Mappings ──
        self.plugin_mappings = {}     # {plugin_name: mapping_data} loaded from ~/.push2bridge/mappings/
        self.active_mapping = None    # current mapping for the active insert plugin

        # ── Note Repeat ──
        self.repeat_enabled = False
        self.repeat_tempo = 120.0
        self.repeat_subdivision = "1/16"
        
        # ── Accent ──
        self.accent_enabled = False
        self.accent_velocity = 127
        self.accent_held = False  # True when the button is held
        
        # ── Plugin Browser ──
        self.browser_plugins = []           # [{name, vendor, sub_categories, uid}, ...]
        self.browser_collection_index = 1   # Default: "Push" collection
        self.browser_collection_count = 0   # Total number of collections (from JS)
        self.browser_collection_name = ""   # Name of the active collection
        self.browser_collections = []       # [{index, name, count}, ...] all available collections
        self.browser_collections_ready = False  # True when all collection info received
        self.browser_coll_scroll = 0        # Selected collection in picker
        self.browser_list_ready = False     # True when full list received from JS
        self.browser_scroll = 0             # Index of first visible plugin
        self.browser_selected = 0           # Index of selected plugin
        self.browser_target_slot = 0        # Insert slot to load into
        self.browser_phase = "slot_select"  # slot_select / collection_select / folder_select / plugin_list
        self.browser_prev_mode = MODE_VOLUME  # Mode to return to on cancel
        self.browser_instrument = False     # True = browsing/loading VST instruments
        # ── Folder navigation within a collection ──
        # Groups plugins by mCollectionPath ('folder') or by manufacturer
        # ('vendor', virtual folders). "All" (key=None) is always first.
        self.browser_folders = []           # [{key, label, count}]
        self.browser_folder = None          # Selected group key; None = All (flat)
        self.browser_folder_label = ""      # Label of the selected group (for titles)
        self.browser_folder_scroll = 0      # Selected folder in the folder picker
        # 'type' = the collection's own folders (mCollectionPath); 'vendor' =
        # virtual folders by manufacturer. Only takes effect on the "Default"
        # collection (whose folders are organised by plugin type).
        self.browser_group_mode = 'type'
        
        # ── Channel Strip (v1.0.4) ──
        # Holds the selected track's PreFilter, ChannelEQ, and 5 strip slots.
        # Updated by nuendo_link.py from SysEx 0x30/0x32/0x33 messages.
        self.channel_strip = ChannelStripState()
        # Sub-page within MODE_CHANNEL_STRIP. Starts on the 8-cell module
        # overview; upper-row buttons 1-6 drill into module pages (gate/comp/eq/
        # tools/sat/limiter), upper-row 1 on a sub-page returns.
        self.cs_page = CS_PAGE_OVERVIEW

    @property
    def visible_tracks(self):
        """Returns the 8 currently displayed tracks."""
        start = self.bank_offset
        end = start + BANK_SIZE
        return self.tracks[start:end]

    @property
    def selected_track(self):
        """Returns the currently selected track."""
        if 0 <= self.selected_track_index < len(self.tracks):
            return self.tracks[self.selected_track_index]
        return self.tracks[0]

    def _browser_effective_group(self):
        """The grouping only switches to 'vendor' on the Default collection
        (its folders are by type); every other collection always shows its own
        folders (mCollectionPath)."""
        name = (getattr(self, 'browser_collection_name', '') or '').strip().lower()
        if name == 'default' and getattr(self, 'browser_group_mode', 'type') == 'vendor':
            return 'vendor'
        return 'type'

    def _browser_group_field(self):
        return 'vendor' if self._browser_effective_group() == 'vendor' \
            else 'collection_path'

    def build_browser_folders(self):
        """Group the current plugin list by folder (mCollectionPath) or by
        manufacturer (vendor), per the effective grouping. Produces
        self.browser_folders = [{key,label,count}] with an "All" (key=None)
        entry first."""
        mode = self._browser_effective_group()
        field = self._browser_group_field()
        counts = {}
        for p in self.browser_plugins:
            if not p:
                continue
            key = (p.get(field) or '').strip()
            counts[key] = counts.get(key, 0) + 1
        total = sum(counts.values())
        folders = [{'key': None, 'label': 'All', 'count': total}]
        for key in sorted(counts, key=lambda k: k.lower()):
            if key == '':
                label = '(no vendor)' if mode == 'vendor' else '(root)'
            elif mode == 'vendor':
                label = key
            else:
                label = key.lstrip('/').replace('/', ' / ')
            folders.append({'key': key, 'label': label, 'count': counts[key]})
        self.browser_folders = folders

    def browser_view_indices(self):
        """Absolute indices into browser_plugins for the current group filter
        (browser_folder). None → the whole collection (flat)."""
        key = self.browser_folder
        if key is None:
            return [i for i, p in enumerate(self.browser_plugins) if p]
        field = self._browser_group_field()
        return [i for i, p in enumerate(self.browser_plugins)
                if p and (p.get(field) or '').strip() == key]

    def get_encoder_value_for_mode(self, track_index_in_bank, mode=None):
        """
        Returns the value (0.0-1.0) that encoder N should reflect
        according to the active mode.

        Used by the renderer to draw encoder positions. `mode` overrides
        self.mode (used by the Navigation page, whose effective mode is the
        underlying mix mode) without mutating shared state.
        """
        m = mode if mode is not None else self.mode
        absolute_index = self.bank_offset + track_index_in_bank
        if absolute_index >= len(self.tracks):
            return 0.0

        track = self.tracks[absolute_index]

        if m == MODE_VOLUME:
            return track.volume

        elif m == MODE_PAN:
            # Pan goes from -1.0 to +1.0, normalize to 0.0-1.0 for display
            return (track.pan + 1.0) / 2.0

        elif m == MODE_SENDS:
            return track.sends[self.current_send]

        elif m == MODE_DEVICE:
            selected = self.selected_track
            if track_index_in_bank < len(selected.quick_controls):
                return selected.quick_controls[track_index_in_bank].value
            return 0.0

        elif m == MODE_TRACK:
            # Combined mode on the selected track
            selected = self.selected_track
            if track_index_in_bank == 0:
                return selected.volume
            elif track_index_in_bank == 1:
                return (selected.pan + 1.0) / 2.0
            elif track_index_in_bank >= 2 and track_index_in_bank <= 7:
                send_idx = track_index_in_bank - 2
                if send_idx < len(selected.sends):
                    return selected.sends[send_idx]
            return 0.0
        
        return 0.0

    def can_go_bank_left(self):
        return self.bank_offset > 0

    def can_go_bank_right(self):
        return self.bank_offset + BANK_SIZE < self.total_tracks

    def go_bank_left(self):
        if self.can_go_bank_left():
            self.bank_offset = max(0, self.bank_offset - BANK_SIZE)

    def go_bank_right(self):
        if self.can_go_bank_right():
            self.bank_offset += BANK_SIZE

    def __repr__(self):
        return (f"<AppState mode={self.mode} bank={self.bank_offset} "
                f"selected={self.selected_track_index} "
                f"nuendo={'OK' if self.nuendo_connected else 'disconnected'}>")
