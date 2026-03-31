"""
repeat.py — Note Repeat mode for the Push 2

When enabled, held notes are repeated according to a configurable
subdivision and tempo. The tempo changes in real time, and the
velocity is updated on each repeat via aftertouch.
"""

import time
import threading


SUBDIVISIONS = {
    '1/4':   1.0,
    '1/4t':  2.0 / 3.0,
    '1/8':   0.5,
    '1/8t':  1.0 / 3.0,
    '1/16':  0.25,
    '1/16t': 1.0 / 6.0,
    '1/32':  0.125,
    '1/32t': 1.0 / 12.0,
}

SUBDIV_NAMES = ['1/4', '1/4t', '1/8', '1/8t', '1/16', '1/16t', '1/32', '1/32t']


class NoteRepeat:
    def __init__(self):
        self.enabled = False
        self.tempo = 120.0
        self.subdivision_index = 4  # 1/16
        self._active_notes = {}
        self._lock = threading.Lock()
    
    @property
    def subdivision_name(self):
        return SUBDIV_NAMES[self.subdivision_index]
    
    @property
    def interval_seconds(self):
        beat_duration = 60.0 / self.tempo
        fraction = SUBDIVISIONS[self.subdivision_name]
        return beat_duration * fraction
    
    def set_subdivision(self, index):
        if 0 <= index <= 7:
            self.subdivision_index = index
    
    def update_velocity(self, note, velocity):
        """Updates the velocity of an active note (via aftertouch)."""
        with self._lock:
            if note in self._active_notes:
                self._active_notes[note]['velocity'] = velocity
    
    def note_on(self, note, velocity, send_note_on, send_note_off):
        with self._lock:
            if note in self._active_notes:
                self._active_notes[note]['stop'] = True
            
            if not self.enabled:
                return
            
            state = {'stop': False, 'velocity': velocity}
            self._active_notes[note] = state
            
            def _repeat_loop():
                TICK = 0.005
                while not state['stop']:
                    interval = self.interval_seconds
                    on_time = interval * 0.8
                    off_time = interval * 0.2
                    
                    elapsed = 0.0
                    while elapsed < on_time and not state['stop']:
                        time.sleep(TICK)
                        elapsed += TICK
                    
                    if state['stop']:
                        break
                    send_note_off(note)
                    
                    elapsed = 0.0
                    while elapsed < off_time and not state['stop']:
                        time.sleep(TICK)
                        elapsed += TICK
                    
                    if state['stop']:
                        break
                    send_note_on(note, state['velocity'])
            
            threading.Thread(target=_repeat_loop, daemon=True).start()
    
    def note_off(self, note, send_note_off):
        with self._lock:
            if note in self._active_notes:
                self._active_notes[note]['stop'] = True
                del self._active_notes[note]
    
    def stop_all(self, send_note_off):
        with self._lock:
            for note, s in self._active_notes.items():
                s['stop'] = True
                send_note_off(note)
            self._active_notes.clear()
