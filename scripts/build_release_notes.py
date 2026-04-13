#!/usr/bin/env python3
"""Generate Release Notes PDF for Push 2 / Nuendo Bridge."""

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

ACCENT = HexColor('#00B4C8')
DARK_GRAY = HexColor('#666666')
MED_GRAY = HexColor('#CCCCCC')

styles = getSampleStyleSheet()
styles.add(ParagraphStyle('DocTitle', parent=styles['Title'],
    fontSize=24, leading=30, textColor=ACCENT, spaceAfter=6))
styles.add(ParagraphStyle('DocSub', parent=styles['Normal'],
    fontSize=12, leading=16, textColor=DARK_GRAY, spaceAfter=20, alignment=TA_CENTER))
styles.add(ParagraphStyle('VerTitle', parent=styles['Heading1'],
    fontSize=18, leading=22, textColor=ACCENT, spaceBefore=20, spaceAfter=8))
styles.add(ParagraphStyle('Section', parent=styles['Heading2'],
    fontSize=13, leading=17, textColor=HexColor('#333333'), spaceBefore=12, spaceAfter=6))
styles.add(ParagraphStyle('Body', parent=styles['Normal'],
    fontSize=10, leading=14, alignment=TA_JUSTIFY, spaceAfter=6))
styles.add(ParagraphStyle('BulletRN', parent=styles['Normal'],
    fontSize=10, leading=14, leftIndent=24, bulletIndent=12, spaceAfter=3))
styles.add(ParagraphStyle('Note', parent=styles['Normal'],
    fontSize=9, leading=13, textColor=DARK_GRAY, backColor=HexColor('#FFF8E1'),
    borderWidth=0.5, borderColor=HexColor('#FFD54F'), borderPadding=8,
    spaceAfter=10, leftIndent=12, rightIndent=12))

def B(text):
    return Paragraph(f"\u2022  {text}", styles['BulletRN'])

def add_footer(c, doc):
    c.saveState()
    c.setFont('Helvetica', 8)
    c.setFillColor(DARK_GRAY)
    c.drawCentredString(letter[0]/2, 0.5*inch, f"Push 2 / Nuendo Bridge — Release Notes — Page {doc.page}")
    c.restoreState()

def build():
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    docs_dir = os.path.join(project_dir, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    path = os.path.join(docs_dir, "Push2_Nuendo_Bridge_Release_Notes.pdf")
    doc = SimpleDocTemplate(path, pagesize=letter,
        topMargin=0.75*inch, bottomMargin=0.75*inch,
        leftMargin=0.8*inch, rightMargin=0.8*inch)
    s = []

    s.append(Spacer(1, 1*inch))
    s.append(Paragraph("Push 2 / Nuendo Bridge", styles['DocTitle']))
    s.append(Paragraph("Release Notes", styles['DocSub']))
    s.append(HRFlowable(width="50%", color=ACCENT, thickness=2, spaceAfter=30))

    # ═══════ v1.0.2 ═══════
    s.append(Paragraph("Version 1.0.2", styles['VerTitle']))
    s.append(Paragraph("April 2026", styles['Body']))

    s.append(Paragraph("New Features", styles['Section']))
    s.append(B("<b>Setup Page</b> (Setup button): configurable settings with tabbed interface"))
    s.append(B("<b>Aftertouch Mode</b>: choose Polyphonic, Channel, or Off from the Setup page"))
    s.append(B("<b>Velocity Curve</b>: 5 presets (Linear, Logarithmic, Exponential, S-Curve, Fixed) with visual graphs"))
    s.append(B("<b>Fixed Velocity</b>: adjustable value via encoder, synchronized with the Accent button"))
    s.append(B("<b>About Page</b>: displays Bridge version and JS Script version"))
    s.append(B("<b>MIDI CC Controller</b> (Shift+Note): 8 assignable CC faders with value bars, CC number editing, and on/off toggle"))
    s.append(B("<b>Mute/Solo/Monitor/Rec on Device and Inserts pages</b>: lower row buttons 5-8 toggle M/S/Mon/R on the selected track"))
    s.append(B("<b>Long press upper row in Inserts</b>: opens plugin UI without entering parameters mode (0.5s)"))
    s.append(B("<b>Double press upper row in Mix mode</b>: opens Edit Channel Settings for the corresponding track"))
    s.append(B("<b>Clear Monitor / Clear Rec</b> (Shift+Mute/Solo in Mon/Rec mode): clears all monitors or rec arms across all tracks"))

    s.append(Paragraph("Bug Fixes", styles['Section']))
    s.append(B("Volume bar 0 dB marker replaced with color change (turquoise to red above 0 dB)"))
    s.append(B("Peak clip false triggers at startup: 10-second grace period after connection"))
    s.append(B("Peak clip false triggers on mode change: 3-second grace period"))
    s.append(B("Peak clip false triggers during Send adjustment: requires 2 consecutive max VU readings"))
    s.append(B("Send 1 CC conflict resolved: sends moved to MIDI channel 7"))
    s.append(B("Control Room CC conflict resolved: CR knobs moved to MIDI channel 6"))
    s.append(B("Pan asymmetry corrected: left = 64 steps, right = 63 steps, center = CC 64"))
    s.append(B("Fallback MIDI port names updated for cross-system compatibility"))
    s.append(B("All French comments translated to English"))

    s.append(Paragraph("Technical", styles['Section']))
    s.append(B("JS Script version sent to Bridge via SysEx 0x10 at startup"))
    s.append(B("Centralized version constant (BRIDGE_VERSION) in state.py"))
    s.append(B("DirectAccess API 1.2+ detection (reserved for future features)"))

    # ═══════ v1.0.1 ═══════
    s.append(Spacer(1, 20))
    s.append(HRFlowable(width="100%", color=MED_GRAY, thickness=0.5, spaceAfter=10))
    s.append(Paragraph("Version 1.0.1", styles['VerTitle']))
    s.append(Paragraph("March 2026", styles['Body']))

    s.append(Paragraph("Bug Fixes", styles['Section']))
    s.append(B("Volume stutter fix: reverted to <b>track.volume</b> for bar graphic"))
    s.append(B("Peak clip at startup: added initial grace period for VU meters"))
    s.append(B("Send 1 CC conflict with volume CC range"))
    s.append(B("CR knob CC conflict with mixer CC range"))
    s.append(B("Pan offset: asymmetric L/R conversion for accurate center"))
    s.append(B("Windows log path documented"))
    s.append(B("Fallback port names for systems without IAC"))

    # ═══════ v1.0.0 ═══════
    s.append(Spacer(1, 20))
    s.append(HRFlowable(width="100%", color=MED_GRAY, thickness=0.5, spaceAfter=10))
    s.append(Paragraph("Version 1.0.0", styles['VerTitle']))
    s.append(Paragraph("February 2026 — Initial Release", styles['Body']))

    s.append(Paragraph("Features", styles['Section']))
    s.append(B("<b>Mixer Modes</b>: Volume, Pan, Track (combined Vol+Pan+Sends)"))
    s.append(B("<b>Sends Mode</b>: 8 sends per track with level, on/off, pre/post control"))
    s.append(B("<b>Device Mode</b>: 8 Quick Controls per track"))
    s.append(B("<b>Inserts Mode</b>: browse 8 insert slots, edit parameters, bypass, open plugin UI"))
    s.append(B("<b>Transport</b>: Play, Stop, Record, Cycle/Loop, Metronome, Undo"))
    s.append(B("<b>Automation</b>: cycle through Off/Read/Write modes"))
    s.append(B("<b>Control Room</b>: 4 pages (Main, Phones, Cues, Sources) with full knob control"))
    s.append(B("<b>Note Input</b>: chromatic and drum pad modes, scale selection, Note Repeat"))
    s.append(B("<b>Touchstrip</b>: Pitch Bend, Mod Wheel, or Volume mode"))
    s.append(B("<b>Track Management</b>: Add Track, Duplicate, New Track Version, Delete"))
    s.append(B("<b>VU Meters</b> with peak clip indicators"))
    s.append(B("<b>Push 2 Display</b>: full 960x160 pixel rendering with track colors"))
    s.append(B("<b>macOS Menu Bar App</b> with Start at Login, Show Logs"))
    s.append(B("<b>Virtual MIDI Ports</b>: auto-created IAC ports (NuendoBridge In/Out, BridgeNotes)"))

    s.append(Paragraph("Architecture", styles['Section']))
    s.append(B("Python bridge (push2-python, python-rtmidi, Pillow, numpy, rumps)"))
    s.append(B("Steinberg MIDI Remote API JavaScript script"))
    s.append(B("7-channel MIDI allocation scheme to avoid CC conflicts"))
    s.append(B("GPL-3.0 license with Developer Certificate of Origin (DCO)"))

    doc.build(s, onFirstPage=add_footer, onLaterPages=add_footer)
    print(f"PDF generated: {path}")

if __name__ == "__main__":
    build()
