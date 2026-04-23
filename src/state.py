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

# Bridge version
BRIDGE_VERSION = "1.0.3"

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

# MIDI CC encoder modes
CC_ABSOLUTE = "absolute"  # Encoder value sent immediately (can cause jumps)
CC_PICKUP   = "pickup"    # Encoder only sends after catching up to Nuendo value

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
        
        # ── MIDI CC page ──
        self.cc_numbers = [1, 2, 7, 8, 10, 11, 64, 65]  # default CC assignments
        self.cc_values = [0] * 8       # current CC values (0-127) — encoder position
        self.cc_edit_mode = False      # True = encoders change CC number instead of value
        self.cc_mode = CC_ABSOLUTE     # CC_ABSOLUTE or CC_PICKUP
        self.cc_nuendo_values = [-1] * 8  # last known value from Nuendo (-1 = unknown)
        self.cc_picked_up = [True] * 8    # whether each encoder has caught up
        self.cc_pickup_direction = [0] * 8  # initial turn direction (0=none, 1=CW, -1=CCW)
        
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
