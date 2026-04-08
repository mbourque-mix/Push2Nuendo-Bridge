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

    def _open_iac_input(self):
        """Open an existing IAC/loopMIDI input port."""
        self._midi_in = rtmidi.MidiIn()
        self._midi_in.ignore_types(sysex=False, timing=False, active_sense=True)
        ports = self._midi_in.get_ports()
        
        for i, port_name in enumerate(ports):
            if PORT_FROM_NUENDO in port_name:
                self._midi_in.open_port(i)
                self._midi_in.set_callback(self._on_midi_received)
                print(f"  ✓ IAC port '{PORT_FROM_NUENDO}' connected")
                return True
        
        print(f"  ✗ Port '{PORT_FROM_NUENDO}' not found")
        print(f"    Available ports: {ports}")
        return False

    def _open_iac_output(self):
        """Open an existing IAC/loopMIDI output port."""
        self._midi_out = rtmidi.MidiOut()
        ports = self._midi_out.get_ports()
        
        for i, port_name in enumerate(ports):
            if PORT_TO_NUENDO in port_name:
                self._midi_out.open_port(i)
                print(f"  ✓ IAC port '{PORT_TO_NUENDO}' connected")
                return True
        
        print(f"  ✗ Port '{PORT_TO_NUENDO}' not found")
        return False

    # ── Notes ports (always virtual) ──

    def _open_notes_ports(self):
        """Create virtual ports for MIDI note I/O."""
        # Output: bridge sends notes to Nuendo
        self._midi_notes_out = rtmidi.MidiOut()
        try:
            self._midi_notes_out.open_virtual_port(PORT_NOTES_OUT)
            print(f"  ✓ Virtual port '{PORT_NOTES_OUT}' created")
        except Exception as e:
            print(f"  ⚠ Notes output port failed: {e}")
            self._midi_notes_out = None
        
        # Input: receive playback notes from Nuendo
        self._midi_notes_in = rtmidi.MidiIn()
        try:
            self._midi_notes_in.open_virtual_port(PORT_NOTES_IN)
            self._midi_notes_in.set_callback(self._on_notes_received)
            print(f"  ✓ Virtual port '{PORT_NOTES_IN}' created")
        except Exception as e:
            print(f"  ⚠ Notes input port failed: {e}")
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
                # Peak clip: ignore for 1s after connection or bank change
                if value >= 126 and time.time() > getattr(self, '_vu_ignore_until', 0):
                    state.tracks[abs_index].peak_clipped = True
        
        # ── Send enable feedback (CC 24-31) ──
        elif 24 <= cc_num <= 31:
            track_in_bank = cc_num - 24
            abs_index = state.bank_offset + track_in_bank
            if abs_index < len(state.tracks):
                send_idx = state.current_send
                state.tracks[abs_index].send_enabled[send_idx] = (value > 64)
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
            # Ignore during bypass viewer positioning
            if getattr(self, '_insert_positioning', False):
                return
            slot = message[3]
            name = ''.join(chr(b) for b in message[4:-1])
            state = self.state
            if slot < len(state.current_insert_names):
                if name:
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
                state.current_insert_active[slot] = not bypassed
                print(f"  Insert bypass slot {slot}: {'BYPASS' if bypassed else 'ACTIVE'}")
                self._leds_dirty = True
            return
        elif len(message) >= 4 and message[1] == 0x00 and message[2] == 0x18:
            # Send name : [F0 00 18 idx ...chars F7]
            idx = message[3]
            name = ''.join(chr(b) for b in message[4:-1])
            state = self.state
            if idx < 8:
                state.send_names[idx] = name
                if name:
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

    def send_note(self, note, velocity):
        """Send a Note On/Off message to Nuendo (Loop port)."""
        if self._midi_out and self._running:
            if velocity > 0:
                self._midi_out.send_message([0x90, note & 0x7F, velocity & 0x7F])
            else:
                self._midi_out.send_message([0x80, note & 0x7F, 0])

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

