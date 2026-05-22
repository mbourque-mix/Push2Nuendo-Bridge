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
    "Octatonic WH":     [0, 2, 3, 5, 6, 8, 9, 11],   # whole-half diminished
    "Octatonic HW":     [0, 1, 3, 4, 6, 7, 9, 10],   # half-whole diminished
    "Chromatic":        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
    "Piano":            [],  # Special: piano-style 4-octave layout, see _update_piano_note_map
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
PAD_PURPLE     = 116  # Purple (root in chromatic mode, all C's in piano mode)
PAD_ORANGE     = 9    # Orange/amber (keyswitch pads) — palette index, tune on hardware

# Natural notes (no accidentals) = indices in the chromatic scale
NATURAL_NOTES = {0, 2, 4, 5, 7, 9, 11}  # C, D, E, F, G, A, B

# ─────────────────────────────────────────────
# Note Input layouts (cycled by the Layout button)
# ─────────────────────────────────────────────
LAYOUT_64    = "64"     # 64 playable pads (current default)
LAYOUT_KS8   = "ks8"    # 56 playable pads + 8 keyswitches (bottom row)
LAYOUT_KS16  = "ks16"   # 48 playable pads + 16 keyswitches (bottom two rows)
LAYOUT_DRUM  = "drum"   # 4x4 drum layout
LAYOUT_CYCLE = [LAYOUT_64, LAYOUT_KS8, LAYOUT_KS16, LAYOUT_DRUM]

# Keyswitch note-assignment modes
KS_CHROMATIC = "chromatic"   # consecutive semitones
KS_NATURALS  = "naturals"    # consecutive natural (white-key) notes


def midi_note_name(note):
    """MIDI note number -> name using the Cubase/Nuendo convention (C-2 = 0)."""
    if note is None or note < 0:
        return "--"
    note = max(0, min(127, int(note)))
    return f"{NOTE_NAMES[note % 12]}{note // 12 - 2}"


class PadGrid:
    """Manages pad mapping, colors, and Scale mode."""
    
    def __init__(self):
        self.root_note = 0       # 0 = C, 1 = C#, etc.
        self.scale_index = 0     # Index in SCALE_NAMES
        self.octave = 3          # Starting octave (3 = C3 = MIDI 48)
        self.scale_mode = False  # True = scale selection screen
        self.note_layout = LAYOUT_64  # 64 / ks8 / ks16 / drum
        self.drum_base_note = 36 # Base MIDI note for drums (C1 = GM kick)

        # ── Keyswitch config (shared between ks8 and ks16) ──
        self.ks_start_note = 0           # MIDI note of keyswitch #1 (0 = C-2 in Cubase)
        self.ks_mode = KS_CHROMATIC      # KS_CHROMATIC or KS_NATURALS
        self.ks_overrides = {}           # {ks_index: midi_note} manual per-pad overrides
        self.ks_edit = False             # True = keyswitch config screen is open
        self.ks_edit_page = 0            # 0 = pads 1-8, 1 = pads 9-16 (ks16 only)
        self.ks_latch = False            # True = keyswitch pads latch (hold until re-selected)
        self.ks_latched_index = None     # currently latched KS index (when ks_latch), or None
        
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

    # ── Layout helpers ──

    @property
    def drum_mode(self):
        """Backward-compat: True when the drum layout is active."""
        return self.note_layout == LAYOUT_DRUM

    @drum_mode.setter
    def drum_mode(self, value):
        self.note_layout = LAYOUT_DRUM if value else LAYOUT_64

    @property
    def is_keyswitch_layout(self):
        return self.note_layout in (LAYOUT_KS8, LAYOUT_KS16)

    def ks_count(self):
        """Number of keyswitch pads in the active layout (0, 8 or 16)."""
        if self.note_layout == LAYOUT_KS8:
            return 8
        if self.note_layout == LAYOUT_KS16:
            return 16
        return 0

    def cycle_layout(self):
        """Advance the Layout button: 64 -> ks8 -> ks16 -> drum -> 64."""
        idx = LAYOUT_CYCLE.index(self.note_layout) if self.note_layout in LAYOUT_CYCLE else 0
        self.note_layout = LAYOUT_CYCLE[(idx + 1) % len(LAYOUT_CYCLE)]
        if not self.is_keyswitch_layout:
            self.ks_edit = False
        self._update_note_map()

    @staticmethod
    def _ks_pad_position(ks_index):
        """Keyswitch index (0..15) -> (row, col) in note_map convention.

        Bottom physical row first (note_map row 7), then the row above (row 6),
        left-to-right.
        """
        row = 7 - (ks_index // 8)
        col = ks_index % 8
        return row, col

    def _ks_index_for_pad(self, row, col):
        """(row, col) -> keyswitch index, or None if the pad is not a keyswitch."""
        count = self.ks_count()
        if count >= 8 and row == 7:
            return col
        if count == 16 and row == 6:
            return 8 + col
        return None

    @staticmethod
    def _next_natural(note):
        """Smallest natural (white-key) MIDI note strictly above ``note``."""
        m = note + 1
        while m < 127 and (m % 12) not in NATURAL_NOTES:
            m += 1
        return min(127, m)

    def _ks_auto_sequence(self, count):
        """Generate the auto keyswitch notes from ks_start_note + ks_mode."""
        seq = []
        cur = max(0, min(127, self.ks_start_note))
        for i in range(count):
            if i == 0:
                seq.append(cur)
            else:
                cur = self._next_natural(cur) if self.ks_mode == KS_NATURALS else min(127, cur + 1)
                seq.append(cur)
        return seq

    def ks_effective_notes(self):
        """Keyswitch notes actually mapped to pads (auto sequence + overrides)."""
        count = self.ks_count()
        seq = self._ks_auto_sequence(count)
        for i, n in self.ks_overrides.items():
            if 0 <= i < count:
                seq[i] = max(0, min(127, n))
        return seq

    # ── Keyswitch config mutators ──

    def set_ks_start(self, note):
        """Set the first keyswitch note; regenerates the sequence (clears overrides)."""
        self.ks_start_note = max(0, min(127, note))
        self.ks_overrides = {}
        self._update_note_map()

    def set_ks_mode(self, mode):
        """Set chromatic/naturals; regenerates the sequence (clears overrides)."""
        if mode in (KS_CHROMATIC, KS_NATURALS):
            self.ks_mode = mode
            self.ks_overrides = {}
            self._update_note_map()

    def set_ks_override(self, ks_index, note):
        """Manually override one keyswitch pad's note."""
        self.ks_overrides[ks_index] = max(0, min(127, note))
        self._update_note_map()

    def reset_ks(self):
        """Drop all manual overrides (back to the pure auto sequence)."""
        self.ks_overrides = {}
        self._update_note_map()

    def toggle_ks_latch(self):
        """Toggle keyswitch latch mode. Returns the new state."""
        self.ks_latch = not self.ks_latch
        if not self.ks_latch:
            self.ks_latched_index = None
        return self.ks_latch
    
    def _update_note_map(self):
        """Recomputes the pad-to-MIDI-note mapping."""
        if self.note_layout == LAYOUT_DRUM:
            self._update_drum_note_map()
            return
        # Playable zone: same mapping as the 64-pad layout for the active scale.
        if self.scale_name == "Piano":
            self._update_piano_note_map()
        else:
            self._update_scale_note_map()
        # Keyswitch layouts overwrite the bottom row(s) with absolute KS notes.
        if self.is_keyswitch_layout:
            self._overlay_keyswitches()

    def _update_scale_note_map(self):
        """Fill note_map for all 8 rows using the active scale (the 64-pad layout)."""
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

    def _overlay_keyswitches(self):
        """Overwrite the bottom KS row(s) with the configured keyswitch notes.

        Keyswitch notes are absolute (independent of the octave), so they are
        unaffected by Octave Up/Down — only the playable zone shifts.
        """
        for i, note in enumerate(self.ks_effective_notes()):
            row, col = self._ks_pad_position(i)
            self.note_map[row][col] = max(0, min(127, note))
    
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
    
    def _update_piano_note_map(self):
        """Piano-style layout: 4 octaves stacked vertically.
        
        Each octave occupies 2 rows of pads on the Push 2 hardware:
          - Bottom of each pair (lower on the physical pad grid): white keys
              C  D  E  F  G  A  B  C(next)
          - Top of each pair    (higher on the physical pad grid): black keys
              C# D# X  F# G# A# X  C#(next)
        
        The lowest octave is at the bottom of the pad grid, the highest at the top —
        bottom-left pad plays the lowest C, top-right plays the highest C# of the
        topmost pair, like looking down at a piano keyboard.
        
        Note: by codebase convention (see push2_controller._update_pad_colors),
        note_map[0] is the TOP physical row of the Push 2 and note_map[7] is the
        BOTTOM. inverted_row mirrors what the other scales do so the layout reads
        correctly on the hardware.
        
        The root note is fixed at C — set_root() is a no-op while this scale is active.
        The C# at col 7 of each black row sits above the C at col 7 of the white row
        and shares its MIDI note with col 0 of the black row of the next pair above.
        Each octave_up / octave_down shifts the whole 4-octave block by 12 semitones.
        max self.octave = 6 keeps the highest note within the 0–127 MIDI range.
        """
        # Semitone offsets from the base C of each octave-pair
        # White row (cols 0-7): C, D, E, F, G, A, B, C(next octave)
        white_offsets = [0, 2, 4, 5, 7, 9, 11, 12]
        # Black row (cols 0-7): C#, D#, off, F#, G#, A#, off, C#(next octave)
        # Note: black_offsets[7] = 13 plays the same note as black_offsets[0] of the
        # next pair-of-rows above, mirroring the octave-boundary overlap of the white row.
        black_offsets = [1, 3, -1, 6, 8, 10, -1, 13]
        
        base_c = self.octave * 12  # MIDI value of the bottom-most C
        
        for row in range(8):
            inverted_row = 7 - row              # row 7 (bottom of hardware) → 0 (lowest pair)
            pair_index = inverted_row // 2      # 0..3 — which octave pair this row belongs to
            is_white_row = (inverted_row % 2 == 0)  # bottom of each pair is white
            pair_base_c = base_c + pair_index * 12
            
            for col in range(8):
                offset = white_offsets[col] if is_white_row else black_offsets[col]
                if offset < 0:
                    self.note_map[row][col] = -1  # silent pad
                else:
                    self.note_map[row][col] = max(0, min(127, pair_base_c + offset))
    
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
        # Keyswitch pads (bottom row(s) in ks8/ks16): orange, or green when latched-active.
        if self.is_keyswitch_layout:
            ksi = self._ks_index_for_pad(row, col)
            if ksi is not None:
                if self.ks_latch and self.ks_latched_index == ksi:
                    return PAD_GREEN
                return PAD_ORANGE
        if self.drum_mode:
            if self.note_map[row][col] < 0:
                return PAD_OFF
            # C1 (note 36) in blue as a reference marker
            if self.note_map[row][col] == 36:
                return PAD_BLUE
            return PAD_WHITE
        # Piano mode: every C in purple, other notes in white, X pads off
        if self.scale_name == "Piano":
            note = self.note_map[row][col]
            if note < 0:
                return PAD_OFF
            if (note % 12) == 0:  # any C across all octaves
                return PAD_PURPLE
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

    def note_range_label(self):
        """Lowest-highest PLAYABLE note as a short label, e.g. 'C1-G5'.

        Ignores inactive pads (note -1) and, in keyswitch layouts, the
        keyswitch pads (whose absolute notes would skew the range).
        Returns '' if no playable pad.
        """
        ks = self.is_keyswitch_layout
        notes = []
        for r in range(8):
            for c in range(8):
                if ks and self._ks_index_for_pad(r, c) is not None:
                    continue  # skip keyswitch pads
                n = self.note_map[r][c]
                if n >= 0:
                    notes.append(n)
        if not notes:
            return ""
        return f"{midi_note_name(min(notes))}-{midi_note_name(max(notes))}"
    
    def midi_note_to_pad(self, midi_note):
        """Converts a Push 2 pad MIDI note (36-99) to (row, col) in note_map convention.
        
        By codebase convention (see push2_controller._update_pad_colors and the
        inverted_row pattern used throughout this module), note_map row 0 is the
        TOP physical row of the Push 2 and row 7 is the BOTTOM.
        Push 2 hardware sends:
          - notes 36-43 from the BOTTOM physical row → (row=7, col=0..7)
          - notes 92-99 from the TOP physical row    → (row=0, col=0..7)
        """
        if midi_note < 36 or midi_note > 99:
            return None, None
        row = 7 - ((midi_note - 36) // 8)
        col = (midi_note - 36) % 8
        return row, col
    
    def set_root(self, root):
        """Changes the root note (0-11). Locked in Piano mode."""
        if self.scale_name == "Piano":
            return  # Piano layout is rooted at C — root is not user-selectable
        self.root_note = root % 12
        self._update_note_map()
    
    def set_scale(self, index):
        """Changes the scale by index."""
        self.scale_index = index % len(SCALE_NAMES)
        if self.scale_name == "Piano":
            self.root_note = 0  # Force C when entering Piano mode
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
            # Piano spans 4 octaves, so cap at 6 to keep the top note within MIDI range
            max_oct = 6 if self.scale_name == "Piano" else 8
            if self.octave < max_oct:
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
