"""
nuendo_link.py — MIDI link with Nuendo

This module handles communication between the Python Bridge and Nuendo.

HOW IT WORKS:
- Nuendo (via its JS script) sends MIDI messages on the "NuendoBridge In" port
- This module listens on this port and updates the application state (state.py)
- When the user moves an encoder, this module sends a CC on "NuendoBridge Out"
- Nuendo receives this CC and changes the corresponding parameter

COMMUNICATION PROTOCOL (MIDI CC):
Nuendo → Bridge (port NuendoBridge In) :
  CC 127 ch15 : Heartbeat (sent every ~100ms — proves Nuendo is connected)
  CC 10  : Total number of tracks (value = count)
  CC 11  : Selected track index
  CC 20-27 : Volume of tracks in the current bank (shared bank)
  CC 30-37 : Track pan (value 0-127, 64 = center)
  CC 40-47 : Send 1 levels
  CC 50-57 : Send 2 levels
  CC 60-67 : Quick Controls of the selected track
  SysEx F0 00 21 09 01 ... F7 : Track names and metadata

Bridge → Nuendo (port NuendoBridge Out) :
  CC 1   : Active mode (0=Volume, 1=Pan, 2=Sends, 3=Device, 4=Inserts)
  CC 2   : Bank offset (which bank of 8 tracks is visible)
  CC 20-27 : Volume changes (encoders 1-8)
  CC 30-37 : Pan changes
  CC 40-47 : Send changes
  CC 60-67 : Quick Control changes
  CC 80   : Selected track (index)
"""

import rtmidi
import threading
import time
import struct
import os
from state import (
    AppState, TrackInfo, InsertInfo, QuickControl,
    MODE_VOLUME, MODE_PAN, MODE_SENDS, MODE_DEVICE, MODE_INSERTS, MODE_OVERVIEW,
    BANK_SIZE
)

# Virtual MIDI port names (created by the bridge at startup)
# Nuendo will see these in its MIDI port list
# IMPORTANT: Names must NOT contain "Push 2" or "Ableton" to avoid
# confusion with the actual Push 2 MIDI ports detected by push2-python
PORT_BRIDGE_IN   = "NuendoBridge In"    # Nuendo sends TO this port (bridge listens)
PORT_BRIDGE_OUT  = "NuendoBridge Out"   # Bridge sends TO Nuendo via this port
PORT_NOTES_OUT   = "BridgeNotes"        # Notes from bridge to Nuendo
PORT_NOTES_IN    = "BridgeNotes In"     # Playback notes from Nuendo to bridge

# Legacy IAC/loopMIDI port names (fallback if virtual ports fail)
# On Windows, users must create these ports in loopMIDI
PORT_FROM_NUENDO = "NuendoBridge In"
PORT_TO_NUENDO   = "NuendoBridge Out"

PORT_NOTES       = "Push 2"            # Push 2 User port for MIDI notes
PORT_NOTES_ALT   = "User Port"         # Alternate name

# Nuendo connection timeout (in seconds)
# If no heartbeat received for X seconds → disconnected
HEARTBEAT_TIMEOUT = 10.0


class NuendoLink:
    """
    Handle bidirectional MIDI communication with Nuendo.
    
    Usage :
        link = NuendoLink(state)
        link.start()      # Starts the MIDI reading threads
        ...
        link.stop()       # Stop cleanly
    """

    def __init__(self, state: AppState):
        self.state = state
        
        self._midi_in  = None
        self._midi_out = None
        self._midi_notes_out = None  # Push 2 User port for notes
        self._midi_notes_in = None   # Port to receive playback notes
        self._note_display_callback = None  # Callback for lighting pads
        self._cr_state = None  # Reference to ControlRoomState
        self._last_heartbeat = 0.0
        self._connection_grace_until = 0.0  # Ignore value CCs until this timestamp
        self._vu_ignore_until = time.time() + 10.0  # Ignore VU peaks until Nuendo is connected
        self._touchstrip_led_callback = None  # Callback for touchstrip LEDs
        self._watchdog_thread = None
        self._running = False
        self._on_connected_callback = None
        self._da_available = False  # True when JS reports DirectAccess is active
        self._da_inserts_ready = False  # True when JS has explored the insert tree
        self._da_insert_cache = []  # Mirrored from JS: [{bypass_tag, title, bypassed}]
        # Strip slot DA (v1.0.4)
        self._da_strip_slot_cache = []   # [{slot_index, mod_id, bypassed, is_on, plugin_name, slot_title}]
        self._da_strip_explored   = False  # True once JS has sent 0x35
        # ── Channel Strip discovery dump (Axe B) ──
        # Auto-written each time a strip param announce or display change
        # triggers a real state change. Lets users inspect the bank zone
        # contents for each module without scrolling Nuendo's console window.
        # Path is rewritten in full on each update — newest state always wins.
        self._strip_discovery_log = os.path.expanduser('~/strip-discovery.log')
        self._da_bypass_fallback_slot = -1  # Slot needing viewer fallback
        
        # MTC (MIDI Time Code)
        self._mtc_pieces = [0] * 8  # 8 quarter frame pieces
        self._mtc_hours = 0
        self._mtc_minutes = 0
        self._mtc_seconds = 0
        self._mtc_frames = 0
        
        # MIDI Clock for bars:beats
        self._clock_ticks = 0       # Tick counter (24 per quarter note)
        self._clock_beat = 1        # Current beat (1-based)
        self._clock_bar = 1         # Current bar (1-based)
        self._clock_time_sig_num = 4  # Time signature: numerator
        self._clock_time_sig_den = 4  # Time signature: denominator

    # ─────────────────────────────────────────────
    # MIDI port connection
    # ─────────────────────────────────────────────

    def start(self):
        """
        Open MIDI ports and start listening.
        
        Strategy:
        1. Try to create virtual ports (no IAC/loopMIDI needed)
        2. Fall back to IAC/loopMIDI ports if virtual ports fail
        
        Returns True if successful, False if ports could not be opened.
        """
        # Try virtual ports first, fall back to IAC/loopMIDI
        success_in = self._open_virtual_input()
        success_out = self._open_virtual_output()
        
        if not success_in or not success_out:
            print("  ⚠ Virtual ports failed, trying IAC/loopMIDI...")
            if not success_in:
                success_in = self._open_iac_input()
            if not success_out:
                success_out = self._open_iac_output()
        
        # Notes ports (always virtual)
        self._open_notes_ports()
        
        if success_in and success_out:
            self._running = True
            self._watchdog_thread = threading.Thread(
                target=self._watchdog_loop, daemon=True
            )
            self._watchdog_thread.start()
            return True
        else:
            print("  ✗ Could not open MIDI ports")
            return False

    def stop(self):
        """Cleanly close all MIDI ports."""
        self._running = False
        for port in [self._midi_in, self._midi_out, self._midi_notes_out, self._midi_notes_in]:
            if port:
                try:
                    port.close_port()
                except Exception:
                    pass

    # ── Virtual ports (preferred — no IAC/loopMIDI needed) ──

    def _open_virtual_input(self):
        """Create a virtual input port that Nuendo can send to."""
        try:
            self._midi_in = rtmidi.MidiIn()
            self._midi_in.ignore_types(sysex=False, timing=False, active_sense=True)
            self._midi_in.open_virtual_port(PORT_BRIDGE_IN)
            self._midi_in.set_callback(self._on_midi_received)
            print(f"  ✓ Virtual port '{PORT_BRIDGE_IN}' created (Nuendo → Bridge)")
            return True
        except Exception as e:
            print(f"  ⚠ Virtual input port failed: {e}")
            return False

    def _open_virtual_output(self):
        """Create a virtual output port that Nuendo can receive from."""
        try:
            self._midi_out = rtmidi.MidiOut()
            self._midi_out.open_virtual_port(PORT_BRIDGE_OUT)
            print(f"  ✓ Virtual port '{PORT_BRIDGE_OUT}' created (Bridge → Nuendo)")
            return True
        except Exception as e:
            print(f"  ⚠ Virtual output port failed: {e}")
            return False

    # ── IAC/loopMIDI fallback ──

    @staticmethod
    def _find_port_index(ports, target):
        """
        Return the index of a port matching ``target``.

        Prefers an exact name match; loopMIDI sometimes appends an index
        (e.g. "NuendoBridge In 2"), so fall back to a substring match.
        Returns None if not found.
        """
        for i, name in enumerate(ports):
            if name == target:
                return i
        for i, name in enumerate(ports):
            if target in name:
                return i
        return None

    def _open_iac_input(self):
        """Open an existing IAC/loopMIDI input port."""
        self._midi_in = rtmidi.MidiIn()
        self._midi_in.ignore_types(sysex=False, timing=False, active_sense=True)
        ports = self._midi_in.get_ports()
        
        idx = self._find_port_index(ports, PORT_FROM_NUENDO)
        if idx is not None:
            try:
                self._midi_in.open_port(idx)
            except Exception as e:
                print(f"  ✗ Could not open input port '{ports[idx]}': {e}")
                print(f"    Available input ports: {ports}")
                print( "    → That port is already in use by another app.")
                print( "      Close other MIDI software, make sure only ONE")
                print( "      copy of the bridge runs, and in Nuendo/Cubase")
                print( "      uncheck it from 'In All MIDI Inputs'.")
                return False
            self._midi_in.set_callback(self._on_midi_received)
            print(f"  ✓ loopMIDI port '{PORT_FROM_NUENDO}' connected")
            return True
        
        print(f"  ✗ Port '{PORT_FROM_NUENDO}' not found")
        print(f"    Available ports: {ports}")
        return False

    def _open_iac_output(self):
        """Open an existing IAC/loopMIDI output port."""
        self._midi_out = rtmidi.MidiOut()
        ports = self._midi_out.get_ports()
        
        idx = self._find_port_index(ports, PORT_TO_NUENDO)
        if idx is not None:
            try:
                self._midi_out.open_port(idx)
            except Exception as e:
                print(f"  ✗ Could not open output port '{ports[idx]}': {e}")
                print(f"    Available output ports: {ports}")
                print( "    → That port is already in use by another app.")
                return False
            print(f"  ✓ loopMIDI port '{PORT_TO_NUENDO}' connected")
            return True

        print(f"  ✗ Output port '{PORT_TO_NUENDO}' not found")
        print(f"    Available output ports: {ports}")
        print(f"    → Create a loopMIDI port named exactly '{PORT_TO_NUENDO}'")
        return False

    # ── Notes ports (always virtual) ──

    def _open_notes_ports(self):
        """Create virtual ports for MIDI note I/O."""
        # Output: bridge sends notes to Nuendo
        self._midi_notes_out = rtmidi.MidiOut()
        try:
            self._midi_notes_out.open_virtual_port(PORT_NOTES_OUT)
            print(f"  ✓ Virtual port '{PORT_NOTES_OUT}' created")
        except Exception:
            # Windows (WinMM) has no virtual ports — use the loopMIDI port
            ports = self._midi_notes_out.get_ports()
            idx = self._find_port_index(ports, PORT_NOTES_OUT)
            if idx is not None:
                try:
                    self._midi_notes_out.open_port(idx)
                    print(f"  ✓ loopMIDI port '{PORT_NOTES_OUT}' connected")
                except Exception as e:
                    print(f"  ⚠ Notes output port failed: {e}")
                    self._midi_notes_out = None
            else:
                print(f"  ⚠ Notes output port '{PORT_NOTES_OUT}' not found "
                      f"(create a loopMIDI port with this exact name)")
                self._midi_notes_out = None
        
        # Input: receive playback notes from Nuendo
        self._midi_notes_in = rtmidi.MidiIn()
        try:
            self._midi_notes_in.open_virtual_port(PORT_NOTES_IN)
            self._midi_notes_in.set_callback(self._on_notes_received)
            print(f"  ✓ Virtual port '{PORT_NOTES_IN}' created")
        except Exception:
            # Windows (WinMM) has no virtual ports — use the loopMIDI port
            ports = self._midi_notes_in.get_ports()
            idx = self._find_port_index(ports, PORT_NOTES_IN)
            if idx is not None:
                try:
                    self._midi_notes_in.open_port(idx)
                    self._midi_notes_in.set_callback(self._on_notes_received)
                    print(f"  ✓ loopMIDI port '{PORT_NOTES_IN}' connected")
                except Exception as e:
                    print(f"  ⚠ Notes input port failed: {e}")
                    self._midi_notes_in = None
            else:
                print(f"  ⚠ Notes input port '{PORT_NOTES_IN}' not found "
                      f"(create a loopMIDI port with this exact name)")
                self._midi_notes_in = None

    # ─────────────────────────────────────────────
    # Receiving messages from Nuendo
    # ─────────────────────────────────────────────

    def _on_midi_received(self, event, data=None):
        """
        Callback called automatically on each MIDI message received from Nuendo.
        """
        message, delta_time = event
        
        if not message:
            return
        
        status = message[0]
        
        # ── Control Change (CC) — Channel 0 ──
        if status == 0xB0 and len(message) >= 3:
            cc_num   = message[1]
            cc_value = message[2]
            self._handle_cc(cc_num, cc_value)
        
        # ── Heartbeat — Channel 15 (0xBF), CC 127 ──
        elif status == 0xBF and len(message) >= 3:
            if message[1] == 127:
                self._handle_heartbeat()
        
        # ── SysEx ──
        elif status == 0xF0:
            self._handle_sysex(message)
        
        # ── Other SysEx (rtmidi may omit 0xF0 sometimes) ──
        elif len(message) > 5 and message[-1] == 0xF7:
            self._handle_sysex([0xF0] + list(message))
        
        # ── MTC Quarter Frame (0xF1) ──
        elif status == 0xF1 and len(message) >= 2:
            self._handle_mtc_quarter_frame(message[1])

    def _handle_mtc_quarter_frame(self, data):
        """Parse an MTC Quarter Frame message."""
        msg_type = (data >> 4) & 0x07
        nibble = data & 0x0F
        self._mtc_pieces[msg_type] = nibble
        
        if msg_type == 7:
            self._mtc_frames = self._mtc_pieces[0] | (self._mtc_pieces[1] << 4)
            self._mtc_seconds = self._mtc_pieces[2] | (self._mtc_pieces[3] << 4)
            self._mtc_minutes = self._mtc_pieces[4] | (self._mtc_pieces[5] << 4)
            self._mtc_hours = self._mtc_pieces[6] | ((self._mtc_pieces[7] & 0x01) << 4)
            self._update_position_display()
    
    def _update_position_display(self):
        """Update the timecode position display."""
        self.state.position_display = (
            f"{self._mtc_hours:02d}:{self._mtc_minutes:02d}:"
            f"{self._mtc_seconds:02d}.{self._mtc_frames:02d}"
        )

    def _handle_heartbeat(self):
        """Process heartbeat from Nuendo (channel 15, CC 127)."""
        self._last_heartbeat = time.time()
        state = self.state
        if not state.nuendo_connected:
            state.nuendo_connected = True
            self._connection_grace_until = time.time() + 3.0
            self._vu_ignore_until = time.time() + 3.0
            print("  ✓ Nuendo connected!")
            self._request_name_scan()

    def _handle_cc(self, cc_num, value):
        """
        Process a CC message received from Nuendo.
        """
        state = self.state
        
        # ── Total number of tracks (CC 10) ──
        if cc_num == 10:
            if value > 0:
                state.total_tracks = value
        
        # ── Selection from Nuendo (CC 11) ──
        elif cc_num == 11:
            rel_index = value
            abs_index = state.bank_offset + rel_index
            state.selected_track_index = abs_index
            for t in state.tracks:
                t.is_selected = False
            if abs_index < len(state.tracks):
                state.tracks[abs_index].is_selected = True
            # Update LEDs
            if hasattr(self, '_on_selection_changed'):
                self._on_selection_changed()
        
        # ── Scan complete (CC 15 from JS) ──
        elif cc_num == 15:
            if hasattr(self, '_scan_done'):
                self._scan_done = True
        
        # ── Transport feedback (CC 16 = is_playing) ──
        elif cc_num == 16:
            self.state.is_playing = (value > 64)
            self._leds_dirty = True
        
        # ── Automation feedback (CC 17 = read, CC 18 = write) ──
        elif cc_num == 17:
            sel = self.state.selected_track
            sel.automation_read = (value > 64)
            self._leds_dirty = True
        elif cc_num == 18:
            sel = self.state.selected_track
            sel.automation_write = (value > 64)
            self._leds_dirty = True
        
        # ── Send index feedback (CC 19) ──
        elif cc_num == 19:
            self.state.current_send = value
        
        # ── Metronome feedback (CC 22) ──
        elif cc_num == 22:
            self.state.metronome_on = (value > 64)
            self._leds_dirty = True
        
        # ── Cycle/loop feedback (CC 53) ──
        elif cc_num == 53:
            self.state.cycle_active = (value > 64)
            self._leds_dirty = True
        
        # ── Record feedback (CC 73) ──
        elif cc_num == 73:
            self.state.is_recording = (value > 64)
            self._leds_dirty = True
        
        # ── Control Room volume feedback (CC 23) ──
        elif cc_num == 23:
            pass  # Display value comes via SysEx 0x08
        
        # ── VU meters (CC 30-37) ──
        elif 30 <= cc_num <= 37:
            if getattr(self, '_insert_positioning', False):
                return
            track_in_bank = cc_num - 30
            abs_index = state.bank_offset + track_in_bank
            if abs_index < len(state.tracks):
                vu_val = value / 127.0
                state.tracks[abs_index].vu_meter = vu_val
                # Peak clip: require 2 consecutive max readings to avoid false triggers
                if value >= 126 and time.time() > getattr(self, '_vu_ignore_until', 0):
                    prev = getattr(self, '_vu_prev_max', {})
                    if prev.get(track_in_bank, 0) >= 126:
                        state.tracks[abs_index].peak_clipped = True
                    prev[track_in_bank] = value
                    self._vu_prev_max = prev
                else:
                    prev = getattr(self, '_vu_prev_max', {})
                    prev[track_in_bank] = value
                    self._vu_prev_max = prev
        
        # ── Send enable feedback (CC 24-31) ──
        elif 24 <= cc_num <= 31:
            track_in_bank = cc_num - 24
            abs_index = state.bank_offset + track_in_bank
            if abs_index < len(state.tracks):
                send_idx = state.current_send
                state.tracks[abs_index].send_enabled[send_idx] = (value > 64)
                if hasattr(self, '_on_selection_changed'):
                    self._on_selection_changed()
        
        # ── DirectAccess status feedback (CC 68) ──
        elif cc_num == 68:
            if value == 0:
                # DA fallback requested — Python should handle it
                self._da_fallback_needed = True
            elif value == 1:
                self._da_available = True
                print("  ✓ DirectAccess available (API 1.2+)")
            elif value == 2:
                # DA cleared all monitors — sync local state
                for t in state.tracks:
                    t.is_monitored = False
                print("  DA: All monitors cleared")
                if hasattr(self, '_on_selection_changed'):
                    self._on_selection_changed()
            elif value == 3:
                # DA cleared all rec arms — sync local state
                for t in state.tracks:
                    t.is_armed = False
                print("  DA: All rec arms cleared")
                if hasattr(self, '_on_selection_changed'):
                    self._on_selection_changed()
        
        # ── Volumes of the 8 visible tracks (CC 20-27) ──
        elif 20 <= cc_num <= 27:
            track_in_bank = cc_num - 20
            abs_index = state.bank_offset + track_in_bank
            if abs_index < len(state.tracks):
                track = state.tracks[abs_index]
                # Skip if encoder is being touched (avoid feedback glitch)
                if time.time() < getattr(track, '_vol_touched_until', 0):
                    return
                normalized = value / 127.0
                track.volume = normalized
                track.volume_db = _to_db(normalized)
                # Update touchstrip LEDs if it's the selected track
                if abs_index == state.selected_track_index and state.touchstrip_mode == 'volume':
                    if hasattr(self, '_touchstrip_led_callback') and self._touchstrip_led_callback:
                        self._touchstrip_led_callback(normalized)
        
        # ── Track selection (CC 80-87) ──
        elif 80 <= cc_num <= 87:
            track_in_bank = cc_num - 80
            abs_index = state.bank_offset + track_in_bank
            is_selected = (value > 64)
            if abs_index < len(state.tracks):
                state.tracks[abs_index].is_selected = is_selected
                if is_selected:
                    state.selected_track_index = abs_index
                    for j in range(len(state.tracks)):
                        if j != abs_index:
                            state.tracks[j].is_selected = False
                    # Update touchstrip LEDs with the new track's volume
                    if state.touchstrip_mode == 'volume':
                        if hasattr(self, '_touchstrip_led_callback') and self._touchstrip_led_callback:
                            self._touchstrip_led_callback(state.tracks[abs_index].volume)
        
        # ── Track pan (CC 40-47) ──
        elif 40 <= cc_num <= 47:
            track_in_bank = cc_num - 40
            abs_index = state.bank_offset + track_in_bank
            if abs_index < len(state.tracks):
                # CC 0=L100, 64=C, 127=R100
                if value == 64:
                    state.tracks[abs_index].pan = 0.0
                elif value < 64:
                    state.tracks[abs_index].pan = (value - 64) / 64.0
                else:
                    state.tracks[abs_index].pan = (value - 64) / 63.0
        
        # ── Mute/solo/monitor/rec states (relative to the bank) ──
        # Ignore during scan (_scanning flag active)
        if getattr(self, '_scanning', False) and 90 <= cc_num <= 125:
            return
        
        if 90 <= cc_num <= 97:
            abs_index = state.bank_offset + (cc_num - 90)
            if abs_index < len(state.tracks):
                state.tracks[abs_index].is_muted = (value > 64)
        
        elif 100 <= cc_num <= 107:
            abs_index = state.bank_offset + (cc_num - 100)
            if abs_index < len(state.tracks):
                state.tracks[abs_index].is_solo = (value > 64)
        
        elif 110 <= cc_num <= 117:
            abs_index = state.bank_offset + (cc_num - 110)
            if abs_index < len(state.tracks):
                state.tracks[abs_index].is_monitored = (value > 64)
        
        elif 118 <= cc_num <= 125:
            abs_index = state.bank_offset + (cc_num - 118)
            if abs_index < len(state.tracks):
                state.tracks[abs_index].is_armed = (value > 64)
                self._leds_dirty = True

    def _handle_sysex(self, message):
        """
        Process SysEx messages from Nuendo.
        Used for long data (track names, colors, etc.)
        
        Custom SysEx format:
        F0 00 21 09  ← Manufacturer ID (fictitious, for our own use)
        XX           ← Message type
        ... data ...
        F7           ← End SysEx
        """
        if len(message) < 5:
            return
        
        # ── Full Frame MTC (F0 7F 7F 01 01 hh mm ss ff F7) ──
        if len(message) >= 10 and message[1] == 0x7F and message[2] == 0x7F and message[3] == 0x01 and message[4] == 0x01:
            self._mtc_hours = message[5] & 0x1F
            self._mtc_minutes = message[6]
            self._mtc_seconds = message[7]
            self._mtc_frames = message[8]
            self._update_position_display()
            return
        
        # Check our manufacturer ID
        if message[1:4] == [0x00, 0x21, 0x09]:
            pass  # Continue to normal processing below
        elif len(message) >= 6 and message[1] == 0x00 and message[2] == 0x0E:
            # CR value feedback : [F0 00 0E param_id value_127 F7]
            if getattr(self, '_scanning', False):
                return
            param_id = message[3]
            value_127 = message[4]
            if hasattr(self, '_cr_state') and self._cr_state:
                self._cr_state.set_value(param_id, value_127)
            return
        elif len(message) >= 6 and message[1] == 0x00 and message[2] == 0x0F:
            # CR toggle feedback : [F0 00 0F param_id on_off F7]
            if getattr(self, '_scanning', False):
                return
            param_id = message[3]
            on = message[4] > 0
            if hasattr(self, '_cr_state') and self._cr_state:
                self._cr_state.set_toggle(param_id, on)
                self._leds_dirty = True
            return
        elif len(message) >= 5 and message[1] == 0x00 and message[2] == 0x10:
            # CR display value : [F0 00 10 param_id ...chars F7]
            if getattr(self, '_scanning', False):
                return
            param_id = message[3]
            text = ''.join(chr(b) for b in message[4:-1])
            if hasattr(self, '_cr_state') and self._cr_state:
                self._cr_state.set_display(param_id, text)
            return
        elif len(message) >= 4 and message[1] == 0x00 and message[2] == 0x11:
            # Insert slot name : [F0 00 11 slotIndex ...chars F7]
            if getattr(self, '_bypass_navigating', False):
                return
            slot = message[3]
            name = ''.join(chr(b) for b in message[4:-1])
            state = self.state
            if slot < len(state.current_insert_names):
                if name and name != state.current_insert_names[slot]:
                    state.current_insert_names[slot] = name
                    print(f"  Insert slot {slot}: '{name}'")
            return
        elif len(message) >= 4 and message[1] == 0x00 and message[2] == 0x12:
            # Insert scan complete : [F0 00 12 7F F7]
            print("  ✓ Insert scan complete")
            self._leds_dirty = True
            return
        elif len(message) >= 4 and message[1] == 0x00 and message[2] == 0x14:
            # Current insert viewer slot (0-based)
            slot = message[3]
            state = self.state
            state.selected_insert_slot = slot
            if hasattr(self, '_insert_current_slot'):
                self._insert_current_slot = slot
            return
        elif len(message) >= 4 and message[1] == 0x00 and message[2] == 0x16:
            # Insert param name : [F0 00 16 paramIndex ...chars F7]
            if getattr(self, '_da_mapping_active', False):
                return  # Suppress — DA params are driving the display
            idx = message[3]
            name = ''.join(chr(b) for b in message[4:-1])
            state = self.state
            if idx < 8:
                if idx >= len(state.insert_param_names):
                    state.insert_param_names.extend([''] * (idx + 1 - len(state.insert_param_names)))
                state.insert_param_names[idx] = name
            return
        elif len(message) >= 4 and message[1] == 0x00 and message[2] == 0x17:
            # Insert param display value : [F0 00 17 paramIndex ...chars F7]
            if getattr(self, '_da_mapping_active', False):
                return  # Suppress — DA params are driving the display
            idx = message[3]
            value = ''.join(chr(b) for b in message[4:-1])
            state = self.state
            if idx < 8:
                if idx >= len(state.insert_param_values):
                    state.insert_param_values.extend([''] * (idx + 1 - len(state.insert_param_values)))
                state.insert_param_values[idx] = value
            return
        elif len(message) >= 5 and message[1] == 0x00 and message[2] == 0x13:
            # Insert bypass state : [F0 00 13 slotIndex bypass F7]
            slot = message[3]
            bypassed = message[4] > 0
            state = self.state
            if slot < len(state.current_insert_active):
                new_active = not bypassed
                old_active = state.current_insert_active[slot]
                state.current_insert_active[slot] = new_active
                if not getattr(self, '_bypass_navigating', False) and new_active != old_active:
                    print(f"  Insert bypass slot {slot}: {'BYPASS' if bypassed else 'ACTIVE'}")
                self._leds_dirty = True
            return
        elif len(message) >= 4 and message[1] == 0x00 and message[2] == 0x18:
            # Send name : [F0 00 18 idx ...chars F7]
            idx = message[3]
            name = ''.join(chr(b) for b in message[4:-1])
            state = self.state
            if idx < 8:
                if name and name != state.send_names[idx]:
                    state.send_names[idx] = name
                    print(f"  Send {idx}: '{name}'")
            return
        elif len(message) >= 4 and message[1] == 0x00 and message[2] == 0x19:
            # Send level display : [F0 00 19 idx ...chars F7]
            idx = message[3]
            value = ''.join(chr(b) for b in message[4:-1])
            state = self.state
            if idx < 8:
                state.send_levels[idx] = value
            return
        elif len(message) >= 5 and message[1] == 0x00 and message[2] == 0x1A:
            # Send on/off : [F0 00 1A idx on F7]
            idx = message[3]
            on = message[4] > 0
            state = self.state
            if idx < 8:
                state.send_on[idx] = on
                self._leds_dirty = True
            return
        elif len(message) >= 5 and message[1] == 0x00 and message[2] == 0x1B:
            # Send pre/post : [F0 00 1B idx prepost F7]
            idx = message[3]
            pre = message[4] > 0
            state = self.state
            if idx < 8:
                state.send_prepost[idx] = pre
                self._leds_dirty = True
            return
        elif len(message) >= 4 and message[1] == 0x00 and message[2] == 0x0A:
            # Diagnostic (keep for debug)
            return
        elif len(message) >= 4 and message[1] == 0x00 and message[2] == 0x24:
            # DA Insert slot cache entry : [F0 00 24 slotIdx tagLo tagHi bypassed ...title F7]
            slot = message[3]
            if len(message) >= 7:
                tag_lo = message[4]
                tag_hi = message[5]
                bypass_tag = tag_lo | (tag_hi << 7)
                bypassed = message[6] > 0 if len(message) > 7 else False
                title = ''.join(chr(b) for b in message[7:-1]) if len(message) > 8 else ''
                state = self.state
                # Update state with DA-discovered insert info
                if slot < len(state.current_insert_names):
                    state.current_insert_names[slot] = title
                    state.current_insert_active[slot] = not bypassed
                # Store DA metadata for bypass commands
                if not hasattr(self, '_da_insert_cache'):
                    self._da_insert_cache = []
                while len(self._da_insert_cache) <= slot:
                    self._da_insert_cache.append(None)
                self._da_insert_cache[slot] = {
                    'bypass_tag': bypass_tag,
                    'title': title,
                    'bypassed': bypassed
                }
                print(f"  DA slot {slot}: '{title}' bypass_tag={bypass_tag} {'BYPASS' if bypassed else 'ACTIVE'}")
            return
        elif len(message) >= 4 and message[1] == 0x00 and message[2] == 0x25:
            # DA exploration complete : [F0 00 25 slotCount F7]
            count = message[3]
            self._da_inserts_ready = True
            # Clear remaining slots beyond what DA found
            state = self.state
            for i in range(count, 16):
                state.current_insert_names[i] = ''
                state.current_insert_active[i] = False
            self._leds_dirty = True
            print(f"  ✓ DA Insert exploration complete: {count} slots cached")
            # One-time Plugin Manager exploration on the first slot with a plugin
            if not getattr(self, '_pm_explored', False):
                self._pm_explored = True  # Set to False in console to re-run
                # Find first slot with a plugin
                for i in range(count):
                    if state.current_insert_names[i]:
                        self.request_da_plugin_manager_explore(i)
                        break
            # One-time plugin list fetch (collection "Push" = index 1)
            if not getattr(self, '_plugin_list_fetched', False):
                self._plugin_list_fetched = True
                import threading
                def _delayed_fetch():
                    import time
                    time.sleep(2.0)  # Wait for PM exploration to finish
                    self.request_da_plugin_list(1)  # "Push" collection
                threading.Thread(target=_delayed_fetch, daemon=True).start()
            return
        elif len(message) >= 5 and message[1] == 0x00 and message[2] == 0x26:
            # DA bypass result : [F0 00 26 slotIdx success bypassed F7]
            slot = message[3]
            success = message[4] > 0
            if success and len(message) >= 6:
                bypassed = message[5] > 0
                state = self.state
                if slot < len(state.current_insert_active):
                    state.current_insert_active[slot] = not bypassed
                    print(f"  DA Bypass slot {slot}: {'BYPASS' if bypassed else 'ACTIVE'} ✓")
                    self._leds_dirty = True
            elif not success:
                # DA bypass failed — Python should fall back to viewer-based
                self._da_bypass_fallback_slot = slot
                print(f"  DA Bypass slot {slot}: FAILED — will use viewer fallback")
            return
        elif len(message) >= 3 and message[1] == 0x00 and message[2] == 0x27:
            # DA cache invalidated : [F0 00 27 F7]
            self._da_inserts_ready = False
            if hasattr(self, '_da_insert_cache'):
                self._da_insert_cache = []
            print("  DA Inserts: cache invalidated (tree changed)")
            return
        elif len(message) >= 5 and message[1] == 0x00 and message[2] == 0x28:
            # DA edit result : [F0 00 28 slotIdx success F7]
            slot = message[3]
            success = message[4] > 0
            if success:
                print(f"  DA Edit slot {slot}: ✓")
            else:
                self._da_edit_fallback_slot = slot
                print(f"  DA Edit slot {slot}: FAILED — will use viewer fallback")
            return
        elif len(message) >= 11 and message[1] == 0x00 and message[2] == 0x29:
            # DA plugin param entry : [F0 00 29 slotIdx idxLo idxHi val127 tagB0-B3 ...title F7]
            slot = message[3]
            param_idx = message[4] | (message[5] << 7)
            val127 = message[6]
            tag = message[7] | (message[8] << 7) | (message[9] << 14) | (message[10] << 21)
            title = ''.join(chr(b) for b in message[11:-1]) if len(message) > 12 else ''

            # Store in DA param cache
            if not hasattr(self, '_da_plugin_params'):
                self._da_plugin_params = {}
            self._da_plugin_params[param_idx] = {
                'name': title,
                'tag': tag,
                'value': val127 / 127.0,
                'value_display': '',
            }
            # For strip slot enum (slot >= 16), mirror into a per-slot dict and log
            if slot >= self.DA_STRIP_SLOT_OFFSET:
                strip_si = slot - self.DA_STRIP_SLOT_OFFSET
                if not hasattr(self, '_da_strip_params'):
                    self._da_strip_params = {}
                if strip_si not in self._da_strip_params:
                    self._da_strip_params[strip_si] = {}
                self._da_strip_params[strip_si][param_idx] = {
                    'name': title, 'tag': tag, 'value': val127 / 127.0,
                }
                # Mirror for renderer display of DA-based footer toggles, keyed
                # by plugin_name so custom strip layouts work without remapping.
                cache_entry = (self._da_strip_slot_cache[strip_si]
                               if strip_si < len(self._da_strip_slot_cache) else None)
                pname = cache_entry.get('plugin_name') if cache_entry else None
                if pname:
                    self.state.da_strip_toggle_values[(pname, param_idx)] = val127 / 127.0
                print(f"    [strip {strip_si}] param {param_idx:3d}: '{title}' "
                      f"tag={tag} val={val127/127.0:.3f}")
            return
        elif len(message) >= 6 and message[1] == 0x00 and message[2] == 0x2A:
            # DA plugin param enum complete : [F0 00 2A slotIdx countLo countHi F7]
            slot = message[3]
            count = message[4] | (message[5] << 7)
            if slot >= self.DA_STRIP_SLOT_OFFSET:
                strip_si = slot - self.DA_STRIP_SLOT_OFFSET
                print(f"  ✓ DA Strip params enumerated: strip slot {strip_si}, {count} params total")
                # Chain next strip slot enum if auto-enum is in progress
                if getattr(self, '_strip_enum_active', False):
                    queue = getattr(self, '_strip_enum_queue', [])
                    if queue:
                        si, name = queue.pop(0)
                        print(f"  → DA Strip: auto-enum slot {si} ({name})")
                        self.request_da_strip_params(si)
                    else:
                        self._strip_enum_active = False
                        print("  ✓ DA Strip: all slots enumerated")
            else:
                print(f"  ✓ DA Plugin params enumerated: slot {slot}, {count} params")
            self._da_params_enumerated = True

            # Notify controller to apply mapping
            if hasattr(self, '_on_da_params_ready') and self._on_da_params_ready:
                self._on_da_params_ready(slot)
            return
        elif len(message) >= 5 and message[1] == 0x00 and message[2] == 0x2B:
            # DA encoder feedback : [F0 00 2B encIdx val127 ...displayStr F7]
            enc_idx = message[3]
            val127 = message[4]
            display = ''.join(chr(b) for b in message[5:-1]) if len(message) > 6 else ''
            state = self.state
            if enc_idx < 8:
                state.insert_param_values[enc_idx] = display if display else f"{val127/127:.2f}"
                self._leds_dirty = True
            return
        elif len(message) >= 6 and message[1] == 0x00 and message[2] == 0x2C:
            # DA plugin list entry : [F0 00 2C idxLo idxHi ...name 00 ...vendor 00 ...subCat 00 ...uid F7]
            idx = message[3] | (message[4] << 7)
            # Parse null-separated fields from message[5:-1]
            fields = []
            current = []
            for b in message[5:-1]:
                if b == 0x00:
                    fields.append(''.join(chr(c) for c in current))
                    current = []
                else:
                    current.append(b)
            # Last field (UID) has no trailing null
            if current:
                fields.append(''.join(chr(c) for c in current))
            
            name = fields[0] if len(fields) > 0 else ''
            vendor = fields[1] if len(fields) > 1 else ''
            sub_cat = fields[2] if len(fields) > 2 else ''
            uid = fields[3] if len(fields) > 3 else ''
            
            state = self.state
            # Ensure list is large enough
            while len(state.browser_plugins) <= idx:
                state.browser_plugins.append(None)
            state.browser_plugins[idx] = {
                'name': name,
                'vendor': vendor,
                'sub_categories': sub_cat,
                'uid': uid,
            }
            return
        elif len(message) >= 7 and message[1] == 0x00 and message[2] == 0x2D:
            # DA plugin list complete : [F0 00 2D countLo countHi collIdx collCount ...collName F7]
            count = message[3] | (message[4] << 7)
            coll_idx = message[5]
            coll_count = message[6] if len(message) > 7 else 0
            coll_name = ''.join(chr(b) for b in message[7:-1]) if len(message) > 8 else ''
            state = self.state
            # Trim to exact count
            state.browser_plugins = state.browser_plugins[:count]
            state.browser_collection_index = coll_idx
            state.browser_collection_count = coll_count
            state.browser_collection_name = coll_name
            state.browser_list_ready = True
            print(f"  ✓ Plugin list received: {count} entries from \"{coll_name}\" (collection {coll_idx}/{coll_count})")
            # Print first 5 entries as sample
            for i in range(min(5, count)):
                p = state.browser_plugins[i]
                if p:
                    print(f"    [{i}] {p['name']} ({p['vendor']}) — {p['sub_categories']}")
            if count > 5:
                print(f"    ... +{count - 5} more")
            return
        elif len(message) >= 7 and message[1] == 0x00 and message[2] == 0x2F:
            # DA collection info : [F0 00 2F collIdx collCount cntLo cntHi ...name F7]
            coll_idx = message[3]
            coll_count = message[4]
            entry_count = message[5] | (message[6] << 7)
            coll_name = ''.join(chr(b) for b in message[7:-1]) if len(message) > 8 else ''
            state = self.state
            # Initialize or extend list
            if coll_idx == 0:
                state.browser_collections = []
            state.browser_collections.append({
                'index': coll_idx,
                'name': coll_name,
                'count': entry_count
            })
            state.browser_collection_count = coll_count
            print(f"  Collection [{coll_idx}/{coll_count}]: \"{coll_name}\" ({entry_count} plugins)")
            if len(state.browser_collections) >= coll_count:
                state.browser_collections_ready = True
                print(f"  ✓ All {coll_count} collections received")
            return
        elif len(message) >= 5 and message[1] == 0x00 and message[2] == 0x2E:
            # DA plugin load result : [F0 00 2E slotIdx success F7]
            slot = message[3]
            success = message[4] > 0
            if success:
                print(f"  ✓ DA Plugin loaded into slot {slot + 1}")
                # Invalidate insert cache to force rescan
                self._da_inserts_ready = False
                if hasattr(self, '_da_insert_cache'):
                    self._da_insert_cache = []
            else:
                print(f"  ✗ DA Plugin load FAILED for slot {slot + 1}")
            return

        # ── DA Strip Slot handlers (v1.0.4) ──

        elif len(message) >= 7 and message[1] == 0x00 and message[2] == 0x34:
            # DA strip slot cache entry:
            # [F0 00 34 slotIdx modId bypassed isOn ...pluginName 00 ...slotTitle F7]
            slot_idx = message[3]
            mod_id   = message[4]
            bypassed = message[5] > 0
            is_on    = message[6] > 0
            rest     = message[7:-1]
            # Split plugin name / slot title at the 0x00 separator
            sep = len(rest)
            for j, b in enumerate(rest):
                if b == 0:
                    sep = j
                    break
            plugin_name = ''.join(chr(b) for b in rest[:sep])
            slot_title  = ''.join(chr(b) for b in rest[sep + 1:]) if sep < len(rest) - 1 else ''

            if not hasattr(self, '_da_strip_slot_cache'):
                self._da_strip_slot_cache = []
            while len(self._da_strip_slot_cache) <= slot_idx:
                self._da_strip_slot_cache.append(None)
            self._da_strip_slot_cache[slot_idx] = {
                'slot_index':  slot_idx,
                'mod_id':      mod_id,
                'bypassed':    bypassed,
                'is_on':       is_on,
                'plugin_name': plugin_name,
                'slot_title':  slot_title,
            }
            print(f"  DA Strip slot {slot_idx} (mod {mod_id:02X}): '{slot_title}'"
                  f" plugin='{plugin_name}' on={is_on} bypass={bypassed}")
            return

        elif len(message) >= 4 and message[1] == 0x00 and message[2] == 0x35:
            # DA strip slot cache complete : [F0 00 35 count F7]
            count = message[3]
            self._da_strip_explored = True
            self._leds_dirty = True
            print(f"  ✓ DA Strip exploration complete: {count} slots cached")
            # Diagnostic: auto-enum params for every loaded slot so we can
            # inspect which extended params (beyond bank zone) are available.
            # Chain sequentially via 0x2A: each completion triggers the next request.
            self._strip_enum_queue = [
                (e['slot_index'], e['plugin_name'])
                for e in self._da_strip_slot_cache
                if e and e.get('plugin_name')
            ]
            self._strip_enum_active = True
            if self._strip_enum_queue:
                si, name = self._strip_enum_queue.pop(0)
                print(f"  → DA Strip: auto-enum slot {si} ({name})")
                self.request_da_strip_params(si)
            if hasattr(self, '_on_strip_da_ready') and self._on_strip_da_ready:
                self._on_strip_da_ready()
            return

        elif len(message) >= 9 and message[1] == 0x00 and message[2] == 0x3D:
            # Live DA param feedback from host (e.g. user touched a param in
            # Nuendo's GUI). Format:
            #   [F0 00 3D slotIdxLo slotIdxHi paramIdxLo paramIdxHi val127 ...display F7]
            slot_idx  = message[3] | (message[4] << 7)
            param_idx = message[5] | (message[6] << 7)
            val127    = message[7]
            try:
                disp = bytes(message[8:-1]).decode('utf-8', errors='ignore').rstrip('\x00')
            except Exception:
                disp = ''
            val_norm = val127 / 127.0

            # Resolve plugin_name from the strip cache
            strip_si = slot_idx - getattr(self, 'DA_STRIP_SLOT_OFFSET', 16)
            cache = getattr(self, '_da_strip_slot_cache', []) or []
            pname = None
            if 0 <= strip_si < len(cache) and cache[strip_si]:
                pname = cache[strip_si].get('plugin_name')

            # Update DA toggle/value mirror so the renderer sees fresh values
            if pname:
                self.state.da_strip_toggle_values[(pname, param_idx)] = val_norm
                self._leds_dirty = True

            # If this is an EQ param and the user is currently on the EQ page,
            # also refresh insert_param_values / eq_band_cache so the encoder
            # cells and the curve update without waiting for a Push encoder
            # touch to fire SysEx 0x2B.
            if pname == 'EQ':
                # Map param_idx → (band_idx, role)  where role ∈ {'type','gain','freq','q','on'}
                # Band N: On=5+N*6, Type=6+N*6, Gain=7+N*6, Freq=8+N*6, Q=9+N*6
                roles_by_offset = {0: 'on', 1: 'type', 2: 'gain', 3: 'freq', 4: 'q'}
                if 5 <= param_idx < 29:
                    band_idx = (param_idx - 5) // 6
                    role_off = (param_idx - 5) % 6
                    role = roles_by_offset.get(role_off)
                    if 0 <= band_idx <= 3 and role:
                        cache_entry = self.state.eq_band_cache[band_idx]
                        # Update numeric cache (parse display if available)
                        if role == 'freq':
                            # Parse "30.0 Hz" / "1.5 kHz"
                            v = self._parse_eq_freq(disp)
                            if v is not None: cache_entry['freq'] = v
                        elif role == 'gain':
                            v = self._parse_eq_db(disp)
                            if v is not None: cache_entry['gain'] = v
                        elif role == 'q':
                            try: cache_entry['q'] = float(disp.strip()) if disp else None
                            except ValueError: pass
                        elif role == 'type':
                            cache_entry['type'] = disp.lower() if disp else None
                        # If this is the SELECTED band's currently-armed encoder,
                        # also update insert_param_values for the cell display.
                        sel = self.state.eq_selected_band
                        if band_idx == sel:
                            enc_pos_for_role = {'type': 1, 'freq': 2, 'q': 3, 'gain': 4}
                            ep = enc_pos_for_role.get(role)
                            if ep is not None and 0 <= ep < 8:
                                self.state.insert_param_values[ep] = (
                                    disp if disp else f"{val_norm:.2f}")
            return

        elif len(message) >= 4 and message[1] == 0x00 and message[2] == 0x3E:
            # Edit Channel Settings window state: [F0 00 3E open F7]
            self.state.editor_open = (message[3] > 0)
            self._leds_dirty = True
            return

        elif len(message) >= 4 and message[1] == 0x00 and message[2] == 0x3B:
            # JS-side strip cache reset notification (e.g. on Nuendo reload).
            self._da_strip_explored = False
            self._da_strip_slot_cache = []
            print("  ℹ DA Strip cache reset by JS (Nuendo reload?)")
            # If we're currently in a CS drill-down sub-page, re-trigger exploration
            # right away — otherwise it would only fire on the next page switch and
            # DA-dependent commands (Edit, encoder feedback) would fail silently.
            cur_page = getattr(self.state, 'cs_page', 'overview')
            if cur_page and cur_page != 'overview':
                print("  → Re-triggering strip exploration (in drill-down)")
                self.request_da_strip_exploration()
            return

        elif len(message) >= 5 and message[1] == 0x00 and message[2] == 0x3A:
            # Variant switch result: [F0 00 3A daSlot success F7]
            da_slot = message[3]
            success = message[4] > 0
            if success:
                print(f"  ✓ Variant switch slot {da_slot} succeeded — strip cache invalidated")
                # Re-explore so the cache reflects the new plugin
                self.request_da_strip_exploration()
            else:
                print(f"  ✗ Variant switch slot {da_slot} failed")
            return

        elif len(message) >= 7 and message[1] == 0x00 and message[2] == 0x39:
            # DA param flip feedback: [F0 00 39 daSlot paramIdx val127 F7]
            da_slot   = message[3]
            param_idx = message[4]
            val127    = message[5]
            val_norm  = val127 / 127.0
            if da_slot >= self.DA_STRIP_SLOT_OFFSET:
                strip_si = da_slot - self.DA_STRIP_SLOT_OFFSET
                cache = getattr(self, '_da_strip_params', {}).get(strip_si, {})
                info = cache.get(param_idx)
                if info:
                    info['value'] = val_norm
                    print(f"  DA flip: strip {strip_si} param {param_idx} → {val_norm:.3f}")
                # Mirror keyed by plugin_name (custom strip layouts).
                slot_cache = getattr(self, '_da_strip_slot_cache', [])
                cache_entry = slot_cache[strip_si] if strip_si < len(slot_cache) else None
                pname = cache_entry.get('plugin_name') if cache_entry else None
                if pname:
                    self.state.da_strip_toggle_values[(pname, param_idx)] = val_norm
                self._leds_dirty = True
            return

        elif len(message) >= 5 and message[1] == 0x00 and message[2] == 0x36:
            # DA strip bypass result : [F0 00 36 slotIdx success bypassed F7]
            slot_idx = message[3]
            success  = message[4] > 0
            if success and len(message) >= 7:
                bypassed = message[5] > 0
                # Update DA cache
                cache = getattr(self, '_da_strip_slot_cache', [])
                if slot_idx < len(cache) and cache[slot_idx]:
                    cache[slot_idx]['bypassed'] = bypassed
                    mod_id = cache[slot_idx]['mod_id']
                    # Mirror into ChannelStripState
                    slot_state = self.state.channel_strip.slots.get(mod_id)
                    if slot_state:
                        slot_state.bypassed = bypassed
                        self._leds_dirty = True
                print(f"  DA Strip bypass slot {slot_idx}: {'BYPASS' if bypassed else 'ACTIVE'} ✓")
            elif not success:
                print(f"  DA Strip bypass slot {slot_idx}: FAILED")
            return

        elif len(message) >= 5 and message[1] == 0x00 and message[2] == 0x37:
            # DA strip edit result : [F0 00 37 slotIdx success F7]
            slot_idx = message[3]
            success  = message[4] > 0
            print(f"  DA Strip edit slot {slot_idx}: {'✓' if success else 'FAILED'}")
            return

        else:
            return
        
        msg_type = message[4]
        payload  = message[5:-1]  # Data between header and F7
        
        # ── Track name (type 0x01) ──
        # Payload: [relative_track_index, ...name bytes...]
        if msg_type == 0x01 and len(payload) >= 2:
            if getattr(self, '_scan_returning', False):
                return
            rel_index = payload[0]
            abs_index = self.state.bank_offset + rel_index
            name_bytes  = bytes(payload[1:])
            try:
                name = name_bytes.decode('utf-8').rstrip('\x00')
                if abs_index < len(self.state.tracks):
                    self.state.tracks[abs_index].name = name
            except UnicodeDecodeError:
                pass
        
        # ── Track color (type 0x02) ──
        # Payload: [relative_track_index, R, G, B]
        elif msg_type == 0x02 and len(payload) >= 4:
            if getattr(self, '_scan_returning', False):
                return
            rel_index = payload[0]
            abs_index = self.state.bank_offset + rel_index
            r, g, b = payload[1], payload[2], payload[3]
            if abs_index < len(self.state.tracks):
                self.state.tracks[abs_index].color = (
                    min(255, r * 2), min(255, g * 2), min(255, b * 2)
                )
        
        # ── Quick Control name (type 0x03) ──
        # Payload: [qc_index, ...UTF-8 name bytes...]
        elif msg_type == 0x03 and len(payload) >= 2:
            qc_index   = payload[0]
            name_bytes = bytes(payload[1:])
            try:
                name     = name_bytes.decode('utf-8').rstrip('\x00')
                selected = self.state.selected_track
                if qc_index < len(selected.quick_controls):
                    selected.quick_controls[qc_index].name = name
            except UnicodeDecodeError:
                pass
        
        # ── Display value (type 0x04) ──
        elif msg_type == 0x04 and len(payload) >= 2:
            rel_index = payload[0]
            abs_index = self.state.bank_offset + rel_index
            display_bytes = bytes(payload[1:])
            try:
                display_str = display_bytes.decode('utf-8').rstrip('\x00')
                if abs_index < len(self.state.tracks):
                    track = self.state.tracks[abs_index]
                    track.volume_display = display_str
                    try:
                        parts = display_str.split()
                        if parts and parts[0] not in ('', '-oo', 'Off'):
                            db_val = float(parts[0])
                            track.volume_db = db_val
                            # Update normalized volume from dB, unless encoder is being touched
                            if time.time() >= getattr(track, '_vol_touched_until', 0):
                                track.volume = max(0.0, min(1.0, _from_db(db_val)))
                    except (ValueError, IndexError):
                        pass
            except UnicodeDecodeError:
                pass
        
        # ── Insert info (type 0x05) ──
        # Payload: [track_index, slot, is_active, ...nom...]
        elif msg_type == 0x05 and len(payload) >= 3:
            track_index = payload[0]
            slot        = payload[1]
            is_active   = bool(payload[2])
            name_bytes  = bytes(payload[3:])
            try:
                name = name_bytes.decode('utf-8').rstrip('\x00')
                if track_index < len(self.state.tracks):
                    track = self.state.tracks[track_index]
                    existing = next((ins for ins in track.inserts if ins.slot == slot), None)
                    if existing:
                        existing.name      = name
                        existing.is_active = is_active
                    else:
                        track.inserts.append(InsertInfo(slot, name, is_active))
                    track.inserts.sort(key=lambda x: x.slot)
            except UnicodeDecodeError:
                pass
        
        # ── Selection changed by the user (type 0x06) ──
        # Payload: [...chars of the selected track name...]
        elif msg_type == 0x06 and len(payload) >= 1:
            # Ignore if recent selection from Push
            if getattr(self, '_ignore_selection_until', 0) > time.time():
                return
            
            name_bytes = bytes(payload)
            try:
                name = name_bytes.decode('utf-8').rstrip('\x00')
                # Search first in the visible bank, then globally
                found_index = -1
                bank_start = self.state.bank_offset
                bank_end = bank_start + 8
                
                # Priority 1: in the visible bank
                for t in self.state.tracks[bank_start:min(bank_end, len(self.state.tracks))]:
                    if t.name == name:
                        found_index = t.index
                        break
                
                # Priority 2: globally (only if not found in visible bank)
                if found_index < 0:
                    for t in self.state.tracks:
                        if t.name == name:
                            found_index = t.index
                            break
                
                if found_index >= 0:
                    # Only update if it's a real change
                    old_selected = self.state.selected_track_index
                    self.state.selected_track_index = found_index
                    for tr in self.state.tracks:
                        tr.is_selected = (tr.index == found_index)
                    
                    # Auto-switch only if the found track is not
                    # in the visible bank AND it's a significant change
                    bank_start = self.state.bank_offset
                    bank_end = bank_start + 8
                    if found_index < bank_start or found_index >= bank_end:
                        # Check that it's not a false positive
                        # (same name in another bank)
                        if old_selected < bank_start or old_selected >= bank_end:
                            # The old selection was also outside the bank → real change
                            new_bank = (found_index // 8) * 8
                            if hasattr(self, '_on_bank_switch_needed'):
                                self._on_bank_switch_needed(new_bank)
                    
                    if hasattr(self, '_on_selection_changed'):
                        self._on_selection_changed()
            except UnicodeDecodeError:
                pass
        
        # ── Send display values (type 0x07) ──
        # Payload: [sendIndex, channelIndex, ...chars]
        elif msg_type == 0x07 and len(payload) >= 3:
            send_idx = payload[0]
            ch_index = payload[1]
            abs_index = self.state.bank_offset + ch_index
            display_bytes = bytes(payload[2:])
            try:
                display_str = display_bytes.decode('utf-8').rstrip('\x00')
                if abs_index < len(self.state.tracks) and send_idx < 8:
                    self.state.tracks[abs_index].send_display[send_idx] = display_str
            except UnicodeDecodeError:
                pass
        
        # ── Control Room display value (type 0x08) ──
        elif msg_type == 0x08 and len(payload) >= 1:
            try:
                self.state.cr_volume_display = bytes(payload).decode('utf-8').rstrip('\x00')
            except UnicodeDecodeError:
                pass
        
        # ── Tempo display (type 0x09) ──
        elif msg_type == 0x09 and len(payload) >= 1:
            try:
                self.state.tempo_display = bytes(payload).decode('utf-8').rstrip('\x00')
            except UnicodeDecodeError:
                pass
        
        # ── Position display (type 0x0A) ──
        elif msg_type == 0x0A and len(payload) >= 1:
            try:
                self.state.position_display = bytes(payload).decode('utf-8').rstrip('\x00')
            except UnicodeDecodeError:
                pass
        
        # ── Quick Control display value (type 0x0B) ──
        elif msg_type == 0x0B and len(payload) >= 2:
            qc_index = payload[0]
            try:
                display_str = bytes(payload[1:]).decode('utf-8').rstrip('\x00')
                selected = self.state.selected_track
                if qc_index < len(selected.quick_controls):
                    selected.quick_controls[qc_index].display_value = display_str
            except UnicodeDecodeError:
                pass
        
        # ── Quick Control title (type 0x0C) ──
        elif msg_type == 0x0C and len(payload) >= 2:
            qc_index = payload[0]
            try:
                title_str = bytes(payload[1:]).decode('utf-8').rstrip('\x00')
                selected = self.state.selected_track
                if qc_index < len(selected.quick_controls):
                    selected.quick_controls[qc_index].name = title_str
            except UnicodeDecodeError:
                pass
        
        # ── Quick Control normalized value (type 0x0D) ──
        elif msg_type == 0x0D and len(payload) >= 2:
            qc_index = payload[0]
            norm_val = payload[1] / 127.0
            selected = self.state.selected_track
            if qc_index < len(selected.quick_controls):
                selected.quick_controls[qc_index].value = norm_val
        
        # ── JS Script version (type 0x10) ──
        elif msg_type == 0x10 and len(payload) >= 1:
            try:
                ver = bytes(payload).decode('utf-8').rstrip('\x00')
                self.state.js_version = ver
                print(f"  ✓ JS Script version: {ver}")
            except UnicodeDecodeError:
                pass
        
        # ── DirectAccess diagnostic log (type 0x20) ──
        elif msg_type == 0x20 and len(payload) >= 1:
            try:
                log_text = bytes(payload).decode('utf-8').rstrip('\x00')
                print(f"  [DA] {log_text}")
            except UnicodeDecodeError:
                pass
        
        # ── Strip Exploration (Phase 1a/1b/1c) — types 0x30/0x31/0x32/0x33 ──
        # Module IDs: 0x00 = PreFilter, 0x01 = ChannelEQ
        #             0x10..0x14 = strip slots (Gate, Comp, Tools, Sat, Limit)
        # 0x30 = parameter announce  (modId, paramId, ascii name)
        # 0x31 = parameter value     (modId, paramId, val127)
        # 0x32 = parameter display   (modId, paramId, ascii display)
        # 0x33 = plugin identity     (modId, ascii pluginName) — variant change
        #
        # Each call routes into self.state.channel_strip which deduplicates
        # against its cached values. A real change returns True and is logged
        # at debug level; redundant fires (Nuendo emits each callback 4-10×
        # per actual user action) are silently dropped.
        # _STRIP_LOG_EMPTY=True forces logging of empty strings for diagnostics.
        elif msg_type == 0x30 and len(payload) >= 2:
            mod_id = payload[0]
            param_id = payload[1]
            try:
                name = bytes(payload[2:]).decode('utf-8').rstrip('\x00')
                if name:
                    if self.state.channel_strip.update_announce(mod_id, param_id, name):
                        mod_name = _strip_module_name(mod_id)
                        print(f"  [STRIP] {mod_name} 0x{param_id:02X} announce='{name}'")
                        self._leds_dirty = True
                        # Refresh the on-disk discovery dump (Axe B).
                        self._dump_strip_discovery()
                elif _STRIP_LOG_EMPTY:
                    mod_name = _strip_module_name(mod_id)
                    print(f"  [STRIP] {mod_name} 0x{param_id:02X} announce=<empty>")
            except UnicodeDecodeError:
                pass
        
        elif msg_type == 0x31 and len(payload) >= 3:
            mod_id = payload[0]
            param_id = payload[1]
            val127 = payload[2]
            # Cache the raw 0-127 value for delta/toggle commands.
            # state.channel_strip.update_value() returns True only on changes,
            # so this stays cheap even with the 4-10× duplicate fires.
            if self.state.channel_strip.update_value(mod_id, param_id, val127):
                # Logging is opt-in via attribute flag (volume of fires is high)
                if getattr(self, '_strip_log_values', False):
                    mod_name = _strip_module_name(mod_id)
                    print(f"  [STRIP] {mod_name} 0x{param_id:02X} val={val127}")
        
        elif msg_type == 0x32 and len(payload) >= 2:
            mod_id = payload[0]
            param_id = payload[1]
            try:
                text = bytes(payload[2:]).decode('utf-8').rstrip('\x00')
                if text:
                    if self.state.channel_strip.update_display(mod_id, param_id, text):
                        mod_name = _strip_module_name(mod_id)
                        print(f"  [STRIP] {mod_name} 0x{param_id:02X} display='{text}'")
                        self._leds_dirty = True
                elif _STRIP_LOG_EMPTY:
                    mod_name = _strip_module_name(mod_id)
                    print(f"  [STRIP] {mod_name} 0x{param_id:02X} display=<empty>")
            except UnicodeDecodeError:
                pass
        
        # ── Plugin identity (Phase 1c) — type 0x33 ──
        # Fired by slot.mOnChangePluginIdentity when a strip module variant changes.
        # Format: F0 00 21 09 33 modId <ascii pluginName> F7
        # E.g. variant switch in Compressor slot fires plugin='Tube Compressor'.
        elif msg_type == 0x33 and len(payload) >= 1:
            mod_id = payload[0]
            try:
                name = bytes(payload[1:]).decode('utf-8').rstrip('\x00')
                if name:
                    if self.state.channel_strip.update_plugin(mod_id, name):
                        mod_name = _strip_module_name(mod_id)
                        print(f"  [STRIP] {mod_name} plugin='{name}'")
                        self._leds_dirty = True
                        self._dump_strip_discovery()
                        # If the user is currently drilled into THIS slot,
                        # re-activate the variant-specific sub-page so the
                        # JS encoder/toggle bindings match the new plugin.
                        cs_page = getattr(self.state, 'cs_page', 'overview')
                        if self._PAGE_TO_MOD_ID.get(cs_page) == mod_id:
                            print(f"  [STRIP] re-activating sub-page for new variant")
                            self.activate_subpage(cs_page)
                elif _STRIP_LOG_EMPTY:
                    mod_name = _strip_module_name(mod_id)
                    print(f"  [STRIP] {mod_name} plugin=<empty>")
            except UnicodeDecodeError:
                pass

    # ─────────────────────────────────────────────
    # Sending messages to Nuendo
    # ─────────────────────────────────────────────

    def send_cc(self, cc_num, value):
        """
        Send a CC message to Nuendo.
        
        cc_num : CC number (0-127)
        value  : value (0-127)
        """
        if self._midi_out and self._running:
            # Ignore VU peak clips after bank change or selection
            if cc_num in (8, 9, 80, 81, 82, 83, 84, 85, 86, 87):
                self._vu_ignore_until = time.time() + 1.5
            self._midi_out.send_message([0xB0, cc_num & 0x7F, int(value) & 0x7F])

    def send_cc_ch2(self, cc_num, value):
        """Send a CC message on channel 2 (0xB1)."""
        if self._midi_out and self._running:
            self._midi_out.send_message([0xB1, cc_num & 0x7F, int(value) & 0x7F])

    def send_cc_ch3(self, cc_num, value):
        """Send a CC message on channel 3 (0xB2)."""
        if self._midi_out and self._running:
            self._midi_out.send_message([0xB2, cc_num & 0x7F, int(value) & 0x7F])

    def send_cc_ch4(self, cc_num, value):
        """Send a CC message on channel 4 (0xB3)."""
        if self._midi_out and self._running:
            self._midi_out.send_message([0xB3, cc_num & 0x7F, int(value) & 0x7F])

    def send_cc_ch5(self, cc_num, value):
        """Send a CC message on channel 5 (0xB4)."""
        if self._midi_out and self._running:
            self._midi_out.send_message([0xB4, cc_num & 0x7F, int(value) & 0x7F])

    def send_cc_ch6(self, cc_num, value):
        """Send a CC message on channel 6 (0xB5). Used for Control Room."""
        if self._midi_out and self._running:
            self._midi_out.send_message([0xB5, cc_num & 0x7F, int(value) & 0x7F])

    def send_cc_ch7(self, cc_num, value):
        """Send a CC message on channel 7 (0xB6). Used for bank zone sends."""
        if self._midi_out and self._running:
            self._midi_out.send_message([0xB6, cc_num & 0x7F, int(value) & 0x7F])

    def send_cc_ch8(self, cc_num, value):
        """Send a CC message on channel 8 (0xB7). Used for Channel Strip writes."""
        if self._midi_out and self._running:
            self._midi_out.send_message([0xB7, cc_num & 0x7F, int(value) & 0x7F])

    def send_cc_ch9(self, cc_num, value):
        """Send a CC message on MIDI Remote channel index 9 (wire byte 0xB9).
        
        ⚠ Naming exception: the existing send_cc_chN functions in this file use
        a "1-based user-facing" channel naming where chN sends wire byte 0xB(N-1).
        This function BREAKS that convention because the MIDI Remote API on the
        JS side uses 0-based channel indexing — bindToControlChange(9, ...)
        listens specifically for wire byte 0xB9. To match, we send 0xB9 directly.
        
        Used for Channel Strip CONTINUOUS writes (PreGain encoder delta).
        Channel 8 (0xB8) is heavily used by the DirectAccess encoder routing
        system, hence the +1 here.
        """
        if self._midi_out and self._running:
            self._midi_out.send_message([0xB9, cc_num & 0x7F, int(value) & 0x7F])

    def send_note_ch9(self, note_num, velocity):
        """Send a note-on message on MIDI Remote channel index 9 (wire byte 0x99).
        
        Used for Channel Strip BINARY toggle writes (slot.mOn, Phase, section
        bypasses). Steinberg MIDI Remote API requires Button + bindToNote +
        setTypeToggle for binary host writes — confirmed by the working
        sendOnBtn pattern at line ~475 of Ableton_Push2.js. Knob + CC +
        setTypeToggle does NOT propagate writes for binary hosts.
        
        Each note-on event flips the host's binary value via the toggle binding.
        We send velocity 127 (press) which is what the toggle binding watches for.
        """
        if self._midi_out and self._running:
            self._midi_out.send_message([0x99, note_num & 0x7F, int(velocity) & 0x7F])

    # ── Channel Strip control (Axe A) ─────────────────────────────
    # Channel 9 (raw, 0-indexed) — wire bytes 0xB9 (CC) and 0x99 (note-on).
    # Free of conflicts with daBypass (raw 7) and DA encoder system (raw 8).
    #
    # CONTINUOUS hosts (PreGain) → CC 9/N, value is absolute 0-127
    # BINARY hosts (Phase, Bypass, slot.mOn) → Note 9/N (velocity 127), each
    #   note-on toggles the host via .setTypeToggle() binding on JS side
    #
    # The number N is the same in both cases (it's just a row in the table),
    # but messages with the same N differ in type:
    #   N=0 : PreGain         — CC (continuous)
    #   N=1 : Phase Switch    — Note (toggle)
    #   N=2 : PreFilter sec   — Note (toggle)
    #   N=3 : ChannelEQ sec   — Note (toggle)
    #   N=4..8 : slot.mOn     — Note (toggle)
    
    # Map (mod_id, param_id) → message number N on channel 9
    _STRIP_PARAM_NUM = {
        (0x00, 0x00): 0,   # PreFilter PreGain (CC, continuous)
        (0x00, 0x01): 1,   # PreFilter Phase Switch (Note, toggle)
        (0x00, 0x7F): 2,   # PreFilter section bypass (Note, toggle)
        (0x01, 0x7F): 3,   # ChannelEQ section bypass (Note, toggle)
        (0x10, 0x00): 4,   # Gate slot.mOn (Note, toggle)
        (0x11, 0x00): 5,   # Compressor slot.mOn (Note, toggle)
        (0x12, 0x00): 6,   # Tools slot.mOn (Note, toggle)
        (0x13, 0x00): 7,   # Saturator slot.mOn (Note, toggle)
        (0x14, 0x00): 8,   # Limiter slot.mOn (Note, toggle)
        (0x00, 0x03): 9,   # PreFilter HC On (Note, toggle)
        (0x00, 0x06): 10,  # PreFilter LC On (Note, toggle)
        (0x00, 0x02): 18,  # PreFilter HC Freq (CC, continuous)
        (0x00, 0x05): 19,  # PreFilter LC Freq (CC, continuous)
    }
    # Backward-compatible alias for code that still references _STRIP_PARAM_CC
    _STRIP_PARAM_CC = _STRIP_PARAM_NUM
    
    def send_strip_param_set(self, mod_id, param_id, val127):
        """
        Send an absolute 0-127 value to a continuous strip parameter via CC.
        Currently only used implicitly by the delta helper for PreGain.
        For binary params, use send_strip_param_toggle instead.
        """
        n = self._STRIP_PARAM_NUM.get((mod_id, param_id))
        if n is None:
            print(f"[STRIP] send_strip_param_set: no mapping for "
                  f"mod={mod_id:02X} param={param_id:02X}")
            return
        val = max(0, min(127, int(val127)))
        print(f"[STRIP→Nuendo] CC9/{n} = {val}  (set, mod={mod_id:02X} param={param_id:02X})")
        self.send_cc_ch9(n, val)
    
    def send_strip_param_delta(self, mod_id, param_id, delta):
        """
        Apply a relative delta to a continuous strip param (PreGain). Reads the
        cached value from state.channel_strip, adds delta, sends the new absolute
        value via CC on channel 9. Used by encoder turns.
        """
        n = self._STRIP_PARAM_NUM.get((mod_id, param_id))
        if n is None:
            print(f"[STRIP] send_strip_param_delta: no mapping for "
                  f"mod={mod_id:02X} param={param_id:02X}")
            return
        current = self.state.channel_strip.get_value(mod_id, param_id)
        if current is None:
            current = 64
        new_val = max(0, min(127, current + int(delta)))
        print(f"[STRIP→Nuendo] CC9/{n} = {new_val}  (delta from {current} +{delta:+d}, "
              f"mod={mod_id:02X} param={param_id:02X})")
        self.send_cc_ch9(n, new_val)
    
    def send_strip_param_toggle(self, mod_id, param_id):
        """
        Flip a binary strip param (slot.mOn, mPhaseSwitch, section bypass).
        Sends a note-on event on channel 9, note number = mapping table N,
        velocity 127. The JS binding has .setTypeToggle() which flips the
        host's binary value on each note-on event.

        Some Cubase params (notably PreFilter HC/LC On and section bypass)
        don't fire mOnProcessValueChange/mOnDisplayValueChange callbacks
        reliably, so we also OPTIMISTICALLY update the cached value/display
        with the predicted new state. If a real SysEx 0x31/0x32 arrives
        later, it overrides our prediction.
        """
        n = self._STRIP_PARAM_NUM.get((mod_id, param_id))
        if n is None:
            print(f"[STRIP] send_strip_param_toggle: no mapping for "
                  f"mod={mod_id:02X} param={param_id:02X}")
            return
        current = self.state.channel_strip.get_value(mod_id, param_id)
        # Predict the post-toggle value
        new_val = 0 if (current is not None and current >= 64) else 127
        self.state.channel_strip.update_value(mod_id, param_id, new_val)
        self.state.channel_strip.update_display(
            mod_id, param_id, 'On' if new_val >= 64 else 'Off')
        self._leds_dirty = True
        print(f"[STRIP→Nuendo] Note9/{n} velocity 127  (toggle, current={current} "
              f"→ predicted {new_val}, mod={mod_id:02X} param={param_id:02X})")
        self.send_note_ch9(n, 127)
    
    # ── Channel Strip drill-down (Axe B) ─────────────────────────────
    # Sub-page activation: bridge sends a note on channel 9 to activate the
    # corresponding sub-page in the JS script. Once a sub-page is active,
    # encoder writes (CC 9/10..17) route to that sub-page's param bindings.
    #
    #   Note 9/100 = Overview
    #   Note 9/101 = Gate
    #   Note 9/102 = Comp
    #   Note 9/103 = EQ
    #   Note 9/104 = Tools
    #   Note 9/105 = Sat
    #   Note 9/106 = Limiter
    
    # Sub-page activator notes. Each Channel Strip variant has its own sub-page
    # in JS with bindings tailored to that variant's params (continuous vs
    # binary positions differ between, e.g., Standard and Vintage Comp).
    #
    # Lookup is keyed by (cs_page, plugin_name). plugin_name=None falls back
    # to the "primary" variant for that slot (used when drilling in before
    # the variant is detected, or when the slot has no plugin loaded yet).
    _SUBPAGE_NOTES = {
        # Overview + single-variant slots
        ('overview', None):                    100,
        ('gate',     None):                    101,
        ('gate',     'Noise Gate'):            101,
        ('eq',       None):                    103,
        # Comp variants (3)
        ('comp',     None):                    110,  # fallback → Standard
        ('comp',     'Standard Compressor'):   110,
        ('comp',     'Tube Compressor'):       111,
        ('comp',     'VintageCompressor'):     112,
        # Tools variants (2 known so far) — moved out of 120-127 range to avoid
        # collision with drilldown toggle notes (120 = Auto Threshold for DeEsser).
        ('tools',    None):                    113,  # fallback → DeEsser
        ('tools',    'DeEsser'):               113,
        ('tools',    'EnvelopeShaper'):        114,
        # Sat variants (3)
        ('sat',      None):                    130,  # fallback → Magneto II
        ('sat',      'Magneto II'):            130,
        ('sat',      'Tape Saturation'):       131,
        ('sat',      'Tube Saturation'):       132,
        # Limit variants (3)
        ('limiter',  None):                    140,  # fallback → Brickwall
        ('limiter',  'Brickwall Limiter'):     140,
        ('limiter',  'Maximizer'):             141,
        ('limiter',  'Standard Limiter'):      142,
    }
    
    # Map cs_page name → mod_id, used by the bridge to resolve the slot's
    # current plugin_name when activating the right variant sub-page.
    _PAGE_TO_MOD_ID = {
        'gate':    0x10,
        'comp':    0x11,
        'tools':   0x12,
        'sat':     0x13,
        'limiter': 0x14,
    }
    
    def activate_subpage(self, name):
        """
        Send a note-on to activate the corresponding Channel Strip sub-page
        in JS. Called whenever state.cs_page changes so encoder write
        bindings route to the right module's parameters.
        
        For multi-variant slots, looks up the current plugin_name in
        state.channel_strip.slots[mod_id] and activates the variant-specific
        sub-page. Falls back to the "primary" variant (key with None) when
        no plugin is loaded or the variant is unknown.
        """
        # Look up the current plugin name for this page's slot (if any).
        variant = None
        mod_id = self._PAGE_TO_MOD_ID.get(name)
        if mod_id is not None:
            slot = self.state.channel_strip.slots.get(mod_id)
            if slot and slot.plugin_name:
                variant = slot.plugin_name
        
        # Resolve activator note. Try exact match first, then fall back to
        # the page's primary variant (None key).
        note = self._SUBPAGE_NOTES.get((name, variant))
        if note is None:
            note = self._SUBPAGE_NOTES.get((name, None))
        if note is None:
            print(f"[STRIP] activate_subpage: unknown page '{name}'")
            return
        
        variant_str = f"variant='{variant}'" if variant else "no-variant"
        print(f"[STRIP→Nuendo] Note9/{note} velocity 127  "
              f"(activate sub-page '{name}' {variant_str})")
        self.send_note_ch9(note, 127)
    
    def send_slot_param_delta(self, mod_id, param_id, delta, encoder_index=None):
        """
        Apply a relative delta to a strip slot's bank zone parameter.
        Used by drill-down encoders 1..8 when a slot sub-page is active.
        
        encoder_index : 0..7 — physical encoder index, determines which CC is
                        sent (CC 9/(10+encoder_index)). This must match the
                        JS knob's CC binding, which is fixed per knob position.
                        Defaults to (param_id - 0x01) for backward compat when
                        encoders are 1:1 mapped to paramIds, but for custom
                        sub-page layouts (where enc N may control paramId
                        other than N+1), the caller must pass encoder_index
                        explicitly.
        
        mod_id, param_id : used for cache lookup. The sub-page binding on the
                           JS side determines which paramVal the CC drives;
                           we mirror that here to compute current + delta.
        """
        if param_id < 0x01 or param_id > 0x08:
            print(f"[STRIP] send_slot_param_delta: param_id 0x{param_id:02X} "
                  f"out of bank zone range (0x01..0x08)")
            return
        if encoder_index is None:
            encoder_index = param_id - 0x01
        if encoder_index < 0 or encoder_index > 7:
            print(f"[STRIP] send_slot_param_delta: encoder_index {encoder_index} "
                  f"out of range (0..7)")
            return
        cc = 10 + encoder_index
        slot = self.state.channel_strip.slots.get(mod_id)
        if slot is None:
            print(f"[STRIP] send_slot_param_delta: slot mod=0x{mod_id:02X} not found")
            return
        cached = slot.params.get(param_id, {}).get('value')
        current = cached if cached is not None else 64
        new_val = max(0, min(127, current + int(delta)))
        print(f"[STRIP→Nuendo] CC9/{cc} = {new_val}  (slot delta enc{encoder_index+1} "
              f"from {current} {delta:+d}, mod={mod_id:02X} param={param_id:02X})")
        self.send_cc_ch9(cc, new_val)
    
    def send_drilldown_toggle(self, lower_row_idx):
        """
        Toggle a drill-down lower-row binary param. The JS Button at note
        9/(120 + lower_row_idx) is wired (per active sub-page) to a bank zone
        paramVal with setTypeToggle. Bridge just sends the note — JS flips
        the value on the active sub-page's binding.
        
        lower_row_idx : 0..7 — which physical lower row button was pressed.
        Returns silently if the active sub-page doesn't have a toggle at
        that position (the JS Button still receives the note but has no
        binding to act on).
        """
        if lower_row_idx < 0 or lower_row_idx > 7:
            return
        note = 120 + lower_row_idx
        print(f"[STRIP→Nuendo] Note9/{note} velocity 127 "
              f"(drill-down toggle, lower row {lower_row_idx + 1})")
        self.send_note_ch9(note, 127)
        # Defer the release so the rising edge is processed in its own audio
        # buffer by Steinberg's MIDI Remote (back-to-back messages get coalesced
        # to the final value and setTypeToggle never sees the 0→1 transition).
        # Use a real note-off (status 0x89) — `bindToNote` ignores 0x99 vel=0
        # so the surface value would stay stuck at 1.0 and the next press would
        # not be a rising edge.
        def _release(n=note):
            if self._midi_out and self._running:
                self._midi_out.send_message([0x89, n & 0x7F, 0])
        threading.Timer(0.05, _release).start()
    
    def _dump_strip_discovery(self):
        """
        Rewrite the strip discovery log file with the current state of all
        Channel Strip modules. Easier than scrolling the Nuendo JS console
        for capturing the bank zone param inventory of each module.
        
        Called on every announce/display change that actually mutates state.
        Rewrites the file in full each time — latest state always wins.
        """
        cs = self.state.channel_strip
        try:
            with open(self._strip_discovery_log, 'w') as f:
                f.write("# Channel Strip parameter discovery dump\n")
                f.write("# Auto-updated by Push2Nuendo-Bridge on every strip\n")
                f.write("# announce / display change.\n#\n")
                
                # PreFilter (mod_id 0x00)
                if cs.prefilter:
                    f.write("\n## PreFilter (mod_id=0x00)\n")
                    for pid in sorted(cs.prefilter.keys()):
                        p = cs.prefilter[pid]
                        f.write(f"  pid=0x{pid:02X}  name='{p.get('name','')}'  "
                                f"display='{p.get('display','')}'  "
                                f"value={p.get('value','')}\n")
                
                # ChannelEQ + 4 bands (mod_id 0x01)
                if cs.eq:
                    f.write("\n## ChannelEQ (mod_id=0x01)\n")
                    for pid in sorted(cs.eq.keys()):
                        p = cs.eq[pid]
                        f.write(f"  pid=0x{pid:02X}  name='{p.get('name','')}'  "
                                f"display='{p.get('display','')}'  "
                                f"value={p.get('value','')}\n")
                
                # Strip slots (mod_id 0x10..0x14)
                for mod_id in sorted(cs.slots.keys()):
                    slot = cs.slots[mod_id]
                    f.write(f"\n## Slot mod_id=0x{mod_id:02X} ({slot.label})\n")
                    f.write(f"#   plugin variant: {slot.plugin_name or '<empty>'}\n")
                    f.write(f"#   on={slot.on}  bypassed={slot.bypassed}\n")
                    for pid in sorted(slot.params.keys()):
                        p = slot.params[pid]
                        f.write(f"  pid=0x{pid:02X}  name='{p.get('name','')}'  "
                                f"display='{p.get('display','')}'  "
                                f"value={p.get('value','')}\n")
        except Exception as e:
            # Don't crash the bridge over a file-write error
            print(f"[STRIP] discovery dump error: {e}")

    def send_note(self, note, velocity):
        """Send a Note On/Off message to Nuendo (Loop port)."""
        if self._midi_out and self._running:
            if velocity > 0:
                self._midi_out.send_message([0x90, note & 0x7F, velocity & 0x7F])
            else:
                self._midi_out.send_message([0x80, note & 0x7F, 0])

    def toggle_edit_channel_settings(self):
        """Toggle the Edit Channel Settings window for the selected channel.

        JS binds Note 0/78 to selectedCh.mValue.mEditorOpen with setTypeToggle.
        A note-on (with deferred note-off so each press is a fresh rising edge)
        flips the window open/closed.
        """
        if not (self._midi_out and self._running):
            return
        self._midi_out.send_message([0x90, 78, 127])
        def _release():
            if self._midi_out and self._running:
                self._midi_out.send_message([0x80, 78, 0])
        threading.Timer(0.05, _release).start()
        print("[STRIP→Nuendo] Note0/78 (toggle Edit Channel Settings window)")

    def send_note_on(self, note, velocity=100):
        """Send a Note On via the Push 2 User port (channel 1)."""
        port = self._midi_notes_out or self._midi_out
        if port and self._running:
            port.send_message([0x90, note & 0x7F, velocity & 0x7F])

    def send_note_off(self, note):
        """Send a Note Off via the Push 2 User port (channel 1)."""
        port = self._midi_notes_out or self._midi_out
        if port and self._running:
            port.send_message([0x80, note & 0x7F, 0])

    def send_aftertouch(self, note, pressure):
        """Send a Polyphonic Aftertouch via the notes port (channel 1)."""
        port = self._midi_notes_out or self._midi_out
        if port and self._running:
            port.send_message([0xA0, note & 0x7F, pressure & 0x7F])

    def send_channel_aftertouch(self, pressure):
        """Send a Channel Aftertouch via the notes port (channel 1)."""
        port = self._midi_notes_out or self._midi_out
        if port and self._running:
            port.send_message([0xD0, pressure & 0x7F])

    def send_midi_cc_to_notes(self, cc_number, value):
        """Send a MIDI CC message via the notes port (channel 1)."""
        port = self._midi_notes_out or self._midi_out
        if port and self._running:
            port.send_message([0xB0, cc_number & 0x7F, value & 0x7F])

    def send_da_toggle(self, track_index, function):
        """Send a DA toggle command to JS via CC 16 (track index) + CC 17 (function).
        
        track_index: absolute track index in the project (0-127)
        function: 0=Mute, 1=Solo, 2=Monitor, 3=Record
        
        CC 17 = set target track index
        CC 18 = execute toggle (value = function)
        """
        if self._midi_out and self._running:
            self._midi_out.send_message([0xB0, 17, track_index & 0x7F])
            import time as _t; _t.sleep(0.005)
            self._midi_out.send_message([0xB0, 18, function & 0x7F])

    def request_da_insert_exploration(self):
        """Ask JS to explore the insert tree via DirectAccess (CC 88 = 127).
        
        JS will respond with SysEx 0x24 (slot entries) and 0x25 (complete).
        If DA is not available, nothing happens.
        """
        if self._midi_out and self._running and self._da_available:
            self._da_inserts_ready = False
            self._midi_out.send_message([0xB0, 88, 127])
            print("  → DA: Requested insert tree exploration")

    def send_da_bypass(self, slot_index, want_bypass):
        """Toggle bypass on an insert slot via DirectAccess (CC 85).
        
        slot_index: 0-15 (insert slot)
        want_bypass: True = bypass ON, False = bypass OFF (active)
        
        JS will respond with SysEx 0x26 (result).
        Falls back to viewer-based if DA cache not ready.
        
        Returns True if DA command was sent, False if not available.
        """
        if not (self._midi_out and self._running):
            return False
        if not getattr(self, '_da_available', False):
            return False
        if not getattr(self, '_da_inserts_ready', False):
            return False
        
        # Encode: value = slot_index + (64 if want_bypass)
        # Send on channel 8 (0xB7) to avoid conflict with selButtons on ch1
        value = (slot_index & 0x1F) | (0x40 if want_bypass else 0x00)
        self._midi_out.send_message([0xB7, 85, value & 0x7F])
        return True

    def send_da_edit(self, slot_index):
        """Toggle plugin UI on an insert slot via DirectAccess (CC 86 ch8).
        
        slot_index: 0-15 (insert slot)
        
        JS will respond with SysEx 0x28 (result).
        Returns True if DA command was sent, False if not available.
        """
        if not (self._midi_out and self._running):
            return False
        if not getattr(self, '_da_available', False):
            return False
        if not getattr(self, '_da_inserts_ready', False):
            return False
        
        self._midi_out.send_message([0xB7, 86, slot_index & 0x7F])
        return True

    def request_da_plugin_params(self, slot_index):
        """Ask JS to enumerate all parameters of the plugin in a slot (CC 87 ch8).
        
        JS will respond with SysEx 0x29 (param entries) and 0x2A (complete).
        Returns True if command was sent.
        """
        if not (self._midi_out and self._running):
            return False
        if not getattr(self, '_da_available', False):
            return False
        if not getattr(self, '_da_inserts_ready', False):
            return False
        
        self._da_plugin_params = {}  # Clear previous enum
        self._da_params_enumerated = False
        self._midi_out.send_message([0xB7, 87, slot_index & 0x7F])
        print(f"  → DA: Requested param enumeration for slot {slot_index}")
        return True

    def send_da_encoder_setup(self, slot_index, da_param_indices):
        """Configure which DA params the 8 encoders control (channel 9).
        
        slot_index: 0-15
        da_param_indices: list of 8 DA param indices (use -1 for unused encoders)
        """
        if not (self._midi_out and self._running):
            return False
        if not getattr(self, '_da_available', False):
            return False
        
        # CC 0 ch9: set slot
        self._midi_out.send_message([0xB8, 0, slot_index & 0x7F])
        
        # CC 1-8 ch9: low bits, CC 9-16 ch9: high bits
        for i in range(8):
            idx = da_param_indices[i] if i < len(da_param_indices) else -1
            if idx < 0:
                idx = 0  # Will have tag 0 which won't match anything
            lo = idx & 0x7F
            hi = (idx >> 7) & 0x7F
            self._midi_out.send_message([0xB8, 1 + i, lo])
            self._midi_out.send_message([0xB8, 9 + i, hi])
        
        return True

    def request_da_plugin_manager_explore(self, slot_index):
        """Ask JS to explore Plugin Manager collections for a slot (CC 84 ch8).
        
        Results come back via daLog (SysEx 0x20).
        """
        if not (self._midi_out and self._running):
            return False
        if not getattr(self, '_da_available', False):
            return False
        if not getattr(self, '_da_inserts_ready', False):
            return False
        
        self._midi_out.send_message([0xB7, 84, slot_index & 0x7F])
        print(f"  → DA: Requested Plugin Manager exploration for slot {slot_index}")
        return True

    def request_da_plugin_list(self, collection_index=1):
        """Ask JS to send the full plugin list for a collection (CC 83 ch8).
        
        collection_index: 0 = Default (all plugins), 1 = Push (curated), etc.
        
        JS will respond with SysEx 0x2C (entries) and 0x2D (complete).
        Results stored in state.browser_plugins[].
        """
        if not (self._midi_out and self._running):
            return False
        if not getattr(self, '_da_available', False):
            return False
        if not getattr(self, '_da_inserts_ready', False):
            return False
        
        # Reset browser state
        self.state.browser_plugins = []
        self.state.browser_list_ready = False
        
        self._midi_out.send_message([0xB7, 83, collection_index & 0x7F])
        print(f"  → DA: Requested plugin list for collection {collection_index}")
        return True

    def request_da_collection_info(self):
        """Ask JS to send info about all plugin collections (CC 88 ch8).
        
        JS will respond with SysEx 0x2F for each collection.
        Results stored in state.browser_collections[].
        """
        if not (self._midi_out and self._running):
            return False
        if not getattr(self, '_da_available', False):
            return False
        if not getattr(self, '_da_inserts_ready', False):
            return False
        
        self.state.browser_collections = []
        self.state.browser_collections_ready = False
        
        self._midi_out.send_message([0xB7, 88, 0])
        print("  → DA: Requested collection info")
        return True

    def send_da_load_plugin(self, target_slot, entry_index, collection_index):
        """Load a plugin into an insert slot via DA Plugin Manager.
        
        target_slot: 0-15 (insert slot)
        entry_index: index into the collection's mEntries array
        collection_index: which collection (0=Default, 1=Push, etc.)
        
        Sends 3 CCs on ch8:
          CC 82: target slot index
          CC 81: entry index low 7 bits
          CC 80: (entry index high bits) | (collection index << 4) → triggers load
        
        JS will respond with SysEx 0x2E (result).
        """
        if not (self._midi_out and self._running):
            return False
        if not getattr(self, '_da_available', False):
            return False
        if not getattr(self, '_da_inserts_ready', False):
            return False
        
        entry_lo = entry_index & 0x7F
        entry_hi = (entry_index >> 7) & 0x0F
        coll_bits = (collection_index & 0x07) << 4
        
        self._midi_out.send_message([0xB7, 82, target_slot & 0x7F])
        import time as _t; _t.sleep(0.005)
        self._midi_out.send_message([0xB7, 81, entry_lo])
        _t.sleep(0.005)
        self._midi_out.send_message([0xB7, 80, entry_hi | coll_bits])
        
        print(f"  → DA: Load plugin entry {entry_index} from coll {collection_index} into slot {target_slot}")
        return True

    def send_da_clear_slot(self, slot_index):
        """Attempt to clear (remove plugin from) an insert slot via DA (CC 79 ch8).
        
        JS will try trySetSlotPlugin with empty UID.
        Result comes back via SysEx 0x2E.
        """
        if not (self._midi_out and self._running):
            return False
        if not getattr(self, '_da_available', False):
            return False
        if not getattr(self, '_da_inserts_ready', False):
            return False
        
        self._midi_out.send_message([0xB7, 79, slot_index & 0x7F])
        print(f"  → DA: Clear slot {slot_index}")
        return True

    # ── DA Strip Slot methods (v1.0.4) ────────────────────────────────────────

    # Strip slot index mapping: Gate=0, Comp=1, Tools=2, Sat=3, Limiter=4
    # In the unified DA encoder system these map to slot indices 16-20.
    _STRIP_MOD_TO_SLOT_INDEX = {
        0x10: 0,  # Gate
        0x11: 1,  # Compressor
        0x12: 2,  # Tools
        0x13: 3,  # Saturator
        0x14: 4,  # Limiter
    }
    DA_STRIP_SLOT_OFFSET = 16  # insert slots 0-15, strip slots 16-20

    @staticmethod
    def _parse_eq_freq(disp):
        """Parse '30.0 Hz' / '1.5 kHz' → float Hz, or None."""
        if not disp:
            return None
        s = disp.strip().lower().replace(' ', '')
        try:
            if s.endswith('khz'): return float(s[:-3]) * 1000.0
            if s.endswith('hz'):  return float(s[:-2])
            return float(s)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_eq_db(disp):
        """Parse '0.0 dB' / '-3.5 dB' → float dB, or None."""
        if not disp:
            return None
        s = disp.strip().lower().replace(' ', '')
        if s.endswith('db'): s = s[:-2]
        try:
            return float(s)
        except (ValueError, TypeError):
            return None

    def request_da_strip_exploration(self):
        """Ask JS to explore strip slot objects via DA (CC 70 ch8).

        JS responds with SysEx 0x34 (slot entries) and 0x35 (complete).
        """
        if not (self._midi_out and self._running):
            return False
        if not getattr(self, '_da_available', False):
            return False
        self._da_strip_slot_cache = []
        self._da_strip_explored   = False
        self._midi_out.send_message([0xB7, 70, 127])
        print("  → DA: Requested strip slot exploration")
        return True

    def send_da_strip_bypass(self, slot_index, want_bypass):
        """Set bypass on a strip slot via DirectAccess (CC 71 ch8).

        slot_index: 0-4 (Gate=0, Comp=1, Tools=2, Sat=3, Limiter=4)
        want_bypass: True = bypass ON, False = bypass OFF

        JS responds with SysEx 0x36.
        Returns True if command was sent.
        """
        if not (self._midi_out and self._running):
            return False
        if not getattr(self, '_da_available', False):
            return False
        if not getattr(self, '_da_strip_explored', False):
            return False
        value = (slot_index & 0x07) | (0x40 if want_bypass else 0x00)
        self._midi_out.send_message([0xB7, 71, value & 0x7F])
        return True

    def send_da_strip_edit(self, slot_index):
        """Toggle the plugin UI for a strip slot via the binding path mEdit.

        slot_index: 0-4 (Gate, Comp, Tools, Sat, Limiter)

        Uses the HostStripEffectSlot.mEdit binding path (CC 90..94 channel 0)
        with setTypeToggle — same pattern as insert Edit (CC 99 ch0). The DA
        tag-based path (tag 4101) only flips a metadata flag; tag 4127 opens
        the Routing Patcher, not the plugin UI.
        """
        if not (self._midi_out and self._running):
            return False
        if not (0 <= slot_index <= 4):
            return False
        cc = 90 + slot_index
        # Reset pulse so consecutive presses re-fire the binding (Steinberg
        # ignores identical CC values; setTypeToggle needs a fresh rising edge).
        self._midi_out.send_message([0xB0, cc, 0])
        self._midi_out.send_message([0xB0, cc, 127])
        print(f"  → Strip Edit toggle slot {slot_index} (CC0/{cc})")
        return True

    def diag_probe_effect_type(self, da_slot):
        """Probe tag 4125 across [0..1] to discover discrete variant mapping.

        Captures original value, sweeps, restores. Output goes to Nuendo JS console.
        """
        if not (self._midi_out and self._running):
            return False
        if not getattr(self, '_da_available', False):
            return False
        self._midi_out.send_message([0xB7, 78, da_slot & 0x7F])
        print(f"  → DA diag: probe tag 4125 for DA slot {da_slot}")
        return True

    def diag_enum_slot_object(self, da_slot):
        """Dump the SLOT object's own params + children to the Nuendo JS console.

        Diagnostic for finding a strip-variant type selector tag.
        """
        if not (self._midi_out and self._running):
            return False
        if not getattr(self, '_da_available', False):
            return False
        self._midi_out.send_message([0xB7, 77, da_slot & 0x7F])
        print(f"  → DA diag: enum slot-object params for DA slot {da_slot}")
        return True

    def send_variant_switch(self, da_slot, variant_idx):
        """Swap the plugin in a strip slot to a named variant via DA Plugin Manager.

        da_slot: 16-20 (strip slot index)
        variant_idx: index into the variant name list for that slot
                     (must match Ableton_Push2.js STRIP_VARIANTS order)

        JS responds with SysEx 0x3A [daSlot, success].
        """
        if not (self._midi_out and self._running):
            return False
        if not getattr(self, '_da_available', False):
            return False
        if not getattr(self, '_da_strip_explored', False):
            return False
        self._midi_out.send_message([0xB7, 75, variant_idx & 0x7F])
        # Sentinel so the next slot value is always seen as a change.
        self._midi_out.send_message([0xB7, 76, 127])
        self._midi_out.send_message([0xB7, 76, da_slot & 0x7F])
        print(f"  → DA: Variant switch slot {da_slot} → idx {variant_idx}")
        return True

    def send_da_param_flip(self, da_slot, param_idx):
        """Flip a binary plugin param via DirectAccess (CC 73 + CC 74 ch8).

        Bypasses the bank-zone binding/setTypeToggle path, which Cubase
        sometimes invalidates after value changes on certain params
        (e.g. VintageCompressor Att-Mode). JS reads current value, flips
        0<->1, and notifies via SysEx 0x39.

        da_slot: 0-15 for insert slots, 16-20 for strip slots
        param_idx: index into the DA-enumerated param list of that plugin
        """
        if not (self._midi_out and self._running):
            return False
        if not getattr(self, '_da_available', False):
            return False
        self._midi_out.send_message([0xB7, 73, param_idx & 0x7F])
        # Sentinel reset on CC 74 ensures the next slot value is seen as a
        # change even when flipping the same (slot, param) twice in a row.
        self._midi_out.send_message([0xB7, 74, 127])
        self._midi_out.send_message([0xB7, 74, da_slot & 0x7F])
        return True

    def request_da_strip_params(self, slot_index):
        """Enumerate all parameters of a strip slot plugin (CC 87 ch8, slot 16+).

        slot_index: 0-4 (bridge adds DA_STRIP_SLOT_OFFSET internally)
        JS responds with SysEx 0x29 (param entries) and 0x2A (complete).
        Returns True if command was sent.
        """
        if not (self._midi_out and self._running):
            return False
        if not getattr(self, '_da_available', False):
            return False
        if not getattr(self, '_da_strip_explored', False):
            return False
        da_idx = self.DA_STRIP_SLOT_OFFSET + slot_index
        self._da_plugin_params    = {}
        self._da_params_enumerated = False
        self._midi_out.send_message([0xB7, 87, da_idx & 0x7F])
        print(f"  → DA: Requested strip param enum for strip slot {slot_index} (DA idx {da_idx})")
        return True

    # ─────────────────────────────────────────────────────────────────────────

    def send_da_encoder_value(self, encoder_idx, relative_midi):
        """Send a relative encoder value to JS for DA param control (CC 20-27 ch9).

        encoder_idx: 0-7
        relative_midi: signed bit encoding (1-63=CW, 65-127=CCW)

        Sends CC=0 first (reset) then the actual delta, so the JS button
        binding always sees a value change and fires its callback.
        """
        if not (self._midi_out and self._running):
            return
        cc = 20 + encoder_idx
        self._midi_out.send_message([0xB8, cc, 0])  # Reset pulse
        self._midi_out.send_message([0xB8, cc, relative_midi & 0x7F])  # Delta

    def _on_notes_received(self, event, data=None):
        """Receive playback MIDI notes from Nuendo to light up pads."""
        message, _ = event
        if len(message) < 2:
            return
        status = message[0] & 0xF0
        if status == 0x90 and len(message) >= 3:
            # Note On
            note = message[1]
            velocity = message[2]
            if self._note_display_callback:
                self._note_display_callback(note, velocity > 0)
        elif status == 0x80 and len(message) >= 3:
            # Note Off
            note = message[1]
            if self._note_display_callback:
                self._note_display_callback(note, False)
        elif status == 0xB0 and len(message) >= 3:
            # CC received from Nuendo (automation playback, other controllers)
            cc_num = message[1]
            cc_val = message[2]
            state = self.state
            for i in range(8):
                if state.cc_numbers[i] == cc_num:
                    # Mirror the incoming Nuendo value on the encoder position
                    state.cc_nuendo_values[i] = cc_val
                    state.cc_values[i] = cc_val
                    break

    def send_mode_change(self, mode):
        """Change encoder mode.
        
        With the multi-knobs approach, all bindings are always active.
        The bridge simply redirects the encoders to the correct CCs.
        Nothing to send to JS script.
        """
        pass  # Nothing to send to JS

    def send_bank_change(self, bank_offset):
        """Notify Nuendo of the displayed track bank."""
        # bank_offset / 8 = bank number (0-15)
        self.send_cc(2, min(127, bank_offset // BANK_SIZE))

    def send_volume_change(self, track_in_bank, value_0_to_1):
        """
        Send a volume change for a track.
        
        track_in_bank : 0-7 (position in the visible bank)
        value_0_to_1  : normalized value 0.0-1.0
        """
        midi_val = int(value_0_to_1 * 127)
        self.send_cc(20 + track_in_bank, midi_val)

    def send_pan_change(self, track_in_bank, pan_value):
        """Send a pan change. CC 40-47. pan_value: -1.0 (L) to +1.0 (R)."""
        # CC 0=L100, 64=C, 127=R100
        if pan_value <= 0:
            midi_val = int(64 + pan_value * 64)
        else:
            midi_val = int(64 + pan_value * 63)
        midi_val = max(0, min(127, midi_val))
        self.send_cc(40 + track_in_bank, midi_val)

    def send_send_change(self, track_in_bank, value_0_to_1):
        """Send a send level change. CC 48-55 channel 7."""
        midi_val = int(value_0_to_1 * 127)
        self.send_cc_ch7(48 + track_in_bank, midi_val)

    def send_quick_control_change(self, qc_index, value_0_to_1):
        """Send a Quick Control change. CC 56-63 channel 5."""
        midi_val = int(value_0_to_1 * 127)
        self.send_cc_ch5(56 + qc_index, midi_val)

    def send_select_track(self, track_in_bank):
        """Select a track in the current bank (0-7)."""
        if 0 <= track_in_bank < 8:
            self.send_cc(80 + track_in_bank, 127)

    def send_mute_toggle(self, track_in_bank, is_muted):
        """Set mute on a track."""
        self.send_cc(90 + track_in_bank, 127 if is_muted else 0)

    def send_solo_toggle(self, track_in_bank, is_solo):
        """Set solo on a track."""
        self.send_cc(100 + track_in_bank, 127 if is_solo else 0)

    def send_monitor_toggle(self, track_in_bank, is_monitored):
        """Set monitor on a track."""
        self.send_cc(110 + track_in_bank, 127 if is_monitored else 0)

    def send_rec_toggle(self, track_in_bank, is_armed):
        """Set record arm on a track."""
        self.send_cc(118 + track_in_bank, 127 if is_armed else 0)

    def _request_name_scan(self):
        """Start initial scan via on_connected callback."""
        import threading
        def _delayed():
            time.sleep(1.5)
            if self._on_connected_callback:
                self._on_connected_callback()
        threading.Thread(target=_delayed, daemon=True).start()

    def request_full_state(self):
        """
        Ask Nuendo to send all current values.
        Useful at startup or after reconnection.
        CC 127 value 127 = signal for 'full sync request'
        """
        self.send_cc(127, 127)

    # ─────────────────────────────────────────────
    # Connection monitoring
    # ─────────────────────────────────────────────

    def _watchdog_loop(self):
        """
        Run in background and monitor if Nuendo is still connected.
        If no heartbeat received for HEARTBEAT_TIMEOUT seconds,
        mark the state as disconnected.
        """
        while self._running:
            time.sleep(1.0)
            
            if self.state.nuendo_connected:
                elapsed = time.time() - self._last_heartbeat
                if elapsed > HEARTBEAT_TIMEOUT:
                    self.state.nuendo_connected = False
                    self._connection_grace_until = time.time() + 5.0
                    # Reset state to avoid stale data
                    self.state.is_playing = False
                    self.state.is_recording = False
                    self.state.metronome_on = False
                    self.state.cycle_active = False
                    for t in self.state.tracks:
                        t.vu_meter = 0.0
                        t.peak_clipped = False
                    self._leds_dirty = True
                    print("  ✗ Nuendo connection lost (heartbeat timeout)")


# ─────────────────────────────────────────────
# Utility: volume <-> dB conversion
# ─────────────────────────────────────────────

# 0 dB = CC 101 on a 7-bit MIDI fader = process value 101/127
_ZERO_DB = 99.0 / 127.0  # 0.779528


# ─────────────────────────────────────────────
# Strip Exploration (v1.0.4) — module ID lookup
# ─────────────────────────────────────────────

_STRIP_MODULE_NAMES = {
    0x00: "PreFilter",
    0x01: "ChannelEQ",
    0x10: "Gate",
    0x11: "Compressor",
    0x12: "Tools",
    0x13: "Saturator",
    0x14: "Limiter",
}


# Diagnostic flag: when True, empty announce/display strings are logged with a
# <empty> marker. Useful when investigating why a binding's callbacks don't seem
# to fire — an empty fire still tells us the binding is alive. Default False to
# keep startup logs clean (28+ params from PreFilter/EQ would otherwise spam).
_STRIP_LOG_EMPTY = False


def _strip_module_name(mod_id):
    """Returns the human-readable name of a strip module from its byte ID.
    Falls back to a hex placeholder if the ID is unknown."""
    return _STRIP_MODULE_NAMES.get(mod_id, f"Mod{mod_id:02X}")


def _to_db(normalized_volume):
    """
    Convert a Nuendo process value (0.0-1.0) to dB.
    Calibrated so that CC 101 = 0 dB exactly.
    """
    import math
    if normalized_volume <= 0.001:
        return -96.0
    
    v = normalized_volume
    if v >= _ZERO_DB:
        db = (v - _ZERO_DB) / (1.0 - _ZERO_DB) * 6.02
    elif v >= 0.5:
        db = (v - 0.5) / (_ZERO_DB - 0.5) * 12.0 - 12.0
    elif v >= 0.25:
        db = (v - 0.25) / (0.5 - 0.25) * 12.0 - 24.0
    elif v >= 0.1:
        db = (v - 0.1) / (0.25 - 0.1) * 24.0 - 48.0
    else:
        db = 20.0 * math.log10(v / 0.1) - 48.0
    
    return round(db, 1)


def _from_db(db):
    """
    Convert dB to Nuendo process value (0.0-1.0).
    Inverse of _to_db(). Calibrated so that 0 dB = CC 101.
    """
    if db <= -96.0:
        return 0.0
    elif db >= 0.0:
        return _ZERO_DB + (db / 6.02) * (1.0 - _ZERO_DB)
    elif db >= -12.0:
        return 0.5 + (db + 12.0) / 12.0 * (_ZERO_DB - 0.5)
    elif db >= -24.0:
        return 0.25 + (db + 24.0) / 12.0 * (0.5 - 0.25)
    elif db >= -48.0:
        return 0.1 + (db + 48.0) / 24.0 * (0.25 - 0.1)
    else:
        import math
        return 0.1 * math.pow(10, (db + 48.0) / 20.0)

