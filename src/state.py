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
MODE_OVERVIEW = "overview" # Overview mode: pads = project tracks
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
BRIDGE_VERSION = "1.0.6-dev"

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
        
        # Pad note range label for the Mix footer (e.g. "C1-G5"), updated by the controller
        self.pad_note_range = ""

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
        
        # ── Overview ──
        self.overview_page = 0
        
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
        self.browser_phase = "slot_select"  # "slot_select" or "plugin_list"
        self.browser_prev_mode = MODE_VOLUME  # Mode to return to on cancel
        self.browser_instrument = False     # True = browsing/loading VST instruments
        
        # ── Channel Strip (v1.0.4) ──
        # Holds the selected track's PreFilter, ChannelEQ, and 5 strip slots.
        # Updated by nuendo_link.py from SysEx 0x30/0x32/0x33 messages.
        self.channel_strip = ChannelStripState()
        # Sub-page within MODE_CHANNEL_STRIP. Starts on "overview"; upper row
        # buttons 1-6 drill into module pages, upper row 1 on a sub-page returns.
        self.cs_page = CS_PAGE_OVERVIEW
        # Sub-page within MODE_CHANNEL_STRIP:
        #   "overview"  — 8-cell module overview (Gate/Comp/EQ/Tools/Sat/Limiter/Phase/PreGain)
        #   "gate" / "comp" / "eq" / "tools" / "sat" / "limiter" — drill-down pages (TBD)
        self.cs_page = "overview"

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

    def get_encoder_value_for_mode(self, track_index_in_bank):
        """
        Returns the value (0.0-1.0) that encoder N should reflect
        according to the active mode.
        
        Used by the renderer to draw encoder positions.
        """
        absolute_index = self.bank_offset + track_index_in_bank
        if absolute_index >= len(self.tracks):
            return 0.0
        
        track = self.tracks[absolute_index]
        
        if self.mode == MODE_VOLUME:
            return track.volume
        
        elif self.mode == MODE_PAN:
            # Pan goes from -1.0 to +1.0, normalize to 0.0-1.0 for display
            return (track.pan + 1.0) / 2.0
        
        elif self.mode == MODE_SENDS:
            return track.sends[self.current_send]
        
        elif self.mode == MODE_DEVICE:
            selected = self.selected_track
            if track_index_in_bank < len(selected.quick_controls):
                return selected.quick_controls[track_index_in_bank].value
            return 0.0
        
        elif self.mode == MODE_TRACK:
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
