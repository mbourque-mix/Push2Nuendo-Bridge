#!/usr/bin/env python3
"""Generate PDF documents for Push2Nuendo-Bridge v1.0.3

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
    doc = SimpleDocTemplate(os.path.join(_DOCS_DIR, "Push2_Nuendo_Bridge_Release_Notes_v1_0_3.pdf"), pagesize=letter, topMargin=0.75*inch, bottomMargin=0.75*inch, leftMargin=inch, rightMargin=inch)
    s = []
    s.append(Paragraph("Push 2 / Nuendo Bridge", sTitle))
    s.append(Paragraph("Release Notes", sSub))
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
    doc = SimpleDocTemplate(os.path.join(_DOCS_DIR, "Push2_Nuendo_Bridge_User_Guide_v1_0_3.pdf"), pagesize=letter, topMargin=0.75*inch, bottomMargin=0.75*inch, leftMargin=inch, rightMargin=inch)
    s = []
    s.append(Paragraph("Push 2 / Nuendo Bridge", sTitle))
    s.append(Paragraph("User Guide &amp; Installation Manual \u2014 Version 1.0.3", sSub))
    s.append(Paragraph("Compatible with Nuendo 14+ and Cubase 14+ \u2014 macOS and Windows", sCtr))
    s.append(Paragraph("This guide covers installation, configuration, and use of the Push 2 / Nuendo Bridge.", sB))
    # TOC
    s.append(Paragraph("Table of Contents", sH1))
    for item in ["1. System Requirements","2. Installation \u2014 macOS","3. Installation \u2014 Windows","4. First Launch","5. Nuendo Configuration","6. Using the Bridge","7. Mixer Modes","8. Sends Mode","9. Inserts Mode","10. Plugin Browser","11. Quick Controls","12. Transport","13. Automation","14. Touchstrip","15. Note Input","16. Control Room","17. Setup Page","18. MIDI CC Controller","19. Plugin Mapper","20. Button Reference","21. MIDI Channel Allocation","22. Troubleshooting","23. Support"]:
        s.append(Paragraph(item, ParagraphStyle('toc',parent=sB,spaceAfter=1,fontSize=10)))
    s.append(PageBreak())
    # 1
    s.append(Paragraph("1. System Requirements", sH1))
    s.append(B("Ableton Push 2 (USB), Steinberg Nuendo 14+ or Cubase 14+, macOS 11+ or Windows 10/11"))
    s.append(B("Developer: Python 3.9+, libusb"))
    s.append(B("Plugin Mapper (optional): pip install fastapi uvicorn pedalboard"))
    s.append(Paragraph("<b>Nuendo 15+ features:</b> Plugin Browser (Add Device) and DirectAccess insert control require API 1.3. All other features work with Nuendo 14+.", sNote))
    # 2
    s.append(Paragraph("2. Installation \u2014 macOS", sH1))
    s.append(Paragraph("Option A: Standalone App (Recommended)", sH2))
    s.append(B("Step 1: Install Homebrew (if not already installed) \u2014 open Terminal and run:<br/><font face='Courier'>/bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"</font><br/>See https://brew.sh for details."))
    s.append(B("Step 2: Install libusb \u2014 <font face='Courier'>brew install libusb</font>"))
    s.append(B("Step 3: Copy Push2 Nuendo Bridge.app to /Applications"))
    s.append(B("Step 4: Copy Ableton_Push2.js to:<br/>~/Documents/Steinberg/Nuendo/MIDI Remote/Driver Scripts/Local/Ableton/Push2/<br/>Create the Ableton/Push2 folder if it doesn't exist."))
    s.append(B("Step 5: Double-click the app. A P2 icon appears in the menu bar."))
    # 3
    s.append(Paragraph("3. Installation \u2014 Windows", sH1))
    s.append(Paragraph("See the separate Windows Installation Guide for detailed instructions.", sB))
    # 4
    s.append(Paragraph("4. First Launch", sH1))
    s.append(Paragraph("Connect Push 2 via USB, launch the bridge, open Nuendo. Menu bar icon: P2 \u2713 = connected, P2 \u231b = waiting. Click for Start/Stop, Show Logs, Plugin Mapper, Start at Login, Quit.", sB))
    # 5
    s.append(Paragraph("5. Nuendo Configuration", sH1))
    s.append(Paragraph("Automatic setup: Nuendo detects the script and assigns ports. If needed, assign manually: Input = NuendoBridge Out, Output = NuendoBridge In. For note input, enable BridgeNotes in MIDI Port Setup.", sB))
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
    # 16
    s.append(Paragraph("16. Control Room", sH1))
    s.append(Paragraph("Press User. 4 pages: Main, Phones, Cues, Sources. Master encoder = Main level. User+Master = Phones.", sB))
    s.append(PageBreak())
    # 17
    s.append(Paragraph("17. Setup Page", sH1))
    s.append(Paragraph("Press Setup. Tabs: MIDI Ctrl (aftertouch), Vel Curve (5 presets), CC Mode (Absolute/Pick-up), About.", sB))
    s.append(Paragraph("CC Mode", sH2))
    s.append(B("<b>Absolute</b> (default): encoder value is sent immediately. May cause parameter jumps if the encoder position differs from the current value in Nuendo."))
    s.append(B("<b>Pick-up</b>: encoder does not send values until the user reverses the direction of rotation. This prevents jumps but requires a direction change to engage."))
    s.append(Paragraph("<b>Important:</b> Nuendo does not send the current CC parameter value back to the Push 2. Because of this limitation, the bridge cannot know the actual value in Nuendo and cannot implement a true pick-up (where the encoder catches up to the existing value). Instead, pick-up mode uses direction-change detection: turn the encoder in one direction (nothing happens in Nuendo), then reverse \u2014 the encoder engages from that point on.", sNote))
    # 18
    s.append(Paragraph("18. MIDI CC Controller", sH1))
    s.append(Paragraph("Shift+Note. 8 assignable CC faders on BridgeNotes port. Upper row = edit CC number. Lower row = toggle 0/127. Defaults: CC 1,2,7,8,10,11,64,65.", sB))
    # 19
    s.append(Paragraph("19. Plugin Mapper", sH1))
    s.append(Paragraph("Create custom parameter mappings for VST3 plugins. Access via menu bar (Plugin Mapper) or http://localhost:8100. Mappings saved in <b>~/.push2bridge/mappings/</b>. See the separate Plugin Mapper Guide for details.", sB))
    s.append(Paragraph("Requires: pip install fastapi uvicorn pedalboard. The bridge works without these \u2014 the Mapper is optional.", sNote))
    # 20
    s.append(Paragraph("20. Button Reference", sH1))
    s.append(T([['Button','Action','Shift + Button'],['Mix','Volume mode','Track mode'],['Clip','Sends mode','Pan mode'],['Device','Quick Controls',''],['Browse','Inserts mode',''],['Add Device','Plugin Browser',''],['Note','MIDI note pads','MIDI CC controller'],['Setup','Setup page',''],['Left/Right','Bank nav (8)','Nudge (1) in Vol/Pan'],['Play','Playback',''],['Record','Record toggle',''],['Mute','Mute/Monitor','Clear all'],['Solo','Solo/Rec arm','Clear all'],['User','Control Room',''],['Layout','Drum/Chromatic','Touchstrip cycle'],['Scale','Scale selector',''],['Accent','Fixed velocity',''],['Repeat','Auto-repeat','']],w=[80,170,200]))
    s.append(PageBreak())
    # 21
    s.append(Paragraph("21. MIDI Channel Allocation", sH1))
    s.append(T([['Channel','Usage'],['1 (0xB0)','Mixer (volume, pan, transport, selection, VU)'],['2 (0xB1)','Insert plugin parameters'],['3 (0xB2)','Send levels (selected track)'],['4 (0xB3)','Insert bypass toggles'],['5 (0xB4)','Quick Controls'],['6 (0xB5)','Control Room'],['7 (0xB6)','Bank zone sends'],['8 (0xB7)','DirectAccess commands (browser, bypass, edit)'],['9 (0xB8)','DirectAccess encoder control (mapped params)'],['16 (0xBF)','Heartbeat']],w=[80,380]))
    # 22
    s.append(Paragraph("22. Troubleshooting", sH1))
    s.append(B("<b>Push 2 not found</b>: check USB, libusb, close Ableton Live."))
    s.append(B("<b>No Nuendo connection</b>: check bridge is running, verify MIDI Remote ports."))
    s.append(B("<b>Plugin Browser not working</b>: requires Nuendo 15+ (API 1.3)."))
    s.append(B("<b>Plugin Mapper not loading</b>: pip install fastapi uvicorn pedalboard."))
    s.append(B("<b>Track names not loading</b>: navigate Left/Right to refresh."))
    s.append(Paragraph("Logs: macOS \u2014 ~/Library/Logs/Push2NuendoBridge.log. Windows \u2014 terminal output.", sNote))
    # 23
    s.append(Paragraph("23. Support", sH1))
    s.append(Paragraph("Push 2 / Nuendo Bridge is donationware.", sB))
    s.append(B("GitHub: https://github.com/mbourque-mix/Push2Nuendo-Bridge"))
    s.append(B("Buy Me A Coffee: https://buymeacoffee.com/mbourque"))
    s.append(B("Issues: https://github.com/mbourque-mix/Push2Nuendo-Bridge/issues"))
    s.append(Paragraph("Licensed under GPL-3.0. Built with push2-python and the Steinberg MIDI Remote API.", sNote))
    doc.build(s, onFirstPage=footer, onLaterPages=footer)
    print("  done: User Guide")

if __name__ == "__main__":
    print("Generating documents...")
    build_release_notes()
    build_mapper_guide()
    build_user_guide()
    print("All done!")
