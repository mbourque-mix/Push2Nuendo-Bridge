#!/usr/bin/env python3
"""Generate the Push 2 / Nuendo Bridge User Guide as PDF."""

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
    KeepTogether, HRFlowable, Image
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY

ACCENT = HexColor('#00B4C8')
DARK_BG = HexColor('#222222')
LIGHT_GRAY = HexColor('#F0F0F0')
MED_GRAY = HexColor('#CCCCCC')
DARK_GRAY = HexColor('#666666')
HEADER_BG = HexColor('#1A1A2D')

styles = getSampleStyleSheet()

styles.add(ParagraphStyle('DocTitle', parent=styles['Title'],
    fontSize=28, leading=34, textColor=ACCENT, spaceAfter=6))
styles.add(ParagraphStyle('DocSubtitle', parent=styles['Normal'],
    fontSize=14, leading=18, textColor=DARK_GRAY, spaceAfter=30, alignment=TA_CENTER))
styles.add(ParagraphStyle('H1', parent=styles['Heading1'],
    fontSize=20, leading=24, textColor=ACCENT, spaceBefore=24, spaceAfter=10))
styles.add(ParagraphStyle('H2', parent=styles['Heading2'],
    fontSize=15, leading=19, textColor=HexColor('#333333'), spaceBefore=16, spaceAfter=8))
styles.add(ParagraphStyle('H3', parent=styles['Heading3'],
    fontSize=12, leading=16, textColor=HexColor('#444444'), spaceBefore=12, spaceAfter=6))
styles.add(ParagraphStyle('Body', parent=styles['Normal'],
    fontSize=10, leading=14, alignment=TA_JUSTIFY, spaceAfter=8))
styles.add(ParagraphStyle('BodyBold', parent=styles['Normal'],
    fontSize=10, leading=14, spaceAfter=8, fontName='Helvetica-Bold'))
styles.add(ParagraphStyle('CodeBlock', parent=styles['Normal'],
    fontSize=9, leading=12, fontName='Courier', backColor=LIGHT_GRAY,
    borderWidth=0.5, borderColor=MED_GRAY, borderPadding=6, spaceAfter=8, leftIndent=12))
styles.add(ParagraphStyle('BulletItem', parent=styles['Normal'],
    fontSize=10, leading=14, leftIndent=24, bulletIndent=12, spaceAfter=4))
styles.add(ParagraphStyle('Note', parent=styles['Normal'],
    fontSize=9, leading=13, textColor=DARK_GRAY, backColor=HexColor('#FFF8E1'),
    borderWidth=0.5, borderColor=HexColor('#FFD54F'), borderPadding=8,
    spaceBefore=16, spaceAfter=14, leftIndent=12, rightIndent=12))
styles.add(ParagraphStyle('TableHeader', parent=styles['Normal'],
    fontSize=9, leading=12, fontName='Helvetica-Bold', textColor=white))
styles.add(ParagraphStyle('TableCell', parent=styles['Normal'],
    fontSize=9, leading=12))

def T(headers, rows, col_widths=None):
    header_cells = [Paragraph(h, styles['TableHeader']) for h in headers]
    data = [header_cells]
    for row in rows:
        data.append([Paragraph(str(c), styles['TableCell']) for c in row])
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, LIGHT_GRAY]),
        ('GRID', (0, 0), (-1, -1), 0.5, MED_GRAY),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    return t

def B(text):
    return Paragraph(f"\u2022  {text}", styles['BulletItem'])

def add_page_number(c, doc):
    c.saveState()
    c.setFont('Helvetica', 8)
    c.setFillColor(DARK_GRAY)
    c.drawCentredString(letter[0]/2, 0.5*inch, f"Push 2 / Nuendo Bridge  -  Page {doc.page}")
    c.restoreState()

def build():
    path = "/home/claude/Push2_Nuendo_Bridge_User_Guide.pdf"
    doc = SimpleDocTemplate(path, pagesize=letter,
        topMargin=0.75*inch, bottomMargin=0.75*inch,
        leftMargin=0.8*inch, rightMargin=0.8*inch)
    s = []

    # ═══ TITLE PAGE ═══
    s.append(Spacer(1, 2*inch))
    s.append(Paragraph("Push 2 / Nuendo Bridge", styles['DocTitle']))
    s.append(Paragraph("User Guide &amp; Installation Manual", styles['DocSubtitle']))
    s.append(Spacer(1, 0.5*inch))
    s.append(HRFlowable(width="60%", color=ACCENT, thickness=2, spaceAfter=20))
    s.append(Spacer(1, 0.3*inch))
    s.append(Paragraph("Version 1.0.1", styles['Body']))
    s.append(Paragraph("Compatible with Nuendo 14+ and Cubase 14+", styles['Body']))
    s.append(Paragraph("macOS and Windows", styles['Body']))
    s.append(Spacer(1, 1.5*inch))
    s.append(Paragraph(
        "This guide covers installation, configuration, and use of the Push 2 / Nuendo Bridge, "
        "which turns your Ableton Push 2 into a full-featured control surface for Steinberg Nuendo.",
        styles['Body']))
    s.append(PageBreak())

    # ═══ TABLE OF CONTENTS ═══
    s.append(Paragraph("Table of Contents", styles['H1']))
    s.append(Spacer(1, 12))
    toc = [
        "1. System Requirements", "2. Installation - macOS", "3. Installation - Windows",
        "4. First Launch", "5. Nuendo Configuration", "6. Using the Bridge",
        "7. Mixer Modes", "8. Sends Mode", "9. Inserts Mode",
        "10. Quick Controls (Device Mode)", "11. Transport Controls", "12. Automation",
        "13. Touchstrip", "14. Note Input", "15. Control Room",
        "16. Button Reference", "17. MIDI Channel Allocation", "18. Troubleshooting",
        "19. Known Issues", "20. Support",
    ]
    for item in toc:
        s.append(Paragraph(item, styles['Body']))
    s.append(PageBreak())

    # ═══ 1. SYSTEM REQUIREMENTS ═══
    s.append(Paragraph("1. System Requirements", styles['H1']))
    s.append(Paragraph("Hardware", styles['H2']))
    s.append(B("Ableton Push 2 (connected via USB)"))
    s.append(B("USB cable (included with Push 2)"))
    s.append(Paragraph("Software", styles['H2']))
    s.append(B("Steinberg Nuendo 14+ (or Cubase 14+)"))
    s.append(B("macOS 11+ (Big Sur or later) or Windows 10/11"))
    s.append(Paragraph("For Developer Installation (optional)", styles['H2']))
    s.append(B("Python 3.9 or later"))
    s.append(B("libusb (macOS: install via Homebrew)"))
    s.append(Paragraph(
        "<b>Note:</b> The standalone .app (macOS) includes all dependencies. "
        "Python and libusb are only needed if you run from source.", styles['Note']))
    s.append(PageBreak())

    # ═══ 2. INSTALLATION - macOS ═══
    s.append(Paragraph("2. Installation - macOS", styles['H1']))
    s.append(Paragraph("Option A: Standalone App (Recommended)", styles['H2']))
    s.append(Paragraph(
        "The standalone .app includes Python and all dependencies. No additional installation needed.",
        styles['Body']))

    s.append(Paragraph("Step 1: Install libusb", styles['H3']))
    s.append(Paragraph(
        "libusb is required for USB communication with the Push 2. Open Terminal and run:",
        styles['Body']))
    s.append(Paragraph("brew install libusb", styles['CodeBlock']))
    s.append(Paragraph(
        "If you don't have Homebrew, install it first from https://brew.sh", styles['Note']))

    s.append(Paragraph("Step 2: Copy the App", styles['H3']))
    s.append(Paragraph(
        "Copy <b>Push2 Nuendo Bridge.app</b> to your <b>/Applications</b> folder.",
        styles['Body']))

    s.append(Paragraph("Step 3: Install the MIDI Remote Script", styles['H3']))
    s.append(Paragraph("Copy <b>Ableton_Push2.js</b> to:", styles['Body']))
    s.append(Paragraph(
        "~/Documents/Steinberg/Nuendo/MIDI Remote/Driver Scripts/Local/Ableton/Push2/",
        styles['CodeBlock']))
    s.append(Paragraph(
        "Create the <b>Ableton/Push2</b> folder if it doesn't exist. The script must be placed in this "
        "exact subfolder structure for the MIDI Remote to detect it correctly. "
        "For Cubase, the path is similar: replace \"Nuendo\" with \"Cubase\" in the path.",
        styles['Note']))

    s.append(Paragraph("Step 4: Launch", styles['H3']))
    s.append(Paragraph(
        "Double-click the app. A <b>P2</b> icon will appear in your menu bar. "
        "The bridge will automatically search for your Push 2 and connect when found.",
        styles['Body']))
    s.append(Spacer(1, 12))

    s.append(Paragraph("Option B: From Source (Developers)", styles['H2']))
    s.append(Paragraph("brew install libusb python3", styles['CodeBlock']))
    s.append(Paragraph("pip3 install -r requirements.txt", styles['CodeBlock']))
    s.append(Paragraph("cd src &amp;&amp; python3 main.py", styles['CodeBlock']))
    s.append(Paragraph(
        "Use <b>--terminal</b> flag to force terminal mode instead of the menu bar app.",
        styles['Note']))
    s.append(PageBreak())

    # ═══ 3. INSTALLATION - Windows ═══
    s.append(Paragraph("3. Installation - Windows", styles['H1']))
    s.append(Paragraph("Step 1: Install Python", styles['H3']))
    s.append(Paragraph(
        "Download and install Python 3.9+ from https://python.org. "
        "Make sure to check <b>\"Add Python to PATH\"</b> during installation.",
        styles['Body']))
    s.append(Paragraph("Step 2: Install Dependencies", styles['H3']))
    s.append(Paragraph("pip install -r requirements.txt", styles['CodeBlock']))
    s.append(Paragraph("Step 3: Install the MIDI Remote Script", styles['H3']))
    s.append(Paragraph("Copy <b>Ableton_Push2.js</b> to:", styles['Body']))
    s.append(Paragraph(
        "%APPDATA%\\Steinberg\\Nuendo\\MIDI Remote\\Driver Scripts\\Local\\Ableton\\Push2\\",
        styles['CodeBlock']))
    s.append(Paragraph("Step 4: Run the Bridge", styles['H3']))
    s.append(Paragraph("cd src", styles['CodeBlock']))
    s.append(Paragraph("python main.py --terminal", styles['CodeBlock']))
    s.append(Paragraph(
        "On Windows, the bridge runs in terminal mode. A future version may include a system tray app.",
        styles['Note']))
    s.append(PageBreak())

    # ═══ 4. FIRST LAUNCH ═══
    s.append(Paragraph("4. First Launch", styles['H1']))
    s.append(Paragraph("Follow this order for the first launch:", styles['Body']))
    s.append(B("Connect your Push 2 via USB and make sure it's powered on"))
    s.append(B("Launch the Push 2 Nuendo Bridge app"))
    s.append(B("Open Nuendo (the MIDI Remote script will load automatically)"))
    s.append(B("Configure the MIDI ports in Nuendo (see next section)"))
    s.append(Spacer(1, 12))

    s.append(Paragraph("Menu Bar Icon (macOS)", styles['H2']))
    s.append(Paragraph("The menu bar shows a <b>P2</b> icon with a status indicator:", styles['Body']))
    s.append(T(['Icon', 'Meaning'],
        [['P2 (checkmark)', 'Push 2 and Nuendo are both connected'],
         ['P2 (hourglass)', 'Waiting for Push 2 or Nuendo'],
         ['P2 (x)', 'Not running or connection failed']],
        col_widths=[1.8*inch, 3.8*inch]))
    s.append(Spacer(1, 12))
    s.append(Paragraph(
        "Click the P2 icon to access the menu: Start/Stop Bridge, Show Logs, "
        "Start at Login, and Quit.", styles['Body']))
    s.append(Paragraph(
        "<b>Start at Login:</b> When enabled, the bridge launches automatically when you log in. "
        "It will wait for the Push 2 to be connected before activating.", styles['Note']))
    s.append(PageBreak())

    # ═══ 5. NUENDO CONFIGURATION ═══
    s.append(Paragraph("5. Nuendo Configuration", styles['H1']))

    s.append(Paragraph("Automatic Setup", styles['H2']))
    s.append(Paragraph(
        "The MIDI Remote script is designed to configure itself automatically. "
        "When you launch Nuendo with the bridge running, Nuendo will detect the script "
        "and assign the MIDI ports on its own. No manual configuration is required.",
        styles['Body']))
    s.append(Paragraph(
        "After Nuendo starts, the Push 2 screen should light up and display your tracks "
        "within a few seconds. If it does, you're all set.",
        styles['Body']))
    s.append(Spacer(1, 12))

    s.append(Paragraph("Manual Setup (if needed)", styles['H2']))
    s.append(Paragraph(
        "If the automatic detection does not work, you can configure the controller manually:",
        styles['Body']))
    s.append(Paragraph("1. Open a project in Nuendo.", styles['Body']))
    s.append(Paragraph("2. Go to <b>Studio &gt; Studio Setup</b>, select <b>MIDI Remote</b>, "
        "then click <b>Open MIDI Remote Manager</b>.", styles['Body']))
    s.append(Paragraph("3. Click <b>+ Add Surface</b>.", styles['Body']))
    s.append(Paragraph("4. Select <b>Ableton</b> as Vendor and <b>Push 2 for Nuendo</b> as Model.", styles['Body']))
    s.append(Paragraph("5. Assign the MIDI ports:", styles['Body']))
    s.append(T(['Port Name', 'Assignment'],
        [['NuendoBridge Out (Input)', 'NuendoBridge Out'],
         ['NuendoBridge In (Output)', 'NuendoBridge In']],
        col_widths=[2.5*inch, 3*inch]))
    s.append(Spacer(1, 8))
    s.append(Paragraph("6. Click <b>Activate MIDI Controller Surface</b>.", styles['Body']))
    s.append(Spacer(1, 12))

    s.append(Paragraph(
        "<b>Note:</b> Nuendo may create multiple instances of the controller in the MIDI Remote Manager. "
        "This is a known Nuendo behavior and does not affect functionality.",
        styles['Note']))
    s.append(Spacer(1, 12))

    s.append(Paragraph("Notes Port (Optional)", styles['H2']))
    s.append(Paragraph(
        "For MIDI note input from the Push 2 pads, add <b>BridgeNotes</b> as a MIDI input "
        "in your instrument tracks' input routing, or enable <b>In All MIDI Inputs</b> for "
        "<b>BridgeNotes</b> in <b>Studio &gt; Studio Setup &gt; MIDI Port Setup</b>.",
        styles['Body']))
    s.append(PageBreak())

    # ═══ 6. USING THE BRIDGE ═══
    s.append(Paragraph("6. Using the Bridge", styles['H1']))
    s.append(Paragraph("Display Layout", styles['H2']))
    s.append(Paragraph(
        "The Push 2 screen is divided into 8 vertical zones, one per encoder. "
        "Each zone shows track information for the 8 tracks in the current bank. "
        "Use the Left/Right arrow buttons to navigate between banks of 8 tracks.", styles['Body']))
    s.append(Paragraph("Modes", styles['H2']))
    s.append(Paragraph(
        "The bridge has several display modes, each showing different information and "
        "assigning different functions to the encoders:", styles['Body']))
    s.append(T(['Button', 'Mode', 'Encoders Control'],
        [['Mix', 'Volume', '8 track volume faders'],
         ['Shift+Mix', 'Track', 'Combined Vol+Pan+Sends for selected track'],
         ['Clip', 'Sends', '8 sends of the selected track'],
         ['Shift+Clip', 'Pan', '8 track pan knobs'],
         ['Device', 'Quick Controls', '8 QC of the selected track'],
         ['Browse', 'Inserts', 'Insert plugin parameters']],
        col_widths=[1.3*inch, 1.2*inch, 3*inch]))
    s.append(Paragraph("Lower Row Buttons", styles['H2']))
    s.append(Paragraph(
        "The 8 buttons below the screen toggle between Mute, Solo, Monitor, and Record Arm:", styles['Body']))
    s.append(B("Press <b>Mute</b> button to toggle between Mute and Monitor mode"))
    s.append(B("Press <b>Solo</b> button to toggle between Solo and Record Arm mode"))
    s.append(B("<b>Shift+Mute</b> = Clear all mutes"))
    s.append(B("<b>Shift+Solo</b> = Clear all solos"))
    s.append(PageBreak())

    # ═══ 7. MIXER MODES ═══
    s.append(Paragraph("7. Mixer Modes", styles['H1']))
    s.append(Paragraph("Volume Mode (Mix button)", styles['H2']))
    s.append(Paragraph(
        "Shows 8 tracks with volume bars, VU meters, and peak clip indicators. "
        "Turn an encoder to adjust the volume of the corresponding track. "
        "The display shows the dB value and a visual bar.", styles['Body']))
    s.append(Paragraph(
        "A red bar indicates the track volume is above 0 dB. "
        "Peak clip is indicated by a red outline on the VU meter.", styles['Body']))
    s.append(B("<b>Shift + Upper row button</b> = Clear peak clip for that track"))
    s.append(B("<b>Long press upper row</b> (1 second) = Open instrument UI"))
    s.append(Spacer(1, 12))
    s.append(Paragraph("Pan Mode (Shift+Clip)", styles['H2']))
    s.append(Paragraph(
        "Shows 8 tracks with pan position indicators. Turn an encoder to adjust pan. "
        "The display shows L/C/R position.", styles['Body']))
    s.append(Spacer(1, 12))
    s.append(Paragraph("Track Mode (Shift+Mix)", styles['H2']))
    s.append(Paragraph(
        "Combined mode showing Volume, Pan, and 6 Sends for the selected track on a single screen. "
        "Encoder 1 = Volume, Encoder 2 = Pan, Encoders 3-8 = Sends 1-6.", styles['Body']))
    s.append(PageBreak())

    # ═══ 8. SENDS MODE ═══
    s.append(Paragraph("8. Sends Mode", styles['H1']))
    s.append(Paragraph(
        "Press <b>Clip</b> to enter Sends mode. Shows 8 sends of the selected track "
        "with destination names and level controls.", styles['Body']))
    s.append(B("<b>Encoders</b> = Adjust send levels"))
    s.append(B("<b>Upper row buttons</b> = Toggle send On/Off"))
    s.append(B("<b>Lower row buttons</b> = Toggle Pre/Post fader"))
    s.append(B("<b>Left/Right arrows</b> = Navigate between tracks"))
    s.append(Paragraph(
        "LED colors: White = On, Dim = Off. Blue = Pre-fader, Orange = Post-fader.", styles['Note']))

    # ═══ 9. INSERTS MODE ═══
    s.append(Paragraph("9. Inserts Mode", styles['H1']))
    s.append(Paragraph(
        "Press <b>Browse</b> to enter Inserts mode. Shows 8 insert slots of the selected track.",
        styles['Body']))
    s.append(Paragraph("List View", styles['H2']))
    s.append(B("Shows plugin names in each slot (or 'No Insert' if empty)"))
    s.append(B("<b>Upper row button</b> = Enter parameter view for that insert"))
    s.append(B("<b>Shift + Upper row button</b> = Enter parameters + open plugin UI"))
    s.append(B("<b>Lower row buttons</b> = Toggle bypass per slot"))
    s.append(B("<b>Left/Right arrows</b> = Navigate between tracks"))
    s.append(Paragraph("Parameter View", styles['H2']))
    s.append(Paragraph("When viewing a plugin's parameters:", styles['Body']))
    s.append(B("<b>Encoders</b> = Adjust 8 parameters"))
    s.append(B("<b>Left/Right arrows</b> = Navigate parameter banks"))
    s.append(B("<b>Lower row button 1</b> = Open/Close plugin UI"))
    s.append(B("<b>Lower row button 2</b> = Bypass toggle"))
    s.append(B("<b>Lower row button 3</b> = Deactivate plugin"))
    s.append(B("Press <b>Browse</b> again to return to list view"))
    s.append(PageBreak())

    # ═══ 10. QUICK CONTROLS ═══
    s.append(Paragraph("10. Quick Controls (Device Mode)", styles['H1']))
    s.append(Paragraph(
        "Press <b>Device</b> to enter Quick Controls mode. Shows 8 Quick Controls "
        "of the selected track (configurable in Nuendo's Inspector).", styles['Body']))
    s.append(B("<b>Encoders</b> = Adjust QC values"))
    s.append(B("<b>Lower row button 1</b> = Open instrument UI"))
    s.append(B("<b>Left/Right arrows</b> = Navigate between tracks"))

    # ═══ 11. TRANSPORT ═══
    s.append(Paragraph("11. Transport Controls", styles['H1']))
    s.append(T(['Button', 'Function', 'LED Feedback'],
        [['Play', 'Start playback', 'White=Stop, Green=Play, Purple=Play+Loop'],
         ['Record', 'Toggle recording', 'Red when active'],
         ['Fixed Length', 'Toggle Cycle/Loop', ''],
         ['Automate', 'Automation cycle', 'White=Off, Green=Read, Red=Write'],
         ['Metronome', 'Toggle metronome', 'LED reflects state'],
         ['Undo', 'Undo last action', '']],
        col_widths=[1.3*inch, 1.8*inch, 2.5*inch]))

    # ═══ 12. AUTOMATION ═══
    s.append(Paragraph("12. Automation", styles['H1']))
    s.append(Paragraph(
        "Press the <b>Automate</b> button to cycle through automation modes:", styles['Body']))
    s.append(B("Off -> Read -> Read+Write -> Write -> Off"))
    s.append(Paragraph(
        "The Automate button LED indicates the current state: "
        "White = Off, Green = Read, Red = Write. "
        "Per-track R/W indicators appear below the Record icon on the display.", styles['Body']))
    s.append(PageBreak())

    # ═══ 13. TOUCHSTRIP ═══
    s.append(Paragraph("13. Touchstrip", styles['H1']))
    s.append(Paragraph(
        "The touchstrip on the left side of the Push 2 has three modes. "
        "Press <b>Shift+Layout</b> to cycle between them:", styles['Body']))
    s.append(T(['Mode', 'Function'],
        [['Pitch Bend', 'Standard pitch bend (spring return to center)'],
         ['Mod Wheel', 'Modulation wheel (CC 1, position maintained)'],
         ['Volume', "Controls the selected track's volume fader"]],
        col_widths=[1.5*inch, 4*inch]))
    s.append(Paragraph("An overlay message appears briefly on screen when switching modes.", styles['Body']))

    # ═══ 14. NOTE INPUT ═══
    s.append(Paragraph("14. Note Input", styles['H1']))
    s.append(Paragraph("The 64 pads can be used for MIDI note input in two modes:", styles['Body']))
    s.append(B("<b>Chromatic mode</b> (default): Notes laid out in a grid pattern"))
    s.append(B("<b>Drum mode</b> (press Layout): 4x4 drum pad grid"))
    s.append(Spacer(1, 8))
    s.append(B("<b>Scale button</b>: Opens the scale selector (choose scale and root note)"))
    s.append(B("<b>Accent button</b>: Hold for fixed velocity (adjustable with the first encoder)"))
    s.append(B("<b>Note Repeat</b>: Hold for automatic note repeat at the selected subdivision"))
    s.append(B("<b>Tempo Encoder</b> (top left knob): When Note Repeat is active, adjusts the "
        "repeat tempo (40-300 BPM)"))
    s.append(Paragraph(
        "<b>Note:</b> The Note Repeat tempo is independent from the project tempo. "
        "It controls only the speed of the repeated notes.",
        styles['Note']))
    s.append(Paragraph(
        "Make sure to set your instrument track's MIDI input to <b>BridgeNotes</b> in Nuendo, "
        "or enable <b>In All MIDI Inputs</b> for BridgeNotes in "
        "<b>Studio &gt; Studio Setup &gt; MIDI Port Setup</b>.", styles['Note']))

    # ═══ 15. CONTROL ROOM ═══
    s.append(Paragraph("15. Control Room", styles['H1']))
    s.append(Paragraph(
        "Press <b>User</b> to enter Control Room mode (press again to exit). "
        "The Control Room has 4 pages, selectable via lower row buttons 5-8:", styles['Body']))
    s.append(B("<b>Main</b>: Main level, Click level, Listen level, Ref level, Listen Dim"))
    s.append(B("<b>Phones</b>: Phones level, Click level, Listen level"))
    s.append(B("<b>Cues</b>: Cue 1-4 levels"))
    s.append(B("<b>Sources</b>: Monitor A/B levels, Talkback Dim"))
    s.append(Paragraph(
        "The <b>Master encoder</b> (top right) always controls the Control Room Main level, "
        "regardless of the current mode. Hold <b>User</b> + Master encoder for Phones level.",
        styles['Body']))
    s.append(PageBreak())

    # ═══ 16. BUTTON REFERENCE ═══
    s.append(Paragraph("16. Button Reference", styles['H1']))
    s.append(T(['Button', 'Action', 'Shift + Button'],
        [['Mix', 'Volume mode', 'Track mode'],
         ['Clip', 'Sends mode', 'Pan mode'],
         ['Device', 'Quick Controls mode', ''],
         ['Browse', 'Inserts mode', ''],
         ['Left / Right', 'Bank navigation', 'Track nav (Sends/Inserts/Device)'],
         ['Play', 'Start playback', ''],
         ['Record', 'Record toggle', ''],
         ['Fixed Length', 'Cycle/Loop toggle', ''],
         ['Automate', 'Automation cycle', ''],
         ['Metronome', 'Metronome toggle', ''],
         ['Undo', 'Undo', ''],
         ['Mute', 'Mute / Monitor toggle', 'Clear all mutes'],
         ['Solo', 'Solo / Rec arm toggle', 'Clear all solos'],
         ['Add Track', 'Add Track dialog', ''],
         ['New', 'New Track Version', ''],
         ['Duplicate', 'Duplicate Track', 'Duplicate Track Version'],
         ['Delete', 'Delete', ''],
         ['User', 'Control Room mode', ''],
         ['Layout', 'Drum/Chromatic toggle', 'Touchstrip mode cycle'],
         ['Scale', 'Scale selector', ''],
         ['Accent', 'Fixed velocity (hold)', ''],
         ['Note Repeat', 'Auto-repeat (hold)', ''],
         ['Tempo Encoder', 'Repeat BPM (when active)', ''],
         ['Upper row (long)', 'Open instrument UI', ''],
         ['Lower row 7 + Shift', 'Rescan tracks', '']],
        col_widths=[1.5*inch, 2.2*inch, 2.2*inch]))
    s.append(PageBreak())

    # ═══ 17. MIDI CHANNEL ALLOCATION ═══
    s.append(Paragraph("17. MIDI Channel Allocation", styles['H1']))
    s.append(Paragraph("The bridge uses multiple MIDI channels to avoid CC conflicts:", styles['Body']))
    s.append(T(['Channel', 'Usage'],
        [['1 (0xB0)', 'Mixer controls (volume, pan, transport, selection, VU meters)'],
         ['2 (0xB1)', 'Insert plugin parameters'],
         ['3 (0xB2)', 'Send levels for the selected track'],
         ['4 (0xB3)', 'Insert bypass toggles'],
         ['5 (0xB4)', 'Quick Controls'],
         ['6 (0xB5)', 'Control Room knobs and buttons'],
         ['16 (0xBF)', 'Heartbeat (connection monitoring)']],
        col_widths=[1.3*inch, 4.5*inch]))
    s.append(Paragraph("Virtual MIDI Ports", styles['H2']))
    s.append(Paragraph(
        "The bridge creates the following virtual MIDI ports automatically at startup:", styles['Body']))
    s.append(T(['Port Name', 'Purpose'],
        [['NuendoBridge In', 'Nuendo sends to Bridge (Bridge listens)'],
         ['NuendoBridge Out', 'Bridge sends to Nuendo (Nuendo listens)'],
         ['BridgeNotes', 'Note output from Push 2 pads to Nuendo instruments'],
         ['BridgeNotes In', 'Playback note feedback from Nuendo to Push 2 pads']],
        col_widths=[1.8*inch, 4*inch]))
    s.append(PageBreak())

    # ═══ 18. TROUBLESHOOTING ═══
    s.append(Paragraph("18. Troubleshooting", styles['H1']))
    problems = [
        ("Push 2 not found",
         "Check that the Push 2 is connected via USB and powered on. "
         "Make sure libusb is installed (macOS: brew install libusb). "
         "Make sure Ableton Live is not running (it locks the USB connection)."),
        ("No connection to Nuendo",
         "Make sure the bridge app is running before Nuendo, or use Stop/Start Bridge in the menu. "
         "Check that the MIDI Remote ports are correctly assigned in Studio Setup: "
         "Input = NuendoBridge Out, Output = NuendoBridge In."),
        ("Screen shows nothing after Stop/Start",
         "The bridge reuses the existing Push 2 USB connection. If the screen remains blank, "
         "quit and relaunch the app."),
        ("Track names not loading",
         "Navigate with the Left/Right arrows to force a bank refresh, "
         "or press Shift + 7th lower row button to trigger a full rescan of all tracks."),
        ("Peak clip indicators at startup",
         "This is normal. The bridge applies a 3-second grace period after connection "
         "to filter spurious peak signals."),
        ("Volume/Pan jumps when first adjusted",
         "If the initial values were not synced, navigate away and back to the bank "
         "to force a refresh."),
        ("Logs location",
         "macOS: ~/Library/Logs/Push2NuendoBridge.log. "
         "Windows: logs are printed directly in the terminal window. "
         "You can redirect them to a file by running: python main.py --terminal > bridge.log 2>&1"),
    ]
    for title, desc in problems:
        s.append(Paragraph(f"<b>{title}</b>", styles['BodyBold']))
        s.append(Paragraph(desc, styles['Body']))
        s.append(Spacer(1, 4))
    s.append(PageBreak())

    # ═══ 19. KNOWN ISSUES ═══
    s.append(Paragraph("19. Known Issues", styles['H1']))
    s.append(Paragraph(
        "The following are known limitations of the current version:",
        styles['Body']))
    s.append(Spacer(1, 8))

    issues = [
        ("Occasional bridge restart needed",
         "In some cases, the bridge may lose synchronization with Nuendo. "
         "If the Push 2 display becomes unresponsive or shows stale data, "
         "use Stop/Start Bridge from the menu bar, or quit and relaunch the app."),
        ("Occasional MIDI Remote script reload needed",
         "Nuendo may occasionally lose the connection to the MIDI Remote script, "
         "especially after extended sessions or after waking from sleep. "
         "If controls stop responding but the display still updates, reload the script "
         "in Nuendo via the MIDI Remote tab (right-click the info line, enable Scripting Tools, "
         "then click Reload Scripts)."),
        ("127 track limit",
         "The bridge supports a maximum of 127 tracks due to the 7-bit MIDI CC value range "
         "used for track indexing. Projects with more than 127 tracks will only show "
         "the first 127 on the Push 2."),
        ("Track add/move/delete glitches",
         "Adding, deleting, reordering, or renaming tracks while the bridge is running "
         "may cause temporary display inconsistencies. Press Shift + 7th lower row button "
         "to trigger a full rescan, or navigate away and back with the Left/Right arrows."),
        ("Input and Output tracks display",
         "Input and Output bus tracks (including the Stereo Out) may display incorrect "
         "names or parameters. These special track types are not fully supported by the "
         "Steinberg MIDI Remote API's mixer bank zone."),
    ]
    for title, desc in issues:
        s.append(Paragraph(f"<b>{title}</b>", styles['BodyBold']))
        s.append(Paragraph(desc, styles['Body']))
        s.append(Spacer(1, 4))
    s.append(PageBreak())

    # ═══ 20. SUPPORT ═══
    s.append(Paragraph("20. Support", styles['H1']))
    s.append(Paragraph(
        "Push 2 / Nuendo Bridge is donationware. It is free to use, but if you find it useful, "
        "please consider supporting the project.", styles['Body']))
    s.append(Spacer(1, 12))
    s.append(Paragraph("Links", styles['H2']))
    s.append(B("GitHub: https://github.com/mbourque-mix/Push2Nuendo-Bridge"))
    s.append(B("Buy Me A Coffee: https://buymeacoffee.com/mbourque"))
    s.append(B("Report issues: https://github.com/mbourque-mix/Push2Nuendo-Bridge/issues"))
    s.append(Spacer(1, 20))
    s.append(Paragraph("License", styles['H2']))
    s.append(Paragraph(
        "This project is licensed under the GNU General Public License v3.0 (GPL-3.0). "
        "See the LICENSE file included with the distribution for full terms.", styles['Body']))
    s.append(Spacer(1, 20))
    s.append(Paragraph("Developer Certificate of Origin (DCO)", styles['H2']))
    s.append(Paragraph(
        "This project uses the Developer Certificate of Origin (DCO) to ensure that "
        "all contributions can be legally distributed under the GPL-3.0 license. "
        "By contributing, you certify that you have the right to submit the code "
        "under this license.", styles['Body']))
    s.append(Paragraph(
        "To sign off on your contribution, add a <b>Signed-off-by</b> line to each "
        "commit message using the <b>-s</b> flag:", styles['Body']))
    s.append(Paragraph("git commit -s -m \"Your commit message\"", styles['CodeBlock']))
    s.append(Paragraph(
        "This adds a line like: Signed-off-by: Your Name &lt;your@email.com&gt;", styles['Body']))
    s.append(Paragraph(
        "The full text of the DCO is available at https://developercertificate.org/", styles['Body']))
    s.append(Spacer(1, 20))
    s.append(Paragraph("Credits", styles['H2']))
    s.append(Paragraph(
        "Built with push2-python (https://github.com/ffont/push2-python) and the "
        "Steinberg MIDI Remote API.", styles['Body']))

    doc.build(s, onFirstPage=add_page_number, onLaterPages=add_page_number)
    print(f"PDF generated: {path}")

if __name__ == "__main__":
    build()
