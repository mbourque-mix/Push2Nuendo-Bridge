"""
pad_grid.py — Push 2 pad grid management for MIDI playing

The Push 2 has an 8x8 pad grid (64 pads).
Pads send Note On/Off on notes 36-99.
  - Bottom row (closest to the user): notes 36-43
  - Top row: notes 92-99

This module manages:
- Pad-to-MIDI-note mapping according to a scale
- Pad colors (white = scale note, blue = root note, green = pressed)
- Scale mode for choosing the scale and root note
"""

# ─────────────────────────────────────────────
# Scales (intervals in semitones from the root note)
# ─────────────────────────────────────────────

SCALES = {
    "Major":            [0, 2, 4, 5, 7, 9, 11],
    "Minor":            [0, 2, 3, 5, 7, 8, 10],
    "Dorian":           [0, 2, 3, 5, 7, 9, 10],
    "Mixolydian":       [0, 2, 4, 5, 7, 9, 10],
    "Lydian":           [0, 2, 4, 6, 7, 9, 11],
    "Phrygian":         [0, 1, 3, 5, 7, 8, 10],
    "Locrian":          [0, 1, 3, 5, 6, 8, 10],
    "Harmonic Minor":   [0, 2, 3, 5, 7, 8, 11],
    "Melodic Minor":    [0, 2, 3, 5, 7, 9, 11],
    "Minor Pentatonic": [0, 3, 5, 7, 10],
    "Major Pentatonic": [0, 2, 4, 7, 9],
    "Minor Blues":      [0, 3, 5, 6, 7, 10],
    "Whole Tone":       [0, 2, 4, 6, 8, 10],
    "Chromatic":        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
    "Hungarian Minor":  [0, 2, 3, 6, 7, 8, 11],
    "Spanish":          [0, 1, 3, 4, 5, 6, 8, 10],
}

SCALE_NAMES = list(SCALES.keys())

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Push 2 pad colors (palette index)
PAD_OFF        = 0    # Off
PAD_WHITE      = 122  # White
PAD_WHITE_DIM  = 124  # Dim white
PAD_BLUE       = 45   # Blue (root note)
PAD_GREEN      = 21   # Green (pressed pad)
PAD_CYAN       = 37   # Cyan
PAD_BLACK      = 117  # Black/dark grey (chromatic alterations)
PAD_PURPLE     = 116  # Purple (root in chromatic mode)

# Natural notes (no accidentals) = indices in the chromatic scale
NATURAL_NOTES = {0, 2, 4, 5, 7, 9, 11}  # C, D, E, F, G, A, B


class PadGrid:
    """Manages pad mapping, colors, and Scale mode."""
    
    def __init__(self):
        self.root_note = 0       # 0 = C, 1 = C#, etc.
        self.scale_index = 0     # Index in SCALE_NAMES
        self.octave = 3          # Starting octave (3 = C3 = MIDI 48)
        self.scale_mode = False  # True = scale selection screen
        self.drum_mode = False   # True = 4x4 drum layout
        self.drum_base_note = 36 # Base MIDI note for drums (C1 = GM kick)
        
        # Pad state (True = pressed)
        self.pad_pressed = [[False] * 8 for _ in range(8)]
        
        # MIDI note for each pad (computed by _update_note_map)
        self.note_map = [[0] * 8 for _ in range(8)]
        
        # Recompute
        self._update_note_map()
    
    @property
    def scale_name(self):
        return SCALE_NAMES[self.scale_index]
    
    @property
    def scale_intervals(self):
        return SCALES[self.scale_name]
    
    @property
    def root_note_name(self):
        return NOTE_NAMES[self.root_note]
    
    def _update_note_map(self):
        """Recomputes the pad-to-MIDI-note mapping."""
        if self.drum_mode:
            self._update_drum_note_map()
            return
        
        intervals = self.scale_intervals
        num_notes = len(intervals)
        base_note = self.root_note + self.octave * 12
        
        for row in range(8):
            for col in range(8):
                inverted_row = 7 - row
                note_in_scale = col + inverted_row * 3
                
                scale_octave = note_in_scale // num_notes
                scale_degree = note_in_scale % num_notes
                
                midi_note = base_note + scale_octave * 12 + intervals[scale_degree]
                self.note_map[row][col] = max(0, min(127, midi_note))
    
    def _update_drum_note_map(self):
        """4x4 mapping for drum mode (pads in the bottom-left)."""
        # 4x4 pads in the bottom-left (rows 4-7, cols 0-3 in push2 convention)
        # GM layout: kick, snare, etc. starting from drum_base_note
        for row in range(8):
            for col in range(8):
                if row >= 4 and col < 4:
                    # Drum zone: 4x4 bottom-left
                    drum_row = 7 - row  # Inverted (bottom = row 7 = drum row 0)
                    drum_idx = drum_row * 4 + col
                    self.note_map[row][col] = max(0, min(127, self.drum_base_note + drum_idx))
                else:
                    # Outside drum zone: off (note -1 = no sound)
                    self.note_map[row][col] = -1
    
    def is_root_note(self, row, col):
        """Checks whether the pad corresponds to the root note."""
        note = self.note_map[row][col]
        if note < 0:
            return False
        return (note % 12) == self.root_note
    
    def get_pad_color(self, row, col):
        """Returns the pad color."""
        if self.pad_pressed[row][col]:
            return PAD_GREEN
        if self.drum_mode:
            if self.note_map[row][col] < 0:
                return PAD_OFF
            # C1 (note 36) in blue as a reference marker
            if self.note_map[row][col] == 36:
                return PAD_BLUE
            return PAD_WHITE
        # Chromatic mode: white=natural, black=accidental, purple=root
        if self.scale_name == "Chromatic":
            note = self.note_map[row][col]
            if note < 0:
                return PAD_OFF
            note_class = note % 12
            if note_class == self.root_note:
                return PAD_PURPLE
            if note_class in NATURAL_NOTES:
                return PAD_WHITE
            return PAD_BLACK
        if self.is_root_note(row, col):
            return PAD_BLUE
        return PAD_WHITE
    
    def get_all_pad_colors(self):
        """Returns an 8x8 array of colors."""
        colors = []
        for row in range(8):
            row_colors = []
            for col in range(8):
                row_colors.append(self.get_pad_color(row, col))
            colors.append(row_colors)
        return colors
    
    def pad_to_note(self, row, col):
        """Converts a pad position to a MIDI note."""
        return self.note_map[row][col]
    
    def midi_note_to_pad(self, midi_note):
        """Converts a Push MIDI note number (36-99) to (row, col)."""
        if midi_note < 36 or midi_note > 99:
            return None, None
        # Push 2 notes:
        # Row 0 (bottom) = notes 36-43
        # Row 7 (top)    = notes 92-99
        row = (midi_note - 36) // 8
        col = (midi_note - 36) % 8
        return row, col
    
    def set_root(self, root):
        """Changes the root note (0-11)."""
        self.root_note = root % 12
        self._update_note_map()
    
    def set_scale(self, index):
        """Changes the scale by index."""
        self.scale_index = index % len(SCALE_NAMES)
        self._update_note_map()
    
    def next_scale(self):
        self.set_scale(self.scale_index + 1)
    
    def prev_scale(self):
        self.set_scale(self.scale_index - 1)
    
    def next_root(self):
        self.set_root(self.root_note + 1)
    
    def prev_root(self):
        self.set_root(self.root_note - 1)
    
    def octave_up(self):
        if self.drum_mode:
            if self.drum_base_note + 16 <= 112:
                self.drum_base_note += 16
                self._update_note_map()
        else:
            if self.octave < 8:
                self.octave += 1
                self._update_note_map()
    
    def octave_down(self):
        if self.drum_mode:
            if self.drum_base_note - 16 >= 0:
                self.drum_base_note -= 16
                self._update_note_map()
        else:
            if self.octave > 0:
                self.octave -= 1
                self._update_note_map()
