"""
chords.py — Name the chord formed by a set of held MIDI notes

Used by the renderer to show the chord currently played on the pads.
Pure functions, no dependency on the rest of the bridge.
"""

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
NOTE_NAMES_FLAT = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]

_MAJOR = (0, 2, 4, 5, 7, 9, 11)
_FLAT_MAJOR_KEYS = {5, 10, 3, 8, 1}        # F, Bb, Eb, Ab, Db
_SHARP_MAJOR_KEYS = {7, 2, 9, 4, 11, 6}    # G, D, A, E, B, F#


def scale_prefers_flats(root, intervals):
    """Should accidentals be spelled as flats in this scale?

    Returns True / False, or None when the scale doesn't decide: no scale
    (Piano layout), symmetric scales (Chromatic, Whole Tone, Octatonic), or a
    key without accidentals (C major and its modes)."""
    ivs = sorted(set(i % 12 for i in intervals))
    # No scale, 8+ notes (Octatonic, Spanish, Chromatic) or Whole Tone
    if len(ivs) < 5 or len(ivs) > 7 or ivs == [0, 2, 4, 6, 8, 10]:
        return None
    pcs = set((root + i) % 12 for i in ivs)
    tonic = None
    # A mode of the major scale → its parent major key
    for t in range(12):
        if pcs == set((t + m) % 12 for m in _MAJOR):
            tonic = t
            break
    if tonic is None:
        # Other scales: judge by their quality relative to the root
        if 3 in ivs and 4 not in ivs:
            tonic = (root + 3) % 12   # minor-type → relative major
        else:
            tonic = root % 12         # major-type
    if tonic in _FLAT_MAJOR_KEYS:
        return True
    if tonic in _SHARP_MAJOR_KEYS:
        return False
    return None


# (suffix, intervals from the root). Order = priority when several templates
# could match from the same root (never happens for exact matches, but keeps
# the table readable: triads, then sixths/sevenths, then extensions, then
# shell voicings without the fifth).
_CHORDS = [
    ("",       (0, 4, 7)),
    ("m",      (0, 3, 7)),
    ("dim",    (0, 3, 6)),
    ("aug",    (0, 4, 8)),
    ("sus2",   (0, 2, 7)),
    ("sus4",   (0, 5, 7)),
    ("5",      (0, 7)),
    ("6",      (0, 4, 7, 9)),
    ("m6",     (0, 3, 7, 9)),
    ("7",      (0, 4, 7, 10)),
    ("maj7",   (0, 4, 7, 11)),
    ("m7",     (0, 3, 7, 10)),
    ("mMaj7",  (0, 3, 7, 11)),
    ("m7b5",   (0, 3, 6, 10)),
    ("dim7",   (0, 3, 6, 9)),
    ("aug7",   (0, 4, 8, 10)),
    ("7sus4",  (0, 5, 7, 10)),
    ("add9",   (0, 2, 4, 7)),
    ("m(add9)", (0, 2, 3, 7)),
    ("6/9",    (0, 2, 4, 7, 9)),
    ("9",      (0, 2, 4, 7, 10)),
    ("maj9",   (0, 2, 4, 7, 11)),
    ("m9",     (0, 2, 3, 7, 10)),
    ("7b9",    (0, 1, 4, 7, 10)),
    ("7#9",    (0, 3, 4, 7, 10)),
    ("11",     (0, 2, 4, 5, 7, 10)),
    ("m11",    (0, 2, 3, 5, 7, 10)),
    ("13",     (0, 2, 4, 7, 9, 10)),
    # Shell voicings (fifth omitted)
    ("7",      (0, 4, 10)),
    ("maj7",   (0, 4, 11)),
    ("m7",     (0, 3, 10)),
    ("9",      (0, 2, 4, 10)),
    ("maj9",   (0, 2, 4, 11)),
    ("m9",     (0, 2, 3, 10)),
]
_BY_INTERVALS = {}
for _suffix, _ivs in _CHORDS:
    _BY_INTERVALS.setdefault(frozenset(_ivs), _suffix)


def chord_name(notes, flats=False):
    """Return the name of the chord formed by `notes` (iterable of MIDI note
    numbers), or "" if fewer than two pitch classes are held or nothing matches.
    flats=True spells accidentals as flats (Bb) instead of sharps (A#).

    The lowest note is tried as the root first, so C-E-G-A reads "C6" while
    A-C-E-G reads "Am7". Otherwise the chord is reported as an inversion /
    slash chord ("C/E")."""
    notes = sorted(set(n for n in notes if 0 <= n <= 127))
    if not notes:
        return ""
    pcs = set(n % 12 for n in notes)
    if len(pcs) < 2:
        return ""
    bass = notes[0] % 12
    # Bass as root, then the other pitch classes in ascending order above it
    for root in [bass] + sorted(pcs - {bass}, key=lambda p: (p - bass) % 12):
        suffix = _BY_INTERVALS.get(frozenset((p - root) % 12 for p in pcs))
        if suffix is None:
            continue
        names = NOTE_NAMES_FLAT if flats else NOTE_NAMES
        name = names[root] + suffix
        if root != bass:
            name += "/" + names[bass]
        return name
    return ""
