#!/usr/bin/env python3
"""Generate PDF documents for Push2Nuendo-Bridge v1.0.5

Usage: python scripts/generate_docs.py
Output: docs/*.pdf
"""

import os

# Resolve paths relative to this script
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(_SCRIPT_DIR)
_DOCS_DIR = os.path.join(_PROJECT_DIR, "docs")
os.makedirs(_DOCS_DIR, exist_ok=True)

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Table, TableStyle
)
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

DARK = HexColor('#1a1a2e')
GREY = HexColor('#555555')
LIGHT = HexColor('#888888')
styles = getSampleStyleSheet()

sTitle = ParagraphStyle('T', parent=styles['Title'], fontSize=22, spaceAfter=4, textColor=DARK)
sSub = ParagraphStyle('Sub', parent=styles['Normal'], fontSize=12, spaceAfter=20, textColor=LIGHT, alignment=TA_CENTER)
sH1 = ParagraphStyle('H1', parent=styles['Heading1'], fontSize=16, spaceBefore=20, spaceAfter=8, textColor=DARK)
sH2 = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=13, spaceBefore=14, spaceAfter=6, textColor=HexColor('#2a2a4a'))
sH3 = ParagraphStyle('H3', parent=styles['Heading3'], fontSize=11, spaceBefore=10, spaceAfter=4, textColor=HexColor('#333355'))
sB = ParagraphStyle('B', parent=styles['Normal'], fontSize=10, leading=14, spaceAfter=6, alignment=TA_JUSTIFY)
sBul = ParagraphStyle('Bul', parent=sB, leftIndent=20, bulletIndent=8, spaceAfter=3)
sCode = ParagraphStyle('Code', parent=styles['Code'], fontSize=9, leftIndent=20, spaceAfter=6, backColor=HexColor('#f5f5f5'), borderWidth=0.5, borderColor=HexColor('#dddddd'), borderPadding=4)
sNote = ParagraphStyle('Note', parent=sB, fontSize=9, textColor=GREY, leftIndent=20, fontName='Helvetica-Oblique')
sCtr = ParagraphStyle('Ctr', parent=sB, alignment=TA_CENTER, spaceAfter=10)

def B(t): return Paragraph(f"<bullet>&bull;</bullet> {t}", sBul)
def T(data, w=None):
    t = Table(data, colWidths=w, hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),HexColor('#e8e8e8')),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,-1),9),('GRID',(0,0),(-1,-1),0.5,HexColor('#cccccc')),
        ('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
        ('LEFTPADDING',(0,0),(-1,-1),6)]))
    return t
def footer(c,d):
    c.saveState(); c.setFont('Helvetica',7); c.setFillColor(LIGHT)
    c.drawCentredString(letter[0]/2,0.5*inch,f"Push 2 / Nuendo Bridge \u2014 Page {d.page}"); c.restoreState()

def build_release_notes():
    doc = SimpleDocTemplate(os.path.join(_DOCS_DIR, "Push2_Nuendo_Bridge_Release_Notes_v1_0_5.pdf"), pagesize=letter, topMargin=0.75*inch, bottomMargin=0.75*inch, leftMargin=inch, rightMargin=inch)
    s = []
    s.append(Paragraph("Push 2 / Nuendo Bridge", sTitle))
    s.append(Paragraph("Release Notes", sSub))

    # \u2500\u2500 Version 1.0.5 \u2500\u2500
    s.append(Paragraph("Version 1.0.5 \u2014 May 2026", sH1))
    s.append(Paragraph("New Features", sH2))
    s.append(B("<b>Keyswitch pad layouts</b>: the Layout button now cycles through four pad layouts \u2014 64 notes, 56 notes + 8 keyswitches, 48 notes + 16 keyswitches, and Drum. Keyswitch pads sit on the bottom row(s), light orange, and trigger user-defined absolute notes (ideal for articulation keyswitches). Long-press Layout to configure: Enc 1 sets the starting note, Enc 2-8 override individual pads, and the lower row toggles Chromatic / Naturals layout, Latch (the keyswitch section is monophonic \u2014 only one active at a time), Reset, and Done. Note names follow Cubase convention (C-2 = MIDI 0). Configuration is in-memory (not persisted)."))
    s.append(B("<b>Two octatonic scales</b>: <i>Octatonic WH</i> and <i>Octatonic HW</i> added to the Scale menu."))
    s.append(B("<b>XY pad</b> (Session button): the 64 pads become an XY morphing surface controlling two parameters of the selected track (Volume, Pan, Quick Controls 1-8) or raw MIDI CC. Relative, pressure-weighted input means no jump when you touch down, and two-finger input interpolates smoothly. Lower 1/2 pick the X/Y category (Track / CC), Enc 1/2 pick the X/Y parameter, Enc 4/5 set sensitivity and smoothing, Lower 5-8 toggle Mute/Solo/Monitor/Record for the selected track, and the arrows navigate tracks."))
    s.append(B("<b>Pad note range in the Mix footer</b>: the Mix page footer now shows the MIDI note range currently mapped to the pads (keyswitch pads excluded in keyswitch layouts)."))
    s.append(B("<b>Per-track automation feedback</b>: each bank track's Read/Write automation mode is now reflected on screen, not just the selected track's."))
    s.append(B("<b>Windows System Tray app</b>: on Windows the bridge now runs from the system tray (status, Open Plugin Mapper, Show Log, Quit) instead of a console window. Run with <i>--terminal</i> for the classic console version. The Plugin Mapper no longer opens a browser automatically."))
    s.append(B("<b>Rescan moved to the Setup page</b> (lower-row button 8, available on every Setup page)."))
    s.append(B("<b>macOS app is now fully self-contained</b>: the libusb USB runtime is bundled inside the .app, so Homebrew and <font face='Courier'>brew install libusb</font> are no longer required — just copy the app and run it."))
    s.append(Paragraph("Bug Fixes", sH2))
    s.append(B("<b>Control Room Main reset</b> (Shift+Touch on the rightmost encoder) now lands on an exact 0.00 dB instead of -0.01 dB."))
    s.append(B("<b>Channel Strip module values</b> now appear immediately on entering a module (Gate, Comp, EQ, etc.) and stay visible, instead of only showing after you nudge a parameter."))
    s.append(B("<b>Saturator and Limiter encoders</b> now respond to changes (the sub-page activation could fail silently for those two slots)."))
    s.append(B("<b>Inserts page</b>: an insert is no longer occasionally shown duplicated in another slot (display only)."))
    s.append(B("<b>CC Pick-up mode removed</b>: the MIDI CC page is Absolute only. Pick-up required parameter feedback that a normal setup does not provide, so it behaved identically to Absolute."))
    s.append(PageBreak())

    # \u2500\u2500 Version 1.0.4 \u2500\u2500
    s.append(Paragraph("Version 1.0.4 \u2014 May 2026", sH1))
    s.append(Paragraph("New Features", sH2))
    s.append(B("<b>Channel Strip mode</b> (Mix \u2192 Mix again): a dedicated Channel Strip view with an overview page (Gate, Comp, EQ, Tools, Sat, Limiter shown as Cubase-coloured banners) and six drill-down sub-pages \u2014 one per module."))
    s.append(B("<b>Strip slot extended parameters</b>: parameters that are NOT in Cubase's bank zone are now reachable via DirectAccess on every strip variant \u2014 e.g. VintageCompressor Ratio &amp; Mix, Standard Compressor DryMix &amp; Hold, Tube Compressor Character &amp; High Ratio, DeEsser side-chain filter &amp; Diff, Magneto II Dual &amp; Oversample, Maximizer Release &amp; Recover, Brickwall Link &amp; Oversample, Noise Gate Hold &amp; Analysis, and more."))
    s.append(B("<b>EQ page (EQ-Eight style)</b>: band selector (Enc 1), Type / Freq / Q / Gain for the selected band, PreFilter Low-Cut / High-Cut frequency and on/off, PreGain, plus a live magnitude curve (4 EQ bands + PreFilter) with numbered band markers. The curve updates in real time from the Push <b>and</b> from changes made in Nuendo."))
    s.append(B("<b>Edit Channel Settings</b>: now on lower-row button 8 (Channel Strip pages) and Shift+Upper Row (Mix view), in addition to the existing double-press. The button lights white and the on-screen pill turns white while the window is open (bidirectional state feedback)."))
    s.append(B("<b>Section colours &amp; bold labels</b>: each Channel Strip section uses its Nuendo track-strip colour with bold module names, matching the Cubase/Nuendo GUI."))
    s.append(B("<b>Amber Bypass indicators</b>: bypass pills/LEDs light amber when the section is bypassed (engaged), matching Nuendo's bypass button behaviour."))
    s.append(B("<b>Lower-row LED sync</b>: lower-row button LEDs follow the on-screen toggle states on the Channel Strip overview and all sub-pages."))
    s.append(B("<b>Piano scale mode</b>: a new <i>Piano</i> option in the Scale selector lays the pads out like a piano keyboard — white keys on the lower row of each octave pair, black keys on the upper row, four octaves stacked bottom-to-top, every C highlighted in purple. Rooted at C (root selection is locked in this mode); Octave Up/Down shifts the whole four-octave block."))
    s.append(Paragraph("Technical", sH2))
    s.append(B("Strip slot DA exploration (up to 6 slots) with dynamic DA-slot resolution by plugin name \u2014 supports custom Cubase strip layouts where module order differs."))
    s.append(B("DA param-flip mechanism (CC 73/74 ch8) for binary toggles that Cubase's setTypeToggle handles unreliably (e.g. VintageCompressor Punch, EQ section bypass, EQ band on/off)."))
    s.append(B("Live host-side parameter feedback via SysEx 0x3D from daInserts.mOnParameterChange, de-duplicated to avoid flooding during mouse drags in Nuendo."))
    s.append(B("Edit Channel Settings window state via SysEx 0x3E (separate read binding)."))
    s.append(B("Dedicated read bindings for PreFilter Phase / section bypass and ChannelEQ bypass so the on-screen state stays in sync."))
    s.append(B("SysEx range 0x34\u20130x3E and ch8 CC 70\u201378 allocated for strip slot cache, bypass, edit, param-flip, variant probe and live feedback."))
    s.append(Paragraph("Known Limitations", sH2))
    s.append(B("<b>Windows — the bridge and Ableton Live cannot use the Push 2 at the same time.</b> Windows installs the Push 2's WinUSB driver automatically (no Zadig needed); the bridge and Live share that same driver, but only one app can hold the USB connection at a moment — close one to use the other. (macOS is not affected.)"))
    s.append(B("Channel Strip modules must be <b>activated manually in Nuendo</b> first — an empty or disabled strip slot (Gate, Comp, EQ, Tools, Sat, Limiter) is not exposed to the Push 2. Load/enable the module in the Nuendo channel strip before controlling it from the controller."))
    s.append(B("Strip slot <b>variant switching from the Push is not possible</b> \u2014 Cubase locks strip-slot plugin selection; the MIDI Remote API (trySetSlotPlugin / the slot 'Effect Type' tag) is silently rejected. Switch variants in Nuendo's strip-slot menu; the on-screen chip mirrors the active variant in real time."))
    s.append(B("Opening a strip-slot plugin's <b>Edit UI from the Push is not exposed</b> by the MIDI Remote API (mEdit toggles a flag but Nuendo does not open the window). Use the 'e' button in the mixer console."))
    s.append(B("ChannelEQ <b>bands 2 and 3 are always Peak</b> filters (Cubase restriction) \u2014 the Type encoder has no effect on those bands."))
    s.append(B("No audio spectrogram behind the EQ curve \u2014 the MIDI Remote API provides no audio stream."))
    s.append(B("<b>Remove the Push 2 'Live Port' and 'User Port' from Nuendo's \u201cIn All MIDI Inputs\u201d</b> (Studio Setup \u2192 MIDI Port Setup) or pad notes will be doubled (one copy from the bridge's BridgeNotes port, one direct from the hardware)."))
    s.append(PageBreak())

    s.append(Paragraph("Version 1.0.3 \u2014 April 2026", sH1))
    s.append(Paragraph("New Features", sH2))
    s.append(B("<b>Plugin Browser</b> (Add Device button): browse and load plugins directly from the Push 2. Select an insert slot, scroll through your plugin collection, and load with one press. Uses the DirectAccess Plugin Manager API (Nuendo 15+ / API 1.3)."))
    s.append(B("<b>Collection cycling</b>: switch between Nuendo plugin collections via lower row button 1 in the plugin list view."))
    s.append(B("<b>Plugin Mapper integration</b>: the Plugin Mapper web server (FastAPI) is now integrated into the bridge and starts automatically. Access it from the menu bar or at http://localhost:8100. Dependencies are optional."))
    s.append(B("<b>DirectAccess insert control</b>: bypass, edit (open/close UI), and encoder parameter control via DirectAccess for instant response. Fallback to viewer-based control if DA is not available."))
    s.append(B("<b>DA encoder control</b>: mapped plugin parameters controlled directly via DirectAccess on MIDI channel 9, with display value feedback."))
    s.append(B("<b>Plugin Mapper fuzzy matching</b>: pedalboard parameter names matched to DA parameter names using word-level fuzzy matching."))
    s.append(B("<b>Record button LED</b>: 3-state behavior \u2014 orange (idle), blinking red (track armed), solid red (recording)."))
    s.append(B("<b>Shift+Arrows nudge</b>: in Volume and Pan modes, Shift+Left/Right shifts the bank by 1 track instead of 8."))
    s.append(B("<b>CC Mode pick-up</b> (Setup page): new CC Mode page with Absolute and Pick-up options. Pick-up mode prevents parameter jumps by waiting for a direction change before sending."))
    s.append(B("<b>Adaptive text color</b>: track headers and title bars automatically switch between white and black text based on background luminance. Bold font for headers."))
    s.append(B("<b>Splash screen updated</b>: removed IAC port reference. Now shows 'Load the MIDI Remote script in Nuendo'."))
    s.append(Paragraph("Technical", sH2))
    s.append(B("Plugin list transfer via SysEx 0x2C/0x2D, queued in mOnIdle (10 entries/tick)."))
    s.append(B("Plugin load via CC 80-82 ch8 + trySetSlotPlugin (DA Plugin Manager API 1.3)."))
    s.append(B("Record state feedback via CC 73."))
    s.append(B("Bank shift via CC 38/39 bound to mShiftRight/mShiftLeft."))
    s.append(B("Plugin Mapper server in daemon thread with dedicated asyncio event loop."))
    s.append(B("MIDI channels 8 (0xB7) and 9 (0xB8) allocated for DirectAccess."))
    s.append(Paragraph("Known Limitations", sH2))
    s.append(B("No Effect (remove plugin) not supported \u2014 API 1.3 has no removeSlotPlugin."))
    s.append(B("CC pick-up uses direction-change detection (no Nuendo feedback available)."))
    s.append(B("Plugin Browser requires Nuendo 15+ (API 1.3)."))
    s.append(PageBreak())
    s.append(Paragraph("Version 1.0.2 \u2014 April 2026", sH1))
    s.append(B("Setup Page with Aftertouch Mode and Velocity Curve settings."))
    s.append(B("MIDI CC Controller page (Shift+Note): 8 assignable CC faders."))
    s.append(B("Mute/Solo/Monitor/Rec on Device and Inserts pages."))
    s.append(B("Long press / double press on upper row buttons."))
    s.append(B("Clear Monitor / Clear Rec (Shift+Mute/Solo)."))
    s.append(Paragraph("Version 1.0.1 \u2014 March 2026", sH1))
    s.append(B("Volume stutter fix, peak clip grace period, Send 1 CC conflict fix, CR CC conflict fix, pan offset correction."))
    s.append(Paragraph("Version 1.0.0 \u2014 February 2026", sH1))
    s.append(B("Initial release: Mixer, Sends, Device, Inserts, Transport, Automation, Control Room, Note Input, Touchstrip, Track Management, VU Meters, macOS Menu Bar App."))
    doc.build(s, onFirstPage=footer, onLaterPages=footer)
    print("  done: Release Notes")

def build_mapper_guide():
    doc = SimpleDocTemplate(os.path.join(_DOCS_DIR, "Push2_Nuendo_Bridge_Plugin_Mapper_Guide_v1_0.pdf"), pagesize=letter, topMargin=0.75*inch, bottomMargin=0.75*inch, leftMargin=inch, rightMargin=inch)
    s = []
    s.append(Paragraph("Push 2 / Nuendo Bridge", sTitle))
    s.append(Paragraph("Plugin Mapper Guide \u2014 Version 1.0", sSub))
    s.append(Paragraph("1. Overview", sH1))
    s.append(Paragraph("The Plugin Mapper lets you create custom parameter mappings for your VST3 plugins. When you focus a mapped plugin in Inserts mode, the Push 2 encoders automatically control the parameters you have assigned, organized in pages of 8.", sB))
    s.append(B("<b>Scanner</b>: discovers installed VST3 plugins and extracts their parameter lists using Spotify's pedalboard library (GPL-3.0)."))
    s.append(B("<b>Web interface</b>: a drag-and-drop UI served by FastAPI at http://localhost:8100 for creating and editing mappings."))
    s.append(Paragraph("The server is integrated into the bridge and starts automatically if dependencies are installed. It is entirely optional.", sB))
    s.append(Paragraph("2. Installation", sH1))
    s.append(Paragraph("Install the required packages:", sB))
    s.append(Paragraph("pip install fastapi uvicorn pedalboard", sCode))
    s.append(Paragraph("Without pedalboard (web interface only, no scanning):", sB))
    s.append(Paragraph("pip install fastapi uvicorn", sCode))
    s.append(Paragraph("Startup messages:", sB))
    s.append(B("<b>running at http://localhost:8100, scanner ready</b> \u2014 everything installed"))
    s.append(B("<b>running, scanner unavailable</b> \u2014 pedalboard missing"))
    s.append(B("<b>not available</b> \u2014 fastapi/uvicorn missing (bridge works normally)"))
    s.append(Paragraph("3. File Locations", sH1))
    s.append(T([['File','Location','Description'],
        ['Plugin cache','~/.push2bridge/plugin_cache.json','Scanned plugin parameters (auto-generated)'],
        ['Mappings','~/.push2bridge/mappings/*.json','One JSON file per mapped plugin'],
        ['Settings','~/.push2bridge/mapper_settings.json','Scanner settings (directories, auto-scan)'],
        ['Mapper source','src/mapper/','Scanner, server, and web interface files']],w=[90,210,180]))
    s.append(Spacer(1,8))
    s.append(Paragraph("All user data is stored in <b>~/.push2bridge/</b>. Mappings are plain JSON files that can be shared, backed up, or edited manually.", sNote))
    s.append(Paragraph("4. Scanning Plugins", sH1))
    s.append(Paragraph("The scanner discovers VST3 plugins in standard directories:", sB))
    s.append(B("macOS: /Library/Audio/Plug-Ins/VST3/ and ~/Library/Audio/Plug-Ins/VST3/"))
    s.append(B("Windows: C:/Program Files/Common Files/VST3/"))
    s.append(Paragraph("To scan, open the web interface and click Scan. Each plugin is loaded in an isolated subprocess with a 30-second timeout.", sB))
    s.append(Paragraph("Command line: cd src/mapper &amp;&amp; python scanner.py", sCode))
    s.append(Paragraph("Options: --force (rescan all), --retry (retry errors), --stats (cache statistics).", sNote))
    s.append(PageBreak())
    s.append(Paragraph("5. Creating Mappings", sH1))
    s.append(Paragraph("Open http://localhost:8100 or click Plugin Mapper in the macOS menu bar.", sB))
    s.append(Paragraph("Left Panel \u2014 Plugin List", sH3))
    s.append(B("Lists all scanned plugins with search and filter (All / Effects / Instruments / Mapped / Unmapped)."))
    s.append(Paragraph("Center Panel \u2014 Parameters", sH3))
    s.append(B("Shows all parameters of the selected plugin as draggable cards."))
    s.append(Paragraph("Right Panel \u2014 Mapping Pages", sH3))
    s.append(B("Each page has 8 slots for the 8 Push 2 encoders."))
    s.append(B("Drag parameters from the center panel into encoder slots."))
    s.append(B("Click Add Page for additional pages (navigate with Left/Right on Push)."))
    s.append(B("Edit short labels for each slot (displayed on Push 2 screen)."))
    s.append(B("Click Save Mapping \u2014 saved to ~/.push2bridge/mappings/{plugin_name}.json."))
    s.append(B("Click Delete Mapping to remove an existing mapping."))
    s.append(Paragraph("6. How Mappings Work", sH1))
    s.append(Paragraph("When you enter the parameter view for an insert plugin:", sB))
    s.append(B("1. The bridge checks ~/.push2bridge/mappings/ for a matching JSON file."))
    s.append(B("2. If found, it asks Nuendo (via DirectAccess) to enumerate all plugin parameters."))
    s.append(B("3. It matches pedalboard parameter names to DA names using fuzzy word matching (e.g. 'band_1_frequency' matches 'Band 1 Frequency')."))
    s.append(B("4. Configures the 8 encoders to control the matched parameters directly."))
    s.append(B("5. Displays parameter names and live values on the Push 2 screen."))
    s.append(Paragraph("If no mapping exists, the bridge uses Nuendo's default parameter bank.", sB))
    s.append(Paragraph("Mappings are loaded at startup. Restart the bridge after creating or modifying mappings.", sNote))
    s.append(Paragraph("7. Troubleshooting", sH1))
    s.append(B("<b>Web interface not loading</b>: check that fastapi and uvicorn are installed."))
    s.append(B("<b>Plugin not in list</b>: click Scan. Some plugins are incompatible with pedalboard."))
    s.append(B("<b>Parameters don't match</b>: edit the mapping JSON manually if fuzzy matching fails."))
    s.append(B("<b>Encoders don't respond</b>: ensure DA insert cache is built. Re-enter the insert to re-trigger."))
    s.append(Paragraph("8. Dependencies", sH1))
    s.append(T([['Package','Version','License','Purpose'],
        ['pedalboard','>=0.9.0','GPL-3.0','VST3 plugin loading and parameter extraction'],
        ['fastapi','>=0.104.0','MIT','REST API server'],
        ['uvicorn','>=0.24.0','BSD-3-Clause','ASGI server for FastAPI']],w=[90,70,90,230]))
    s.append(Spacer(1,8))
    s.append(Paragraph("All dependencies are GPL-3.0 compatible.", sNote))
    doc.build(s, onFirstPage=footer, onLaterPages=footer)
    print("  done: Plugin Mapper Guide")

def build_user_guide():
    doc = SimpleDocTemplate(os.path.join(_DOCS_DIR, "Push2_Nuendo_Bridge_User_Guide_v1_0_5.pdf"), pagesize=letter, topMargin=0.75*inch, bottomMargin=0.75*inch, leftMargin=inch, rightMargin=inch)
    s = []
    s.append(Paragraph("Push 2 / Nuendo Bridge", sTitle))
    s.append(Paragraph("User Guide &amp; Installation Manual \u2014 Version 1.0.5", sSub))
    s.append(Paragraph("Compatible with Nuendo 14+ and Cubase 14+ \u2014 macOS and Windows", sCtr))
    s.append(Paragraph("This guide covers installation, configuration, and use of the Push 2 / Nuendo Bridge.", sB))
    # TOC
    s.append(Paragraph("Table of Contents", sH1))
    for item in ["1. System Requirements","2. Installation \u2014 macOS","3. Installation \u2014 Windows","4. First Launch","5. Nuendo Configuration","6. Using the Bridge","7. Mixer Modes","8. Sends Mode","9. Inserts Mode","10. Plugin Browser","11. Quick Controls","12. Transport","13. Automation","14. Touchstrip","15. Note Input","16. Control Room","17. Channel Strip","18. Channel EQ Page","19. Setup Page","20. MIDI CC Controller","21. Plugin Mapper","22. Button Reference","23. MIDI Channel Allocation","24. Troubleshooting","25. Support"]:
        s.append(Paragraph(item, ParagraphStyle('toc',parent=sB,spaceAfter=1,fontSize=10)))
    s.append(PageBreak())
    # 1
    s.append(Paragraph("1. System Requirements", sH1))
    s.append(B("Ableton Push 2 (USB), Steinberg Nuendo 14+ or Cubase 14+, macOS 11+ or Windows 10/11"))
    s.append(B("<b>Standalone app/exe: nothing else to install.</b> The macOS .app and Windows .exe bundle the Python interpreter, all dependencies and the libusb USB runtime. No Homebrew, no libusb, no Python."))
    s.append(B("<b>Running from source only:</b> Python 3.9–3.11.9 (3.12/3.13 not yet supported), libusb (macOS: <font face='Courier'>brew install libusb</font>), and push2-python from source:<br/><font face='Courier'>pip install git+https://github.com/ffont/push2-python.git</font>"))
    s.append(B("Plugin Mapper (optional): pip install fastapi uvicorn pedalboard"))
    s.append(Paragraph("<b>Nuendo 15+ features:</b> Plugin Browser, DirectAccess insert control and the Channel Strip extended-parameter / EQ-curve pages require API 1.3. All other features work with Nuendo 14+.", sNote))
    # 2
    s.append(Paragraph("2. Installation \u2014 macOS", sH1))
    s.append(Paragraph("Option A: Standalone App (Recommended)", sH2))
    s.append(Paragraph("No Homebrew, libusb or Python required \u2014 the app bundles everything, including the libusb USB runtime.", sNote))
    s.append(B("Step 1: Copy Push2 Nuendo Bridge.app to /Applications"))
    s.append(B("Step 2: The app is <b>not code-signed</b>, so macOS Gatekeeper blocks it on first launch. Open Terminal and remove the quarantine flag (match the version in the .app name to your copy):"))
    s.append(Paragraph("xattr -dr com.apple.quarantine \"/Applications/Push2 Nuendo Bridge_v1.0.5.app\"", sCode))
    s.append(B("Step 3: Copy Ableton_Push2.js to:<br/>~/Documents/Steinberg/Nuendo/MIDI Remote/Driver Scripts/Local/Ableton/Push2/<br/>Create the Ableton/Push2 folder if it doesn't exist."))
    s.append(B("Step 4: Double-click the app. A P2 icon appears in the menu bar."))
    # 3
    s.append(Paragraph("3. Installation \u2014 Windows", sH1))
    s.append(Paragraph("Windows now ships as a <b>standalone .exe</b> \u2014 no Python, pip or command line required. See the separate Windows Installation Guide for the step-by-step walkthrough. Key points:", sB))
    s.append(B("Download <b>Push2NuendoBridge-vX.Y.Z-Windows.zip</b> and unzip it anywhere (e.g. Documents). It contains the <font face='Courier'>.exe</font>, <font face='Courier'>Ableton_Push2.js</font> and the PDF guides."))
    s.append(B("Install <b>loopMIDI</b> and create the four ports: <font face='Courier'>NuendoBridge In</font>, <font face='Courier'>NuendoBridge Out</font>, <font face='Courier'>BridgeNotes</font>, <font face='Courier'>BridgeNotes In</font>. Set it to start with Windows."))
    s.append(B("<b>Plug in the Push 2</b> — Windows installs the required USB driver (WinUSB) automatically the first time you connect it. No Zadig, no manual driver step."))
    s.append(Paragraph("Note: the bridge and Ableton Live share the same Push 2 USB connection, so they cannot both control it at the same time \u2014 close one to use the other. macOS is not affected. (If Windows ever fails to auto-install the driver, the Windows Installation Guide's Troubleshooting section shows how to force it with Zadig.)", sNote))
    s.append(B("<b>Double-click the .exe</b> to run the bridge \u2014 a console window shows the status and a clickable Plugin Mapper link (http://localhost:8100)."))
    s.append(Paragraph("No Python install is needed: the interpreter, all dependencies and the libusb runtime are bundled inside the .exe.", sNote))
    s.append(B("Copy <b>Ableton_Push2.js</b> to the MIDI Remote scripts folder, creating the sub-folders if needed:"))
    s.append(Paragraph("Nuendo:<br/>C:\\Users\\&lt;user&gt;\\Documents\\Steinberg\\Nuendo\\MIDI Remote\\Driver Scripts\\Local\\Ableton\\Push2\\", sCode))
    s.append(Paragraph("Cubase:<br/>C:\\Users\\&lt;user&gt;\\Documents\\Steinberg\\Cubase\\MIDI Remote\\Driver Scripts\\Local\\Ableton\\Push2\\", sCode))
    s.append(Paragraph("Replace &lt;user&gt; with your Windows user name. The <font face='Courier'>Local\\Ableton\\Push2</font> folders usually do not exist yet \u2014 create them.", sNote))
    # 4
    s.append(Paragraph("4. First Launch", sH1))
    s.append(Paragraph("Connect Push 2 via USB, launch the bridge, open Nuendo. Menu bar icon: P2 \u2713 = connected, P2 \u231b = waiting. Click for Start/Stop, Show Logs, Plugin Mapper, Start at Login, Quit.", sB))
    # 5
    s.append(Paragraph("5. Nuendo Configuration", sH1))
    s.append(Paragraph("Automatic setup: Nuendo usually detects the script and assigns its ports on its own.", sB))
    s.append(Paragraph("If the script does not load automatically", sH2))
    s.append(B("Open any project."))
    s.append(B("Studio → MIDI Remote Manager → <b>Add MIDI Controller Surface</b>."))
    s.append(B("Vendor = <b>Ableton</b>, Model = <b>Push2</b>."))
    s.append(B("MIDI Input = <b>NuendoBridge Out</b>, MIDI Output = <b>NuendoBridge In</b> (the ports carry the same names as listed here)."))
    s.append(Paragraph("Note Input", sH2))
    s.append(Paragraph("Set the instrument track's MIDI input to <b>BridgeNotes</b> (enable it in MIDI Port Setup if hidden).", sB))
    s.append(Paragraph("Important — avoid doubled notes", sH2))
    s.append(B("In Studio Setup → MIDI Port Setup, <b>uncheck “In ‘All MIDI Inputs’” for both Push 2 ports</b> — “Ableton Push 2” (Live Port) and “Ableton Push 2 User Port”."))
    s.append(Paragraph("If left checked, every pad you play is received twice: once via the bridge's BridgeNotes port and once directly from the Push 2 hardware. Excluding the raw Push 2 ports is standard practice for any control-surface bridge and is permanent once set.", sNote))
    s.append(PageBreak())
    # 6
    s.append(Paragraph("6. Using the Bridge", sH1))
    s.append(Paragraph("8 vertical zones on the Push 2 screen. Left/Right = bank by 8 tracks. Shift+Left/Right = nudge by 1 track (Volume/Pan modes).", sB))
    s.append(T([['Button','Mode','Encoders'],['Mix','Volume','8 track volumes'],['Shift+Mix','Track','Vol+Pan+Sends'],['Clip','Sends','8 sends'],['Shift+Clip','Pan','8 track pans'],['Device','Quick Controls','8 QC'],['Browse','Inserts','Plugin params'],['Add Device','Plugin Browser','Browse/load plugins']],w=[80,90,290]))
    s.append(Spacer(1,6))
    s.append(Paragraph("Lower row: Mute toggles Mute/Monitor. Solo toggles Solo/Rec. Shift+Mute/Solo clears all.", sB))
    # 7
    s.append(Paragraph("7. Mixer Modes", sH1))
    s.append(Paragraph("Volume Mode (Mix button)", sH2))
    s.append(Paragraph("Shows 8 tracks with volume bars, VU meters, and peak clip indicators. Turn an encoder to adjust volume.", sB))
    s.append(Paragraph("Upper row buttons (above the display):", sB))
    s.append(B("Short press = select track"))
    s.append(B("Shift + press = clear peak clip for that track"))
    s.append(B("Long press (1 second) = open instrument UI"))
    s.append(B("Double press = open Edit Channel Settings"))
    s.append(Paragraph("Lower row buttons (below the display):", sB))
    s.append(B("Toggle Mute, Solo, Monitor, or Record Arm on the corresponding track"))
    s.append(B("Press the Mute button to switch between Mute and Monitor mode"))
    s.append(B("Press the Solo button to switch between Solo and Record Arm mode"))
    s.append(B("Long press (0.5s) in Mute mode = toggle Monitor on that track"))
    s.append(B("Long press (0.5s) in Solo mode = toggle Record Arm on that track"))
    s.append(B("Shift+Mute = clear all mutes (or all monitors in Monitor mode)"))
    s.append(B("Shift+Solo = clear all solos (or all rec arms in Rec mode)"))
    s.append(Paragraph("Pan Mode (Shift+Clip)", sH2))
    s.append(Paragraph("Shows 8 tracks with pan position indicators. Turn an encoder to adjust pan.", sB))
    s.append(Paragraph("Track Mode (Shift+Mix)", sH2))
    s.append(Paragraph("Combined mode for the selected track: Enc1=Volume, Enc2=Pan, Enc3-8=Sends 1-6.", sB))
    # 8
    s.append(Paragraph("8. Sends Mode", sH1))
    s.append(Paragraph("Press Clip. Encoders = send levels. Upper row = On/Off. Lower row = Pre/Post. Left/Right = navigate tracks.", sB))
    # 9
    s.append(Paragraph("9. Inserts Mode", sH1))
    s.append(Paragraph("<b>List View:</b> Short press upper = params. Long press = open UI. Shift+upper = params+UI. Lower = bypass. Shift+Left/Right = slots 1-8 / 9-16.", sB))
    s.append(Paragraph("<b>Parameter View:</b> Encoders = 8 params. Left/Right = bank/page nav. Lower 1=UI, 2=bypass, 3=deactivate. If mapped: \u2605 MAPPED indicator.", sB))
    s.append(PageBreak())
    # 10
    s.append(Paragraph("10. Plugin Browser", sH1))
    s.append(Paragraph("<i>Requires Nuendo 15+ (MIDI Remote API 1.3)</i>", sNote))
    s.append(Paragraph("Press Add Device to open the browser.", sB))
    s.append(Paragraph("Phase 1 \u2014 Slot Selection", sH2))
    s.append(Paragraph("The screen shows the insert slots of the selected track.", sB))
    s.append(B("Upper row buttons (above the display) = select the target slot"))
    s.append(B("Left/Right = switch between slots 1-8 and 9-16"))
    s.append(B("Lower row button 8 = Cancel"))
    s.append(Paragraph("Phase 2 \u2014 Plugin List", sH2))
    s.append(B("Encoder 1 = page scroll (8 at a time)"))
    s.append(B("Encoder 2 = fine scroll (highlight moves within page)"))
    s.append(B("Upper row = load plugin from that column"))
    s.append(B("Lower row button 1 = cycle to next collection"))
    s.append(B("Lower row button 8 / Browse = back / cancel"))
    s.append(Paragraph("After loading, the bridge returns to Inserts mode and rescans slots automatically.", sB))
    # 11
    s.append(Paragraph("11. Quick Controls (Device Mode)", sH1))
    s.append(Paragraph("Press Device. 8 Quick Controls of the selected track. Left/Right = navigate tracks.", sB))
    # 12
    s.append(Paragraph("12. Transport Controls", sH1))
    s.append(T([['Button','Function','LED'],['Play','Playback','White/Green/Purple'],['Record','Recording','Orange/Blink Red/Solid Red'],['Fixed Length','Cycle/Loop',''],['Automate','Automation cycle','White/Green/Red'],['Metronome','Metronome','LED reflects state']],w=[80,130,250]))
    # 13
    s.append(Paragraph("13. Automation", sH1))
    s.append(Paragraph("Automate button cycles: Off \u2192 Read \u2192 Read+Write \u2192 Write \u2192 Off.", sB))
    # 14
    s.append(Paragraph("14. Touchstrip", sH1))
    s.append(Paragraph("Shift+Layout to cycle: Pitch Bend, Mod Wheel (CC 1), Volume.", sB))
    # 15
    s.append(Paragraph("15. Note Input", sH1))
    s.append(Paragraph("64 pads: Chromatic (default) or Drum (Layout). Scale, Accent, Note Repeat available. Set instrument input to BridgeNotes.", sB))
    s.append(Paragraph("Scale selector (Scale button): pick a musical scale or the <b>Piano</b> layout. Piano mode arranges the pads like a piano keyboard — white keys on the lower row of each octave pair, black keys on the upper row, four octaves stacked bottom-to-top, every C in purple. The root is locked to C in Piano mode; use Octave Up/Down to move the whole four-octave block.", sB))
    # 16
    s.append(Paragraph("16. Control Room", sH1))
    s.append(Paragraph("Press User. 4 pages: Main, Phones, Cues, Sources. Master encoder = Main level. User+Master = Phones.", sB))
    s.append(PageBreak())
    # 17 — Channel Strip
    s.append(Paragraph("17. Channel Strip", sH1))
    s.append(Paragraph("<i>Extended-parameter and EQ-curve control require Nuendo 15+ (API 1.3).</i>", sNote))
    s.append(Paragraph("From the Mixer view, press <b>Mix again</b> to enter Channel Strip mode. The overview shows the six strip sections as Cubase-coloured banners (Gate, Comp, EQ, Tools, Sat, Limiter) plus PreFilter Phase and PreGain.", sB))
    s.append(Paragraph("<b>Important:</b> a strip module can only be controlled once it has been <b>activated manually in Nuendo</b>. Open the channel's strip in the Nuendo mixer and load/enable each module (Gate, Comp, EQ, Tools, Sat, Limiter) you want to use. An empty or disabled strip slot is not exposed to the Push 2 — its banner and encoders stay inactive until you turn the module on in Nuendo.", sNote))
    s.append(Paragraph("Overview", sH2))
    s.append(B("Each banner shows the section colour (dimmed when bypassed) and the loaded plugin variant."))
    s.append(B("Lower row 1-6 = Bypass each section (pill/LED amber when bypassed)."))
    s.append(B("Lower row 7 = PreFilter Phase On/Off. Lower row 8 = Edit Channel Settings (white when the window is open)."))
    s.append(B("Upper row 1-6 = drill into that module's sub-page."))
    s.append(Paragraph("Module Sub-pages", sH2))
    s.append(B("8 encoders control that module's parameters. Parameters beyond Cubase's bank zone are exposed via DirectAccess (e.g. VintageCompressor Ratio &amp; Mix, Tube Compressor Character, DeEsser side-chain filter, Maximizer Release/Recover)."))
    s.append(B("Lower row = the module's binary toggles (Auto Release, Solo, Diff, etc.) — LEDs follow the on-screen pills."))
    s.append(B("Upper row layout: 1 = module name (inactive), 2 = Bypass, 3-5 = variant chips, 8 = back to overview."))
    s.append(Paragraph("Variant chips show the currently loaded plugin. Switching the variant must be done in Nuendo's strip-slot menu — the MIDI Remote API does not allow changing strip-slot plugins from a controller; the chip mirrors the active variant in real time.", sNote))
    # 18 — EQ page
    s.append(Paragraph("18. Channel EQ Page", sH1))
    s.append(Paragraph("Drill into the EQ section for an EQ-Eight-style page with a live frequency-response curve.", sB))
    s.append(T([['Encoder','Function'],
        ['1','Band selector (1-4) — turn to pick the active band'],
        ['2','Filter Type of the selected band (bands 2-3 are fixed Peak)'],
        ['3','Frequency of the selected band'],
        ['4','Q of the selected band'],
        ['5','Gain of the selected band'],
        ['6','PreFilter Low-Cut frequency'],
        ['7','PreFilter High-Cut frequency'],
        ['8','PreGain']], w=[70,390]))
    s.append(Spacer(1,6))
    s.append(B("Lower row 1 = selected band On/Off. Lower 6 = LC On, Lower 7 = HC On, Lower 8 = PreFilter bypass."))
    s.append(B("Upper row 2 = EQ section bypass (amber when bypassed). Upper 8 = back."))
    s.append(B("The curve combines the 4 EQ bands + PreFilter HC/LC. Numbered circles mark each band at its (freq, gain) point — white when the band is on, grey when off. The curve and markers update live, whether you change a parameter from the Push or directly in Nuendo."))
    s.append(PageBreak())
    # 19
    s.append(Paragraph("19. Setup Page", sH1))
    s.append(Paragraph("Press Setup. Tabs: MIDI Ctrl (aftertouch), Vel Curve (5 presets), CC Mode (Absolute/Pick-up), About.", sB))
    s.append(Paragraph("CC Mode", sH2))
    s.append(B("<b>Absolute</b> (default): encoder value is sent immediately. May cause parameter jumps if the encoder position differs from the current value in Nuendo."))
    s.append(B("<b>Pick-up</b>: encoder does not send values until the user reverses the direction of rotation. This prevents jumps but requires a direction change to engage."))
    s.append(Paragraph("<b>Important:</b> Nuendo does not send the current CC parameter value back to the Push 2. Because of this limitation, the bridge cannot know the actual value in Nuendo and cannot implement a true pick-up (where the encoder catches up to the existing value). Instead, pick-up mode uses direction-change detection: turn the encoder in one direction (nothing happens in Nuendo), then reverse \u2014 the encoder engages from that point on.", sNote))
    # 18
    s.append(Paragraph("20. MIDI CC Controller", sH1))
    s.append(Paragraph("Shift+Note. 8 assignable CC faders on BridgeNotes port. Upper row = edit CC number. Lower row = toggle 0/127. Defaults: CC 1,2,7,8,10,11,64,65.", sB))
    # 19
    s.append(Paragraph("21. Plugin Mapper", sH1))
    s.append(Paragraph("Create custom parameter mappings for VST3 plugins. Access via menu bar (Plugin Mapper) or http://localhost:8100. Mappings saved in <b>~/.push2bridge/mappings/</b>. See the separate Plugin Mapper Guide for details.", sB))
    s.append(Paragraph("Requires: pip install fastapi uvicorn pedalboard. The bridge works without these \u2014 the Mapper is optional.", sNote))
    # 20
    s.append(Paragraph("22. Button Reference", sH1))
    s.append(T([['Button','Action','Shift + Button'],['Mix','Volume mode (press again: Channel Strip)','Track mode'],['Clip','Sends mode','Pan mode'],['Device','Quick Controls',''],['Browse','Inserts mode',''],['Add Device','Plugin Browser',''],['Note','MIDI note pads','MIDI CC controller'],['Setup','Setup page',''],['Left/Right','Bank nav (8)','Nudge (1) in Vol/Pan'],['Play','Playback',''],['Record','Record toggle',''],['Mute','Mute/Monitor','Clear all'],['Solo','Solo/Rec arm','Clear all'],['User','Control Room',''],['Layout','Drum/Chromatic','Touchstrip cycle'],['Upper (dbl / Shift)','Edit Channel Settings',''],['Scale','Scale selector',''],['Accent','Fixed velocity',''],['Repeat','Auto-repeat','']],w=[80,170,200]))
    s.append(PageBreak())
    # 23
    s.append(Paragraph("23. MIDI Channel Allocation", sH1))
    s.append(T([['Channel','Usage'],['1 (0xB0)','Mixer (volume, pan, transport, selection, VU)'],['2 (0xB1)','Insert plugin parameters'],['3 (0xB2)','Send levels (selected track)'],['4 (0xB3)','Insert bypass toggles'],['5 (0xB4)','Quick Controls'],['6 (0xB5)','Control Room'],['7 (0xB6)','Bank zone sends'],['8 (0xB7)','DirectAccess commands (browser, bypass, edit, strip slot, param-flip, variant)'],['9 (0xB8)','DirectAccess encoder control (mapped params, strip slots)'],['16 (0xBF)','Heartbeat']],w=[80,380]))
    # 22
    s.append(Paragraph("24. Troubleshooting", sH1))
    s.append(B("<b>Push 2 not found</b>: check USB, libusb, close Ableton Live."))
    s.append(B("<b>push2-python error</b>: install it from source \u2014 pip install git+https://github.com/ffont/push2-python.git. Use Python 3.11.9 or lower."))
    s.append(B("<b>No Nuendo connection</b>: check bridge is running; add the surface manually (MIDI Remote Manager \u2192 Add, Vendor Ableton / Model Push2)."))
    s.append(B("<b>Pads play doubled notes</b>: uncheck \u201cIn \u2018All MIDI Inputs\u2019\u201d for the Push 2 Live Port and User Port (Studio Setup \u2192 MIDI Port Setup)."))
    s.append(B("<b>Channel Strip / EQ curve not working</b>: requires Nuendo 15+ (API 1.3). Drill into a section once to trigger DA strip exploration."))
    s.append(B("<b>Plugin Mapper not loading</b>: pip install fastapi uvicorn pedalboard."))
    s.append(B("<b>Track names not loading</b>: navigate Left/Right to refresh."))
    s.append(Paragraph("Logs: macOS \u2014 ~/Library/Logs/Push2NuendoBridge.log. Windows \u2014 terminal output.", sNote))
    # 25
    s.append(Paragraph("25. Support", sH1))
    s.append(Paragraph("Push 2 / Nuendo Bridge is donationware.", sB))
    s.append(B("GitHub: https://github.com/mbourque-mix/Push2Nuendo-Bridge"))
    s.append(B("Buy Me A Coffee: https://buymeacoffee.com/mbourque"))
    s.append(B("Issues: https://github.com/mbourque-mix/Push2Nuendo-Bridge/issues"))
    s.append(Paragraph("Licensed under GPL-3.0. Built with push2-python and the Steinberg MIDI Remote API.", sNote))
    doc.build(s, onFirstPage=footer, onLaterPages=footer)
    print("  done: User Guide")

def build_windows_install_guide():
    doc = SimpleDocTemplate(os.path.join(_DOCS_DIR, "Push2_Nuendo_Bridge_Windows_Installation_Guide_v1_0_5.pdf"), pagesize=letter, topMargin=0.75*inch, bottomMargin=0.75*inch, leftMargin=inch, rightMargin=inch)
    s = []
    s.append(Paragraph("Push 2 / Nuendo Bridge", sTitle))
    s.append(Paragraph("Windows Installation Guide — Version 1.0.5", sSub))
    s.append(Paragraph("Standalone .exe — no Python, no pip, no command line", sCtr))
    s.append(Paragraph("From version 1.0.4 the Windows bridge is a single self-contained executable. The Python interpreter, every dependency and the libusb USB runtime are bundled inside the .exe. You only need to set up the virtual MIDI ports (loopMIDI) and the Nuendo/Cubase MIDI Remote script — the Push 2's USB driver installs itself automatically on Windows.", sB))
    s.append(Paragraph("On Windows the bridge runs from the <b>system tray</b> (look for its icon near the clock) rather than a console window. Right-click the tray icon for status, Open Plugin Mapper, Show Log, and Quit. To run the classic console version instead, launch the .exe with the <font face='Courier'>--terminal</font> flag.", sNote))

    s.append(Paragraph("What you downloaded", sH1))
    s.append(B("<b>Push2NuendoBridge-vX.Y.Z-Windows.zip</b> — unzip it anywhere you like (e.g. <font face='Courier'>Documents\\Push2Bridge</font>). It contains:"))
    s.append(B("<font face='Courier'>Push2 Nuendo Bridge_vX.Y.Z.exe</font> — the bridge (double-click to run)."))
    s.append(B("<font face='Courier'>Ableton_Push2.js</font> — the Nuendo / Cubase MIDI Remote script."))
    s.append(B("PDF guides (User Guide, Release Notes, Plugin Mapper Guide)."))
    s.append(Paragraph("Do not delete the .exe after “installing” — it is the application; run it from wherever you keep the unzipped folder.", sNote))

    s.append(Paragraph("Step 1 — loopMIDI virtual ports", sH1))
    s.append(B("Download and install loopMIDI: https://www.tobias-erichsen.de/software/loopmidi.html"))
    s.append(B("Open loopMIDI and create <b>four</b> ports with these EXACT names (type the name, click the <b>+</b> button):"))
    s.append(Paragraph("NuendoBridge In<br/>NuendoBridge Out<br/>BridgeNotes<br/>BridgeNotes In", sCode))
    s.append(B("Right-click the loopMIDI tray icon and enable <b>“Autostart loopMIDI”</b> so the ports exist every time Windows starts."))

    s.append(Paragraph("Step 2 — Push 2 USB driver (automatic)", sH1))
    s.append(B("<b>There is nothing to install.</b> The Push 2 advertises a Microsoft “WinUSB” compatible-ID descriptor, so Windows 8/10/11 installs the right driver automatically the first time you plug it in. The bridge talks to the Push 2 through that built-in WinUSB driver."))
    s.append(B("Just connect the Push 2 by USB and wait a few seconds for Windows to finish setting it up. No Zadig, no manual driver step."))
    s.append(Paragraph("The bridge and Ableton Live use this same WinUSB driver, but only one app can hold the Push 2's USB connection at a time — so the bridge and Live cannot control the Push simultaneously. Close one to use the other. No driver change is needed to go back and forth (tested with Live 12). macOS is not affected.", sNote))
    s.append(Paragraph("Fallback (rare): if the bridge cannot find the Push 2 even though it is connected, see “Push 2 not detected” in Troubleshooting below.", sNote))

    s.append(Paragraph("Step 3 — Install the MIDI Remote script", sH1))
    s.append(B("Copy <b>Ableton_Push2.js</b> into the Steinberg MIDI Remote scripts folder, creating the sub-folders if they do not exist:"))
    s.append(Paragraph("Nuendo:<br/>C:\\Users\\&lt;user&gt;\\Documents\\Steinberg\\Nuendo\\MIDI Remote\\Driver Scripts\\Local\\Ableton\\Push2\\", sCode))
    s.append(Paragraph("Cubase:<br/>C:\\Users\\&lt;user&gt;\\Documents\\Steinberg\\Cubase\\MIDI Remote\\Driver Scripts\\Local\\Ableton\\Push2\\", sCode))
    s.append(Paragraph("Replace &lt;user&gt; with your Windows user name. The <font face='Courier'>Local\\Ableton\\Push2</font> sub-folders usually do not exist yet — create them.", sNote))

    s.append(PageBreak())
    s.append(Paragraph("Step 4 — Run the bridge", sH1))
    s.append(B("Connect the Push 2 by USB (and make sure Ableton Live is closed)."))
    s.append(B("<b>Double-click the .exe.</b> A console window opens and shows the startup status:"))
    s.append(Paragraph("[0/3] Plugin Mapper: running at http://localhost:8100<br/>[1/3] Connecting to MIDI ports...<br/>[2/3] Connecting to Push 2...<br/>[3/3] Bridge is running!", sCode))
    s.append(B("The console prints a framed <b>Plugin Mapper link</b> (http://localhost:8100) and opens it in your browser automatically. Most terminals also let you Ctrl+click the link. Launch the .exe with <font face='Courier'>--no-browser</font> to skip the auto-open."))
    s.append(B("Keep the console window open while you work — it shows live status and any errors. Press <b>Ctrl+C</b> (or close the window) to stop the bridge."))
    s.append(Paragraph("Windows SmartScreen may warn on first launch because the .exe is not code-signed. Click “More info → Run anyway”. The CI-built release is reproducible from the public source.", sNote))

    s.append(Paragraph("Step 5 — Nuendo / Cubase configuration", sH1))
    s.append(Paragraph("Automatic setup: Nuendo usually detects the script and assigns its ports on its own when you open a project.", sB))
    s.append(Paragraph("If the script does not load automatically", sH2))
    s.append(B("Open any project."))
    s.append(B("Studio → MIDI Remote Manager → <b>Add MIDI Controller Surface</b>."))
    s.append(B("Vendor = <b>Ableton</b>, Model = <b>Push2</b>."))
    s.append(B("MIDI Input = <b>NuendoBridge Out</b>, MIDI Output = <b>NuendoBridge In</b>."))
    s.append(Paragraph("Note Input", sH2))
    s.append(Paragraph("Set the instrument track's MIDI input to <b>BridgeNotes</b> (enable it in Studio Setup → MIDI Port Setup if hidden).", sB))
    s.append(Paragraph("Important — avoid doubled notes", sH2))
    s.append(B("In Studio Setup → MIDI Port Setup, <b>uncheck “In ‘All MIDI Inputs’” for both Push 2 ports</b> — “Ableton Push 2” (Live Port) and “Ableton Push 2 User Port”. Otherwise every pad is received twice."))

    s.append(Paragraph("Plugin Mapper (optional)", sH1))
    s.append(B("The Plugin Mapper web server is bundled and starts automatically with the .exe — no extra install. Open <font face='Courier'>http://localhost:8100</font> (the console prints and opens the link) to create custom plugin parameter mappings. See the Plugin Mapper Guide for details."))

    s.append(Paragraph("Troubleshooting", sH1))
    s.append(B("<b>Push 2 not detected / “Could not connect to Push 2”</b> — Close Ableton Live (only one app can hold the Push at a time). Unplug and replug the USB cable so Windows finishes installing the driver; give it a few seconds. <b>Last resort</b> (very rare, e.g. an old Windows build or a corporate-locked PC that does not auto-install the driver): install WinUSB manually with <b>Zadig</b> (https://zadig.akeo.ie) — Options → List All Devices → select <b>Ableton Push 2</b> (display/bulk interface, USB ID <font face='Courier'>2982:1967</font>, <b>not</b> the MIDI interface) → WinUSB → Install Driver."))
    s.append(B("<b>“Could not open MIDI ports”</b> — loopMIDI is not running or the four port names are not exactly as in Step 1."))
    s.append(B("<b>Push 2 connects but Nuendo does nothing</b> — The MIDI Remote script is missing or the surface ports are wrong (Step 3 / Step 5)."))
    s.append(B("<b>Doubled pad notes</b> — Uncheck the two Push 2 ports from “In All MIDI Inputs” (Step 5)."))
    s.append(B("<b>SmartScreen / antivirus blocks the .exe</b> — Allow it; PyInstaller one-file executables are a common false positive."))

    s.append(Paragraph("Support", sH1))
    s.append(B("Website: https://push2bridge.kaikuaudio.com"))
    s.append(B("Issues: https://github.com/mbourque-mix/Push2Nuendo-Bridge/issues"))
    s.append(Paragraph("Licensed under GPL-3.0. Built with push2-python and the Steinberg MIDI Remote API.", sNote))
    doc.build(s, onFirstPage=footer, onLaterPages=footer)
    print("  done: Windows Installation Guide")

if __name__ == "__main__":
    print("Generating documents...")
    build_release_notes()
    build_mapper_guide()
    build_user_guide()
    build_windows_install_guide()
    print("All done!")
