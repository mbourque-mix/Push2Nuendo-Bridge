"""
coremidi_ids.py — Stable CoreMIDI unique IDs for the bridge's virtual ports (macOS)

WHY:
CoreMIDI gives every virtual endpoint a new random kMIDIPropertyUniqueID each
time it is created. Nuendo/Cubase identify MIDI ports by that ID (see
"Port Setup.xml": ID = "I|MIDI System|<uniqueID>"), not by name. So on every
bridge launch Nuendo saw four brand-new ports and reset their settings to the
defaults — in particular "In 'All MIDI Inputs'" was re-checked for
"NuendoBridge Out", leaking the bridge's control CCs into MIDI tracks.

Pinning the unique ID makes Nuendo recognise the ports from one session to the
next, so the user's MIDI Port Setup choices stick.

No-op on other platforms (Windows uses loopMIDI ports, which are persistent).
"""

import sys
import zlib

_STATUS_ID_NOT_UNIQUE = -10843  # kMIDIIDNotUnique
_UTF8 = 0x08000100              # kCFStringEncodingUTF8


def stable_unique_id(port_name):
    """Deterministic, positive, non-zero SInt32 derived from the port name."""
    uid = zlib.crc32(("Push2NuendoBridge:" + port_name).encode("utf-8")) & 0x7FFFFFFF
    return uid or 1


def pin_unique_id(port_name, is_source):
    """
    Give our virtual endpoint named `port_name` a stable unique ID.

    is_source=True  → port created with rtmidi.MidiOut (a CoreMIDI source)
    is_source=False → port created with rtmidi.MidiIn  (a CoreMIDI destination)

    Returns True if the endpoint now carries the stable ID. Never raises.
    """
    if sys.platform != "darwin":
        return False
    try:
        import ctypes
        from ctypes import c_int32, c_uint32, c_ulong, c_void_p, c_char_p, byref

        cm = ctypes.CDLL("/System/Library/Frameworks/CoreMIDI.framework/CoreMIDI")
        cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")

        count_fn = cm.MIDIGetNumberOfSources if is_source else cm.MIDIGetNumberOfDestinations
        get_fn = cm.MIDIGetSource if is_source else cm.MIDIGetDestination
        count_fn.restype = c_ulong
        get_fn.restype = c_uint32
        get_fn.argtypes = [c_ulong]
        cm.MIDIObjectGetStringProperty.argtypes = [c_uint32, c_void_p, ctypes.POINTER(c_void_p)]
        cm.MIDIObjectGetIntegerProperty.argtypes = [c_uint32, c_void_p, ctypes.POINTER(c_int32)]
        cm.MIDIObjectSetIntegerProperty.argtypes = [c_uint32, c_void_p, c_int32]
        cf.CFStringGetCString.argtypes = [c_void_p, c_char_p, ctypes.c_long, c_uint32]
        cf.CFRelease.argtypes = [c_void_p]

        prop_name = c_void_p.in_dll(cm, "kMIDIPropertyName")
        prop_uid = c_void_p.in_dll(cm, "kMIDIPropertyUniqueID")
        wanted = stable_unique_id(port_name)

        for i in range(count_fn()):
            endpoint = get_fn(i)
            if not endpoint:
                continue
            cf_name = c_void_p()
            if cm.MIDIObjectGetStringProperty(endpoint, prop_name, byref(cf_name)) != 0:
                continue
            buf = ctypes.create_string_buffer(256)
            ok = cf.CFStringGetCString(cf_name, buf, len(buf), _UTF8)
            cf.CFRelease(cf_name)
            if not ok or buf.value.decode("utf-8", "replace") != port_name:
                continue

            current = c_int32()
            cm.MIDIObjectGetIntegerProperty(endpoint, prop_uid, byref(current))
            if current.value == wanted:
                return True
            # Fails for endpoints owned by another process (e.g. an IAC port
            # with the same name) — keep looking for our own.
            status = cm.MIDIObjectSetIntegerProperty(endpoint, prop_uid, wanted)
            if status == 0:
                return True
            if status == _STATUS_ID_NOT_UNIQUE:
                print(f"  ⚠ Stable MIDI ID for '{port_name}' already in use "
                      f"(another bridge instance running?)")
                return False
        return False
    except Exception as e:
        print(f"  ⚠ Could not pin MIDI ID for '{port_name}': {e}")
        return False
