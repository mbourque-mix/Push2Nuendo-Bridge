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
    MODE_VOLUME, MODE_PAN, MODE_SENDS, MODE_DEVICE, MODE_INSERTS, MODE_TRACK, MODE_OVERVIEW, MODE_CR
)
from pad_grid import PadGrid
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
}

# ─────────────────────────────────────────────────────────────────────────────
# Encoder sensitivity
#
# Push 2 encoders send relative deltas (+1 or -1 per notch).
# We multiply by these values to adjust the rate of change.
# ─────────────────────────────────────────────────────────────────────────────

ENCODER_SENSITIVITY_NORMAL = 0.008   # Normal speed (1 notch = 0.8%)
ENCODER_SENSITIVITY_FINE   = 0.001   # Fine speed with Shift (1 notch = 0.1%)


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
        
        # Callback for initial scan when Nuendo connects
        self.nuendo_link._on_connected_callback = lambda: self._initial_bank_refresh()
        
        # Callback for auto bank switch
        self.nuendo_link._on_bank_switch_needed = lambda new_bank: self._auto_switch_bank(new_bank)
        
        # Callback for touchstrip LEDs in volume mode
        self.nuendo_link._touchstrip_led_callback = lambda val: self._update_touchstrip_leds(val)
        
        # Callback for LED update when selection changes
        self.nuendo_link._on_selection_changed = lambda: self._update_all_leds()

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
                # Swing Encoder (top left) = AI Knob
                if increment > 0:
                    midi_val = min(63, abs(increment))
                else:
                    midi_val = 64 + min(63, abs(increment))
                self.nuendo_link.send_cc(64, midi_val)
            elif 'master' in encoder_name.lower():
                # Master Encoder (haut droite)
                if self.note_repeat.enabled:
                    self.note_repeat.tempo += increment * 1.0
                    self.note_repeat.tempo = max(40.0, min(300.0, self.note_repeat.tempo))
                    self._sync_repeat_state()
                elif self.state.user_held:
                    # User + Master Encoder = Phones Level
                    if increment > 0:
                        midi_val = min(63, abs(increment))
                    else:
                        midi_val = 64 + min(63, abs(increment))
                    self.nuendo_link.send_cc(77, midi_val)
                else:
                    # Control Room Volume
                    if increment > 0:
                        midi_val = min(63, abs(increment))
                    else:
                        midi_val = 64 + min(63, abs(increment))
                    self.nuendo_link.send_cc(79, midi_val)
            return
        
        encoder_index = TRACK_ENCODERS.index(encoder_name)
        
        # When Accent is held, the first encoder adjusts velocity
        if self.state.accent_held:
            if encoder_index == 0:
                self.state.accent_velocity = max(1, min(127, self.state.accent_velocity + increment))
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
        
        elif mode == MODE_DEVICE:
            selected = state.selected_track
            if encoder_index < len(selected.quick_controls):
                selected.quick_controls[encoder_index].value = new_val
            self.nuendo_link.send_quick_control_change(encoder_index, new_val)
        
        elif mode == MODE_INSERTS and state.insert_params_mode:
            # Send CC on channel 2 for insert parameters
            if increment > 0:
                midi_val = min(63, abs(increment))
            else:
                midi_val = 64 + min(63, abs(increment))
            self.nuendo_link.send_cc_ch2(20 + encoder_index, midi_val)
            return  # No local update, feedback comes from JS
        
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
            # Shift + touch Master Encoder = reset Control Room to ~0 dB (-0.01)
            self.nuendo_link.send_cc(78, 95)
    
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
        
        # ── Layout (toggle drum mode) ──
        if BTN_LAYOUT and button_name == BTN_LAYOUT:
            if state.shift_held:
                modes = ["pitchbend", "modwheel", "volume"]
                current_idx = modes.index(self.state.touchstrip_mode) if self.state.touchstrip_mode in modes else 0
                self.state.touchstrip_mode = modes[(current_idx + 1) % len(modes)]
                self._configure_touchstrip_mode()
                print(f"  Touchstrip mode: {self.state.touchstrip_mode}")
                # Display mode temporarily
                labels = {"pitchbend": "PITCH BEND", "modwheel": "MOD WHEEL", "volume": "VOLUME FADER"}
                self.state._touchstrip_overlay = labels[self.state.touchstrip_mode]
                self.state._touchstrip_overlay_until = time.time() + 2.0
            else:
                self.state.drum_mode = not self.state.drum_mode
                self.pad_grid.drum_mode = self.state.drum_mode
                self.pad_grid._update_note_map()
                self._update_pad_colors()
            self._set_button_led(BTN_LAYOUT, self.state.drum_mode)
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
                # In parameters mode : Left = previous bank
                self.nuendo_link.send_cc_ch2(3, 127)
                time.sleep(0.01)
                self.nuendo_link.send_cc_ch2(3, 0)
                return
            if state.mode in (MODE_INSERTS, MODE_SENDS, MODE_DEVICE):
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
                            self._scan_inserts()
                        self._update_upper_row_leds()
                        self._update_lower_row_leds()
                        self._update_nav_leds()
                    threading.Thread(target=_nav_left, daemon=True).start()
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
                self.nuendo_link.send_cc_ch2(2, 127)
                time.sleep(0.01)
                self.nuendo_link.send_cc_ch2(2, 0)
                return
            if state.mode in (MODE_INSERTS, MODE_SENDS, MODE_DEVICE):
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
                            self._scan_inserts()
                        self._update_upper_row_leds()
                        self._update_lower_row_leds()
                        self._update_nav_leds()
                    threading.Thread(target=_nav_right, daemon=True).start()
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
                self._set_mode(MODE_TRACK)
            else:
                self._set_mode(MODE_VOLUME)
            return
        
        if button_name == BTN_MODE_SENDS:
            if state.shift_held:
                self._set_mode(MODE_PAN)
            elif state.mode == MODE_SENDS:
                self._set_mode(MODE_VOLUME)
            else:
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
            # Return to MIDI note pads (exit Overview if active)
            if state.mode == MODE_OVERVIEW:
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
            if state.mode != MODE_INSERTS:
                self._set_mode(MODE_INSERTS)
            state.selected_insert_slot = 0
            self.nuendo_link._insert_current_slot = 0
            self._scan_inserts()
            return
        
        # ── Overview mode (disabled for now) ──
        # if button_name == BTN_MODE_OVERVIEW:
        #     ...
        
        # ── Page ◄/► (inactive without Overview) ──
        
        # ── Rescan (Shift + 7th lower row button) ──
        if button_name == BTN_RESCAN and state.shift_held:
            for t in state.tracks:
                t.name = f"Track {t.index + 1}"
                t.color = (150, 150, 150)
            self._full_scan()
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
        
        # ── Device mode: intercept buttons ──
        if state.mode == MODE_DEVICE:
            # Lower row: button 1 = Open Instrument UI
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
        
        # ── Inserts mode: intercept buttons ──
        if state.mode == MODE_INSERTS:
            names = state.current_insert_names
            
            # Upper row
            for i, btn in enumerate(BUTTONS_UPPER_ROW):
                if button_name == btn:
                    if state.insert_params_mode:
                        # In parameters mode, upper row = back to list
                        state.insert_params_mode = False
                        self._update_upper_row_leds()
                        self._update_lower_row_leds()
                    elif i < len(names) and names[i]:
                        # Navigate to slot and enter parameters mode
                        state.selected_insert_slot = i
                        state.insert_param_names = [''] * 8
                        state.insert_param_values = [''] * 8
                        if state.shift_held:
                            # Shift+Upper = params + open UI
                            self._insert_action(i, 'params_and_edit')
                        else:
                            # Upper = params only
                            self._insert_action(i, 'params')
                        state.insert_params_mode = True
                        self._update_upper_row_leds()
                        self._update_lower_row_leds()
                    return
            
            # Lower row
            for i, btn in enumerate(BUTTONS_LOWER_ROW):
                if button_name == btn:
                    if state.insert_params_mode:
                        # In parameters mode, lower row = actions
                        slot = state.selected_insert_slot
                        if i == 0:
                            # Button 1 = Open/Close UI
                            self._insert_action(slot, 'edit')
                        elif i == 1:
                            # Button 2 = Bypass toggle
                            self._insert_action(slot, 'bypass')
                        elif i == 2:
                            # Button 3 = Deactivate (mOn)
                            self._insert_action(slot, 'deactivate')
                    else:
                        # List view : bypass
                        if i < len(names) and names[i]:
                            self._insert_action(i, 'bypass')
                    return
            
            # Browse → re-scan (refresh after adding insert)
            if button_name == BTN_MODE_INSERTS:
                self._scan_inserts()
                return
            
            return
        
        # ── Mode buttons Mute/Monitor (CC 60) ──
        if button_name == Push2Constants.BUTTON_MUTE:
            if state.shift_held:
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
        
        # ── Boutons du bas (lower row 1-8) : Mute/Solo/Monitor/Rec ──
        for i, btn in enumerate(BUTTONS_LOWER_ROW):
            if button_name == btn:
                track_in_bank = i
                abs_index = state.bank_offset + i
                if abs_index >= state.total_tracks:
                    return
                
                track = state.tracks[abs_index]
                mode = state.lower_mode
                
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
                
                self._update_lower_row_leds()
                return
        
        # ── Track selection buttons (upper row) ──
        for i, btn in enumerate(BUTTONS_UPPER_ROW):
            if button_name == btn:
                abs_index = state.bank_offset + i
                
                # Shift + upper row button = clear peak for this track
                if state.shift_held and abs_index < len(state.tracks):
                    state.tracks[abs_index].peak_clipped = False
                    return
                
                # Record timestamp for long press detection
                self._upper_row_press_time[button_name] = time.time()
                
                # Timer for long press : open instrument UI after 1.5s
                if state.mode not in (MODE_INSERTS, MODE_CR, MODE_SENDS):
                    import threading
                    def _long_press_check(btn_name=button_name, idx=i):
                        time.sleep(1.0)
                        # Check that the button is still pressed
                        if btn_name in self._upper_row_press_time:
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
        
        # Long press on upper row: clean up tracking
        if button_name in self._upper_row_press_time:
            self._upper_row_press_time.pop(button_name)

    # ─────────────────────────────────────────
    # Pad handling
    # ─────────────────────────────────────────

    def _handle_pad_press(self, pad_n, pad_ij, velocity):
        """Called when a pad is pressed."""
        row, col = pad_ij
        if row is None:
            return
        
        if self.pad_grid.scale_mode:
            self._handle_scale_pad(row, col)
            return
        
        # In Overview mode, pads control mute/solo/rec/monitor
        if self.state.mode == MODE_OVERVIEW:
            self._handle_overview_pad(row, col)
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
        
        if self.pad_grid.scale_mode:
            return
        
        if self.state.mode == MODE_OVERVIEW:
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
        """Called when pad pressure changes (aftertouch)."""
        row, col = pad_ij
        if row is None:
            return
        if self.state.mode == MODE_OVERVIEW or self.pad_grid.scale_mode:
            return
        midi_note = self.pad_grid.pad_to_note(row, col)
        if midi_note < 0:
            return
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
        if not self.push or not self.push.midi_is_configured():
            return
        
        # In Overview mode, pads are handled by _update_overview_pads
        if self.state.mode == MODE_OVERVIEW:
            self._update_overview_pads()
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
        
        Only acts on tracks in the current bank (displayed on screen).
        For tracks in other banks, navigate with ◄/► first.
        """
        state = self.state
        pad_map, _, _ = compute_overview_layout(state.tracks, state.total_tracks, state.overview_page)
        
        track_idx = pad_map.get((row, col))
        if track_idx is None:
            return
        
        track = state.tracks[track_idx]
        target_bank = (track_idx // BANK_SIZE) * BANK_SIZE
        track_in_bank = track_idx - target_bank
        
        # Only tracks in the current bank
        if target_bank != state.bank_offset:
            return
        
        mode = state.lower_mode
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
        """Update pad colors in Overview mode."""
        if not self.push or self.state.mode != MODE_OVERVIEW:
            return
        
        state = self.state
        pad_map, _, _ = compute_overview_layout(state.tracks, state.total_tracks, state.overview_page)
        
        any_solo = any(t.is_solo for t in state.tracks if t.name)
        blink_on = getattr(self, '_overview_blink_phase', True)
        
        pad_count = 0
        _reserved = {0, 21, 37, 45, 122, 124, 110, 111, 112, 113, 114, 115, 116, 117}
        
        for row in range(8):
            for col in range(8):
                track_idx = pad_map.get((row, col))
                pad_note = 36 + (7 - row) * 8 + col
                
                palette_idx = 1 + pad_count
                while palette_idx in _reserved:
                    palette_idx += 1
                pad_count += 1
                
                if track_idx is None:
                    self._send_midi_to_push([0x90, pad_note, 0])
                    continue
                
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
        self._send_midi_to_push([0xF0, 0x00, 0x21, 0x1D, 0x01, 0x01, 0x1E, 0x01, 0xF7])
        print("  ✓ Push 2 aftertouch → polyphonic")

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
        self.nuendo_link.send_mode_change(new_mode)
        self._update_all_leds()
        
        if new_mode == MODE_OVERVIEW:
            self.state.overview_page = 0
        elif old_mode == MODE_OVERVIEW:
            self._restore_default_palette()
            self._update_pad_colors()
    
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
            
            # Rec (CC 86, colored): solid red if rec active, blinking otherwise
            # Push 2 button palette: 5 = dim blink, 7 = bright solid
            any_armed = any(t.is_armed for t in self.state.tracks if t.name)
            self._send_midi_to_push([0xB0, 86, 7 if any_armed else 5])
            
            if BTN_AUTOMATE:
                track = self.state.selected_track
                if track and track.automation_write:
                    self._send_midi_to_push([0xB0, 89, 4])    # Red
                elif track and track.automation_read:
                    self._send_midi_to_push([0xB0, 89, 21])   # Green
                else:
                    self._send_midi_to_push([0xB0, 89, BTN_WHITE])
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
        except Exception:
            pass

    def _update_mode_leds(self):
        """Light the active mode button, turn off others."""
        if not self.push:
            return
        
        mode = self.state.mode
        buttons_modes = {
            BTN_MODE_VOLUME:  [MODE_VOLUME, MODE_TRACK],
            BTN_MODE_SENDS:   [MODE_SENDS, MODE_PAN],
            BTN_DEVICE:       [MODE_DEVICE],
            BTN_MODE_INSERTS: [MODE_INSERTS],
            BTN_MODE_OVERVIEW: [MODE_OVERVIEW],
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
        
        left_color  = LED_WHITE if self.state.can_go_bank_left() else LED_DIM_GREY
        right_color = LED_WHITE if self.state.can_go_bank_right() else LED_DIM_GREY
        
        self.push.buttons.set_button_color(BTN_LEFT, left_color)
        self.push.buttons.set_button_color(BTN_RIGHT, right_color)

    def _update_upper_row_leds(self):
        """Upper row LEDs (CC 102-109)."""
        if not self.push:
            return
        
        state = self.state
        
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
                for i in range(8):
                    cc = 102 + i
                    try:
                        name = state.current_insert_names[i] if i < len(state.current_insert_names) else ''
                        if name:
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
        
        # ── Device mode: button 1 = OPEN UI, rest off ──
        if state.mode == MODE_DEVICE:
            for i in range(8):
                cc = 20 + i
                try:
                    if i == 0:
                        self._send_midi_to_push([0xB0, cc, BTN_WHITE])
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
            if state.insert_params_mode:
                # Parameters mode: action buttons
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
                        else:
                            self._send_midi_to_push([0xB0, cc, LED_OFF])
                    except Exception:
                        pass
            else:
                # List view: bypass state
                for i in range(8):
                    cc = 20 + i
                    try:
                        name = state.current_insert_names[i] if i < len(state.current_insert_names) else ''
                        active = state.current_insert_active[i] if i < len(state.current_insert_active) else False
                        if not name:
                            self._send_midi_to_push([0xB0, cc, LED_OFF])
                        elif active:
                            self._send_midi_to_push([0xB0, cc, BTN_BLUE])
                        else:
                            self._send_midi_to_push([0xB0, cc, BTN_DIM])
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
                
                # Update LEDs if a change was signaled
                if getattr(self.nuendo_link, '_leds_dirty', False):
                    self.nuendo_link._leds_dirty = False
                    self._update_all_leds()
                
                # Blink for Overview mode (~2Hz)
                if self.state.mode == MODE_OVERVIEW:
                    if not hasattr(self, '_overview_blink_counter'):
                        self._overview_blink_counter = 0
                    self._overview_blink_counter += 1
                    if self._overview_blink_counter >= 8:  # ~4Hz at 30fps
                        self._overview_blink_counter = 0
                        self._overview_blink_phase = not getattr(self, '_overview_blink_phase', True)
                        self._update_overview_pads()

                if _display_ok:
                    frame = render_frame(self.state, self.pad_grid, self.cr_state)
                    self.push.display.display_frame(
                        frame,
                        input_format=push2_python.constants.FRAME_FORMAT_BGR565
                    )
                    _frame_count += 1
                    if _frame_count == 1:
                        print("  ✓ First frame sent to Push 2 display")
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
        
        def _do():
            if action == 'bypass':
                # CC 20+slot channel 4 to toggle the dedicated viewer bypass
                self.nuendo_link.send_cc_ch4(20 + target_slot, 127)
                time.sleep(0.01)
                self.nuendo_link.send_cc_ch4(20 + target_slot, 0)
                print(f"  Bypass toggle slot {target_slot}")
            elif action == 'edit':
                # Navigate the main viewer to the correct slot
                self.nuendo_link.send_cc(89, 127)  # Reset
                time.sleep(0.01)
                self.nuendo_link.send_cc(89, 0)
                time.sleep(0.15)
                for _ in range(target_slot):
                    self.nuendo_link.send_cc(1, 127)  # Next
                    time.sleep(0.01)
                    self.nuendo_link.send_cc(1, 0)
                    time.sleep(0.15)
                # Toggle edit via CC 99 (bound to mEdit via custom var)
                # We use the same mechanism as the bypass viewer
                # but for edit, there is only one viewer
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
                # Navigate + open UI
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

    def _scan_inserts(self):
        """Scan 8 inserts by navigating the viewer slot by slot."""
        import threading
        
        self._insert_scan_version += 1
        my_version = self._insert_scan_version
        
        def _scan():
            # Reset names
            self.state.current_insert_names = [''] * 16
            self.state.current_insert_active = [False] * 16
            
            track_name = self.state.selected_track.name if self.state.selected_track else '?'
            print(f"  Inserts: scan v{my_version} (track='{track_name}')")
            
            # Reset to slot 0
            self.nuendo_link.send_cc(89, 127)
            time.sleep(0.01)
            self.nuendo_link.send_cc(89, 0)
            time.sleep(0.3)
            
            for slot in range(1, 8):
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
            print(f"  ✓ Inserts scan v{my_version}: {scanned_names[:8]}")
            
            if my_version != self._insert_scan_version:
                return
            
            # Position the bypass viewers
            self.nuendo_link._insert_positioning = True
            self._position_bypass_viewers()
            self.nuendo_link._insert_positioning = False
            
            # Restore scanned names
            self.state.current_insert_names = scanned_names
            
            self._update_lower_row_leds()
            self._update_upper_row_leds()
        
        threading.Thread(target=_scan, daemon=True).start()

    def _position_bypass_viewers(self):
        """Position the 8 bypass viewers, each on its slot."""
        names = self.state.current_insert_names
        count = sum(1 for n in names[:8] if n)
        if count == 0:
            return
        print(f"  Positioning {count} bypass viewers...")
        for slot in range(8):
            # Reset viewer N : Note 60+N
            self.nuendo_link.send_note(60 + slot, 127)
            time.sleep(0.01)
            self.nuendo_link.send_note(60 + slot, 0)
            time.sleep(0.03)
            
            # Next viewer N : Note 70+N, N fois
            for _ in range(slot):
                self.nuendo_link.send_note(70 + slot, 127)
                time.sleep(0.01)
                self.nuendo_link.send_note(70 + slot, 0)
                time.sleep(0.03)
        
        print("  ✓ Bypass viewers positioned")

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
