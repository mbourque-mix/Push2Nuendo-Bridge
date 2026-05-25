// =============================================================================
// Ableton_Push2.js — MIDI Remote Script for Nuendo / Cubase
// Version 1.0.5
//
// Un seul bank zone de 8 canaux.
// Banking via mNextBank/mPrevBank (CC 8/9).
// Scan via selButtons[0-7].setProcessValue (CC 5 start, mOnIdle séquentiel).
// Noms/couleurs via mTrackSelection → mOnTitleChange/mOnColorChange.
//
// CC 20-27 : Volume     CC 40-47 : Pan
// CC 48-55 : Send 1     CC 56-63 : Quick Controls
// CC 80-87 : Sélection  CC 8/9 : Bank next/prev
// CC 90-97 : Mute       CC 100-107 : Solo
// CC 110-117 : Monitor  CC 118-125 : Record Arm
// CC 50-53 : Transport  CC 5 : Start scan  CC 7 : Stop scan
// =============================================================================

var JS_VERSION = '1.0.5';

var midiremote_api = require('midiremote_api_v1');

var deviceDriver = midiremote_api.makeDeviceDriver(
    'Ableton',
    'Push 2 for Nuendo',
    'Push2-Nuendo-Bridge'
);

// ── PORTS ──
// Only the bridge loop ports are needed in the JS script.
// Push 2 USB/MIDI and note routing are handled entirely by the Python bridge.
var midiInput_Loop  = deviceDriver.mPorts.makeMidiInput('NuendoBridge Out');
var midiOutput_Loop = deviceDriver.mPorts.makeMidiOutput('NuendoBridge In');

// ── AUTO-DETECTION ──
var detection = deviceDriver.makeDetectionUnit();
detection.detectPortPair(midiInput_Loop, midiOutput_Loop)
    .expectInputNameContains('NuendoBridge')
    .expectOutputNameContains('NuendoBridge');

var surface = deviceDriver.mSurface;

// ── KNOBS ──
var knobsVol = [], knobsPan = [], knobsSend = [], knobsQC = [];
for (var i = 0; i < 8; i++) {
    var kv = surface.makeKnob(i*3, 0, 3, 3);
    kv.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 20+i);
    knobsVol.push(kv);
    var kp = surface.makeKnob(i*3, 2, 3, 3);
    kp.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 40+i);
    knobsPan.push(kp);
    var ks = surface.makeKnob(i*3, 4, 3, 3);
    ks.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(6, 48+i);
    knobsSend.push(ks);
    var kq = surface.makeKnob(i*3, 6, 3, 3);
    kq.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(4, 56+i);
    knobsQC.push(kq);
}

// Boutons Up/Down pour changer de send (CC 46/47)
var sendNextBtn = surface.makeButton(8, 6, 3, 2);
sendNextBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 46);
var sendPrevBtn = surface.makeButton(12, 6, 3, 2);
sendPrevBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 47);

// ── BOUTONS ──
var selButtons = [], muteButtons = [], soloButtons = [], monitorButtons = [], recButtons = [];
var editorOpenButtons = [];
for (var i = 0; i < 8; i++) {
    var sb = surface.makeButton(i*3, 8, 3, 2);
    sb.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).setOutputPort(midiOutput_Loop).bindToControlChange(0, 80+i);
    selButtons.push(sb);
    var mb = surface.makeButton(i*3, 10, 3, 2);
    mb.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).setOutputPort(midiOutput_Loop).bindToControlChange(0, 90+i);
    muteButtons.push(mb);
    var slb = surface.makeButton(i*3, 12, 3, 2);
    slb.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).setOutputPort(midiOutput_Loop).bindToControlChange(0, 100+i);
    soloButtons.push(slb);
    var mnb = surface.makeButton(i*3, 14, 3, 2);
    mnb.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).setOutputPort(midiOutput_Loop).bindToControlChange(0, 110+i);
    monitorButtons.push(mnb);
    var rb = surface.makeButton(i*3, 16, 3, 2);
    rb.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).setOutputPort(midiOutput_Loop).bindToControlChange(0, 118+i);
    recButtons.push(rb);
    // Edit Channel Settings toggle (Note 70+i)
    var eb = surface.makeButton(i*3, 19, 3, 2);
    eb.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToNote(0, 70+i);
    editorOpenButtons.push(eb);
}

// ── SEND ENABLE BUTTONS (CC 60-67) ──
var sendEnableButtons = [];
for (var i = 0; i < 8; i++) {
    var seb = surface.makeButton(i*3, 17, 3, 2);
    seb.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).setOutputPort(midiOutput_Loop).bindToControlChange(0, 60+i);
    sendEnableButtons.push(seb);
}

// ── SELECTED TRACK TOGGLE BUTTONS (CC 10-13) ──
// Pour le mode Overview : toggle mute/solo/rec/monitor sur la piste sélectionnée
var selMuteBtn = surface.makeButton(0, 30, 3, 2);
selMuteBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 10);
var selSoloBtn = surface.makeButton(4, 30, 3, 2);
selSoloBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 12);
var selRecBtn = surface.makeButton(8, 30, 3, 2);
selRecBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 13);
var selMonBtn = surface.makeButton(12, 30, 3, 2);
selMonBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 14);

// ── AI KNOB (Mouse Pointer) CC 64, relative mode ──
var aiKnob = surface.makeKnob(0, 26, 3, 3);
aiKnob.mSurfaceValue.mMidiBinding
    .setInputPort(midiInput_Loop)
    .bindToControlChange(0, 64)
    .setTypeRelativeSignedBit();
var scanBtn = surface.makeButton(0, 18, 3, 2);
scanBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 5);
var absSelBtn = surface.makeButton(4, 18, 3, 2);
absSelBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 6);
var stopScanBtn = surface.makeButton(8, 18, 3, 2);
stopScanBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 7);

// ── BANK NAVIGATION ──
var bankNextBtn = surface.makeButton(0, 20, 3, 2);
bankNextBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 8);
var bankPrevBtn = surface.makeButton(4, 20, 3, 2);
bankPrevBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 9);

// ── NUDGE NAVIGATION (shift by 1 track) ──
var shiftRightBtn = surface.makeButton(8, 20, 3, 2);
shiftRightBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 38);
var shiftLeftBtn = surface.makeButton(12, 20, 3, 2);
shiftLeftBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 39);

// ── TRANSPORT ──
var transportPlay = surface.makeButton(0, 22, 3, 2);
transportPlay.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 50);
var transportStop = surface.makeButton(4, 22, 3, 2);
transportStop.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 51);
var transportRecord = surface.makeButton(8, 22, 3, 2);
transportRecord.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 52);
var transportCycle = surface.makeButton(12, 22, 3, 2);
transportCycle.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 53);

// ── UNDO / REDO ──
var undoBtn = surface.makeButton(0, 24, 3, 2);
undoBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 54);
var redoBtn = surface.makeButton(4, 24, 3, 2);
redoBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 55);

// ── AUTOMATION READ/WRITE (piste sélectionnée) ──
var autoReadBtn = surface.makeButton(8, 24, 3, 2);
autoReadBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 56);
var autoWriteBtn = surface.makeButton(12, 24, 3, 2);
autoWriteBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 57);

// ── METRONOME (CC 58) ──
var metronomeBtn = surface.makeButton(0, 26, 3, 2);
metronomeBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 58);

// ── CONTROL ROOM VOLUME (CC 65, relative) ──
var crVolumeKnob = surface.makeKnob(4, 26, 3, 3);
crVolumeKnob.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop)
    .bindToControlChange(0, 65)
    .setTypeRelativeSignedBit();

// ══════════════════════════════════════════════════
// MAPPING
// ══════════════════════════════════════════════════
var page = deviceDriver.mMapping.makePage('Push2');

var bankZone = page.mHostAccess.mMixConsole.makeMixerBankZone()
    .setFollowVisibility(true);

page.makeActionBinding(bankNextBtn.mSurfaceValue, bankZone.mAction.mNextBank);
page.makeActionBinding(bankPrevBtn.mSurfaceValue, bankZone.mAction.mPrevBank);

// Nudge by 1 track (mShiftLeft/mShiftRight — API 1.2+)
try {
    page.makeActionBinding(shiftRightBtn.mSurfaceValue, bankZone.mAction.mShiftRight);
    page.makeActionBinding(shiftLeftBtn.mSurfaceValue, bankZone.mAction.mShiftLeft);
    console.log('Bank shift (nudge ±1) OK');
} catch(e) {
    console.log('Bank shift not available: ' + e);
}

// Send index actif (0-7), changé par CC 46/47 ou CC 19 (set direct)
var currentSendIndex = 0;

// Bouton pour set le send index directement (CC 19, bridge → JS)
var setSendIdxBtn = surface.makeButton(16, 6, 3, 2);
setSendIdxBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 19);
setSendIdxBtn.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
    var idx = Math.round(value * 127);
    if (idx >= 0 && idx < 8) currentSendIndex = idx;
};

// État on/off de chaque send × canal
var sendOnState = [];
for (var s = 0; s < 8; s++) {
    var row = [];
    for (var i = 0; i < 8; i++) row.push(true);
    sendOnState.push(row);
}

sendNextBtn.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
    if (value > 0.5 && currentSendIndex < 7) {
        currentSendIndex++;
        // Notifie le bridge du send actif
        midiOutput_Loop.sendMidi(activeDevice, [0xB0, 19, currentSendIndex]);
    }
};
sendPrevBtn.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
    if (value > 0.5 && currentSendIndex > 0) {
        currentSendIndex--;
        midiOutput_Loop.sendMidi(activeDevice, [0xB0, 19, currentSendIndex]);
    }
};

// Custom variables pour les 8 sends × 8 canaux
var sendVars = [];  // sendVars[send][channel]
for (var s = 0; s < 8; s++) {
    var sendRow = [];
    for (var i = 0; i < 8; i++) {
        sendRow.push(surface.makeCustomValueVariable('send_' + s + '_' + i));
    }
    sendVars.push(sendRow);
}

// Custom variables pour le send enable (on/off) × 8 sends × 8 canaux
var sendOnVars = [];  // sendOnVars[send][channel]
for (var s = 0; s < 8; s++) {
    var sendOnRow = [];
    for (var i = 0; i < 8; i++) {
        sendOnRow.push(surface.makeCustomValueVariable('sendOn_' + s + '_' + i));
    }
    sendOnVars.push(sendOnRow);
}

for (var i = 0; i < 8; i++) {
    var ch = bankZone.makeMixerBankChannel();
    page.makeValueBinding(knobsVol[i].mSurfaceValue, ch.mValue.mVolume);
    page.makeValueBinding(knobsPan[i].mSurfaceValue, ch.mValue.mPan);
    
    // VU Meter → bridge (CC 30-37)
    var vuVar = surface.makeCustomValueVariable('vu_' + i);
    page.makeValueBinding(vuVar, ch.mValue.mVUMeter);
    vuVar.mOnProcessValueChange = (function(idx) {
        return function(activeDevice, value, diff) {
            var val = Math.round(value * 127);
            // Filtrer les valeurs max parasites (artefact lors du changement de bank/sélection)
            if (val < 127) {
                midiOutput_Loop.sendMidi(activeDevice, [0xB0, 30 + idx, val]);
            }
        };
    })(i);
    
    // Binder les 8 sends (level + on) pour chaque canal
    for (var s = 0; s < 8; s++) {
        page.makeValueBinding(sendVars[s][i], ch.mSends.getByIndex(s).mLevel);
        page.makeValueBinding(sendOnVars[s][i], ch.mSends.getByIndex(s).mOn);
        
        // Display value des sends → bridge via SysEx 0x07
        // Payload: [sendIndex, channelIndex, ...chars]
        sendVars[s][i].mOnDisplayValueChange = (function(sendIdx, chIdx) {
            return function(activeDevice, value, units) {
                var str = value + ' ' + units;
                var msg = [0xF0, 0x00, 0x21, 0x09, 0x07, sendIdx & 0x7F, chIdx & 0x7F];
                for (var c = 0; c < Math.min(str.length, 16); c++) {
                    msg.push(str.charCodeAt(c) & 0x7F);
                }
                msg.push(0xF7);
                midiOutput_Loop.sendMidi(activeDevice, msg);
            };
        })(s, i);
    }
    
    // Le knob send route vers le bon send via setProcessValue
    knobsSend[i].mSurfaceValue.mOnProcessValueChange = (function(idx) {
        return function(activeDevice, value, diff) {
            sendVars[currentSendIndex][idx].setProcessValue(activeDevice, value);
        };
    })(i);
    
    // Le bouton send enable toggle le send actif
    // On track l'état dans un tableau
    sendEnableButtons[i].mSurfaceValue.mOnProcessValueChange = (function(idx) {
        return function(activeDevice, value, diff) {
            if (value > 0.5) {
                var current = sendOnVars[currentSendIndex][idx];
                var isOn = sendOnState[currentSendIndex][idx];
                current.setProcessValue(activeDevice, isOn ? 0.0 : 1.0);
            }
        };
    })(i);
    // Feedback send enable → bridge
    // On met un callback sur chaque sendOnVar pour chaque send
    for (var s = 0; s < 8; s++) {
        sendOnVars[s][i].mOnProcessValueChange = (function(sendIdx, chIdx) {
            return function(activeDevice, value, diff) {
                sendOnState[sendIdx][chIdx] = (value > 0.5);
                // N'envoyer le feedback que pour le send actif
                if (sendIdx == currentSendIndex) {
                    midiOutput_Loop.sendMidi(activeDevice, [0xB0, 24 + chIdx, value > 0.5 ? 127 : 0]);
                }
            };
        })(s, i);
    }

    page.makeValueBinding(selButtons[i].mSurfaceValue, ch.mValue.mSelected);
    page.makeValueBinding(muteButtons[i].mSurfaceValue, ch.mValue.mMute);
    page.makeValueBinding(soloButtons[i].mSurfaceValue, ch.mValue.mSolo);
    page.makeValueBinding(monitorButtons[i].mSurfaceValue, ch.mValue.mMonitorEnable);
    page.makeValueBinding(recButtons[i].mSurfaceValue, ch.mValue.mRecordEnable);
    page.makeValueBinding(editorOpenButtons[i].mSurfaceValue, ch.mValue.mEditorOpen).setTypeToggle();

    // Per-track automation Read/Write feedback → bridge (SysEx tag 0x0E).
    // [F0 00 21 09 0E idx kind value F7]  kind: 0=read, 1=write.
    // Selected-track CC 17/18 only covered the selected track, so non-selected
    // bank tracks never reflected automation-mode changes (#2).
    var autoReadVar = surface.makeCustomValueVariable('autoRead_' + i);
    page.makeValueBinding(autoReadVar, ch.mValue.mAutomationRead);
    autoReadVar.mOnProcessValueChange = (function(idx) {
        return function(activeDevice, value, diff) {
            midiOutput_Loop.sendMidi(activeDevice,
                [0xF0, 0x00, 0x21, 0x09, 0x0E, idx & 0x7F, 0, value > 0.5 ? 1 : 0, 0xF7]);
        };
    })(i);
    var autoWriteVar = surface.makeCustomValueVariable('autoWrite_' + i);
    page.makeValueBinding(autoWriteVar, ch.mValue.mAutomationWrite);
    autoWriteVar.mOnProcessValueChange = (function(idx) {
        return function(activeDevice, value, diff) {
            midiOutput_Loop.sendMidi(activeDevice,
                [0xF0, 0x00, 0x21, 0x09, 0x0E, idx & 0x7F, 1, value > 0.5 ? 1 : 0, 0xF7]);
        };
    })(i);

    // Instrument Open : CC 15 channel 2 + index via Note (on utilise un bouton dédié par canal)
    // Note 80+i channel 1 = toggle instrument UI pour canal i
    var instrOpenBtn = surface.makeButton(80 + i, 88, 2, 2);
    instrOpenBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToNote(0, 80 + i);
    page.makeValueBinding(instrOpenBtn.mSurfaceValue, ch.mValue.mInstrumentOpen).setTypeToggle();

    knobsVol[i].mSurfaceValue.mOnProcessValueChange = (function(idx) {
        return function(activeDevice, value, diff) {
            midiOutput_Loop.sendMidi(activeDevice, [0xB0, 20 + idx, Math.round(value * 127)]);
        };
    })(i);
    
    // Pan feedback → bridge (CC 40-47)
    knobsPan[i].mSurfaceValue.mOnProcessValueChange = (function(idx) {
        return function(activeDevice, value, diff) {
            midiOutput_Loop.sendMidi(activeDevice, [0xB0, 40 + idx, Math.round(value * 127)]);
        };
    })(i);
    knobsVol[i].mSurfaceValue.mOnDisplayValueChange = (function(idx) {
        return function(activeDevice, value, units) {
            var str = value + ' ' + units;
            var msg = [0xF0, 0x00, 0x21, 0x09, 0x04, idx & 0x7F];
            for (var c = 0; c < Math.min(str.length, 16); c++) {
                msg.push(str.charCodeAt(c) & 0x7F);
            }
            msg.push(0xF7);
            midiOutput_Loop.sendMidi(activeDevice, msg);
        };
    })(i);
    
    // Nom de piste automatique via le bank zone (pas besoin de sélectionner)
    knobsVol[i].mSurfaceValue.mOnTitleChange = (function(idx) {
        return function(activeDevice, objectTitle, valueTitle) {
            // objectTitle = nom de la piste
            var msg = [0xF0, 0x00, 0x21, 0x09, 0x01, idx & 0x7F];
            for (var c = 0; c < Math.min(objectTitle.length, 24); c++) {
                msg.push(objectTitle.charCodeAt(c) & 0x7F);
            }
            msg.push(0xF7);
            midiOutput_Loop.sendMidi(activeDevice, msg);
            
            // Envoyer aussi la couleur stockée pour cette piste
            if (bankColors[idx]) {
                midiOutput_Loop.sendMidi(activeDevice,
                    [0xF0, 0x00, 0x21, 0x09, 0x02, idx & 0x7F,
                     bankColors[idx][0], bankColors[idx][1], bankColors[idx][2], 0xF7]);
            }
        };
    })(i);
    
    // Couleur de piste automatique via le bank zone
    // Stocker dans bankColors pour pouvoir les renvoyer avec le nom
    knobsVol[i].mSurfaceValue.mOnColorChange = (function(idx) {
        return function(activeDevice, r, g, b, a, isActive) {
            var cr = Math.round(r * 127);
            var cg = Math.round(g * 127);
            var cb = Math.round(b * 127);
            bankColors[idx] = [cr, cg, cb];
            midiOutput_Loop.sendMidi(activeDevice,
                [0xF0, 0x00, 0x21, 0x09, 0x02, idx & 0x7F, cr, cg, cb, 0xF7]);
        };
    })(i);
    selButtons[i].mSurfaceValue.mOnProcessValueChange = (function(idx) {
        return function(activeDevice, value, diff) {
            if (value > 0.5) {
                lastSelectedIndex = idx;
                if (!scanActive && scanCooldown <= 0) {
                    midiOutput_Loop.sendMidi(activeDevice, [0xB0, 11, idx & 0x7F]);
                }
            }
        };
    })(i);
}

// Quick Controls
var selectedCh = page.mHostAccess.mTrackSelection.mMixerChannel;

// Edit Channel Settings toggle for the SELECTED channel (Note 0/78).
// Independent of bank position — always acts on the focused channel.
var selEditSettingsBtn = surface.makeButton(0, 92, 2, 2);
selEditSettingsBtn.mSurfaceValue.mMidiBinding
    .setInputPort(midiInput_Loop)
    .bindToNote(0, 78);
page.makeValueBinding(selEditSettingsBtn.mSurfaceValue,
                      selectedCh.mValue.mEditorOpen).setTypeToggle();

// Separate read binding so the bridge knows when the Channel Settings window
// is open/closed (the setTypeToggle button doesn't reliably report state).
// SysEx 0x3E: [F0 00 3E open(0/1) F7]
var selEditStateVar = surface.makeCustomValueVariable('sel_editor_open_r');
page.makeValueBinding(selEditStateVar, selectedCh.mValue.mEditorOpen);
selEditStateVar.mOnProcessValueChange = function(activeDevice, value, diff) {
    midiOutput_Loop.sendMidi(activeDevice,
        [0xF0, 0x00, 0x3E, value >= 0.5 ? 1 : 0, 0xF7]);
};

for (var i = 0; i < 8; i++) {
    page.makeValueBinding(knobsQC[i].mSurfaceValue, selectedCh.mQuickControls.getByIndex(i));
    
    // Feedback QC process value → bridge via SysEx 0x0D (valeur normalisée)
    knobsQC[i].mSurfaceValue.mOnProcessValueChange = (function(idx) {
        return function(activeDevice, value, diff) {
            var msg = [0xF0, 0x00, 0x21, 0x09, 0x0D, idx & 0x7F, Math.round(value * 127) & 0x7F, 0xF7];
            midiOutput_Loop.sendMidi(activeDevice, msg);
        };
    })(i);
    
    // Feedback QC display value → bridge via SysEx 0x0B
    knobsQC[i].mSurfaceValue.mOnDisplayValueChange = (function(idx) {
        return function(activeDevice, value, units) {
            var str = value + ' ' + units;
            var msg = [0xF0, 0x00, 0x21, 0x09, 0x0B, idx & 0x7F];
            for (var c = 0; c < Math.min(str.length, 16); c++) {
                msg.push(str.charCodeAt(c) & 0x7F);
            }
            msg.push(0xF7);
            midiOutput_Loop.sendMidi(activeDevice, msg);
        };
    })(i);
    
    // Feedback QC title → bridge via SysEx 0x0C
    knobsQC[i].mSurfaceValue.mOnTitleChange = (function(idx) {
        return function(activeDevice, objectTitle, valueTitle) {
            var str = valueTitle || objectTitle || '---';
            var msg = [0xF0, 0x00, 0x21, 0x09, 0x0C, idx & 0x7F];
            for (var c = 0; c < Math.min(str.length, 16); c++) {
                msg.push(str.charCodeAt(c) & 0x7F);
            }
            msg.push(0xF7);
            midiOutput_Loop.sendMidi(activeDevice, msg);
        };
    })(i);
}

// ══════════════════════════════════════════════
// SENDS DE LA PISTE SÉLECTIONNÉE (noms, on/off, pre/post)
// ══════════════════════════════════════════════
var selTrackSends = page.mHostAccess.mTrackSelection.mMixerChannel.mSends;

// 8 sends : nom, on/off toggle (Note 90-97), pre/post toggle (Note 100-107)
var sendNameVars = [];
var sendOnSelVars = [];
var sendPrePostVars = [];

for (var ss = 0; ss < 8; ss++) {
    var sendSlot = selTrackSends.getByIndex(ss);
    
    // Nom du send (via mOnTitleChange du level)
    var sendNameVar = surface.makeCustomValueVariable('selSendName_' + ss);
    page.makeValueBinding(sendNameVar, sendSlot.mLevel);
    sendNameVars.push(sendNameVar);
    
    sendNameVar.mOnTitleChange = (function(idx) {
        return function(activeDevice, objectTitle, valueTitle) {
            // objectTitle = nom de la destination (ex: "FX 1 - Reverb")
            var name = objectTitle || '';
            var bytes = [0xF0, 0x00, 0x18, idx & 0x7F];
            for (var c = 0; c < name.length && c < 20; c++) {
                bytes.push(name.charCodeAt(c) & 0x7F);
            }
            bytes.push(0xF7);
            midiOutput_Loop.sendMidi(activeDevice, bytes);
        };
    })(ss);
    
    // Display value du level
    sendNameVar.mOnDisplayValueChange = (function(idx) {
        return function(activeDevice, value, units) {
            var str = value || '';
            var bytes = [0xF0, 0x00, 0x19, idx & 0x7F];
            for (var c = 0; c < str.length && c < 16; c++) {
                bytes.push(str.charCodeAt(c) & 0x7F);
            }
            bytes.push(0xF7);
            midiOutput_Loop.sendMidi(activeDevice, bytes);
        };
    })(ss);
    
    // On/Off toggle via Note 90+ss
    var sendOnBtn = surface.makeButton(90 + ss, 90, 2, 2);
    sendOnBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToNote(0, 90 + ss);
    page.makeValueBinding(sendOnBtn.mSurfaceValue, sendSlot.mOn).setTypeToggle();
    sendOnSelVars.push(sendOnBtn);
    
    // Feedback On/Off → bridge SysEx 0x1A [idx, on]
    sendSlot.mOn.mOnProcessValueChange = (function(idx) {
        return function(activeDevice, activeMapping, value) {
            midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x1A, idx & 0x7F, value > 0.5 ? 1 : 0, 0xF7]);
        };
    })(ss);
    
    // Pre/Post toggle via Note 100+ss
    var sendPrePostBtn = surface.makeButton(100 + ss, 92, 2, 2);
    sendPrePostBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToNote(0, 100 + ss);
    page.makeValueBinding(sendPrePostBtn.mSurfaceValue, sendSlot.mPrePost).setTypeToggle();
    sendPrePostVars.push(sendPrePostBtn);
    
    // Feedback Pre/Post → bridge SysEx 0x1B [idx, prepost]
    sendSlot.mPrePost.mOnProcessValueChange = (function(idx) {
        return function(activeDevice, activeMapping, value) {
            midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x1B, idx & 0x7F, value > 0.5 ? 1 : 0, 0xF7]);
        };
    })(ss);
}
console.log("Selected Track Sends OK (8 sends)");

// Knobs pour les send levels de la piste sélectionnée (CC 20-27 channel 3)
for (var sk = 0; sk < 8; sk++) {
    var sendKnob = surface.makeKnob(sk * 3, 94, 2, 2);
    sendKnob.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop)
        .bindToControlChange(2, 20 + sk).setTypeRelativeSignedBit();
    page.makeValueBinding(sendKnob.mSurfaceValue, selTrackSends.getByIndex(sk).mLevel);
}
console.log("Send Level Knobs OK (ch3 CC20-27)");

// Transport
page.makeValueBinding(transportPlay.mSurfaceValue, page.mHostAccess.mTransport.mValue.mStart).setTypeToggle();
page.makeValueBinding(transportStop.mSurfaceValue, page.mHostAccess.mTransport.mValue.mStop).setTypeToggle();
page.makeValueBinding(transportRecord.mSurfaceValue, page.mHostAccess.mTransport.mValue.mRecord).setTypeToggle();
page.makeValueBinding(transportCycle.mSurfaceValue, page.mHostAccess.mTransport.mValue.mCycleActive).setTypeToggle();

// Undo / Redo
page.makeCommandBinding(undoBtn.mSurfaceValue, 'Edit', 'Undo');
page.makeCommandBinding(redoBtn.mSurfaceValue, 'Edit', 'Redo');

// Navigation piste par piste (pour mode Overview, sans banking)
// CC 3 = select next track, CC 4 = select previous track
var selNextTrackBtn = surface.makeButton(16, 30, 3, 2);
selNextTrackBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 3);
var selPrevTrackBtn = surface.makeButton(20, 30, 3, 2);
selPrevTrackBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 4);
page.makeCommandBinding(selNextTrackBtn.mSurfaceValue, 'Navigate', 'Down');
page.makeCommandBinding(selPrevTrackBtn.mSurfaceValue, 'Navigate', 'Up');

// New Track (CC 72 - Add Track button)
var newTrackBtn = surface.makeButton(24, 30, 3, 2);
newTrackBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 72);
page.makeCommandBinding(newTrackBtn.mSurfaceValue, 'AddTrack', 'OpenDialog');

// Duplicate Track (CC 69)
var dupTrackBtn = surface.makeButton(28, 30, 3, 2);
dupTrackBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 69);
page.makeCommandBinding(dupTrackBtn.mSurfaceValue, 'Project', 'Duplicate Tracks');

// Duplicate Track Version (CC 70)
var dupVersionBtn = surface.makeButton(32, 30, 3, 2);
dupVersionBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 70);
page.makeCommandBinding(dupVersionBtn.mSurfaceValue, 'TrackVersions', 'Duplicate Version');

// New Track Version (CC 71 - New button)
var newVersionBtn = surface.makeButton(36, 30, 3, 2);
newVersionBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 71);
page.makeCommandBinding(newVersionBtn.mSurfaceValue, 'TrackVersions', 'New Version');

// Deactivate All Solo States (CC 74)
var clearSoloBtn = surface.makeButton(74, 14, 2, 2);
clearSoloBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 74);
page.makeCommandBinding(clearSoloBtn.mSurfaceValue, 'Edit', 'Deactivate All Solo');

// Deactivate All Mute States (CC 75)
var clearMuteBtn = surface.makeButton(75, 14, 2, 2);
clearMuteBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 75);
page.makeCommandBinding(clearMuteBtn.mSurfaceValue, 'Edit', 'Unmute All');

// Delete selected clip (CC 76)
var deleteClipBtn = surface.makeButton(76, 16, 2, 2);
deleteClipBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 76);
page.makeCommandBinding(deleteClipBtn.mSurfaceValue, 'Edit', 'Delete');

// Remove selected tracks (CC 16)
var removeTracksBtn = surface.makeButton(16, 16, 2, 2);
removeTracksBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 16);
page.makeCommandBinding(removeTracksBtn.mSurfaceValue, 'Project', 'Remove Selected Tracks');

// AI Knob (Mouse Pointer)
page.makeValueBinding(aiKnob.mSurfaceValue, page.mHostAccess.mMouseCursor.mValueUnderMouse);

// Metronome
page.makeValueBinding(metronomeBtn.mSurfaceValue,
    page.mHostAccess.mTransport.mValue.mMetronomeActive).setTypeToggle();

// Feedback métronome → bridge (CC 22)
metronomeBtn.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
    midiOutput_Loop.sendMidi(activeDevice, [0xB0, 22, value > 0.5 ? 127 : 0]);
};

// ══════════════════════════════════════════════════════════════
// CONTROL ROOM BINDINGS
// ══════════════════════════════════════════════════════════════
var cr = page.mHostAccess.mControlRoom;
var crMain = cr.mMainChannel;
var crPhones = cr.getPhonesChannelByIndex(0);

// Helper : créer un knob relatif sur un CC
function makeCRKnob(cc) {
    var k = surface.makeKnob(cc, 40, 2, 2);
    k.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(5, cc).setTypeRelativeSignedBit();
    return k;
}

// Helper : create a toggle button on a CC (channel 6)
function makeCRBtn(cc) {
    var b = surface.makeButton(cc, 42, 2, 2);
    b.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(5, cc);
    return b;
}

// Helper : feedback valeur vers bridge via SysEx 0x0E [param_id, value_0_127]
function crFeedback(paramId) {
    return function(activeDevice, value, numValue) {
        var val127 = Math.round(numValue * 127);
        midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x0E, paramId & 0x7F, val127 & 0x7F, 0xF7]);
    };
}

// Helper : feedback display value (texte dB) via SysEx 0x10 [param_id, ...chars]
function crDisplayFeedback(paramId) {
    return function(activeDevice, value, numValue, units) {
        var text = String(numValue);
        var bytes = [0xF0, 0x00, 0x10, paramId & 0x7F];
        for (var i = 0; i < text.length && i < 20; i++) {
            bytes.push(text.charCodeAt(i) & 0x7F);
        }
        bytes.push(0xF7);
        midiOutput_Loop.sendMidi(activeDevice, bytes);
    };
}

// Helper : feedback toggle vers bridge via SysEx 0x0F [param_id, 0/1]
function crToggleFeedback(paramId) {
    return function(activeDevice, value, numValue) {
        midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x0F, paramId & 0x7F, numValue > 0.5 ? 1 : 0, 0xF7]);
    };
}

try {
    // ── PAGE MAIN : Encodeurs ──
    var crMainLevelKnob = makeCRKnob(91);
    page.makeValueBinding(crMainLevelKnob.mSurfaceValue, crMain.mLevelValue);
    crMain.mLevelValue.mOnProcessValueChange = crFeedback(0);
    crMain.mLevelValue.mOnDisplayValueChange = crDisplayFeedback(0);

    var crMainClickLvlKnob = makeCRKnob(92);
    page.makeValueBinding(crMainClickLvlKnob.mSurfaceValue, crMain.mMetronomeClickLevelValue);
    crMain.mMetronomeClickLevelValue.mOnProcessValueChange = crFeedback(1);
    crMain.mMetronomeClickLevelValue.mOnDisplayValueChange = crDisplayFeedback(1);

    var crMainListenLvlKnob = makeCRKnob(93);
    page.makeValueBinding(crMainListenLvlKnob.mSurfaceValue, crMain.mListenLevelValue);
    crMain.mListenLevelValue.mOnProcessValueChange = crFeedback(2);
    crMain.mListenLevelValue.mOnDisplayValueChange = crDisplayFeedback(2);

    var crRefLevelKnob = makeCRKnob(94);
    page.makeValueBinding(crRefLevelKnob.mSurfaceValue, cr.mReferenceLevelValue);
    cr.mReferenceLevelValue.mOnProcessValueChange = crFeedback(3);
    cr.mReferenceLevelValue.mOnDisplayValueChange = crDisplayFeedback(3);

    var crListenDimKnob = makeCRKnob(95);
    page.makeValueBinding(crListenDimKnob.mSurfaceValue, cr.mListenDimLevelValue);
    cr.mListenDimLevelValue.mOnProcessValueChange = crFeedback(4);
    cr.mListenDimLevelValue.mOnDisplayValueChange = crDisplayFeedback(4);

    // ── PAGE MAIN : Boutons toggle ──
    var crDimBtn = makeCRBtn(11);
    page.makeValueBinding(crDimBtn.mSurfaceValue, crMain.mDimActiveValue).setTypeToggle();
    crMain.mDimActiveValue.mOnProcessValueChange = crToggleFeedback(10);

    var crRefEnableBtn = makeCRBtn(15);
    page.makeValueBinding(crRefEnableBtn.mSurfaceValue, crMain.mReferenceLevelEnabledValue).setTypeToggle();
    crMain.mReferenceLevelEnabledValue.mOnProcessValueChange = crToggleFeedback(11);

    var crMonABtn = makeCRBtn(17);
    page.makeValueBinding(crMonABtn.mSurfaceValue, cr.getSelectTargetMonitorValueByIndex(0)).setTypeToggle();
    cr.getSelectTargetMonitorValueByIndex(0).mOnProcessValueChange = function(activeDevice, value, numValue) {
        midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x0F, 12, numValue > 0.5 ? 1 : 0, 0xF7]);
    };
    
    var crMonBBtn = makeCRBtn(18);
    page.makeValueBinding(crMonBBtn.mSurfaceValue, cr.getSelectTargetMonitorValueByIndex(1)).setTypeToggle();
    cr.getSelectTargetMonitorValueByIndex(1).mOnProcessValueChange = function(activeDevice, value, numValue) {
        midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x0F, 13, numValue > 0.5 ? 1 : 0, 0xF7]);
    };

    var crTalkbackBtn = makeCRBtn(28);
    page.makeValueBinding(crTalkbackBtn.mSurfaceValue, cr.mTalkbackActiveValue).setTypeToggle();
    cr.mTalkbackActiveValue.mOnProcessValueChange = crToggleFeedback(14);

    var crMainClickOnBtn = makeCRBtn(29);
    page.makeValueBinding(crMainClickOnBtn.mSurfaceValue, crMain.mMetronomeClickActiveValue).setTypeToggle();
    crMain.mMetronomeClickActiveValue.mOnProcessValueChange = crToggleFeedback(15);

    var crMainListenOnBtn = makeCRBtn(30);
    page.makeValueBinding(crMainListenOnBtn.mSurfaceValue, crMain.mListenEnabledValue).setTypeToggle();
    crMain.mListenEnabledValue.mOnProcessValueChange = crToggleFeedback(16);

    // Cue select pour Main (exclusive)
    var crMainCue1Btn = makeCRBtn(31);
    page.makeValueBinding(crMainCue1Btn.mSurfaceValue, crMain.getSelectSourceCueValueByIndex(0)).setTypeToggle();
    var crMainCue2Btn = makeCRBtn(49);
    page.makeValueBinding(crMainCue2Btn.mSurfaceValue, crMain.getSelectSourceCueValueByIndex(1)).setTypeToggle();
    var crMainCue3Btn = makeCRBtn(71);
    page.makeValueBinding(crMainCue3Btn.mSurfaceValue, crMain.getSelectSourceCueValueByIndex(2)).setTypeToggle();
    var crMainCue4Btn = makeCRBtn(72);
    page.makeValueBinding(crMainCue4Btn.mSurfaceValue, crMain.getSelectSourceCueValueByIndex(3)).setTypeToggle();
    
    // Feedback Cue select Main via host values
    for (var ci = 0; ci < 4; ci++) {
        (function(idx) {
            crMain.getSelectSourceCueValueByIndex(idx).mOnProcessValueChange = function(activeDevice, value, numValue) {
                midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x0F, 17 + idx, numValue > 0.5 ? 1 : 0, 0xF7]);
            };
        })(ci);
    }

    // Main Level Reset -> exact 0.00 dB
    // CC 78 (any value > 0) writes the precise normalized value that maps to
    // 0.00 dB on crMain.mLevelValue. A 7-bit absolute value binding cannot hit
    // this exactly (it lands at ~-0.01 dB). Host values have no setProcessValue,
    // so we bind a dedicated surface value to crMain.mLevelValue and write the
    // exact float through it (setProcessValue propagates via the binding).
    var CR_MAIN_0DB = 0.748222231;  // measured via high-res feedback
    var crMainResetValue = surface.makeCustomValueVariable('crMainReset');
    page.makeValueBinding(crMainResetValue, crMain.mLevelValue);
    var crMainResetBtn = surface.makeButton(78, 40, 2, 2);
    crMainResetBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 78);
    crMainResetBtn.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, numValue) {
        if (numValue > 0) {
            crMainResetValue.setProcessValue(activeDevice, CR_MAIN_0DB);
        }
    };

    // Main Mute
    var crMainMuteBtn = makeCRBtn(73);
    page.makeValueBinding(crMainMuteBtn.mSurfaceValue, crMain.mMuteValue).setTypeToggle();
    crMain.mMuteValue.mOnProcessValueChange = crToggleFeedback(22);

    // ── PAGE PHONES : Encodeurs ──
    var crPhonesLevelKnob = makeCRKnob(96);
    page.makeValueBinding(crPhonesLevelKnob.mSurfaceValue, crPhones.mLevelValue);
    crPhones.mLevelValue.mOnProcessValueChange = crFeedback(30);
    crPhones.mLevelValue.mOnDisplayValueChange = crDisplayFeedback(30);

    var crPhonesClickLvlKnob = makeCRKnob(97);
    page.makeValueBinding(crPhonesClickLvlKnob.mSurfaceValue, crPhones.mMetronomeClickLevelValue);
    crPhones.mMetronomeClickLevelValue.mOnProcessValueChange = crFeedback(31);
    crPhones.mMetronomeClickLevelValue.mOnDisplayValueChange = crDisplayFeedback(31);

    var crPhonesListenLvlKnob = makeCRKnob(98);
    page.makeValueBinding(crPhonesListenLvlKnob.mSurfaceValue, crPhones.mListenLevelValue);
    crPhones.mListenLevelValue.mOnProcessValueChange = crFeedback(32);
    crPhones.mListenLevelValue.mOnDisplayValueChange = crDisplayFeedback(32);

    // ── PAGE PHONES : Boutons ──
    var crPhonesClickOnBtn = makeCRBtn(36);
    page.makeValueBinding(crPhonesClickOnBtn.mSurfaceValue, crPhones.mMetronomeClickActiveValue).setTypeToggle();
    crPhones.mMetronomeClickActiveValue.mOnProcessValueChange = crToggleFeedback(40);

    var crPhonesListenOnBtn = makeCRBtn(37);
    page.makeValueBinding(crPhonesListenOnBtn.mSurfaceValue, crPhones.mListenEnabledValue).setTypeToggle();
    crPhones.mListenEnabledValue.mOnProcessValueChange = crToggleFeedback(41);

    var crPhonesCue1Btn = makeCRBtn(38);
    page.makeValueBinding(crPhonesCue1Btn.mSurfaceValue, crPhones.getSelectSourceCueValueByIndex(0)).setTypeToggle();
    var crPhonesCue2Btn = makeCRBtn(39);
    page.makeValueBinding(crPhonesCue2Btn.mSurfaceValue, crPhones.getSelectSourceCueValueByIndex(1)).setTypeToggle();
    var crPhonesCue3Btn = makeCRBtn(32);
    page.makeValueBinding(crPhonesCue3Btn.mSurfaceValue, crPhones.getSelectSourceCueValueByIndex(2)).setTypeToggle();
    var crPhonesCue4Btn = makeCRBtn(33);
    page.makeValueBinding(crPhonesCue4Btn.mSurfaceValue, crPhones.getSelectSourceCueValueByIndex(3)).setTypeToggle();
    
    // Feedback Cue select Phones via host values
    for (var ci = 0; ci < 4; ci++) {
        (function(idx) {
            crPhones.getSelectSourceCueValueByIndex(idx).mOnProcessValueChange = function(activeDevice, value, numValue) {
                midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x0F, 42 + idx, numValue > 0.5 ? 1 : 0, 0xF7]);
            };
        })(ci);
    }

    var crPhonesMuteBtn = makeCRBtn(34);
    page.makeValueBinding(crPhonesMuteBtn.mSurfaceValue, crPhones.mMuteValue).setTypeToggle();
    crPhones.mMuteValue.mOnProcessValueChange = crToggleFeedback(46);

    // ── PAGE CUE : Encodeurs (4 cues) ──
    var crCue = [];
    var cueLevelCCs = [41, 42, 43, 44];
    var cueMuteCCs = [35, 66, 67, 68];
    for (var c = 0; c < 4; c++) {
        var cue = cr.getCueChannelByIndex(c);
        crCue.push(cue);
        var cueLvlKnob = makeCRKnob(cueLevelCCs[c]);
        page.makeValueBinding(cueLvlKnob.mSurfaceValue, cue.mLevelValue);
        cue.mLevelValue.mOnProcessValueChange = crFeedback(50 + c);
        cue.mLevelValue.mOnDisplayValueChange = crDisplayFeedback(50 + c);

        var cueMuteBtn = makeCRBtn(cueMuteCCs[c]);
        page.makeValueBinding(cueMuteBtn.mSurfaceValue, cue.mMuteValue).setTypeToggle();
        cue.mMuteValue.mOnProcessValueChange = crToggleFeedback(54 + c);
    }

    // ── PAGE MONITORS : Encodeurs ──
    var crMon0LevelKnob = makeCRKnob(45);
    page.makeValueBinding(crMon0LevelKnob.mSurfaceValue, cr.getMonitorChannelByIndex(0).mLevelValue);
    cr.getMonitorChannelByIndex(0).mLevelValue.mOnProcessValueChange = crFeedback(60);
    cr.getMonitorChannelByIndex(0).mLevelValue.mOnDisplayValueChange = crDisplayFeedback(60);

    var crMon1LevelKnob = makeCRKnob(62);
    page.makeValueBinding(crMon1LevelKnob.mSurfaceValue, cr.getMonitorChannelByIndex(1).mLevelValue);
    cr.getMonitorChannelByIndex(1).mLevelValue.mOnProcessValueChange = crFeedback(61);
    cr.getMonitorChannelByIndex(1).mLevelValue.mOnDisplayValueChange = crDisplayFeedback(61);

    // Talkback dim level
    var crTbDimKnob = makeCRKnob(63);
    page.makeValueBinding(crTbDimKnob.mSurfaceValue, cr.mTalkbackDimLevelValue);
    cr.mTalkbackDimLevelValue.mOnProcessValueChange = crFeedback(62);
    cr.mTalkbackDimLevelValue.mOnDisplayValueChange = crDisplayFeedback(62);

    // ── MASTER ENCODER (toujours actif, hors mode CR) ──
    var crMasterKnob = surface.makeKnob(79, 40, 2, 2);
    crMasterKnob.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 79).setTypeRelativeSignedBit();
    page.makeValueBinding(crMasterKnob.mSurfaceValue, crMain.mLevelValue);

    // Phones toujours actif via CC 77
    var crPhonesAlwaysKnob = surface.makeKnob(77, 40, 2, 2);
    crPhonesAlwaysKnob.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 77).setTypeRelativeSignedBit();
    page.makeValueBinding(crPhonesAlwaysKnob.mSurfaceValue, crPhones.mLevelValue);

    console.log('Control Room bindings OK');
} catch(e) {
    console.log('ControlRoom error: ' + e);
}

// Automation Read/Write de la piste sélectionnée
var selChAuto = page.mHostAccess.mTrackSelection.mMixerChannel;
page.makeValueBinding(autoReadBtn.mSurfaceValue, selChAuto.mValue.mAutomationRead).setTypeToggle();
page.makeValueBinding(autoWriteBtn.mSurfaceValue, selChAuto.mValue.mAutomationWrite).setTypeToggle();

// Mute/Solo/Rec/Monitor de la piste sélectionnée (pour mode Overview)
page.makeValueBinding(selMuteBtn.mSurfaceValue, selChAuto.mValue.mMute).setTypeToggle();
page.makeValueBinding(selSoloBtn.mSurfaceValue, selChAuto.mValue.mSolo).setTypeToggle();
page.makeValueBinding(selRecBtn.mSurfaceValue, selChAuto.mValue.mRecordEnable).setTypeToggle();
page.makeValueBinding(selMonBtn.mSurfaceValue, selChAuto.mValue.mMonitorEnable).setTypeToggle();

// Feedback automation → bridge
autoReadBtn.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
    midiOutput_Loop.sendMidi(activeDevice, [0xB0, 17, value > 0.5 ? 127 : 0]);
};
autoWriteBtn.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
    midiOutput_Loop.sendMidi(activeDevice, [0xB0, 18, value > 0.5 ? 127 : 0]);
};

// Feedback transport → bridge (CC 16 = is_playing)
transportPlay.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
    midiOutput_Loop.sendMidi(activeDevice, [0xB0, 16, value > 0.5 ? 127 : 0]);
};

// Feedback cycle → bridge (CC 53 = cycle active)
transportCycle.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
    midiOutput_Loop.sendMidi(activeDevice, [0xB0, 53, value > 0.5 ? 127 : 0]);
};

// Feedback record → bridge (CC 73 = is_recording)
transportRecord.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
    midiOutput_Loop.sendMidi(activeDevice, [0xB0, 73, value > 0.5 ? 127 : 0]);
};

// Tempo et position — TODO: trouver le bon chemin API
// mTransport.mValue.mTempo et mTimeDisplay ne semblent pas exister

// ── Track selection → nom et couleur ──
var nameVar = surface.makeCustomValueVariable('trackName');
page.makeValueBinding(nameVar, page.mHostAccess.mTrackSelection.mMixerChannel.mValue.mVolume);

var lastSelectedIndex = -1;
var lastColorR = 75, lastColorG = 75, lastColorB = 75;
var pendingColorForIndex = -1;
var pendingAbsSelect = -1;
var scanActive = false;
var scanTrackCounter = 0;
var scanCooldown = 0;
var bankColors = [null, null, null, null, null, null, null, null];

nameVar.mOnTitleChange = function(activeDevice, objectTitle, valueTitle) {
    if (scanActive) {
        // Pendant le scan : lastSelectedIndex est set par mOnIdle avant setProcessValue
        var idx = lastSelectedIndex;
        if (idx >= 0 && idx < 8) {
            var msg = [0xF0, 0x00, 0x21, 0x09, 0x01, idx & 0x7F];
            for (var c = 0; c < Math.min(objectTitle.length, 24); c++) {
                msg.push(objectTitle.charCodeAt(c) & 0x7F);
            }
            msg.push(0xF7);
            midiOutput_Loop.sendMidi(activeDevice, msg);
            pendingColorForIndex = idx;
        }
    } else if (scanCooldown <= 0 && daBypassCooldown <= 0) {
        // Hors scan et hors cooldown : envoyer le nom pour auto-switch
        var selMsg = [0xF0, 0x00, 0x21, 0x09, 0x06];
        for (var c = 0; c < Math.min(objectTitle.length, 24); c++) {
            selMsg.push(objectTitle.charCodeAt(c) & 0x7F);
        }
        selMsg.push(0xF7);
        midiOutput_Loop.sendMidi(activeDevice, selMsg);
    }
};

nameVar.mOnColorChange = function(activeDevice, r, g, b, a, isActive) {
    lastColorR = Math.round(r * 127);
    lastColorG = Math.round(g * 127);
    lastColorB = Math.round(b * 127);
    if (lastSelectedIndex >= 0) {
        var idx = lastSelectedIndex & 0x7F;
        midiOutput_Loop.sendMidi(activeDevice,
            [0xF0, 0x00, 0x21, 0x09, 0x02, idx, lastColorR, lastColorG, lastColorB, 0xF7]);
        pendingColorForIndex = -1;
    }
};

// ══════════════════════════════════════════════════
// SCAN & SELECTION
// ══════════════════════════════════════════════════
absSelBtn.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
    var idx = Math.round(value * 127);
    if (idx >= 0 && idx < 8) pendingAbsSelect = idx;
};

scanBtn.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
    if (value > 0.5 && !scanActive) {
        scanActive = true;
        scanTrackCounter = 0;
        scanDelay = 0;
    }
};

stopScanBtn.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
    scanActive = false;
};

// ══════════════════════════════════════════════════
// DIRECT ACCESS (API 1.2+ / Nuendo 14+)
// Diagnostic: explore the MixConsole object tree
// ══════════════════════════════════════════════════

var daAvailable = false;
var da = null;
var daDiagDone = false;
var daMapping = null;  // stored activeMapping from mOnActivate
var daBypassCooldown = 0;  // Suppress DA insert callbacks after our own bypass
var pluginListQueue = null;  // Plugin list send queue (used by mOnIdle)

// CC 15 = trigger DA diagnostic dump
var daDiagBtn = surface.makeButton(92, 22, 2, 2);
daDiagBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 15);

if (page.mHostAccess.makeDirectAccess) {
    var hostMixConsole = page.mHostAccess.mMixConsole;
    da = page.mHostAccess.makeDirectAccess(hostMixConsole);

    // ── DirectAccess #2: Insert Effects (on selected track) ──
    var daInsHostObj = page.mHostAccess.mTrackSelection.mMixerChannel.mInsertAndStripEffects;
    var daInserts = page.mHostAccess.makeDirectAccess(daInsHostObj);
    var daInsActive = false;
    var daInsSlotCache = [];   // [{objectID, bypassTag, title, bypassed, hasPlugin}]
    var daInsExplored = false;

    // Strip slot DA cache (indices 16-20 in the unified DA encoder system)
    // Gate=16, Compressor=17, Tools=18, Saturator=19, Limiter=20
    var daStripSlotCache = [];  // [{objectID, pluginObjectID, modId, slotTitle, pluginName, bypassed, isOn}]
    // After daEnumPluginParams builds these, mOnParameterChange can forward
    // host-side param changes back to Python (used for live EQ curve feedback).
    var daParamTagToIdxBySlot = {};   // slotIdx → {parameterTag: param_idx}
    var daParamPluginIDBySlot = {};   // slotIdx → pluginObjectID
    var daParamLastSent = {};         // "slotIdx:paramIdx" → last val127 (dedup)
    var daStripExplored = false;

    page.mOnActivate = function(activeDevice, activeMapping) {
        daMapping = activeMapping;
        daAvailable = false;
        daInsActive = false;
        daInsExplored = false;
        daInsSlotCache = [];
        daStripSlotCache = [];
        daStripExplored = false;
        midiOutput_Loop.sendMidi(activeDevice, [0xB0, 68, 1]);
        // Notify Python that strip cache is empty so it re-triggers exploration
        // on next drill-in (Python's _da_strip_explored flag wouldn't otherwise
        // know about JS-side resets like Nuendo reload).
        midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x3B, 0xF7]);
        console.log('DirectAccess ready (lazy activation)');
    };

    page.mOnDeactivate = function(activeDevice, activeMapping) {
        da.deactivate(activeMapping);
        if (daInsActive) {
            daInserts.deactivate(activeMapping);
            daInsActive = false;
        }
        daMapping = null;
        daAvailable = false;
        daInsExplored = false;
        daInsSlotCache = [];
        daStripSlotCache = [];
        daStripExplored = false;
    };

    // Send a log line to Python via SysEx 0x20
    function daLog(context, text) {
        var msg = [0xF0, 0x00, 0x21, 0x09, 0x20];
        for (var c = 0; c < Math.min(text.length, 100); c++) {
            var ch = text.charCodeAt(c) & 0x7F;
            if (ch > 0) msg.push(ch);
        }
        msg.push(0xF7);
        midiOutput_Loop.sendMidi(context, msg);
    }

    // Lazy DA activation — only activate when first needed
    function ensureDA() {
        if (!daMapping) return false;
        if (!daAvailable) {
            da.activate(daMapping);
            daAvailable = true;
            console.log('DirectAccess activated (lazy)');
        }
        return true;
    }

    daDiagBtn.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
        if (value < 0.5 || !daMapping || daDiagDone) return;
        if (!ensureDA()) return;
        daDiagDone = true;

        try {
            var m = daMapping;  // use stored activeMapping for all DA calls
            var mixConsoleID = da.getBaseObjectID(m);
            var childCount = da.getNumberOfChildObjects(m, mixConsoleID);

            console.log('=== DA DIAGNOSTIC: MixConsole ===');
            console.log('Base object ID: ' + mixConsoleID);
            console.log('Children (tracks): ' + childCount);
            daLog(activeDevice, '=== DA DIAGNOSTIC ===');
            daLog(activeDevice, 'MixConsole ID: ' + mixConsoleID + ', Children: ' + childCount);

            // Limit to first 16 tracks for readability
            var maxTracks = Math.min(childCount, 16);
            for (var i = 0; i < maxTracks; i++) {
                var childID = da.getChildObjectID(m, mixConsoleID, i);
                var title = da.getObjectTitle(m, childID);
                var visible = da.isMixerChannelVisible(m, childID);
                var position = da.getMixerChannelIndex(m, childID);

                var line = 'Track ' + i + ': "' + title + '" ID=' + childID + ' pos=' + position + ' vis=' + visible;
                console.log(line);
                daLog(activeDevice, line);

                // List parameters for the first 3 tracks only (verbose)
                if (i < 3) {
                    var paramCount = da.getNumberOfParameters(m, childID);
                    daLog(activeDevice, '  Params (' + paramCount + '):');
                    console.log('  Parameters (' + paramCount + '):');
                    for (var p = 0; p < paramCount; p++) {
                        var tag = da.getParameterTagByIndex(m, childID, p);
                        var paramTitle = da.getParameterTitle(m, childID, tag, 30);
                        var paramValue = da.getParameterProcessValue(m, childID, tag);
                        var pLine = '    [' + p + '] tag=' + tag + ' "' + paramTitle + '" val=' + paramValue.toFixed(3);
                        console.log(pLine);
                        daLog(activeDevice, pLine);
                    }
                }

                // Check API 1.3 features
                if (da.getObjectTypeName) {
                    var typeName = da.getObjectTypeName(m, childID);
                    daLog(activeDevice, '  Type: ' + typeName);
                    console.log('  Type: ' + typeName);
                }
            }

            daLog(activeDevice, '=== END DIAGNOSTIC ===');
            console.log('=== END DA DIAGNOSTIC ===');
        } catch(e) {
            console.log('DA Diagnostic error: ' + e);
            daLog(activeDevice, 'ERROR: ' + e);
        }
    };

    // ── DA Clear All Monitor (CC 66) ──
    var daClearMonBtn = surface.makeButton(86, 22, 2, 2);
    daClearMonBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 66);
    daClearMonBtn.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
        if (value < 0.5 || !daMapping) return;
        if (!ensureDA()) return;
        try {
            var m = daMapping;
            var mixConsoleID = da.getBaseObjectID(m);
            var childCount = da.getNumberOfChildObjects(m, mixConsoleID);
            var cleared = 0;
            for (var i = 0; i < childCount; i++) {
                var childID = da.getChildObjectID(m, mixConsoleID, i);
                da.setParameterProcessValue(m, childID, 4001, 0);  // tag 4001 = Monitor
                cleared++;
            }
            // Notify Python: CC 68 val 2 = monitors cleared
            midiOutput_Loop.sendMidi(activeDevice, [0xB0, 68, 2]);
            console.log('DA: Cleared all monitors (' + cleared + ' tracks)');
        } catch(e) {
            console.log('DA Clear Monitor error: ' + e);
            // Notify Python to fallback: CC 68 val 0
            midiOutput_Loop.sendMidi(activeDevice, [0xB0, 68, 0]);
        }
    };

    // ── DA Clear All Rec (CC 67) ──
    var daClearRecBtn = surface.makeButton(89, 22, 2, 2);
    daClearRecBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 67);
    daClearRecBtn.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
        if (value < 0.5 || !daMapping) return;
        if (!ensureDA()) return;
        try {
            var m = daMapping;
            var mixConsoleID = da.getBaseObjectID(m);
            var childCount = da.getNumberOfChildObjects(m, mixConsoleID);
            var cleared = 0;
            for (var i = 0; i < childCount; i++) {
                var childID = da.getChildObjectID(m, mixConsoleID, i);
                da.setParameterProcessValue(m, childID, 4002, 0);  // tag 4002 = Record Enable
                cleared++;
            }
            // Notify Python: CC 68 val 3 = rec cleared
            midiOutput_Loop.sendMidi(activeDevice, [0xB0, 68, 3]);
            console.log('DA: Cleared all rec arms (' + cleared + ' tracks)');
        } catch(e) {
            console.log('DA Clear Rec error: ' + e);
            midiOutput_Loop.sendMidi(activeDevice, [0xB0, 68, 0]);
        }
    };

    // ── DA Toggle Mute/Solo/Mon/Rec on any track ──
    // CC 17 = set target track index, CC 18 = execute toggle (0=Mute,1=Solo,2=Mon,3=Rec)
    var daTargetTrack = 0;
    var daTrackIdxBtn = surface.makeButton(80, 24, 2, 2);
    daTrackIdxBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 17);
    daTrackIdxBtn.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
        daTargetTrack = Math.round(value * 127);
    };

    var daToggleBtn = surface.makeButton(83, 24, 2, 2);
    daToggleBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 18);
    daToggleBtn.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
        if (!daMapping) return;
        if (!ensureDA()) return;
        var func = Math.round(value * 127);  // 0=Mute, 1=Solo, 2=Monitor, 3=Record
        var tagMap = [1027, 1028, 4001, 4002];  // Mute, Solo, Monitor, Record Enable
        if (func >= tagMap.length) return;
        var tag = tagMap[func];
        // daTargetTrack is the position (1-based, matching getMixerChannelIndex)
        var targetPos = daTargetTrack + 1;  // Python track 0 = pos 1, track 1 = pos 2, etc.
        
        try {
            var m = daMapping;
            var mixConsoleID = da.getBaseObjectID(m);
            var childCount = da.getNumberOfChildObjects(m, mixConsoleID);
            
            // Find child with matching position
            for (var i = 0; i < childCount; i++) {
                var childID = da.getChildObjectID(m, mixConsoleID, i);
                var pos = da.getMixerChannelIndex(m, childID);
                if (pos === targetPos) {
                    var currentVal = da.getParameterProcessValue(m, childID, tag);
                    var newVal = (currentVal > 0.5) ? 0 : 1;
                    da.setParameterProcessValue(m, childID, tag, newVal);
                    return;
                }
            }
            console.log('DA Toggle: track pos ' + targetPos + ' not found');
        } catch(e) {
            console.log('DA Toggle error: ' + e);
        }
    };

    console.log('DirectAccess diagnostic ready (Shift+Setup to trigger)');

    // ══════════════════════════════════════════════
    // DIRECT ACCESS — INSERT BYPASS (targeted)
    // ══════════════════════════════════════════════
    // Tree structure discovered by Phase 1 exploration:
    //   Root (AudioChannel)
    //     "Inserts" (Inserts) ← find this by typeName
    //       "1" (Slot) ← bypass = tag 4102, plugin name = first child title
    //       "2" (Slot)
    //       ...
    //       "16" (Slot)
    //
    // Bypass tag is ALWAYS 4102 on Slot objects.
    // Plugin name comes from the Slot's first child (if present).

    var SLOT_BYPASS_TAG = 4102;
    var SLOT_ON_TAG = 4098;
    var SLOT_EDIT_TAG = 4101;

    function ensureDAInserts() {
        if (!daMapping) return false;
        if (!daInsActive) {
            daInserts.activate(daMapping);
            daInsActive = true;
            console.log('DirectAccess Inserts activated (lazy)');
        }
        return true;
    }

    // CC 88 = trigger insert tree exploration from Python
    var daInsExploreBtn = surface.makeButton(88, 22, 2, 2);
    daInsExploreBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 88);
    daInsExploreBtn.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
        if (value < 0.5 || !daMapping) return;
        if (!ensureDAInserts()) return;
        buildInsertCache(activeDevice, daMapping);
    };

    // CC 85 channel 8 (0xB7) = DA bypass command from Python
    // Channel 8 avoids conflict with selButtons (CC 80-87 on channel 1)
    var daBypassBtn = surface.makeButton(85, 22, 2, 2);
    daBypassBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(7, 85);
    daBypassBtn.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
        var raw = Math.round(value * 127);
        if (raw < 0 || !daMapping) return;
        if (!ensureDAInserts()) return;
        var wantBypass = (raw >= 64);
        var slotIdx = raw & 0x1F;
        daBypassSlot(activeDevice, daMapping, slotIdx, wantBypass);
    };

    // CC 86 channel 8 (0xB7) = DA edit (open/close plugin UI) from Python
    // Value = slot index (0-15)
    var daEditBtn = surface.makeButton(86, 22, 2, 2);
    daEditBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(7, 86);
    daEditBtn.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
        var slotIdx = Math.round(value * 127);
        if (slotIdx < 0 || !daMapping) return;
        if (!ensureDAInserts()) return;
        daEditSlot(activeDevice, daMapping, slotIdx);
    };

    function buildInsertCache(activeDevice, activeMapping) {
        try {
            var m = activeMapping;
            var rootID = daInserts.getBaseObjectID(m);
            if (rootID < 0) {
                console.log('DA Inserts: No base object');
                daLog(activeDevice, 'DA Inserts: rootID=-1');
                return;
            }

            daInsSlotCache = [];
            daInsExplored = false;

            // Step 1: Find the "Inserts" container among root's children
            var rootChildCount = daInserts.getNumberOfChildObjects(m, rootID);
            var insertsContainerID = -1;

            for (var i = 0; i < rootChildCount; i++) {
                var childID = daInserts.getChildObjectID(m, rootID, i);
                var typeName = '';
                if (daInserts.getObjectTypeName) {
                    typeName = daInserts.getObjectTypeName(m, childID);
                }
                if (typeName === 'Inserts') {
                    insertsContainerID = childID;
                    break;
                }
            }

            if (insertsContainerID < 0) {
                console.log('DA Inserts: "Inserts" container not found');
                daLog(activeDevice, 'DA Inserts: container not found');
                return;
            }

            // Step 2: Iterate the 16 Slot children
            var slotCount = daInserts.getNumberOfChildObjects(m, insertsContainerID);
            console.log('DA Inserts: Found ' + slotCount + ' slots');

            for (var s = 0; s < slotCount; s++) {
                var slotID = daInserts.getChildObjectID(m, insertsContainerID, s);
                var slotTitle = daInserts.getObjectTitle(m, slotID);  // "1", "2", etc.

                // Read bypass state (tag 4102) and On state (tag 4098)
                var bypassed = (daInserts.getParameterProcessValue(m, slotID, SLOT_BYPASS_TAG) > 0.5);
                var isOn = (daInserts.getParameterProcessValue(m, slotID, SLOT_ON_TAG) > 0.5);

                // Get plugin name from the Slot's first child (if any)
                var pluginName = '';
                var pluginObjID = -1;
                var pluginChildCount = daInserts.getNumberOfChildObjects(m, slotID);
                if (pluginChildCount > 0) {
                    pluginObjID = daInserts.getChildObjectID(m, slotID, 0);
                    pluginName = daInserts.getObjectTitle(m, pluginObjID);
                }

                daInsSlotCache.push({
                    objectID: slotID,
                    pluginObjectID: pluginObjID,
                    bypassTag: SLOT_BYPASS_TAG,
                    title: pluginName,
                    bypassed: bypassed,
                    hasPlugin: (pluginName.length > 0 && isOn > 0)
                });

                if (pluginName) {
                    console.log('  Slot ' + s + ': "' + pluginName + '" ' + (bypassed ? 'BYPASS' : 'ACTIVE'));
                }
            }

            daInsExplored = true;
            console.log('DA Inserts: ' + daInsSlotCache.length + ' slots cached');

            // Send each cached slot to Python via SysEx 0x24
            // Format: [F0 00 24 slotIdx tagLo tagHi bypassed ...title_chars F7]
            for (var s = 0; s < daInsSlotCache.length; s++) {
                var entry = daInsSlotCache[s];
                var tagLo = entry.bypassTag & 0x7F;
                var tagHi = (entry.bypassTag >> 7) & 0x7F;
                var msg = [0xF0, 0x00, 0x24, s & 0x7F, tagLo, tagHi, entry.bypassed ? 1 : 0];
                for (var c = 0; c < entry.title.length && c < 24; c++) {
                    msg.push(entry.title.charCodeAt(c) & 0x7F);
                }
                msg.push(0xF7);
                midiOutput_Loop.sendMidi(activeDevice, msg);
            }

            // Signal exploration complete: SysEx 0x25
            midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x25, daInsSlotCache.length & 0x7F, 0xF7]);

        } catch(e) {
            console.log('DA Inserts build error: ' + e);
            daLog(activeDevice, 'DA Inserts ERROR: ' + e);
        }
    }

    // ── DA Bypass: set bypass on a cached insert slot ──
    function daBypassSlot(activeDevice, activeMapping, slotIdx, wantBypass) {
        if (!daInsExplored || slotIdx >= daInsSlotCache.length) {
            console.log('DA Bypass: cache not ready or slot ' + slotIdx + ' out of range');
            midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x26, slotIdx & 0x7F, 0x00, 0xF7]);
            return;
        }
        try {
            var entry = daInsSlotCache[slotIdx];
            var newVal = wantBypass ? 1.0 : 0.0;
            daBypassCooldown = 10;  // Suppress callbacks for ~200ms
            daInserts.setParameterProcessValue(activeMapping, entry.objectID, entry.bypassTag, newVal);
            entry.bypassed = wantBypass;
            console.log('DA Bypass slot ' + slotIdx + ' (' + entry.title + '): ' + (wantBypass ? 'BYPASS' : 'ACTIVE'));

            // Confirm to Python: SysEx 0x26 [slotIdx, success=1, bypassed]
            midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x26, slotIdx & 0x7F, 0x01, wantBypass ? 1 : 0, 0xF7]);
        } catch(e) {
            console.log('DA Bypass error: ' + e);
            midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x26, slotIdx & 0x7F, 0x00, 0xF7]);
        }
    }

    // ── DA Edit: toggle plugin UI on a cached insert slot ──
    function daEditSlot(activeDevice, activeMapping, slotIdx) {
        if (!daInsExplored || slotIdx >= daInsSlotCache.length) {
            console.log('DA Edit: cache not ready or slot ' + slotIdx + ' out of range');
            // Notify Python to fall back: SysEx 0x28 [slotIdx, success=0]
            midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x28, slotIdx & 0x7F, 0x00, 0xF7]);
            return;
        }
        try {
            var entry = daInsSlotCache[slotIdx];
            // Read current Edit value and toggle it
            var currentVal = daInserts.getParameterProcessValue(activeMapping, entry.objectID, SLOT_EDIT_TAG);
            var newVal = (currentVal > 0.5) ? 0.0 : 1.0;
            daBypassCooldown = 10;  // Suppress callbacks
            daInserts.setParameterProcessValue(activeMapping, entry.objectID, SLOT_EDIT_TAG, newVal);
            console.log('DA Edit slot ' + slotIdx + ' (' + entry.title + '): ' + (newVal > 0.5 ? 'OPEN' : 'CLOSE'));

            // Confirm to Python: SysEx 0x28 [slotIdx, success=1]
            midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x28, slotIdx & 0x7F, 0x01, 0xF7]);
        } catch(e) {
            console.log('DA Edit error: ' + e);
            midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x28, slotIdx & 0x7F, 0x00, 0xF7]);
        }
    }

    // CC 87 channel 8 (0xB7) = enumerate plugin parameters for a slot
    // Value = slot index (0-15)
    var daEnumBtn = surface.makeButton(87, 22, 2, 2);
    daEnumBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(7, 87);
    daEnumBtn.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
        var slotIdx = Math.round(value * 127);
        if (slotIdx < 0 || !daMapping) return;
        if (!ensureDAInserts()) return;
        daEnumPluginParams(activeDevice, daMapping, slotIdx);
    };

    // ── DA Enumerate Plugin Parameters ──
    // Iterates all parameters of the plugin child object in a given slot.
    // Slot 0-15 = insert slots, slot 16-20 = strip slots (uses daGetEncEntry).
    // Sends each param to Python via SysEx 0x29, then completion via 0x2A.
    function daEnumPluginParams(activeDevice, activeMapping, slotIdx) {
        var entry = daGetEncEntry(slotIdx);
        if (!entry) {
            console.log('DA Enum: cache not ready or slot ' + slotIdx + ' out of range');
            return;
        }
        if (entry.pluginObjectID < 0) {
            console.log('DA Enum: no plugin in slot ' + slotIdx);
            // Send completion with 0 params
            midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x2A, slotIdx & 0x7F, 0, 0, 0xF7]);
            return;
        }

        try {
            var m = activeMapping;
            var pluginID = entry.pluginObjectID;
            var paramCount = daInserts.getNumberOfParameters(m, pluginID);

            // Cap to avoid flooding — most plugins have <1000 real params
            var maxParams = Math.min(paramCount, 1024);
            var entryLabel = entry.title || entry.slotTitle || ('slot' + slotIdx);
            console.log('DA Enum slot ' + slotIdx + ' (' + entryLabel + '): ' + paramCount + ' params (sending ' + maxParams + ')');

            // Build tag → param_idx map so mOnParameterChange can forward
            // host-side changes back to Python (e.g. user touching params in
            // Nuendo's GUI updates our EQ curve / cell display).
            var tagMap = {};
            for (var i = 0; i < maxParams; i++) {
                var tag = daInserts.getParameterTagByIndex(m, pluginID, i);
                tagMap[tag] = i;
            }
            daParamTagToIdxBySlot[slotIdx] = tagMap;
            daParamPluginIDBySlot[slotIdx] = pluginID;

            for (var i = 0; i < maxParams; i++) {
                var tag = daInserts.getParameterTagByIndex(m, pluginID, i);
                var title = daInserts.getParameterTitle(m, pluginID, tag, 64);
                var procVal = daInserts.getParameterProcessValue(m, pluginID, tag);
                var displayVal = '';
                if (daInserts.getParameterDisplayValue) {
                    displayVal = daInserts.getParameterDisplayValue(m, pluginID, tag) || '';
                    var units = daInserts.getParameterDisplayUnits ? daInserts.getParameterDisplayUnits(m, pluginID, tag) : '';
                    if (units) displayVal += ' ' + units;
                }

                // SysEx 0x29: [F0 00 29 slotIdx idxLo idxHi val127 tagB0 tagB1 tagB2 tagB3 ...title F7]
                var idxLo = i & 0x7F;
                var idxHi = (i >> 7) & 0x7F;
                var val127 = Math.round(procVal * 127) & 0x7F;
                // Encode tag as 4 x 7-bit bytes (supports up to 28-bit tags)
                var tagB0 = tag & 0x7F;
                var tagB1 = (tag >> 7) & 0x7F;
                var tagB2 = (tag >> 14) & 0x7F;
                var tagB3 = (tag >> 21) & 0x7F;
                var msg = [0xF0, 0x00, 0x29, slotIdx & 0x7F, idxLo, idxHi, val127, tagB0, tagB1, tagB2, tagB3];
                // Append title (truncated to 20 chars)
                for (var c = 0; c < title.length && c < 20; c++) {
                    msg.push(title.charCodeAt(c) & 0x7F);
                }
                msg.push(0xF7);
                midiOutput_Loop.sendMidi(activeDevice, msg);
            }

            // SysEx 0x2A: enumeration complete [F0 00 2A slotIdx countLo countHi F7]
            var cntLo = maxParams & 0x7F;
            var cntHi = (maxParams >> 7) & 0x7F;
            midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x2A, slotIdx & 0x7F, cntLo, cntHi, 0xF7]);

        } catch(e) {
            console.log('DA Enum error: ' + e);
            midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x2A, slotIdx & 0x7F, 0, 0, 0xF7]);
        }
    }

    // ══════════════════════════════════════════════
    // DA PLUGIN MANAGER — explore collections
    // CC 84 channel 8 = explore plugin collections for a slot
    // ══════════════════════════════════════════════

    var daPluginMgrBtn = surface.makeButton(84, 22, 2, 2);
    daPluginMgrBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(7, 84);
    daPluginMgrBtn.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
        var slotIdx = Math.round(value * 127);
        if (slotIdx < 0 || !daMapping) return;
        if (!ensureDAInserts()) return;
        daExplorePluginManager(activeDevice, daMapping, slotIdx);
    };

    function daExplorePluginManager(activeDevice, activeMapping, slotIdx) {
        if (!daInsExplored || slotIdx >= daInsSlotCache.length) {
            console.log('DA PluginMgr: cache not ready or slot ' + slotIdx + ' out of range');
            return;
        }
        var entry = daInsSlotCache[slotIdx];
        var m = activeMapping;

        try {
            if (!daInserts.mPluginManager) {
                console.log('DA PluginMgr: mPluginManager not available (API < 1.3?)');
                daLog(activeDevice, 'PluginMgr: NOT AVAILABLE');
                return;
            }

            var slotID = entry.objectID;
            daLog(activeDevice, '=== PLUGIN MANAGER DEEP EXPLORE ===');
            daLog(activeDevice, 'Slot ' + slotIdx + ' "' + entry.title + '" objID=' + slotID);

            // ── Step 1: Explore mPluginManager methods ──
            var pmMethods = '';
            for (var key in daInserts.mPluginManager) {
                var typ = typeof daInserts.mPluginManager[key];
                pmMethods += key + '(' + typ + '), ';
            }
            daLog(activeDevice, 'PM methods: ' + pmMethods.substring(0, 90));
            if (pmMethods.length > 90) {
                daLog(activeDevice, 'PM methods+: ' + pmMethods.substring(90, 180));
            }

            // ── Step 2: Check if setActivePluginCollection exists ──
            if (typeof daInserts.mPluginManager.setActivePluginCollection === 'function') {
                daLog(activeDevice, 'setActivePluginCollection: EXISTS');
            } else {
                daLog(activeDevice, 'setActivePluginCollection: NOT FOUND');
            }

            // ── Step 3: Collection count and active index ──
            var collCount = daInserts.mPluginManager.getNumberOfPluginCollections(m, slotID);
            var activeCollIdx = daInserts.mPluginManager.getIndexOfActivePluginCollection(m, slotID);
            daLog(activeDevice, 'Collections: ' + collCount + ', active: ' + activeCollIdx);

            // ── Step 4: Explore each collection ──
            for (var ci = 0; ci < collCount; ci++) {
                var coll = daInserts.mPluginManager.getPluginCollectionByIndex(m, slotID, ci);
                if (!coll) {
                    daLog(activeDevice, 'Coll ' + ci + ': null');
                    continue;
                }

                // Collection-level properties
                var collProps = '';
                for (var key in coll) {
                    var val = '';
                    try {
                        var v = coll[key];
                        if (typeof v === 'function') val = '[fn]';
                        else if (Array.isArray(v)) val = '[arr:' + v.length + ']';
                        else if (typeof v === 'object' && v !== null) val = '[obj]';
                        else val = String(v).substring(0, 30);
                    } catch(pe) { val = '[err]'; }
                    collProps += key + '=' + val + ', ';
                }
                var collName = coll.mName || ('Coll ' + ci);
                var entryCount = coll.mEntries ? coll.mEntries.length : 0;
                var marker = (ci === activeCollIdx) ? ' [ACTIVE]' : '';
                daLog(activeDevice, 'Coll ' + ci + ': "' + collName + '" (' + entryCount + ')' + marker);
                daLog(activeDevice, '  CollProps: ' + collProps.substring(0, 90));

                // ── Step 5: Deep dump of first entry properties ──
                if (entryCount > 0) {
                    var fe = coll.mEntries[0];
                    daLog(activeDevice, '  --- Entry[0] deep dump ---');
                    for (var key in fe) {
                        var val = '';
                        try {
                            var v = fe[key];
                            if (typeof v === 'function') val = '[function]';
                            else if (typeof v === 'object' && v !== null) {
                                // Recurse one level into objects
                                var subKeys = '';
                                for (var sk in v) subKeys += sk + ',';
                                val = '{' + subKeys.substring(0, 50) + '}';
                            } else {
                                val = String(v).substring(0, 60);
                            }
                        } catch(pe) { val = '[error]'; }
                        daLog(activeDevice, '    ' + key + ' = ' + val);
                    }

                    // Show first 5 entries with ALL known fields
                    var showCount = Math.min(entryCount, 5);
                    for (var ei = 0; ei < showCount; ei++) {
                        var pe = coll.mEntries[ei];
                        var pName = pe.mPluginName || '?';
                        var pVendor = pe.mPluginVendor || '';
                        var pUID = pe.mPluginUID || '';
                        var pVer = pe.mPluginVersion || '';
                        // Try undocumented fields
                        var pCat = pe.mPluginCategory || pe.mCategory || pe.mSubCategory || pe.mPluginSubCategory || '';
                        var pType = pe.mPluginType || pe.mType || '';
                        var pMedia = pe.mMediaType || pe.mPluginMediaType || '';
                        var line = '  [' + ei + '] "' + pName + '" vendor="' + pVendor + '"';
                        line += ' ver=' + pVer;
                        if (pCat) line += ' cat=' + pCat;
                        if (pType) line += ' type=' + pType;
                        if (pMedia) line += ' media=' + pMedia;
                        line += ' uid=' + pUID.substring(0, 20);
                        daLog(activeDevice, line);
                    }
                    if (entryCount > 5) {
                        daLog(activeDevice, '  ... +' + (entryCount - 5) + ' more');
                    }
                }
            }

            // ── Step 6: Test trySetSlotPlugin existence ──
            if (typeof daInserts.mPluginManager.trySetSlotPlugin === 'function') {
                daLog(activeDevice, 'trySetSlotPlugin: EXISTS');
            } else {
                daLog(activeDevice, 'trySetSlotPlugin: NOT FOUND');
            }

            // ── Step 7: Test other potential methods ──
            var testMethods = ['removeSlotPlugin', 'getSlotPlugin', 'getPluginInfo',
                               'getNumberOfPluginCategories', 'getPluginCategoryByIndex',
                               'setActivePluginCollectionByIndex'];
            for (var ti = 0; ti < testMethods.length; ti++) {
                if (typeof daInserts.mPluginManager[testMethods[ti]] === 'function') {
                    daLog(activeDevice, testMethods[ti] + ': EXISTS');
                }
            }

            daLog(activeDevice, '=== END DEEP EXPLORE ===');

        } catch(e) {
            console.log('DA PluginMgr error: ' + e);
            daLog(activeDevice, 'PluginMgr ERROR: ' + e);
        }
    }

    // ══════════════════════════════════════════════
    // DA PLUGIN LIST — send plugin collection entries to Python
    // CC 83 channel 8 = request plugin list for a collection index
    // Entries queued and sent via mOnIdle to avoid blocking
    // ══════════════════════════════════════════════

    var daPluginListBtn = surface.makeButton(83, 22, 2, 2);
    daPluginListBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(7, 83);
    daPluginListBtn.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
        var collIdx = Math.round(value * 127);
        if (!daMapping || !ensureDAInserts()) return;
        if (!daInsExplored || daInsSlotCache.length === 0) return;

        var m = daMapping;
        var slotID = daInsSlotCache[0].objectID;  // Any valid slot works

        if (!daInserts.mPluginManager) {
            console.log('DA PluginList: mPluginManager not available');
            return;
        }

        var collCount = daInserts.mPluginManager.getNumberOfPluginCollections(m, slotID);
        if (collIdx >= collCount) collIdx = collCount - 1;
        if (collIdx < 0) collIdx = 0;

        var coll = daInserts.mPluginManager.getPluginCollectionByIndex(m, slotID, collIdx);
        if (!coll || !coll.mEntries) {
            console.log('DA PluginList: collection ' + collIdx + ' is empty');
            return;
        }

        pluginListQueue = {
            coll: coll,
            collIdx: collIdx,
            collCount: collCount,
            sendIdx: 0,
            total: coll.mEntries.length,
            collName: coll.mName || ''
        };
        console.log('DA PluginList: queued ' + coll.mEntries.length + ' entries from "' + (coll.mName || '?') + '"');
    };

    console.log('DA Plugin List ready (CC 83 ch8)');

    // ══════════════════════════════════════════════
    // DA COLLECTION INFO — send all collection names and entry counts
    // CC 88 channel 8 = request collection info
    // Response: SysEx 0x2F per collection, then 0x30 completion
    // ══════════════════════════════════════════════

    var daCollInfoBtn = surface.makeButton(88, 22, 2, 2);
    daCollInfoBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(7, 88);
    daCollInfoBtn.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
        if (!daMapping || !ensureDAInserts()) return;
        if (!daInsExplored || daInsSlotCache.length === 0) return;
        if (!daInserts.mPluginManager) return;

        var m = daMapping;
        var slotID = daInsSlotCache[0].objectID;
        var collCount = daInserts.mPluginManager.getNumberOfPluginCollections(m, slotID);

        for (var ci = 0; ci < collCount; ci++) {
            try {
                var coll = daInserts.mPluginManager.getPluginCollectionByIndex(m, slotID, ci);
                var collName = (coll && coll.mName) ? coll.mName : ('Collection ' + ci);
                var entryCount = (coll && coll.mEntries) ? coll.mEntries.length : 0;
                var cntLo = entryCount & 0x7F;
                var cntHi = (entryCount >> 7) & 0x7F;
                // SysEx 0x2F: [F0 00 2F collIdx collCount cntLo cntHi ...name F7]
                var msg = [0xF0, 0x00, 0x2F, ci & 0x7F, collCount & 0x7F, cntLo, cntHi];
                for (var c = 0; c < collName.length && c < 30; c++) {
                    msg.push(collName.charCodeAt(c) & 0x7F);
                }
                msg.push(0xF7);
                midiOutput_Loop.sendMidi(activeDevice, msg);
            } catch(e) {
                console.log('DA CollInfo error at ' + ci + ': ' + e);
            }
        }
        console.log('DA CollInfo: sent ' + collCount + ' collections');
    };

    console.log('DA Collection Info ready (CC 88 ch8)');

    // ══════════════════════════════════════════════
    // DA PLUGIN LOAD — load a plugin into an insert slot
    // CC 82 ch8 = set target slot
    // CC 81 ch8 = set entry index low bits
    // CC 80 ch8 = set entry index high bits + collection index → trigger load
    // ══════════════════════════════════════════════

    var daLoadSlot = -1;
    var daLoadEntryLo = 0;

    var daLoadSlotBtn = surface.makeButton(82, 24, 2, 2);
    daLoadSlotBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(7, 82);
    daLoadSlotBtn.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
        daLoadSlot = Math.round(value * 127);
    };

    var daLoadEntryLoBtn = surface.makeButton(81, 24, 2, 2);
    daLoadEntryLoBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(7, 81);
    daLoadEntryLoBtn.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
        daLoadEntryLo = Math.round(value * 127);
    };

    var daLoadTriggerBtn = surface.makeButton(80, 24, 2, 2);
    daLoadTriggerBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(7, 80);
    daLoadTriggerBtn.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
        var raw = Math.round(value * 127);
        var entryHi = raw & 0x0F;
        var collIdx = (raw >> 4) & 0x07;
        var entryIndex = daLoadEntryLo | (entryHi << 7);

        if (daLoadSlot < 0 || !daMapping || !ensureDAInserts()) {
            midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x2E, daLoadSlot & 0x7F, 0x00, 0xF7]);
            return;
        }
        if (!daInsExplored || daInsSlotCache.length === 0) {
            midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x2E, daLoadSlot & 0x7F, 0x00, 0xF7]);
            return;
        }

        try {
            var m = daMapping;
            var slotID = daInsSlotCache[0].objectID;  // Any valid slot for API call
            var targetSlotID = -1;

            // Find the target slot's objectID
            if (daLoadSlot < daInsSlotCache.length) {
                targetSlotID = daInsSlotCache[daLoadSlot].objectID;
            } else {
                console.log('DA Load: slot ' + daLoadSlot + ' not in cache');
                midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x2E, daLoadSlot & 0x7F, 0x00, 0xF7]);
                return;
            }

            // Get the collection and entry
            var collCount = daInserts.mPluginManager.getNumberOfPluginCollections(m, slotID);
            if (collIdx >= collCount) collIdx = collCount - 1;
            var coll = daInserts.mPluginManager.getPluginCollectionByIndex(m, slotID, collIdx);
            if (!coll || !coll.mEntries || entryIndex >= coll.mEntries.length) {
                console.log('DA Load: invalid entry ' + entryIndex + ' in coll ' + collIdx);
                midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x2E, daLoadSlot & 0x7F, 0x00, 0xF7]);
                return;
            }

            var pluginUID = coll.mEntries[entryIndex].mPluginUID;
            var pluginName = coll.mEntries[entryIndex].mPluginName || '?';
            console.log('DA Load: "' + pluginName + '" (UID=' + pluginUID.substring(0, 16) + '...) into slot ' + daLoadSlot);

            daBypassCooldown = 20;  // Suppress callbacks during load
            daInserts.mPluginManager.trySetSlotPlugin(m, targetSlotID, pluginUID, true);

            // Success — send result
            midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x2E, daLoadSlot & 0x7F, 0x01, 0xF7]);
            console.log('DA Load: trySetSlotPlugin called OK');

            // Invalidate insert cache — it will be rebuilt on next exploration
            daInsExplored = false;
            daInsSlotCache = [];

        } catch(e) {
            console.log('DA Load error: ' + e);
            midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x2E, daLoadSlot & 0x7F, 0x00, 0xF7]);
        }
    };

    console.log('DA Plugin Load ready (CC 80-82 ch8)');

    // ══════════════════════════════════════════════
    // DA PLUGIN CLEAR — remove plugin from a slot
    // CC 79 channel 8 = try multiple strategies to clear a slot
    // ══════════════════════════════════════════════

    var daClearSlotBtn = surface.makeButton(79, 24, 2, 2);
    daClearSlotBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(7, 79);
    daClearSlotBtn.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
        var slotIdx = Math.round(value * 127);
        if (!daMapping || !ensureDAInserts()) {
            midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x2E, slotIdx & 0x7F, 0x00, 0xF7]);
            return;
        }
        if (!daInsExplored || slotIdx >= daInsSlotCache.length) {
            midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x2E, slotIdx & 0x7F, 0x00, 0xF7]);
            return;
        }

        var m = daMapping;
        var targetSlotID = daInsSlotCache[slotIdx].objectID;
        var pluginBefore = daInsSlotCache[slotIdx].title || '(empty)';
        daLog(activeDevice, '=== CLEAR SLOT ' + slotIdx + ' ===');
        daLog(activeDevice, 'Plugin: "' + pluginBefore + '" objID=' + targetSlotID);

        // Check children before
        var childsBefore = daInserts.getNumberOfChildObjects(m, targetSlotID);
        daLog(activeDevice, 'Children before: ' + childsBefore);

        daBypassCooldown = 20;
        var strategies = [
            { name: 'zero UID 32', uid: '00000000000000000000000000000000' },
            { name: 'zero UID 16', uid: '0000000000000000' },
            { name: 'empty string', uid: '' }
        ];

        var cleared = false;
        for (var si = 0; si < strategies.length; si++) {
            var strat = strategies[si];
            try {
                daLog(activeDevice, 'Try: ' + strat.name + ' uid="' + strat.uid + '"');
                daInserts.mPluginManager.trySetSlotPlugin(m, targetSlotID, strat.uid, true);

                // Check if children changed
                var childsAfter = daInserts.getNumberOfChildObjects(m, targetSlotID);
                daLog(activeDevice, 'Children after: ' + childsAfter);

                if (childsAfter < childsBefore) {
                    daLog(activeDevice, 'SUCCESS: "' + strat.name + '" cleared the slot');
                    cleared = true;
                    break;
                } else {
                    daLog(activeDevice, 'No change with "' + strat.name + '"');
                }
            } catch(e) {
                daLog(activeDevice, 'Error with "' + strat.name + '": ' + e);
            }
        }

        if (cleared) {
            midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x2E, slotIdx & 0x7F, 0x01, 0xF7]);
            daInsExplored = false;
            daInsSlotCache = [];
        } else {
            daLog(activeDevice, 'All strategies failed — slot not cleared');
            midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x2E, slotIdx & 0x7F, 0x00, 0xF7]);
        }
        daLog(activeDevice, '=== END CLEAR ===');
    };

    console.log('DA Plugin Clear ready (CC 79 ch8)');

    // ══════════════════════════════════════════════
    // DA STRIP SLOT CONTROL (v1.0.4)
    //
    // Reuses daInserts (attached to mInsertAndStripEffects) — the DA tree
    // exposes both the Inserts container AND a strip effects container at the
    // same root level.  Strip slot indices 16-20 are used in the shared DA
    // encoder system to avoid colliding with insert slots 0-15.
    //
    //   Gate=16, Compressor=17, Tools=18, Saturator=19, Limiter=20
    //
    // CC 70 ch8 → trigger strip exploration  → SysEx 0x34/0x35
    // CC 71 ch8 → bypass a strip slot        → SysEx 0x36
    // CC 72 ch8 → edit (open UI) a strip slot → SysEx 0x37
    // ══════════════════════════════════════════════

    // Slot title → modId mapping (mirrors state.py STRIP_MOD_* constants)
    var STRIP_TITLE_TO_MOD = {
        'Gate': 0x10, 'Noise Gate': 0x10,
        'Compressor': 0x11, 'Comp': 0x11,
        'Tools': 0x12,
        'Saturator': 0x13, 'Sat': 0x13,
        'Limiter': 0x14, 'Brickwall Limiter': 0x14, 'Maximizer': 0x14
    };

    // CC 70 ch8: trigger strip slot DA exploration
    var daStripExploreBtn = surface.makeButton(70, 22, 2, 2);
    daStripExploreBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(7, 70);
    daStripExploreBtn.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
        if (value < 0.5 || !daMapping) return;
        if (!ensureDAInserts()) return;
        buildStripSlotCache(activeDevice, daMapping);
    };

    // CC 71 ch8: bypass a strip slot
    // value = (wantBypass ? 0x40 : 0x00) | (slotIndex & 0x07)
    // slotIndex: 0=Gate, 1=Comp, 2=Tools, 3=Sat, 4=Limiter
    var daStripBypassBtn = surface.makeButton(71, 22, 2, 2);
    daStripBypassBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(7, 71);
    daStripBypassBtn.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
        var raw = Math.round(value * 127);
        if (!daMapping) return;
        if (!ensureDAInserts()) return;
        var wantBypass = (raw & 0x40) !== 0;
        var slotIdx = raw & 0x07;
        daBypassStripSlot(activeDevice, daMapping, slotIdx, wantBypass);
    };

    // CC 72 ch8: open/close plugin UI for a strip slot
    // value = slotIndex (0-4)
    var daStripEditBtn = surface.makeButton(72, 22, 2, 2);
    daStripEditBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(7, 72);
    daStripEditBtn.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
        var slotIdx = Math.round(value * 127);
        if (slotIdx === 127) return;  // Sentinel pulse
        if (!daMapping) return;
        if (!ensureDAInserts()) return;
        daEditStripSlot(activeDevice, daMapping, slotIdx);
    };

    // CC 73 ch8: stash param index for DA strip-param flip
    // CC 74 ch8: execute flip → reads stashed paramIdx + this value as da_slot,
    //            then flips the param via DA (workaround for binding-path toggles
    //            that don't survive Cubase's bank-zone refresh after value changes,
    //            e.g. VintageCompressor Punch/Att-Mode).
    var daFlipParamIdx = 0;
    var daFlipParamLatch = surface.makeButton(73, 22, 2, 2);
    daFlipParamLatch.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(7, 73);
    daFlipParamLatch.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
        daFlipParamIdx = Math.round(value * 127);
    };

    var daFlipSlotExec = surface.makeButton(74, 22, 2, 2);
    daFlipSlotExec.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(7, 74);
    daFlipSlotExec.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
        var daSlot = Math.round(value * 127);
        if (daSlot === 127) return;  // Sentinel/reset pulse — Python sends 127 between flips
        if (!daMapping) return;
        var entry = daGetEncEntry(daSlot);
        if (!entry || entry.pluginObjectID < 0) {
            console.log('DA flip: no entry for slot ' + daSlot);
            return;
        }
        try {
            var m = daMapping;
            var tag = daInserts.getParameterTagByIndex(m, entry.pluginObjectID, daFlipParamIdx);
            var current = daInserts.getParameterProcessValue(m, entry.pluginObjectID, tag);
            var newVal = (current > 0.5) ? 0.0 : 1.0;
            daInserts.setParameterProcessValue(m, entry.pluginObjectID, tag, newVal);
            console.log('DA flip: slot=' + daSlot + ' paramIdx=' + daFlipParamIdx +
                        ' tag=' + tag + ' ' + current.toFixed(3) + '->' + newVal.toFixed(3));
            // Notify Python so display can mirror new value immediately
            var val127 = Math.round(newVal * 127) & 0x7F;
            midiOutput_Loop.sendMidi(activeDevice,
                [0xF0, 0x00, 0x39, daSlot & 0x7F, daFlipParamIdx & 0x7F, val127, 0xF7]);
        } catch(e) {
            console.log('DA flip error: ' + e);
        }
    };

    // ══════════════════════════════════════════════
    // DIAGNOSTIC PROBE — sweep tag 4125 ("Effect Type") through all values
    // CC 78 ch8 value = strip slot index (16-20). Captures the original value
    // first, probes 0.00, 0.05, 0.10, ..., 1.00, then RESTORES the original.
    // ══════════════════════════════════════════════
    var daProbeEffectTypeBtn = surface.makeButton(78, 22, 2, 2);
    daProbeEffectTypeBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(7, 78);
    daProbeEffectTypeBtn.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
        var daSlot = Math.round(value * 127);
        if (!daMapping || !ensureDAInserts()) return;
        var entry = daGetEncEntry(daSlot);
        if (!entry) {
            console.log('Probe 4125: no entry for slot ' + daSlot);
            return;
        }
        var m = daMapping;
        var slotID = entry.objectID;
        var TAG = 4125;
        var originalVal = daInserts.getParameterProcessValue(m, slotID, TAG);
        var originalDisp = daInserts.getParameterDisplayValue(m, slotID, TAG);
        console.log('=== PROBE tag 4125 slot=' + daSlot + ' (original val=' + originalVal.toFixed(3) +
                    ' display="' + originalDisp + '") ===');
        daBypassCooldown = 200;  // Suppress callback storm
        var seen = {};  // display → first val that produced it
        for (var step = 0; step <= 20; step++) {
            var v = step / 20;
            try {
                daInserts.setParameterProcessValue(m, slotID, TAG, v);
                var disp = daInserts.getParameterDisplayValue(m, slotID, TAG);
                var readBack = daInserts.getParameterProcessValue(m, slotID, TAG);
                if (!(disp in seen)) {
                    seen[disp] = v;
                    console.log('  setval=' + v.toFixed(3) + ' → readback=' + readBack.toFixed(3) +
                                ' display="' + disp + '"');
                }
            } catch(e) {
                console.log('  setval=' + v.toFixed(3) + ' → error: ' + e);
            }
        }
        console.log('  unique displays: ' + Object.keys(seen).length);
        // Restore original
        try {
            daInserts.setParameterProcessValue(m, slotID, TAG, originalVal);
            console.log('  restored to val=' + originalVal.toFixed(3));
        } catch(e) {
            console.log('  restore error: ' + e);
        }
        console.log('=== END PROBE ===');
    };

    // ══════════════════════════════════════════════
    // DIAGNOSTIC — enumerate the SLOT object's own params (not the plugin's)
    // CC 77 ch8 value = strip slot index (16-20). Logs all params to JS console.
    // Looking for a "type selector" tag near SLOT_EDIT_TAG (4101) / SLOT_BYPASS_TAG (4102).
    // ══════════════════════════════════════════════
    var daEnumSlotObjBtn = surface.makeButton(77, 22, 2, 2);
    daEnumSlotObjBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(7, 77);
    daEnumSlotObjBtn.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
        var daSlot = Math.round(value * 127);
        if (!daMapping || !ensureDAInserts()) return;
        var entry = daGetEncEntry(daSlot);
        if (!entry) {
            console.log('SlotObj enum: no entry for slot ' + daSlot);
            return;
        }
        var m = daMapping;
        var slotID = entry.objectID;  // The SLOT object, not the plugin
        console.log('=== SLOT OBJECT PARAMS slot=' + daSlot + ' (mod=' + entry.modId.toString(16) + ' "' + entry.slotTitle + '") ===');
        console.log('  slot type/title via DA: type="' + daInserts.getObjectTypeName(m, slotID) +
                    '" title="' + daInserts.getObjectTitle(m, slotID) + '"');
        try {
            var paramCount = daInserts.getNumberOfParameters(m, slotID);
            console.log('  ' + paramCount + ' params:');
            for (var i = 0; i < Math.min(paramCount, 64); i++) {
                var tag = daInserts.getParameterTagByIndex(m, slotID, i);
                var title = daInserts.getParameterTitle(m, slotID, tag, 48) || '';
                var procVal = daInserts.getParameterProcessValue(m, slotID, tag);
                var disp = '';
                if (daInserts.getParameterDisplayValue) {
                    disp = daInserts.getParameterDisplayValue(m, slotID, tag) || '';
                }
                console.log('    [' + i + '] tag=' + tag + ' val=' + procVal.toFixed(3) +
                            ' display="' + disp + '" title="' + title + '"');
            }
        } catch(e) {
            console.log('  enum error: ' + e);
        }
        // Also list child objects (in case the variant selector is a sibling)
        try {
            var childCount = daInserts.getNumberOfChildObjects(m, slotID);
            console.log('  ' + childCount + ' children:');
            for (var ci = 0; ci < childCount; ci++) {
                var cID = daInserts.getChildObjectID(m, slotID, ci);
                console.log('    child[' + ci + '] type="' + daInserts.getObjectTypeName(m, cID) +
                            '" title="' + daInserts.getObjectTitle(m, cID) + '"');
            }
        } catch(e2) {
            console.log('  children enum error: ' + e2);
        }
        console.log('=== END SLOT OBJECT PARAMS ===');
    };

    // ══════════════════════════════════════════════
    // STRIP VARIANT SWITCHING — set a strip slot's plugin by name
    // CC 75 ch8 = variant_idx (stash), CC 76 ch8 = da_slot (execute)
    // SysEx 0x3A response: [F0 00 3A daSlot success F7]
    //
    // The ORDER of names in each list mirrors Python's _VARIANT_SWITCH_OPTIONS.
    // ══════════════════════════════════════════════
    var STRIP_VARIANTS = {
        16: ['Noise Gate'],
        17: ['Standard Compressor', 'Tube Compressor', 'VintageCompressor'],
        18: ['DeEsser', 'EnvelopeShaper'],
        19: ['Magneto II', 'Tape Saturation', 'Tube Saturation'],
        20: ['Brickwall Limiter', 'Maximizer', 'Standard Limiter']
    };

    var daSwitchVariantIdx = 0;
    var daSwitchVariantLatch = surface.makeButton(75, 22, 2, 2);
    daSwitchVariantLatch.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(7, 75);
    daSwitchVariantLatch.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
        daSwitchVariantIdx = Math.round(value * 127);
    };

    var daSwitchVariantExec = surface.makeButton(76, 22, 2, 2);
    daSwitchVariantExec.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(7, 76);
    daSwitchVariantExec.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
        var daSlot = Math.round(value * 127);
        if (daSlot === 127) return;  // Sentinel/reset pulse
        if (!daMapping || !ensureDAInserts()) {
            midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x3A, daSlot & 0x7F, 0x00, 0xF7]);
            return;
        }
        if (!daInserts.mPluginManager) {
            console.log('Variant switch: mPluginManager not available');
            midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x3A, daSlot & 0x7F, 0x00, 0xF7]);
            return;
        }
        var entry = daGetEncEntry(daSlot);
        if (!entry) {
            console.log('Variant switch: no entry for slot ' + daSlot);
            midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x3A, daSlot & 0x7F, 0x00, 0xF7]);
            return;
        }
        var variantList = STRIP_VARIANTS[daSlot];
        if (!variantList || daSwitchVariantIdx >= variantList.length) {
            console.log('Variant switch: idx ' + daSwitchVariantIdx + ' out of range for slot ' + daSlot);
            midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x3A, daSlot & 0x7F, 0x00, 0xF7]);
            return;
        }
        var targetName = variantList[daSwitchVariantIdx];
        try {
            var m = daMapping;
            var slotID = entry.objectID;
            // The strip slot has an "Effect Type" param (tag 4125) that selects
            // the variant. Setting normalized value [idx/(N-1)] picks variant idx.
            var EFFECT_TYPE_TAG = 4125;
            var n = variantList.length;
            var targetVal = (n > 1) ? (daSwitchVariantIdx / (n - 1)) : 0.0;
            daBypassCooldown = 20;
            daInserts.setParameterProcessValue(m, slotID, EFFECT_TYPE_TAG, targetVal);
            var newDisplay = daInserts.getParameterDisplayValue(m, slotID, EFFECT_TYPE_TAG);
            console.log('Variant switch: slot ' + daSlot + ' tag 4125 = ' + targetVal.toFixed(3) +
                        ' (target="' + targetName + '", got display="' + newDisplay + '")');
            midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x3A, daSlot & 0x7F, 0x01, 0xF7]);
            // Invalidate strip cache so next drill-in re-explores with new plugin
            daStripExplored = false;
            daStripSlotCache = [];
        } catch(e) {
            console.log('Variant switch error: ' + e);
            midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x3A, daSlot & 0x7F, 0x00, 0xF7]);
        }
    };

    // ── buildStripSlotCache ──
    // Explores the DA tree of daInserts looking for the strip effects container
    // (sibling of the 'Inserts' container at the root level).
    // Sends SysEx 0x34 per slot, then 0x35 when done.
    function buildStripSlotCache(activeDevice, activeMapping) {
        try {
            var m = activeMapping;
            var rootID = daInserts.getBaseObjectID(m);
            if (rootID < 0) {
                console.log('DA Strip: No base object');
                midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x35, 0x00, 0xF7]);
                return;
            }

            daStripSlotCache = [];
            daStripExplored = false;

            var rootChildCount = daInserts.getNumberOfChildObjects(m, rootID);
            console.log('DA Strip: root has ' + rootChildCount + ' children');

            // Find the strip effects container — it's the non-Inserts root child
            var stripContainerID = -1;
            for (var i = 0; i < rootChildCount; i++) {
                var childID = daInserts.getChildObjectID(m, rootID, i);
                var typeName = daInserts.getObjectTypeName ? daInserts.getObjectTypeName(m, childID) : '';
                var title    = daInserts.getObjectTitle ? daInserts.getObjectTitle(m, childID) : '';
                console.log('  Root child ' + i + ': type="' + typeName + '" title="' + title + '"');
                // Accept any known strip container type/title; skip the Inserts container
                if (typeName === 'Inserts' || title === 'Inserts') continue;
                if (typeName === 'Strips'     || typeName === 'StripEffects' ||
                    typeName === 'Strip'      || typeName === 'ChannelStrip' ||
                    typeName === 'Strip Effects' ||
                    title   === 'Strip'       || title   === 'StripEffects' ||
                    title   === 'Strip Effects') {
                    stripContainerID = childID;
                    break;
                }
                // Fallback: first non-empty container that isn't in a known non-strip category
                var skipTypes = {'Quick Controls':1,'InputFilter':1,'Panner':1,
                                 'Modulators':1,'Sends':1,'Foldbacks':1,
                                 'DirectRouting':1,'cvDevice':1};
                if (stripContainerID < 0 && !skipTypes[typeName] &&
                    daInserts.getNumberOfChildObjects(m, childID) > 0) {
                    stripContainerID = childID;
                }
            }

            if (stripContainerID < 0) {
                console.log('DA Strip: strip container not found');
                midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x35, 0x00, 0xF7]);
                return;
            }

            var slotCount = daInserts.getNumberOfChildObjects(m, stripContainerID);
            // Only the first 5 slots map to known strip effects (Gate/Comp/Tools/Sat/Limiter).
            // Nuendo may expose more (Nuendo 15 shows 8), but slots 6-8 have no Python state.
            var effectiveSlots = Math.min(slotCount, 6);
            console.log('DA Strip: container has ' + slotCount + ' children (using first ' + effectiveSlots + ')');

            for (var s = 0; s < effectiveSlots; s++) {
                var slotID    = daInserts.getChildObjectID(m, stripContainerID, s);
                var slotTitle = daInserts.getObjectTitle ? daInserts.getObjectTitle(m, slotID) : ('Slot' + s);
                var slotType  = daInserts.getObjectTypeName ? daInserts.getObjectTypeName(m, slotID) : '';

                var bypassed = false;
                var isOn = false;
                try {
                    bypassed = (daInserts.getParameterProcessValue(m, slotID, SLOT_BYPASS_TAG) > 0.5);
                    isOn     = (daInserts.getParameterProcessValue(m, slotID, SLOT_ON_TAG)     > 0.5);
                } catch(ePrm) {
                    console.log('  Strip slot ' + s + ' (' + slotTitle + '): params not readable — ' + ePrm);
                }

                // Plugin = first child of the slot (same as insert pattern)
                var pluginName  = '';
                var pluginObjID = -1;
                var childCount  = daInserts.getNumberOfChildObjects(m, slotID);
                if (childCount > 0) {
                    pluginObjID = daInserts.getChildObjectID(m, slotID, 0);
                    pluginName  = daInserts.getObjectTitle ? daInserts.getObjectTitle(m, pluginObjID) : '';
                }

                var modId = STRIP_TITLE_TO_MOD[slotTitle] || (0x10 + s);

                daStripSlotCache.push({
                    objectID:      slotID,
                    pluginObjectID: pluginObjID,
                    modId:         modId,
                    slotIndex:     s,
                    slotTitle:     slotTitle,
                    pluginName:    pluginName,
                    bypassed:      bypassed,
                    isOn:          isOn
                });

                console.log('  Strip ' + s + ' "' + slotTitle + '" type="' + slotType +
                            '" plugin="' + pluginName + '" on=' + isOn + ' bypass=' + bypassed +
                            ' modId=0x' + modId.toString(16));
            }

            daStripExplored = true;
            console.log('DA Strip: ' + daStripSlotCache.length + ' slots cached');

            // SysEx 0x34 per slot:
            // [F0 00 34 slotIdx modId bypassed isOn ...pluginName 00 ...slotTitle F7]
            for (var s = 0; s < daStripSlotCache.length; s++) {
                var e   = daStripSlotCache[s];
                var msg = [0xF0, 0x00, 0x34, s & 0x7F, e.modId & 0x7F,
                           e.bypassed ? 1 : 0, e.isOn ? 1 : 0];
                for (var c = 0; c < Math.min(e.pluginName.length, 20); c++) {
                    msg.push(e.pluginName.charCodeAt(c) & 0x7F);
                }
                msg.push(0x00);  // separator between pluginName and slotTitle
                for (var c = 0; c < Math.min(e.slotTitle.length, 12); c++) {
                    msg.push(e.slotTitle.charCodeAt(c) & 0x7F);
                }
                msg.push(0xF7);
                midiOutput_Loop.sendMidi(activeDevice, msg);
            }

            // SysEx 0x35 = cache complete
            midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x35, daStripSlotCache.length & 0x7F, 0xF7]);

        } catch(e) {
            console.log('DA Strip build error: ' + e);
            midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x35, 0x00, 0xF7]);
        }
    }

    // ── daBypassStripSlot ──
    // Sets SLOT_BYPASS_TAG on the strip slot object via DirectAccess.
    // Confirms via SysEx 0x36 [slotIdx, success, bypassed].
    function daBypassStripSlot(activeDevice, activeMapping, slotIdx, wantBypass) {
        if (!daStripExplored || slotIdx >= daStripSlotCache.length) {
            console.log('DA StripBypass: cache not ready or slot ' + slotIdx + ' out of range');
            midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x36, slotIdx & 0x7F, 0x00, 0xF7]);
            return;
        }
        try {
            var e = daStripSlotCache[slotIdx];
            var newVal = wantBypass ? 1.0 : 0.0;
            daBypassCooldown = 10;
            daInserts.setParameterProcessValue(activeMapping, e.objectID, SLOT_BYPASS_TAG, newVal);
            e.bypassed = wantBypass;
            console.log('DA StripBypass ' + slotIdx + ' (' + e.slotTitle + '): ' + (wantBypass ? 'BYPASS' : 'ACTIVE'));
            midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x36, slotIdx & 0x7F, 0x01, wantBypass ? 1 : 0, 0xF7]);
        } catch(err) {
            console.log('DA StripBypass error: ' + err);
            midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x36, slotIdx & 0x7F, 0x00, 0xF7]);
        }
    }

    // ── daEditStripSlot ──
    // Toggles SLOT_EDIT_TAG (open/close plugin UI) on a strip slot.
    // Confirms via SysEx 0x37 [slotIdx, success].
    function daEditStripSlot(activeDevice, activeMapping, slotIdx) {
        if (!daStripExplored || slotIdx >= daStripSlotCache.length) {
            console.log('DA StripEdit: cache not ready or slot ' + slotIdx + ' out of range');
            midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x37, slotIdx & 0x7F, 0x00, 0xF7]);
            return;
        }
        try {
            var e      = daStripSlotCache[slotIdx];
            // Strip slots use tag 4127 "Open Patcher" for the plugin UI; tag 4101
            // "Edit" is metadata only (set succeeds but the UI doesn't open).
            var STRIP_OPEN_PATCHER_TAG = 4127;
            var curVal = daInserts.getParameterProcessValue(activeMapping, e.objectID, STRIP_OPEN_PATCHER_TAG);
            var newVal = (curVal > 0.5) ? 0.0 : 1.0;
            daBypassCooldown = 10;
            daInserts.setParameterProcessValue(activeMapping, e.objectID, STRIP_OPEN_PATCHER_TAG, newVal);
            var readBack = daInserts.getParameterProcessValue(activeMapping, e.objectID, STRIP_OPEN_PATCHER_TAG);
            var readDisp = daInserts.getParameterDisplayValue(activeMapping, e.objectID, STRIP_OPEN_PATCHER_TAG);
            console.log('DA StripEdit ' + slotIdx + ' (' + e.slotTitle + ') tag 4127: cur=' + curVal.toFixed(3) +
                        ' wrote=' + newVal.toFixed(3) + ' readback=' + readBack.toFixed(3) +
                        ' display="' + readDisp + '"');
            midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x37, slotIdx & 0x7F, 0x01, 0xF7]);
        } catch(err) {
            console.log('DA StripEdit error: ' + err);
            midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x37, slotIdx & 0x7F, 0x00, 0xF7]);
        }
    }

    console.log('DA Strip Slot control ready (CC 70-72 ch8)');

    // ══════════════════════════════════════════════
    // DA ENCODER CONTROL — mapped parameter read/write
    // Protocol on channel 9 (API ch 8, MIDI 0xB8):
    //   CC 0:    Set target slot index
    //   CC 1-8:  Set DA paramIdx (low 7 bits) for encoders 0-7
    //   CC 9-16: Set DA paramIdx (high 7 bits) for encoders 0-7
    //   CC 20-27: Relative encoder input (signed bit)
    // ══════════════════════════════════════════════

    var daEncSlot = -1;
    var daEncParamTag = [0, 0, 0, 0, 0, 0, 0, 0];  // DA param tags for each encoder
    var daEncParamIdx = [0, 0, 0, 0, 0, 0, 0, 0];  // DA param indices for tag lookup

    // Unified cache lookup: slot 0-15 = insert slots, slot 16-20 = strip slots.
    // Returns the cache entry object or null if not available.
    function daGetEncEntry(slot) {
        if (slot >= 16 && slot <= 21) {
            var si = slot - 16;
            if (daStripExplored && si < daStripSlotCache.length) return daStripSlotCache[si];
            return null;
        }
        if (slot >= 0 && daInsExplored && slot < daInsSlotCache.length) return daInsSlotCache[slot];
        return null;
    }

    var DA_ENC_UNUSED = 0x3FFF;  // sentinel param index for an inactive encoder

    // Resolve the DA tag for encoder `idx` and emit its current value + display
    // string to Python (SysEx 0x2B). Used both when the high-bit index arrives
    // and by the explicit refresh trigger below — the latter guarantees values
    // are pushed on sub-page entry even when the param index didn't change (#4).
    function daSendEncoderDisplay(activeDevice, idx) {
        var paramIdx = daEncParamIdx[idx];
        // Inactive encoder: clear its tag and emit nothing. The bridge already
        // reset every cell to empty before configuring the sub-page, so leaving
        // it untouched keeps the cell blank (and avoids resolving param 0).
        if (paramIdx === DA_ENC_UNUSED) {
            daEncParamTag[idx] = 0;
            return;
        }
        var entry = daGetEncEntry(daEncSlot);
        if (!entry || entry.pluginObjectID < 0 || !daMapping) return;
        try {
            var m = daMapping;
            var tag = daInserts.getParameterTagByIndex(m, entry.pluginObjectID, paramIdx);
            daEncParamTag[idx] = tag;
            var procVal = daInserts.getParameterProcessValue(m, entry.pluginObjectID, tag);
            var val127 = Math.round(procVal * 127) & 0x7F;
            var displayStr = '';
            if (daInserts.getParameterDisplayValue) {
                displayStr = daInserts.getParameterDisplayValue(m, entry.pluginObjectID, tag) || '';
                var units = daInserts.getParameterDisplayUnits ? daInserts.getParameterDisplayUnits(m, entry.pluginObjectID, tag) : '';
                if (units && displayStr.indexOf(units) < 0) displayStr += ' ' + units;
            }
            var msg = [0xF0, 0x00, 0x2B, idx & 0x7F, val127];
            for (var c = 0; c < displayStr.length && c < 16; c++) {
                msg.push(displayStr.charCodeAt(c) & 0x7F);
            }
            msg.push(0xF7);
            midiOutput_Loop.sendMidi(activeDevice, msg);
        } catch(e) {
            daEncParamTag[idx] = 0;
        }
    }

    // CC 0 ch9: set target slot
    var daEncSlotBtn = surface.makeButton(0, 100, 2, 2);
    daEncSlotBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(8, 0);
    daEncSlotBtn.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
        daEncSlot = Math.round(value * 127);
    };

    // CC 1-8 ch9: param index low bits, CC 9-16 ch9: param index high bits
    for (var ei = 0; ei < 8; ei++) {
        // Low bits
        var loBtn = surface.makeButton(1 + ei, 100, 2, 2);
        loBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(8, 1 + ei);
        loBtn.mSurfaceValue.mOnProcessValueChange = (function(idx) {
            return function(activeDevice, value, diff) {
                var lo = Math.round(value * 127);
                daEncParamIdx[idx] = (daEncParamIdx[idx] & 0x3F80) | lo;
            };
        })(ei);
        // High bits — resolves the tag and sends current display value
        var hiBtn = surface.makeButton(9 + ei, 100, 2, 2);
        hiBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(8, 9 + ei);
        hiBtn.mSurfaceValue.mOnProcessValueChange = (function(idx) {
            return function(activeDevice, value, diff) {
                var hi = Math.round(value * 127);
                daEncParamIdx[idx] = (daEncParamIdx[idx] & 0x7F) | (hi << 7);
                // Note: display values are emitted by the explicit refresh
                // trigger (CC 17 ch9) the bridge pulses after configuring all
                // encoders — emitting here would fire mid-update with a partial
                // index and is skipped when the index byte doesn't change.
            };
        })(ei);
    }

    // CC 17 ch9: refresh ALL encoder display values (rising edge).
    // The bridge pulses this after configuring encoders for a sub-page so the
    // current values are pushed even when no param index changed (#4).
    // Positioned well clear of the slot/lo/hi/rel button columns (x 0..29 at
    // y=100) to avoid overlapping surface elements, which makes bindings flaky.
    var daEncRefreshBtn = surface.makeButton(40, 120, 2, 2);
    daEncRefreshBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(8, 17);
    daEncRefreshBtn.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
        // The bridge alternates the CC value (1 / 127) so this fires on every
        // sub-page setup; any change re-emits all encoder displays.
        if (value <= 0) return;
        for (var i = 0; i < 8; i++) {
            daSendEncoderDisplay(activeDevice, i);
        }
    };

    // CC 20-27 ch9: relative encoder input
    // Uses buttons (not knobs) to avoid surface value accumulation/boundary issues.
    // Python sends CC=0 (reset) before each delta to ensure value always changes.
    var DA_ENC_STEP = 0.0075;  // Step size per encoder notch (~1/133)
    for (var ri = 0; ri < 8; ri++) {
        var relBtn = surface.makeButton(20 + ri, 100, 2, 2);
        relBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop)
            .bindToControlChange(8, 20 + ri);
        relBtn.mSurfaceValue.mOnProcessValueChange = (function(idx) {
            return function(activeDevice, value, diff) {
                // Decode raw CC value (0-127)
                var raw = Math.round(value * 127);
                if (raw === 0) return;  // Ignore reset pulse

                if (daEncSlot < 0 || !daMapping) return;
                var entry = daGetEncEntry(daEncSlot);
                if (!entry || entry.pluginObjectID < 0) return;
                var tag = daEncParamTag[idx];
                if (!tag) return;

                // Decode relative signed bit: 1-63 = positive, 65-127 = negative
                var delta;
                if (raw >= 1 && raw <= 63) {
                    delta = raw * DA_ENC_STEP;
                } else if (raw >= 65 && raw <= 127) {
                    delta = -(raw - 64) * DA_ENC_STEP;
                } else {
                    return;
                }

                try {
                    var m = daMapping;
                    var pluginID = entry.pluginObjectID;
                    var current = daInserts.getParameterProcessValue(m, pluginID, tag);
                    var newVal = Math.max(0.0, Math.min(1.0, current + delta));
                    daBypassCooldown = 5;
                    daInserts.setParameterProcessValue(m, pluginID, tag, newVal);

                    // Send feedback to Python: SysEx 0x2B
                    var val127 = Math.round(newVal * 127) & 0x7F;
                    var displayStr = '';
                    if (daInserts.getParameterDisplayValue) {
                        displayStr = daInserts.getParameterDisplayValue(m, pluginID, tag) || '';
                        var units = daInserts.getParameterDisplayUnits ? daInserts.getParameterDisplayUnits(m, pluginID, tag) : '';
                        if (units && displayStr.indexOf(units) < 0) displayStr += ' ' + units;
                    }
                    var msg = [0xF0, 0x00, 0x2B, idx & 0x7F, val127];
                    for (var c = 0; c < displayStr.length && c < 16; c++) {
                        msg.push(displayStr.charCodeAt(c) & 0x7F);
                    }
                    msg.push(0xF7);
                    midiOutput_Loop.sendMidi(activeDevice, msg);
                } catch(e) {}
            };
        })(ri);
    }

    console.log('DA Encoder control ready (ch9)');

    // ── DA Callbacks ──
    // NOTE: mOnObjectChange fires during viewer navigation, parameter changes, etc.
    // The Slot objectIDs and bypass tags don't change during these events.
    // Only mOnObjectWillBeRemoved signals actual structural changes (plugin removed).
    // So we DON'T invalidate the cache on mOnObjectChange — it would break
    // bypass after entering/leaving the Edit page.
    daInserts.mOnObjectChange = function(activeDevice, activeMapping, objectID) {
        // Log only — don't clear the cache
    };

    daInserts.mOnParameterChange = function(activeDevice, activeMapping, objectID, parameterTag) {
        if (daBypassCooldown > 0) return;  // Suppress echo from our own bypass

        // Bypass tag — existing behaviour for insert / strip slot bypass tracking.
        if (parameterTag === SLOT_BYPASS_TAG) {
            for (var i = 0; i < daInsSlotCache.length; i++) {
                if (daInsSlotCache[i].objectID === objectID) {
                    var newVal = daInserts.getParameterProcessValue(activeMapping, objectID, parameterTag);
                    var wasBypassed = daInsSlotCache[i].bypassed;
                    daInsSlotCache[i].bypassed = (newVal > 0.5);
                    if (wasBypassed !== daInsSlotCache[i].bypassed) {
                        midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x13, i & 0x7F, daInsSlotCache[i].bypassed ? 1 : 0, 0xF7]);
                        console.log('DA: bypass changed insert ' + i + ' (' + daInsSlotCache[i].title + '): ' + (daInsSlotCache[i].bypassed ? 'BYPASS' : 'ACTIVE'));
                    }
                    return;
                }
            }
            for (var s = 0; s < daStripSlotCache.length; s++) {
                if (daStripSlotCache[s].objectID === objectID) {
                    var newVal = daInserts.getParameterProcessValue(activeMapping, objectID, parameterTag);
                    var wasBypassed = daStripSlotCache[s].bypassed;
                    daStripSlotCache[s].bypassed = (newVal > 0.5);
                    if (wasBypassed !== daStripSlotCache[s].bypassed) {
                        midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x36, s & 0x7F, 0x01, daStripSlotCache[s].bypassed ? 1 : 0, 0xF7]);
                        console.log('DA: bypass changed strip ' + s + ' (' + daStripSlotCache[s].slotTitle + '): ' + (daStripSlotCache[s].bypassed ? 'BYPASS' : 'ACTIVE'));
                    }
                    return;
                }
            }
            return;
        }

        // ── Live param feedback for explored slots ──
        // When a host-side change occurs (user touches a param in Nuendo's GUI),
        // forward (slotIdx, paramIdx, val127, display) to Python via SysEx 0x3D
        // so the EQ curve / cell display update without us having to poll.
        for (var sk in daParamTagToIdxBySlot) {
            var pid = daParamPluginIDBySlot[sk];
            if (pid !== objectID) continue;
            var tmap = daParamTagToIdxBySlot[sk];
            var paramIdx = tmap[parameterTag];
            if (paramIdx === undefined) continue;
            try {
                var procVal = daInserts.getParameterProcessValue(activeMapping, objectID, parameterTag);
                var val127 = Math.round(procVal * 127) & 0x7F;
                // Dedup: mOnParameterChange can fire repeatedly with the same
                // value (and floods during a Nuendo mouse-drag). Only forward
                // when the quantised value actually changed for this tag.
                var dedupKey = sk + ':' + paramIdx;
                if (daParamLastSent[dedupKey] === val127) return;
                daParamLastSent[dedupKey] = val127;
                var disp = '';
                if (daInserts.getParameterDisplayValue) {
                    disp = daInserts.getParameterDisplayValue(activeMapping, objectID, parameterTag) || '';
                    var units = daInserts.getParameterDisplayUnits ? daInserts.getParameterDisplayUnits(activeMapping, objectID, parameterTag) : '';
                    if (units && disp.indexOf(units) < 0) disp += ' ' + units;
                }
                var slotIdxInt = parseInt(sk, 10);
                // SysEx 0x3D: [F0 00 3D slotIdxLo slotIdxHi paramIdxLo paramIdxHi val127 ...display F7]
                var msg = [0xF0, 0x00, 0x3D,
                           slotIdxInt & 0x7F, (slotIdxInt >> 7) & 0x7F,
                           paramIdx & 0x7F, (paramIdx >> 7) & 0x7F,
                           val127];
                for (var c = 0; c < disp.length && c < 20; c++) {
                    msg.push(disp.charCodeAt(c) & 0x7F);
                }
                msg.push(0xF7);
                midiOutput_Loop.sendMidi(activeDevice, msg);
            } catch(e) { /* silent */ }
            return;
        }
    };

    daInserts.mOnObjectWillBeRemoved = function(activeDevice, activeMapping, objectID) {
        if (daBypassCooldown > 0) return;  // Suppress echo from our own bypass
        console.log('DA Inserts: object removed ID=' + objectID);
        daInsExplored = false;
        daInsSlotCache = [];
        midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x27, 0xF7]);
    };

    console.log('DirectAccess Inserts ready (CC 88 to explore)');
} else {
    console.log('DirectAccess not available (API < 1.2)');
}

// ══════════════════════════════════════════════════
// IDLE
// ══════════════════════════════════════════════════
var tick = 0;
var scanDelay = 0;

var initialSyncDone = false;
var initialSyncDelay = 0;

deviceDriver.mOnIdle = function(context) {
    tick++;
    if (tick >= 5) {
        tick = 0;
        midiOutput_Loop.sendMidi(context, [0xBF, 127, 1]);
    }

    // After first heartbeat, send current volume/pan values to bridge
    if (!initialSyncDone) {
        initialSyncDelay++;
        if (initialSyncDelay > 20) {  // ~400ms after script load
            initialSyncDone = true;
            for (var i = 0; i < 8; i++) {
                var vol = knobsVol[i].mSurfaceValue.getProcessValue(context);
                var pan = knobsPan[i].mSurfaceValue.getProcessValue(context);
                midiOutput_Loop.sendMidi(context, [0xB0, 20 + i, Math.round(vol * 127)]);
                midiOutput_Loop.sendMidi(context, [0xB0, 40 + i, Math.round(pan * 127)]);
            }
            // Send JS version to bridge via SysEx 0x10
            var verMsg = [0xF0, 0x00, 0x21, 0x09, 0x10];
            for (var c = 0; c < JS_VERSION.length; c++) {
                verMsg.push(JS_VERSION.charCodeAt(c) & 0x7F);
            }
            verMsg.push(0xF7);
            midiOutput_Loop.sendMidi(context, verMsg);
        }
    }

    if (scanCooldown > 0) scanCooldown--;
    if (daBypassCooldown > 0) daBypassCooldown--;

    // Fallback couleur
    if (pendingColorForIndex >= 0) {
        var idx = pendingColorForIndex & 0x7F;
        midiOutput_Loop.sendMidi(context,
            [0xF0, 0x00, 0x21, 0x09, 0x02, idx, lastColorR, lastColorG, lastColorB, 0xF7]);
        pendingColorForIndex = -1;
    }

    // Sélection
    if (pendingAbsSelect >= 0 && !scanActive) {
        lastSelectedIndex = pendingAbsSelect;
        selButtons[pendingAbsSelect].mSurfaceValue.setProcessValue(context, 1.0);
        pendingAbsSelect = -1;
    }

    // Scan séquentiel (8 pistes du bank zone visible)
    if (scanActive) {
        scanDelay++;
        var needed = (scanTrackCounter == 0) ? 4 : 2;
        if (scanDelay >= needed) {
            scanDelay = 0;
            if (scanTrackCounter < 8) {
                lastSelectedIndex = scanTrackCounter;
                selButtons[scanTrackCounter].mSurfaceValue.setProcessValue(context, 1.0);
                scanTrackCounter++;
            } else {
                midiOutput_Loop.sendMidi(context, [0xB0, 15, scanTrackCounter]);
                scanActive = false;
                scanCooldown = 30;
                // Re-sync volumes/pans after scan
                for (var si = 0; si < 8; si++) {
                    var sv = knobsVol[si].mSurfaceValue.getProcessValue(context);
                    var sp = knobsPan[si].mSurfaceValue.getProcessValue(context);
                    midiOutput_Loop.sendMidi(context, [0xB0, 20 + si, Math.round(sv * 127)]);
                    midiOutput_Loop.sendMidi(context, [0xB0, 40 + si, Math.round(sp * 127)]);
                }
            }
        }
    }

    // Scan séquentiel des inserts — DÉSACTIVÉ
    // Les noms sont récupérés au fur et à mesure via mEdit.mOnTitleChange

    // ── Plugin List queue: send entries in batches ──
    if (pluginListQueue) {
        var q = pluginListQueue;
        var batchSize = 10;  // ~10 entries per tick ≈ 500/s → 352 in ~0.7s
        for (var b = 0; b < batchSize && q.sendIdx < q.total; b++) {
            try {
                var pe = q.coll.mEntries[q.sendIdx];
                var idxLo = q.sendIdx & 0x7F;
                var idxHi = (q.sendIdx >> 7) & 0x7F;
                // SysEx 0x2C: [F0 00 2C idxLo idxHi ...name 00 ...vendor 00 ...subCat 00 ...uid F7]
                var msg = [0xF0, 0x00, 0x2C, idxLo, idxHi];
                var pName = pe.mPluginName || '';
                for (var c = 0; c < pName.length && c < 30; c++) {
                    var ch = pName.charCodeAt(c) & 0x7F;
                    if (ch > 0) msg.push(ch);
                }
                msg.push(0x00);
                var pVendor = pe.mPluginVendor || '';
                for (var c = 0; c < pVendor.length && c < 24; c++) {
                    var ch = pVendor.charCodeAt(c) & 0x7F;
                    if (ch > 0) msg.push(ch);
                }
                msg.push(0x00);
                var pSubCat = pe.mSubCategories || '';
                for (var c = 0; c < pSubCat.length && c < 30; c++) {
                    var ch = pSubCat.charCodeAt(c) & 0x7F;
                    if (ch > 0) msg.push(ch);
                }
                msg.push(0x00);
                var pUID = pe.mPluginUID || '';
                for (var c = 0; c < pUID.length && c < 40; c++) {
                    var ch = pUID.charCodeAt(c) & 0x7F;
                    if (ch > 0) msg.push(ch);
                }
                msg.push(0xF7);
                midiOutput_Loop.sendMidi(context, msg);
            } catch(e) {
                console.log('DA PluginList: error at entry ' + q.sendIdx + ': ' + e);
            }
            q.sendIdx++;
        }
        if (q.sendIdx >= q.total) {
            // SysEx 0x2D: completion [F0 00 2D countLo countHi collIdx collCount ...collName F7]
            var cntLo = q.total & 0x7F;
            var cntHi = (q.total >> 7) & 0x7F;
            var complMsg = [0xF0, 0x00, 0x2D, cntLo, cntHi, q.collIdx & 0x7F, q.collCount & 0x7F];
            for (var c = 0; c < q.collName.length && c < 20; c++) {
                complMsg.push(q.collName.charCodeAt(c) & 0x7F);
            }
            complMsg.push(0xF7);
            midiOutput_Loop.sendMidi(context, complMsg);
            console.log('DA PluginList: sent ' + q.total + ' entries from "' + q.collName + '"');
            pluginListQueue = null;
        }
    }
};

// ══════════════════════════════════════════════
// INSERT EFFECTS VIEWER
// ══════════════════════════════════════════════

try {
    var maxInsertSlots = midiremote_api.mDefaults.getNumberOfInsertEffectSlots();
    var insertsViewer = page.mHostAccess.mTrackSelection.mMixerChannel.mInsertAndStripEffects
        .makeInsertEffectViewer("insertsViewer");

    var insertResetVar = surface.makeCustomValueVariable("insertReset");
    var insertNextVar = surface.makeCustomValueVariable("insertNext");
    var insertEditVar = surface.makeCustomValueVariable("insertEdit");

    page.makeActionBinding(insertResetVar, insertsViewer.mAction.mReset);
    page.makeActionBinding(insertNextVar, insertsViewer.mAction.mNext);
    page.makeValueBinding(insertEditVar, insertsViewer.mEdit);

    // Bypass on main viewer via CC 20 channel 4 (value binding, NOT toggle)
    // CC 127 = bypass ON, CC 0 = bypass OFF — Python sends the desired state
    var insertBypassBtn = surface.makeButton(20, 24, 2, 2);
    insertBypassBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(3, 20);
    page.makeValueBinding(insertBypassBtn.mSurfaceValue, insertsViewer.mBypass);

    // ── INSERT PLUGIN PARAMETERS (8 paramètres via mParameterBankZone) ──
    var insertParamZone = insertsViewer.mParameterBankZone;
    var insertParamValues = [];
    var insertParamKnobs = [];
    
    for (var ip = 0; ip < 8; ip++) {
        var paramVal = insertParamZone.makeParameterValue();
        insertParamValues.push(paramVal);
        
        // Knobs CC 20-27 channel 2 (pour ne pas interférer avec les knobs de volume ch1)
        // Non — utilisons les mêmes knobs mais sur un CC différent
        // CC 110-117 channel 2 ? Non, restons simple : custom vars
        var paramKnob = surface.makeKnob(ip * 3, 82, 2, 2);
        paramKnob.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop)
            .bindToControlChange(1, 20 + ip).setTypeRelativeSignedBit();
        insertParamKnobs.push(paramKnob);
        
        page.makeValueBinding(paramKnob.mSurfaceValue, paramVal);
        
        // Feedback : envoyer le nom et la valeur du paramètre au bridge
        paramVal.mOnTitleChange = (function(idx) {
            return function(activeDevice, activeMapping, objectTitle, valueTitle) {
                var title = valueTitle || objectTitle || '';
                if (title) {
                    var bytes = [0xF0, 0x00, 0x16, idx & 0x7F];
                    for (var c = 0; c < title.length && c < 20; c++) {
                        bytes.push(title.charCodeAt(c) & 0x7F);
                    }
                    bytes.push(0xF7);
                    midiOutput_Loop.sendMidi(activeDevice, bytes);
                }
            };
        })(ip);
        
        paramVal.mOnDisplayValueChange = (function(idx) {
            return function(activeDevice, activeMapping, value, units) {
                var display = value || '';
                var bytes = [0xF0, 0x00, 0x17, idx & 0x7F];
                for (var c = 0; c < display.length && c < 16; c++) {
                    bytes.push(display.charCodeAt(c) & 0x7F);
                }
                bytes.push(0xF7);
                midiOutput_Loop.sendMidi(activeDevice, bytes);
            };
        })(ip);
    }
    
    // Navigation banques de paramètres : CC 2 channel 2 = Next, CC 3 channel 2 = Prev
    var paramBankNextBtn = surface.makeButton(0, 84, 2, 2);
    paramBankNextBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(1, 2);
    page.makeActionBinding(paramBankNextBtn.mSurfaceValue, insertParamZone.mAction.mNextBank);
    
    var paramBankPrevBtn = surface.makeButton(2, 84, 2, 2);
    paramBankPrevBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(1, 3);
    page.makeActionBinding(paramBankPrevBtn.mSurfaceValue, insertParamZone.mAction.mPrevBank);
    
    console.log("Insert Parameters OK (8 params + bank nav)");

    // DEACTIVATE : CC 4 channel 2 toggle mOn du viewer principal
    var insertDeactivateBtn = surface.makeButton(4, 86, 2, 2);
    insertDeactivateBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(1, 4);
    page.makeValueBinding(insertDeactivateBtn.mSurfaceValue, insertsViewer.mOn).setTypeToggle();

    // CC 89: Reset viewer au slot 0
    var insertScanBtn = surface.makeButton(89, 18, 2, 2);
    insertScanBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 89);
    page.makeActionBinding(insertScanBtn.mSurfaceValue, insertsViewer.mAction.mReset);
    
    // CC 1: Next slot
    var insertNextBtn = surface.makeButton(1, 20, 2, 2);
    insertNextBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 1);
    page.makeActionBinding(insertNextBtn.mSurfaceValue, insertsViewer.mAction.mNext);
    
    var insertCurrentViewerSlot = 0;

    // EDIT : CC 99 toggle l'ouverture de l'UI du plugin focusé par le viewer principal
    var insertEditBtn = surface.makeButton(99, 80, 2, 2);
    insertEditBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 99);
    page.makeValueBinding(insertEditBtn.mSurfaceValue, insertsViewer.mEdit).setTypeToggle();

    // mOnTitleChange du viewer : donne le numéro de slot (1-based string "1", "2"...)
    insertsViewer.mOnTitleChange = function(activeDevice, activeMapping, slotNumStr) {
        if (typeof slotNumStr === 'string') {
            var slotNum = parseInt(slotNumStr);
            if (!isNaN(slotNum) && slotNum >= 1 && slotNum <= 16) {
                insertCurrentViewerSlot = slotNum - 1;
            }
        }
    };

    // mEdit.mOnTitleChange donne le nom du plugin
    insertsViewer.mEdit.mOnTitleChange = function(activeDevice, arg1, pluginName, arg3) {
        var slotIndex = insertCurrentViewerSlot;
        if (typeof pluginName === 'string' && pluginName.length > 0 && !pluginName.match(/^\d+$/)) {
            var bytes = [0xF0, 0x00, 0x11, slotIndex & 0x7F];
            for (var i = 0; i < pluginName.length && i < 24; i++) {
                bytes.push(pluginName.charCodeAt(i) & 0x7F);
            }
            bytes.push(0xF7);
            midiOutput_Loop.sendMidi(activeDevice, bytes);
        }
    };

    // Callback : bypass change -> envoyer au bridge
    insertsViewer.mBypass.mOnProcessValueChange = function(activeDevice, activeMapping, value) {
        var slot = insertCurrentViewerSlot;
        midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x13, slot & 0x7F, value > 0.5 ? 1 : 0, 0xF7]);
    };

    console.log("Insert Effects Viewer OK (" + maxInsertSlots + " slots)");
} catch(e) {
    console.log("InsertEffectsViewer error: " + e);
}


// =============================================================================
// STRIP EXPLORATION (v1.0.4)
//
// Sends parameter info from the currently selected channel to the bridge via
// SysEx for exploration / UI development.
//
// SysEx commands (long format, manufacturer ID 00 21 09):
//   0x30 announce: F0 00 21 09 30 modId paramId <ascii name> F7
//   0x31 value:    F0 00 21 09 31 modId paramId <0-127> F7
//   0x32 display:  F0 00 21 09 32 modId paramId <ascii display> F7
//
// Module IDs:
//   0x00 = PreFilter         (8 params: gain, phase, HC freq/on/slope, LC freq/on/slope)
//   0x01 = ChannelEQ         (4 bands × 5 params: freq, gain, q, type, on)
//   0x10 = Gate (slot)       — phase 1b probe: just .mOn for now
//   0x11 = Compressor (slot) — phase 1b probe
//   0x12 = Tools (slot)      — phase 1b probe
//   0x13 = Saturator (slot)  — phase 1b probe
//   0x14 = Limiter (slot)    — phase 1b probe
// =============================================================================

// Registry of strip CustomValueVariables by (modId << 8) | paramId.
// Phase 2A write knobs look up the CV here and drive it via setProcessValue
// (indirection avoids double-makeValueBinding to the same host value).
var stripVarRegistry = {};

// Registry for Phase 1c-v3 slot bank zone paramVals, keyed by (modId<<8)|paramId.
// Phase 1d uses this to attach write Knobs to the same paramVals for drill-down
// encoder writes. paramVals are SHARED between read (CV binding in Phase 1c-v3)
// and write (hardware Knob binding in Phase 1d).
var stripParamValRegistry = {};

// Helper at top level so both phases can use it.
function makeStripVar(name, modId, paramId) {
    var v = surface.makeCustomValueVariable(name);
    
    var key = ((modId & 0xFF) << 8) | (paramId & 0xFF);
    stripVarRegistry[key] = v;
    
    // DIAGNOSTIC: log so we can verify CV callbacks fire when host changes.
    
    v.mOnTitleChange = function(activeDevice, objectTitle, valueTitle) {
        console.log("[StripVar " + name + "] mOnTitleChange: " + 
                    objectTitle + " / " + valueTitle);
        var msg = [0xF0, 0x00, 0x21, 0x09, 0x30, modId & 0x7F, paramId & 0x7F];
        var combined = '';
        if (objectTitle) combined = objectTitle;
        if (valueTitle) combined = combined ? (combined + ':' + valueTitle) : valueTitle;
        for (var c = 0; c < Math.min(combined.length, 60); c++) {
            msg.push(combined.charCodeAt(c) & 0x7F);
        }
        msg.push(0xF7);
        midiOutput_Loop.sendMidi(activeDevice, msg);
    };
    
    v.mOnProcessValueChange = function(activeDevice, value, diff) {
        console.log("[StripVar " + name + "] mOnProcessValueChange: " + value.toFixed(3));
        var val = Math.round(value * 127) & 0x7F;
        midiOutput_Loop.sendMidi(activeDevice,
            [0xF0, 0x00, 0x21, 0x09, 0x31, modId & 0x7F, paramId & 0x7F, val, 0xF7]);
    };
    
    v.mOnDisplayValueChange = function(activeDevice, displayValue, units) {
        console.log("[StripVar " + name + "] mOnDisplayValueChange: " + displayValue + " " + units);
        var msg = [0xF0, 0x00, 0x21, 0x09, 0x32, modId & 0x7F, paramId & 0x7F];
        var s = displayValue || '';
        if (units) s += ' ' + units;
        for (var c = 0; c < Math.min(s.length, 30); c++) {
            msg.push(s.charCodeAt(c) & 0x7F);
        }
        msg.push(0xF7);
        midiOutput_Loop.sendMidi(activeDevice, msg);
    };
    
    return v;
}

// Helper for WRITABLE strip params: same callbacks as makeStripVar, but uses
// a real Knob (with MIDI binding on channel 9) bound to the host via
// page.makeValueBinding. This is the pattern that works for QC knobs and
// volumes — both bind to mTrackSelection.mMixerChannel-rooted hosts.
//
// The earlier indirection (CV.setProcessValue called from a separate write
// knob) doesn't appear to propagate writes for slot.mOn or mPreFilter.mGain
// even though it works for sends. Likely the binding direction supported by
// makeValueBinding(cv, host) varies by host type. Direct Knob binding works
// universally — that's how QC and volumes drive their hosts.
//
// Returns the knob.mSurfaceValue so the caller passes it to page.makeValueBinding.
//
// Position: hidden 2x2 knob at x=100, y=50+ccNum*3 (gap to avoid overlap).
// Helper for WRITABLE strip params: same callbacks as makeStripVar, but uses
// a real Knob (with MIDI binding on channel 9) bound to the host via
// page.makeValueBinding. This is the pattern that works for QC knobs and
// volumes — both bind to mTrackSelection.mMixerChannel-rooted hosts.
//
// Used for CONTINUOUS hosts (PreGain). For BINARY hosts (mOn, mBypass,
// mPhaseSwitch), use makeStripButton instead — Steinberg API expects
// Button + bindToNote + setTypeToggle for binary host writes (verified
// with the working sendOnBtn pattern at line ~475).
//
// Returns the knob.mSurfaceValue so the caller passes it to page.makeValueBinding.
//
// Position: hidden 2x2 knob at x=100, y=50+ccNum*3 (gap to avoid overlap).
function makeStripKnob(name, modId, paramId, ccNum) {
    var k = surface.makeKnob(100, 50 + ccNum * 3, 2, 2);
    k.mSurfaceValue.mMidiBinding
        .setInputPort(midiInput_Loop)
        .bindToControlChange(9, ccNum);
    
    // DIAGNOSTIC: log every callback firing so we can pinpoint where the
    // chain breaks. Remove these logs once the path is validated.
    
    // Read-side feedback callbacks — fire when the host value changes from any
    // source (the bridge writing via CC, or the user clicking in Nuendo's GUI).
    k.mSurfaceValue.mOnTitleChange = function(activeDevice, objectTitle, valueTitle) {
        console.log("[StripKnob " + name + " CC9/" + ccNum + "] mOnTitleChange: " + 
                    objectTitle + " / " + valueTitle);
        var msg = [0xF0, 0x00, 0x21, 0x09, 0x30, modId & 0x7F, paramId & 0x7F];
        var combined = '';
        if (objectTitle) combined = objectTitle;
        if (valueTitle) combined = combined ? (combined + ':' + valueTitle) : valueTitle;
        for (var c = 0; c < Math.min(combined.length, 60); c++) {
            msg.push(combined.charCodeAt(c) & 0x7F);
        }
        msg.push(0xF7);
        midiOutput_Loop.sendMidi(activeDevice, msg);
    };
    
    k.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
        console.log("[StripKnob " + name + " CC9/" + ccNum + "] mOnProcessValueChange: " + 
                    value.toFixed(3) + " (diff=" + (diff !== undefined ? diff.toFixed(3) : "?") + ")");
        var val = Math.round(value * 127) & 0x7F;
        midiOutput_Loop.sendMidi(activeDevice,
            [0xF0, 0x00, 0x21, 0x09, 0x31, modId & 0x7F, paramId & 0x7F, val, 0xF7]);
    };
    
    k.mSurfaceValue.mOnDisplayValueChange = function(activeDevice, displayValue, units) {
        console.log("[StripKnob " + name + " CC9/" + ccNum + "] mOnDisplayValueChange: " + 
                    displayValue + " " + units);
        var msg = [0xF0, 0x00, 0x21, 0x09, 0x32, modId & 0x7F, paramId & 0x7F];
        var s = displayValue || '';
        if (units) s += ' ' + units;
        for (var c = 0; c < Math.min(s.length, 30); c++) {
            msg.push(s.charCodeAt(c) & 0x7F);
        }
        msg.push(0xF7);
        midiOutput_Loop.sendMidi(activeDevice, msg);
    };
    
    return k.mSurfaceValue;
}

// Helper for WRITABLE BINARY strip params (slot.mOn, mBypass, mPhaseSwitch).
//
// The MIDI Remote API requires a specific surface element type AND MIDI
// binding type for binary host values to accept writes from a controller:
//   - surface.makeButton (NOT makeKnob)
//   - bindToNote (NOT bindToControlChange)
//   - .setTypeToggle() on the value binding
//
// This is the same pattern used by sendOnBtn at line ~475 of this script,
// which is bound to sendSlot.mOn — structurally identical to slot.mOn here.
//
// We send a single note-on (status 0x9?, velocity > 0) per toggle event
// from the bridge. The button surface value goes 0→1 on note-on, fires
// mOnProcessValueChange, and the .setTypeToggle binding flips the host value.
//
// Position: hidden 2x2 button at x=103, y=50+noteNum (offset to avoid
// collisions with the makeStripKnob column at x=100).
function makeStripButton(name, modId, paramId, noteNum) {
    // Position: hidden 2x2 button at x=103, y=50+noteNum*3.
    // Step of 3 (NOT 1) ensures non-overlapping 2x2 elements — earlier formula
    // 50+(noteNum%32) made all 5 slot buttons overlap each other, which caused
    // a single note-on to fire ALL the slot bindings simultaneously (toggling
    // the entire CS instead of just the targeted slot).
    var b = surface.makeButton(103, 50 + noteNum * 3, 2, 2);
    b.mSurfaceValue.mMidiBinding
        .setInputPort(midiInput_Loop)
        .bindToNote(9, noteNum);
    
    // DIAGNOSTIC: log every callback firing so we can pinpoint where the
    // chain breaks. Remove these logs once the path is validated.
    
    b.mSurfaceValue.mOnTitleChange = function(activeDevice, objectTitle, valueTitle) {
        console.log("[StripBtn " + name + " Note9/" + noteNum + "] mOnTitleChange: " + 
                    objectTitle + " / " + valueTitle);
        var msg = [0xF0, 0x00, 0x21, 0x09, 0x30, modId & 0x7F, paramId & 0x7F];
        var combined = '';
        if (objectTitle) combined = objectTitle;
        if (valueTitle) combined = combined ? (combined + ':' + valueTitle) : valueTitle;
        for (var c = 0; c < Math.min(combined.length, 60); c++) {
            msg.push(combined.charCodeAt(c) & 0x7F);
        }
        msg.push(0xF7);
        midiOutput_Loop.sendMidi(activeDevice, msg);
    };
    
    b.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
        console.log("[StripBtn " + name + " Note9/" + noteNum + "] mOnProcessValueChange: " + 
                    value.toFixed(3));
        var val = Math.round(value * 127) & 0x7F;
        midiOutput_Loop.sendMidi(activeDevice,
            [0xF0, 0x00, 0x21, 0x09, 0x31, modId & 0x7F, paramId & 0x7F, val, 0xF7]);
    };
    
    b.mSurfaceValue.mOnDisplayValueChange = function(activeDevice, displayValue, units) {
        console.log("[StripBtn " + name + " Note9/" + noteNum + "] mOnDisplayValueChange: " + 
                    displayValue + " " + units);
        var msg = [0xF0, 0x00, 0x21, 0x09, 0x32, modId & 0x7F, paramId & 0x7F];
        var s = displayValue || '';
        if (units) s += ' ' + units;
        for (var c = 0; c < Math.min(s.length, 30); c++) {
            msg.push(s.charCodeAt(c) & 0x7F);
        }
        msg.push(0xF7);
        midiOutput_Loop.sendMidi(activeDevice, msg);
    };
    
    return b.mSurfaceValue;
}


var stripChannel = page.mHostAccess.mTrackSelection.mMixerChannel;

// =============================================================================
// PHASE 1a — PreFilter + ChannelEQ (validated working)
// =============================================================================

try {
    // ── PreFilter (module 0x00) ──
    var preFilter = stripChannel.mPreFilter;
    
    // Writable params:
    //   - CONTINUOUS hosts (PreGain) → makeStripKnob (Knob + CC binding)
    //   - BINARY hosts (Phase, Bypass, slot.mOn) → makeStripButton (Button + Note + setTypeToggle)
    // Read-only params use makeStripVar (CustomValueVariable, no MIDI input).
    //
    // For binary hosts, MIDI Remote API requires Button + bindToNote, not
    // Knob + CC. The sendOnBtn pattern at L~475 confirms this for sendSlot.mOn
    // (structurally identical to slot.mOn).
    
    // PreGain — continuous, on CC 9/0
    var sv = makeStripKnob('pf_gain', 0x00, 0x00, 0);
    page.makeValueBinding(sv, preFilter.mGain);
    
    // Phase — binary toggle, on Note 9/1
    var sv = makeStripButton('pf_phase', 0x00, 0x01, 1);
    page.makeValueBinding(sv, preFilter.mPhaseSwitch).setTypeToggle();
    
    var pfReadOnly = [
        // Phase + section bypass need a separate read binding because
        // makeStripButton with setTypeToggle doesn't reliably fire callbacks
        // on host-side value changes for binary params.
        ['pf_phase_r',  0x01, preFilter.mPhaseSwitch],
        ['pf_bypass_r', 0x7F, preFilter.mBypass],
        ['pf_hc_freq',  0x02, preFilter.mHighCutFreq],
        ['pf_hc_on',    0x03, preFilter.mHighCutOn],
        ['pf_hc_slope', 0x04, preFilter.mHighCutSlope],
        ['pf_lc_freq',  0x05, preFilter.mLowCutFreq],
        ['pf_lc_on',    0x06, preFilter.mLowCutOn],
        ['pf_lc_slope', 0x07, preFilter.mLowCutSlope]
    ];
    for (var p = 0; p < pfReadOnly.length; p++) {
        var def = pfReadOnly[p];
        var v = makeStripVar(def[0], 0x00, def[1]);
        page.makeValueBinding(v, def[2]);
    }
    
    // PreFilter section bypass — binary toggle, on Note 9/2
    if (preFilter.mBypass) {
        var sv = makeStripButton('pf_bypass', 0x00, 0x7F, 2);
        page.makeValueBinding(sv, preFilter.mBypass).setTypeToggle();
    }

    // PreFilter HighCut / LowCut writable bindings (used by the EQ page on Push).
    // HC Freq write (CC 9/18), LC Freq write (CC 9/19),
    // HC On toggle (Note 9/9), LC On toggle (Note 9/10).
    //
    // For the toggle Buttons we DON'T use makeStripButton — its diagnostic
    // callbacks fire on every note-on/off pulse, sending SysEx 0x31 with the
    // transient surface value (1 then 0). That overwrites the authoritative
    // value sent by the makeStripVar read binding in pfReadOnly. Create the
    // button raw without callbacks instead.
    var sv = makeStripKnob('pf_hc_freq_w', 0x00, 0x02, 18);
    page.makeValueBinding(sv, preFilter.mHighCutFreq);
    sv = makeStripKnob('pf_lc_freq_w', 0x00, 0x05, 19);
    page.makeValueBinding(sv, preFilter.mLowCutFreq);
    function makeWriteOnlyToggleBtn(noteNum, hostValue) {
        // Column 108 = free zone between sub-page encoders (col 106-107) and
        // drilldown toggle buttons (col 112-113).
        var b = surface.makeButton(108, 50 + noteNum * 3, 2, 2);
        b.mSurfaceValue.mMidiBinding
            .setInputPort(midiInput_Loop)
            .bindToNote(9, noteNum);
        page.makeValueBinding(b.mSurfaceValue, hostValue).setTypeToggle();
        return b.mSurfaceValue;
    }
    if (preFilter.mHighCutOn) {
        makeWriteOnlyToggleBtn(9, preFilter.mHighCutOn);
    }
    if (preFilter.mLowCutOn) {
        makeWriteOnlyToggleBtn(10, preFilter.mLowCutOn);
    }
    
    // ── ChannelEQ (module 0x01) — 4 bands × 5 params ──
    var eq = stripChannel.mChannelEQ;
    
    // ChannelEQ section bypass — binary toggle, on Note 9/3
    // PLUS a separate read binding so the on-screen pill follows host changes
    // (the setTypeToggle write Button doesn't reliably fire display callbacks).
    if (eq.mBypass) {
        var sv = makeStripButton('eq_bypass', 0x01, 0x7F, 3);
        page.makeValueBinding(sv, eq.mBypass).setTypeToggle();
        var svR = makeStripVar('eq_bypass_r', 0x01, 0x7F);
        page.makeValueBinding(svR, eq.mBypass);
    }
    
    var eqBands = [eq.mBand1, eq.mBand2, eq.mBand3, eq.mBand4];
    for (var b = 0; b < eqBands.length; b++) {
        var bandObj = eqBands[b];
        var basePid = (b + 1) * 0x10;
        var bandDefs = [
            ['eq_b' + (b+1) + '_freq', basePid + 0x00, bandObj.mFreq],
            ['eq_b' + (b+1) + '_gain', basePid + 0x01, bandObj.mGain],
            ['eq_b' + (b+1) + '_q',    basePid + 0x02, bandObj.mQ],
            ['eq_b' + (b+1) + '_type', basePid + 0x03, bandObj.mFilterType],
            ['eq_b' + (b+1) + '_on',   basePid + 0x04, bandObj.mOn]
        ];
        for (var p = 0; p < bandDefs.length; p++) {
            var def = bandDefs[p];
            var v = makeStripVar(def[0], 0x01, def[1]);
            page.makeValueBinding(v, def[2]);
        }
    }
    
    console.log("[Strip 1a] PreFilter + ChannelEQ bound OK");
} catch(e) {
    console.log("[Strip 1a] error: " + e);
}

// =============================================================================
// PHASE 1b — Strip slot .mOn probes
//
// Each slot is bound in its own try/catch so we can see which API paths work.
// The probe binds the .mOn toggle. Each slot also receives a CC binding (CC 9/4
// for Gate ... CC 9/8 for Limiter) so the bridge can drive on/off via lower
// row buttons in MODE_CHANNEL_STRIP overview.
//
// Trying common naming patterns:
//   mInsertAndStripEffects.mStripEffects.mGate / mCompressor / mTools / mSaturator / mLimiter
// =============================================================================

(function(modId, label, accessor, cc) {
    try {
        var ise = stripChannel.mInsertAndStripEffects;
        if (!ise) {
            console.log("[Strip 1b] " + label + ": mInsertAndStripEffects missing");
            return;
        }
        var target = accessor(ise);
        if (!target) {
            console.log("[Strip 1b] " + label + ": accessor returned undefined");
            return;
        }
        if (!target.mOn) {
            console.log("[Strip 1b] " + label + ": .mOn missing on object");
            return;
        }
        // READ binding: CV bound to slot.mOn for display feedback (paramId 0x00).
        // The renderer expects paramId 0x00 for slot On/Off display strings.
        var v_on = makeStripVar('strip_on_' + modId.toString(16), modId, 0x00);
        page.makeValueBinding(v_on, target.mOn);
        
        // WRITE binding: Button bound to slot.mBypass for the toggle (paramId 0x7E).
        // We use mBypass because slot.mOn writes go to the section master toggle
        // in MIDI Remote API (confirmed empirically — toggling .mOn turns the whole
        // strip on/off, not just the slot). slot.mBypass gives slot-specific control.
        if (target.mBypass) {
            var b_byp = makeStripButton('strip_byp_' + modId.toString(16), modId, 0x7E, cc);
            page.makeValueBinding(b_byp, target.mBypass).setTypeToggle();
        } else {
            console.log("[Strip 1b] " + label + ": .mBypass missing — toggle won't work");
        }
        console.log("[Strip 1b] " + label + ": bound OK (CC 9/" + cc + ")");
    } catch(e) {
        console.log("[Strip 1b] " + label + " error: " + e);
    }
})(0x10, 'Gate',       function(ise) { return ise.mStripEffects && ise.mStripEffects.mGate; },       4);

(function(modId, label, accessor, cc) {
    try {
        var ise = stripChannel.mInsertAndStripEffects;
        var target = ise && accessor(ise);
        if (!target || !target.mOn) {
            console.log("[Strip 1b] " + label + ": not accessible");
            return;
        }
        // READ binding: CV bound to slot.mOn for display feedback (paramId 0x00).
        // The renderer expects paramId 0x00 for slot On/Off display strings.
        var v_on = makeStripVar('strip_on_' + modId.toString(16), modId, 0x00);
        page.makeValueBinding(v_on, target.mOn);
        
        // WRITE binding: Button bound to slot.mBypass for the toggle (paramId 0x7E).
        // We use mBypass because slot.mOn writes go to the section master toggle
        // in MIDI Remote API (confirmed empirically — toggling .mOn turns the whole
        // strip on/off, not just the slot). slot.mBypass gives slot-specific control.
        if (target.mBypass) {
            var b_byp = makeStripButton('strip_byp_' + modId.toString(16), modId, 0x7E, cc);
            page.makeValueBinding(b_byp, target.mBypass).setTypeToggle();
        } else {
            console.log("[Strip 1b] " + label + ": .mBypass missing — toggle won't work");
        }
        console.log("[Strip 1b] " + label + ": bound OK (CC 9/" + cc + ")");
    } catch(e) {
        console.log("[Strip 1b] " + label + " error: " + e);
    }
})(0x11, 'Compressor', function(ise) { return ise.mStripEffects && ise.mStripEffects.mCompressor; }, 5);

(function(modId, label, accessor, cc) {
    try {
        var ise = stripChannel.mInsertAndStripEffects;
        var target = ise && accessor(ise);
        if (!target || !target.mOn) {
            console.log("[Strip 1b] " + label + ": not accessible");
            return;
        }
        // READ binding: CV bound to slot.mOn for display feedback (paramId 0x00).
        // The renderer expects paramId 0x00 for slot On/Off display strings.
        var v_on = makeStripVar('strip_on_' + modId.toString(16), modId, 0x00);
        page.makeValueBinding(v_on, target.mOn);
        
        // WRITE binding: Button bound to slot.mBypass for the toggle (paramId 0x7E).
        // We use mBypass because slot.mOn writes go to the section master toggle
        // in MIDI Remote API (confirmed empirically — toggling .mOn turns the whole
        // strip on/off, not just the slot). slot.mBypass gives slot-specific control.
        if (target.mBypass) {
            var b_byp = makeStripButton('strip_byp_' + modId.toString(16), modId, 0x7E, cc);
            page.makeValueBinding(b_byp, target.mBypass).setTypeToggle();
        } else {
            console.log("[Strip 1b] " + label + ": .mBypass missing — toggle won't work");
        }
        console.log("[Strip 1b] " + label + ": bound OK (CC 9/" + cc + ")");
    } catch(e) {
        console.log("[Strip 1b] " + label + " error: " + e);
    }
})(0x12, 'Tools',      function(ise) { return ise.mStripEffects && ise.mStripEffects.mTools; },      6);

(function(modId, label, accessor, cc) {
    try {
        var ise = stripChannel.mInsertAndStripEffects;
        var target = ise && accessor(ise);
        if (!target || !target.mOn) {
            console.log("[Strip 1b] " + label + ": not accessible");
            return;
        }
        // READ binding: CV bound to slot.mOn for display feedback (paramId 0x00).
        // The renderer expects paramId 0x00 for slot On/Off display strings.
        var v_on = makeStripVar('strip_on_' + modId.toString(16), modId, 0x00);
        page.makeValueBinding(v_on, target.mOn);
        
        // WRITE binding: Button bound to slot.mBypass for the toggle (paramId 0x7E).
        // We use mBypass because slot.mOn writes go to the section master toggle
        // in MIDI Remote API (confirmed empirically — toggling .mOn turns the whole
        // strip on/off, not just the slot). slot.mBypass gives slot-specific control.
        if (target.mBypass) {
            var b_byp = makeStripButton('strip_byp_' + modId.toString(16), modId, 0x7E, cc);
            page.makeValueBinding(b_byp, target.mBypass).setTypeToggle();
        } else {
            console.log("[Strip 1b] " + label + ": .mBypass missing — toggle won't work");
        }
        console.log("[Strip 1b] " + label + ": bound OK (CC 9/" + cc + ")");
    } catch(e) {
        console.log("[Strip 1b] " + label + " error: " + e);
    }
})(0x13, 'Saturator',  function(ise) { return ise.mStripEffects && ise.mStripEffects.mSaturator; },  7);

(function(modId, label, accessor, cc) {
    try {
        var ise = stripChannel.mInsertAndStripEffects;
        var target = ise && accessor(ise);
        if (!target || !target.mOn) {
            console.log("[Strip 1b] " + label + ": not accessible");
            return;
        }
        // READ binding: CV bound to slot.mOn for display feedback (paramId 0x00).
        // The renderer expects paramId 0x00 for slot On/Off display strings.
        var v_on = makeStripVar('strip_on_' + modId.toString(16), modId, 0x00);
        page.makeValueBinding(v_on, target.mOn);
        
        // WRITE binding: Button bound to slot.mBypass for the toggle (paramId 0x7E).
        // We use mBypass because slot.mOn writes go to the section master toggle
        // in MIDI Remote API (confirmed empirically — toggling .mOn turns the whole
        // strip on/off, not just the slot). slot.mBypass gives slot-specific control.
        if (target.mBypass) {
            var b_byp = makeStripButton('strip_byp_' + modId.toString(16), modId, 0x7E, cc);
            page.makeValueBinding(b_byp, target.mBypass).setTypeToggle();
        } else {
            console.log("[Strip 1b] " + label + ": .mBypass missing — toggle won't work");
        }
        console.log("[Strip 1b] " + label + ": bound OK (CC 9/" + cc + ")");
    } catch(e) {
        console.log("[Strip 1b] " + label + " error: " + e);
    }
})(0x14, 'Limiter',    function(ise) { return ise.mStripEffects && ise.mStripEffects.mLimiter; },    8);

// =============================================================================
// PHASE 1b FALLBACK — if mStripEffects naming doesn't work, try direct on ise
//
// If all 5 above failed with "not accessible", maybe Steinberg uses:
//   mInsertAndStripEffects.mGate / mCompressor / mTools / mSaturator / mLimiter
// instead of nesting under .mStripEffects. We try that pattern as a fallback.
// Only activates if nothing was bound above (controlled by Nuendo console output).
// =============================================================================

(function tryFallback() {
    try {
        var ise = stripChannel.mInsertAndStripEffects;
        if (!ise) return;
        var fallbacks = [
            [0x10, 'Gate-fallback',       'mGate'],
            [0x11, 'Compressor-fallback', 'mCompressor'],
            [0x12, 'Tools-fallback',      'mTools'],
            [0x13, 'Saturator-fallback',  'mSaturator'],
            [0x14, 'Limiter-fallback',    'mLimiter']
        ];
        for (var i = 0; i < fallbacks.length; i++) {
            var modId = fallbacks[i][0];
            var label = fallbacks[i][1];
            var key   = fallbacks[i][2];
            try {
                var target = ise[key];
                if (!target || !target.mOn) {
                    console.log("[Strip 1b-fb] " + label + ": not accessible");
                    continue;
                }
                // Use param ID 0x01 to differentiate from the primary probe (param 0x00)
                var v = makeStripVar('strip_on_fb_' + modId.toString(16), modId, 0x01);
                page.makeValueBinding(sv, target.mOn).setTypeToggle();
                console.log("[Strip 1b-fb] " + label + ": bound OK");
            } catch(e) {
                console.log("[Strip 1b-fb] " + label + " error: " + e);
            }
        }
    } catch(e) {
        console.log("[Strip 1b-fb] outer error: " + e);
    }
})();

// =============================================================================
// PHASE 1c v3 — Strip slot parameter enumeration (binding + direct hooks)
//
// Discovery from Matthieu's test of v1: CustomValueVariable + binding DOES
// propagate display callbacks (e.g. Gate Threshold -26.6 dB fires correctly)
// — but it does NOT propagate title callbacks (param names stay empty).
//
// This v3 keeps the binding (which appears necessary to "activate" the bank
// zone slot and propagate display values) AND adds direct callbacks on the
// paramVal HostValue (4-arg signature, like the existing insert code at
// line ~2160) to catch the titles which CustomValueVariable doesn't propagate.
//
// Param ID layout per module:
//   0x00       = slot.mOn (Phase 1b, with title = variant name)
//   0x01..0x08 = bank parameters 0..7
//
// Also: slot.mOnChangePluginIdentity → SysEx 0x33 = plugin identity
//
// Note: callbacks are hooked ONLY on paramVal (direct), NOT on the
// CustomValueVariable, to avoid double-firing of display callbacks.
// =============================================================================

(function bindAllStripParamsV3() {
    var ise = stripChannel.mInsertAndStripEffects;
    if (!ise || !ise.mStripEffects) {
        console.log("[Strip 1c-v3] mStripEffects unavailable");
        return;
    }
    
    function makeTitleHook(modId, paramId) {
        return function(activeDevice, activeMapping, objectTitle, valueTitle) {
            var msg = [0xF0, 0x00, 0x21, 0x09, 0x30, modId & 0x7F, paramId & 0x7F];
            var combined = '';
            if (objectTitle) combined = objectTitle;
            if (valueTitle) combined = combined ? (combined + ':' + valueTitle) : valueTitle;
            for (var c = 0; c < Math.min(combined.length, 60); c++) {
                msg.push(combined.charCodeAt(c) & 0x7F);
            }
            msg.push(0xF7);
            midiOutput_Loop.sendMidi(activeDevice, msg);
        };
    }
    
    function makeDisplayHook(modId, paramId) {
        return function(activeDevice, activeMapping, value, units) {
            var msg = [0xF0, 0x00, 0x21, 0x09, 0x32, modId & 0x7F, paramId & 0x7F];
            var s = value || '';
            if (units) s += ' ' + units;
            for (var c = 0; c < Math.min(s.length, 30); c++) {
                msg.push(s.charCodeAt(c) & 0x7F);
            }
            msg.push(0xF7);
            midiOutput_Loop.sendMidi(activeDevice, msg);
        };
    }
    
    function makeValueHook(modId, paramId) {
        // SysEx 0x31 = value update (val127). Bridge caches this so subsequent
        // encoder writes can compute current+delta correctly. Without this hook,
        // the bridge's cache stays at None (default 64), and every encoder
        // turn sends the same (cache + 1) value — host moves once then stalls.
        return function(activeDevice, activeMapping, value, diff) {
            var val = Math.round(value * 127) & 0x7F;
            midiOutput_Loop.sendMidi(activeDevice,
                [0xF0, 0x00, 0x21, 0x09, 0x31, modId & 0x7F, paramId & 0x7F, val, 0xF7]);
        };
    }
    
    function makeIdentityHook(modId) {
        return function(activeDevice, activeMapping, pluginName, pluginVendor, pluginVersion, formatVersion) {
            // SysEx 0x33 = plugin identity (variant change)
            var msg = [0xF0, 0x00, 0x21, 0x09, 0x33, modId & 0x7F];
            var s = pluginName || '';
            for (var c = 0; c < Math.min(s.length, 60); c++) {
                msg.push(s.charCodeAt(c) & 0x7F);
            }
            msg.push(0xF7);
            midiOutput_Loop.sendMidi(activeDevice, msg);
        };
    }
    
    var slots = [
        [0x10, 'Gate',       ise.mStripEffects.mGate],
        [0x11, 'Compressor', ise.mStripEffects.mCompressor],
        [0x12, 'Tools',      ise.mStripEffects.mTools],
        [0x13, 'Saturator',  ise.mStripEffects.mSaturator],
        [0x14, 'Limiter',    ise.mStripEffects.mLimiter]
    ];
    
    for (var s = 0; s < slots.length; s++) {
        var modId = slots[s][0];
        var label = slots[s][1];
        var slot  = slots[s][2];
        
        try {
            if (!slot) {
                console.log("[Strip 1c-v3] " + label + ": slot null");
                continue;
            }
            
            // Plugin identity hook (variant detection — 6-arg signature).
            // Note: in Steinberg's Duktape engine, READING an unassigned function
            // property throws "DukValue is uninitialized". We just assign it
            // unconditionally, in its own try/catch so any failure here doesn't
            // block the param bindings that follow.
            try {
                slot.mOnChangePluginIdentity = makeIdentityHook(modId);
            } catch(eIdent) {
                console.log("[Strip 1c-v3] " + label + " identity hook unavailable: " + eIdent);
            }
            
            if (!slot.mParameterBankZone) {
                console.log("[Strip 1c-v3] " + label + ": no mParameterBankZone");
                continue;
            }
            
            var zone = slot.mParameterBankZone;
            
            // Bank zone discovery: probe size 16 covers all known sparse
            // params for Cubase Strip plugins. Empirical findings:
            //   • Gate window = 16 (uses offsets 0-8 + 14 for SCMonitor)
            //   • Comp / Tools / Sat / Limit windows = 8 (offsets 0-7)
            // Probing higher just yields duplicates (the bank wraps).
            // Extended-view params from the plugin GUI (e.g. Vintage Comp's
            // Ratio + Mix, DeEsser's Diff) are NOT in the bank zone — they
            // require DA on slot.mPlugin.mDirectParameters (future commit).
            try {
                if (zone.setBankSize) {
                    zone.setBankSize(16);
                }
            } catch(eBS) {
                // setBankSize may be unsupported — makeParameterValue() may
                // still extend the zone implicitly.
            }
            
            // Probe 16 paramVals (paramIds 0x01..0x10). Empty positions fire
            // empty title callbacks; they stay registered with idle paramVals
            // which are harmless.
            var bound = 0;
            for (var p = 0; p < 16; p++) {
                try {
                    var paramVal = zone.makeParameterValue();
                    var paramId = 0x01 + p;
                    
                    // Register in global map so Phase 1d can attach write Knobs
                    // to the same paramVals (drill-down encoder bindings).
                    stripParamValRegistry[(modId << 8) | paramId] = paramVal;
                    
                    // Binding: CustomValueVariable → paramVal
                    // Required to "activate" the bank zone slot. Phase 1c v1 confirmed
                    // this propagates display callbacks; we do NOT hook callbacks on
                    // the CustomValueVariable to avoid double-firing.
                    var v = surface.makeCustomValueVariable(
                        'strip_' + modId.toString(16) + '_v3_p' + p);
                    page.makeValueBinding(v, paramVal);
                    
                    // Direct callbacks on paramVal (HostValue, 4-arg signature) —
                    // catches the title, value and display which the binding does
                    // not propagate (the CV bound to it is only there to activate
                    // the bank slot).
                    paramVal.mOnTitleChange = makeTitleHook(modId, paramId);
                    paramVal.mOnDisplayValueChange = makeDisplayHook(modId, paramId);
                    paramVal.mOnProcessValueChange = makeValueHook(modId, paramId);
                    
                    bound++;
                } catch(e) {
                    console.log("[Strip 1c-v3] " + label + " param " + p + " error: " + e);
                    break;
                }
            }
            console.log("[Strip 1c-v3] " + label + ": " + bound + "/8 bindings + direct hooks");
        } catch(e) {
            console.log("[Strip 1c-v3] " + label + " outer error: " + e);
        }
    }

    // NOTE: HostStripEffectSlot.mEdit binding was investigated for opening the
    // plugin UI from Push — confirmed via mOnDisplayValueChange callbacks that
    // setTypeToggle flips the value (Off↔On), but Nuendo does NOT open the UI
    // visually for strip slots. Insert slots support this via insertsViewer.mEdit;
    // strip slots apparently don't. Bindings removed to keep the surface clean.
})();


// =============================================================================
// PHASE 1d — Sub-pages for drill-down (Axe B)
//
// The bridge navigates between an Overview and 6 module drill-down pages
// (Gate, Comp, EQ, Tools, Sat, Limiter). On each module's page, 8 encoders
// control that module's bank zone parameters.
//
// Sub-pages share the 8 encoder Knobs across pages — only the bindings on
// the currently active sub-page take effect. The bridge activates a sub-page
// by sending a note-on (channel 9) bound to that sub-page's mActivate action.
//
// Wire protocol on channel 9:
//   CC 10..17   = encoder 1..8 absolute write (current sub-page's params)
//   Note 100    = activate Overview sub-page
//   Note 101    = activate Gate sub-page
//   Note 102    = activate Comp sub-page  (Step 2)
//   Note 103    = activate EQ sub-page    (Step 3)
//   Note 104    = activate Tools sub-page (Step 2)
//   Note 105    = activate Sat sub-page   (Step 2)
//   Note 106    = activate Limiter sub-page (Step 2)
//
// Step 1 (this commit) populates Gate only. Other sub-pages exist but have
// no encoder bindings yet — encoders 1-8 will be no-op on those pages.
// =============================================================================

(function setupChannelStripSubPages() {
    try {
        var stripSubArea = page.makeSubPageArea('ChannelStrip');
        var subOverview = stripSubArea.makeSubPage('Overview');
        var subGate     = stripSubArea.makeSubPage('Gate');
        var subEQ       = stripSubArea.makeSubPage('EQ');
        // Per-variant sub-pages for slots with multiple plugin variants.
        // Each has its own encoder + toggle bindings tailored to the
        // variant's actual param types (continuous vs binary). The bridge
        // auto-activates the right one based on slot.plugin_name.
        var subCompStd   = stripSubArea.makeSubPage('CompStandard');
        var subCompTube  = stripSubArea.makeSubPage('CompTube');
        var subCompVtg   = stripSubArea.makeSubPage('CompVintage');
        var subToolsDe   = stripSubArea.makeSubPage('ToolsDeesser');
        var subToolsEnv  = stripSubArea.makeSubPage('ToolsEnvShaper');
        var subSatMag    = stripSubArea.makeSubPage('SatMagneto');
        var subSatTape   = stripSubArea.makeSubPage('SatTape');
        var subSatTube   = stripSubArea.makeSubPage('SatTube');
        var subLimBrick  = stripSubArea.makeSubPage('LimitBrickwall');
        var subLimMax    = stripSubArea.makeSubPage('LimitMaximizer');
        var subLimStd    = stripSubArea.makeSubPage('LimitStandard');
        console.log("[Strip 1d] Sub-page area created (Overview + 14 variants)");
        
        // ── 8 hidden encoder write Knobs ──
        // Positioned at x=106 (free column), y stepping by 3 to avoid overlaps.
        // CC 9/10..17 receive absolute values from the bridge. The same Knobs
        // are reused across all sub-pages — only one set of bindings is active
        // at a time, determined by which sub-page mActivate was last triggered.
        var stripEncKnobs = [];
        for (var ei = 0; ei < 8; ei++) {
            var k = surface.makeKnob(106, 50 + ei * 3, 2, 2);
            k.mSurfaceValue.mMidiBinding
                .setInputPort(midiInput_Loop)
                .bindToControlChange(9, 10 + ei);
            
            // Diagnostic logging — verify CC arrives. Remove once validated.
            (function(ccNum) {
                k.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
                    console.log("[StripEnc CC9/" + ccNum + "] " + value.toFixed(3));
                };
            })(10 + ei);
            
            stripEncKnobs.push(k);
        }
        console.log("[Strip 1d] 8 encoder write Knobs created (CC 9/10..17)");
        
        // ── 8 hidden lower-row toggle Buttons ──
        // Positioned at x=112 (free column). Notes 9/120..127. Same sharing
        // pattern as encoder Knobs: each sub-page binds them to its own
        // bank zone toggle paramVals via .setTypeToggle().
        var stripToggleBtns = [];
        for (var bi = 0; bi < 8; bi++) {
            var b = surface.makeButton(112, 50 + bi * 3, 2, 2);
            b.mSurfaceValue.mMidiBinding
                .setInputPort(midiInput_Loop)
                .bindToNote(9, 120 + bi);
            
            (function(noteNum) {
                b.mSurfaceValue.mOnProcessValueChange = function(activeDevice, value, diff) {
                    console.log("[StripToggle Note9/" + noteNum + "] " + value.toFixed(3));
                };
            })(120 + bi);
            
            stripToggleBtns.push(b);
        }
        console.log("[Strip 1d] 8 toggle write Buttons created (Note 9/120..127)");
        
        // ── Sub-page activation buttons ──
        // Each is a hidden Button bound to a note on channel 9. The bridge
        // sends a note-on to switch the active sub-page. ActionBinding
        // (rather than ValueBinding) hooks the button press to the
        // sub-page's mActivate action.
        function bindActivator(sub, noteNum, label) {
            try {
                var b = surface.makeButton(109, 50 + (noteNum - 100) * 3, 2, 2);
                b.mSurfaceValue.mMidiBinding
                    .setInputPort(midiInput_Loop)
                    .bindToNote(9, noteNum);
                page.makeActionBinding(b.mSurfaceValue, sub.mAction.mActivate);
                console.log("[Strip 1d] Activator bound: " + label + " ← Note 9/" + noteNum);
            } catch(e) {
                console.log("[Strip 1d] Activator " + label + " error: " + e);
            }
        }
        bindActivator(subOverview, 100, 'Overview');
        bindActivator(subGate,     101, 'Gate');
        bindActivator(subEQ,       103, 'EQ');
        // Per-variant activator notes. ALL must stay within the 7-bit MIDI
        // range (0-127) — notes >127 get masked to (n & 0x7F) on the wire and
        // never match their bindToNote, leaving the sub-page un-activatable
        // (this previously broke every Sat/Limiter variant: 130-142 → 2-14).
        // They must also avoid the drill-down toggle notes 120-127.
        //   Comp:  110, 111, 112
        //   Tools: 113, 114   (moved out of 120-127 toggle-note range)
        //   Sat:   104, 105, 106
        //   Limit: 107, 108, 109
        bindActivator(subCompStd,  110, 'CompStandard');
        bindActivator(subCompTube, 111, 'CompTube');
        bindActivator(subCompVtg,  112, 'CompVintage');
        bindActivator(subToolsDe,  113, 'ToolsDeesser');
        bindActivator(subToolsEnv, 114, 'ToolsEnvShaper');
        bindActivator(subSatMag,   104, 'SatMagneto');
        bindActivator(subSatTape,  105, 'SatTape');
        bindActivator(subSatTube,  106, 'SatTube');
        bindActivator(subLimBrick, 107, 'LimitBrickwall');
        bindActivator(subLimMax,   108, 'LimitMaximizer');
        bindActivator(subLimStd,   109, 'LimitStandard');
        
        // ── Bindings per sub-page ──
        // Overview: no encoder/toggle bindings here (PreGain and bypass toggles
        // are bound on the main page via Phase 1a/1b, always active).
        //
        // Each module sub-page maps its 6-8 encoders and 2-4 lower-row toggles
        // to its bank zone paramVals. paramIds may be in any order — we use
        // the natural ordering for continuous params and route binary params
        // to the toggle bindings.
        //
        // Param sequence arrays: 8 entries, each is a paramId (0x01..0x08)
        // or null to leave that position unbound.
        function bindModuleEncoders(modId, sub, label, paramIdSeq) {
            try {
                var bound = 0;
                for (var ei = 0; ei < 8; ei++) {
                    var paramId = paramIdSeq[ei];
                    if (!paramId) continue;
                    var pv = stripParamValRegistry[(modId << 8) | paramId];
                    if (!pv) {
                        console.log("[Strip 1d] " + label + " enc " + (ei+1) +
                                    ": paramVal 0x" + paramId.toString(16) +
                                    " not in registry");
                        continue;
                    }
                    page.makeValueBinding(stripEncKnobs[ei].mSurfaceValue, pv)
                        .setSubPage(sub);
                    bound++;
                }
                console.log("[Strip 1d] " + label + " encoders: " + bound + "/8 bound");
            } catch(e) {
                console.log("[Strip 1d] " + label + " encoder binding error: " + e);
            }
        }
        
        function bindModuleToggles(modId, sub, label, paramIdSeq) {
            try {
                var bound = 0;
                for (var bi = 0; bi < 8; bi++) {
                    var paramId = paramIdSeq[bi];
                    if (!paramId) continue;
                    var pv = stripParamValRegistry[(modId << 8) | paramId];
                    if (!pv) {
                        console.log("[Strip 1d] " + label + " toggle " + (bi+1) +
                                    ": paramVal 0x" + paramId.toString(16) +
                                    " not in registry");
                        continue;
                    }
                    page.makeValueBinding(stripToggleBtns[bi].mSurfaceValue, pv)
                        .setSubPage(sub)
                        .setTypeToggle();
                    bound++;
                }
                console.log("[Strip 1d] " + label + " toggles: " + bound + "/8 bound");
            } catch(e) {
                console.log("[Strip 1d] " + label + " toggle binding error: " + e);
            }
        }
        
        // ── Gate (modId 0x10) — only 1 variant (Noise Gate) ──
        // Bank zone (sparse, wraps every 16):
        //   0x01 Threshold, 0x02 Range, 0x03 Attack, 0x04 Release,
        //   0x07 Filter Freq, 0x08 Filter Q on encoders 1-6
        //   0x0E SCMonitor (Listen Filter), 0x06 SCOn (Activate Filter),
        //   0x05 Auto Release on lower 1-3
        bindModuleEncoders(0x10, subGate, 'Gate',
            [0x01, 0x02, 0x03, 0x04, 0x07, 0x08, null, null]);
        bindModuleToggles(0x10, subGate, 'Gate',
            [0x0E, 0x06, 0x05, null, null, null, null, null]);
        
        // ── Compressor variants (modId 0x11) ──
        // Each variant has its own bank zone layout. The bridge auto-activates
        // the right sub-page based on the slot's plugin_name (SysEx 0x33).
        
        // Standard Compressor:
        //   0x01 Threshold, 0x02 Ratio, 0x03 Attack, 0x04 Release, 0x06 MakeUp (cont)
        //   0x05 Au-Release, 0x07 A-MakeUp (toggle)
        bindModuleEncoders(0x11, subCompStd, 'CompStandard',
            [0x01, 0x02, 0x03, 0x04, 0x06, null, null, null]);
        bindModuleToggles(0x11, subCompStd, 'CompStandard',
            [0x05, 0x07, null, null, null, null, null, null]);
        
        // Tube Compressor:
        //   0x01 Input, 0x02 Output, 0x03 Attack, 0x04 Release, 0x06 Drive, 0x07 Mix (cont)
        //   0x05 A-Release (toggle)
        bindModuleEncoders(0x11, subCompTube, 'CompTube',
            [0x01, 0x02, 0x03, 0x04, 0x06, 0x07, null, null]);
        bindModuleToggles(0x11, subCompTube, 'CompTube',
            [0x05, null, null, null, null, null, null, null]);
        
        // VintageCompressor: paramId 0x04 is Att-Mode (Punch, toggle),
        // 0x05 is Release (cont!), 0x06 is Au-Release (toggle).
        //   0x01 Input, 0x02 Output, 0x03 Attack, 0x05 Release (cont)
        //   0x04 Att-Mode (Punch), 0x06 Au-Release (toggle)
        // Note: Ratio + Mix Dry-Wet aren't in our 16-position probe data —
        // they may be at sparse positions beyond 0x10 or need Cubase bank
        // zone customization. Reserved for next discovery pass.
        bindModuleEncoders(0x11, subCompVtg, 'CompVintage',
            [0x01, 0x02, 0x03, 0x05, null, null, null, null]);
        bindModuleToggles(0x11, subCompVtg, 'CompVintage',
            [0x04, 0x06, null, null, null, null, null, null]);
        
        // ── Tools variants (modId 0x12) ──
        
        // DeEsser:
        //   0x01 Threshold, 0x03 Reduction, 0x04 Release, 0x05 Lo Frq, 0x06 Hi Frq (cont)
        //   0x02 Au-Threshold, 0x07 Solo (toggle)
        // Diff toggle reported missing — likely at sparse position beyond 0x10,
        // not in current probe data.
        bindModuleEncoders(0x12, subToolsDe, 'ToolsDeesser',
            [0x01, 0x03, 0x04, 0x05, 0x06, null, null, null]);
        bindModuleToggles(0x12, subToolsDe, 'ToolsDeesser',
            [0x02, 0x07, null, null, null, null, null, null]);
        
        // EnvelopeShaper: 4 named cont params, no clear toggle in bank zone.
        //   0x01 Attk Gn, 0x02 AttLength, 0x04 Rel Gn, 0x06 Output (cont)
        //   paramIds 0x03 and 0x05 are unnamed in dumps — they have values
        //   but no title arrived. Likely Cubase didn't fire title callbacks
        //   for them — they may be RelLength and similar curve params.
        bindModuleEncoders(0x12, subToolsEnv, 'ToolsEnvShaper',
            [0x01, 0x02, 0x04, 0x06, null, null, null, null]);
        bindModuleToggles(0x12, subToolsEnv, 'ToolsEnvShaper',
            [null, null, null, null, null, null, null, null]);
        
        // ── Saturator variants (modId 0x13) ──
        
        // Magneto II:
        //   0x01 Saturation, 0x02 Lo Frq, 0x03 Hi Frq, 0x04 HF Adjust, 0x07 Output (cont)
        //   0x05 HF-On, 0x06 Solo (toggle)
        bindModuleEncoders(0x13, subSatMag, 'SatMagneto',
            [0x01, 0x02, 0x03, 0x04, 0x07, null, null, null]);
        bindModuleToggles(0x13, subSatMag, 'SatMagneto',
            [0x05, 0x06, null, null, null, null, null, null]);
        
        // Tape Saturation:
        //   0x01 Drive, 0x02 Lo Filter, 0x03 Hi Filter, 0x07 Output (cont)
        //   0x05 Dual, 0x06 Au-Gain (toggle)
        // paramId 0x04 is unnamed (likely a Saturation Type or curve param).
        bindModuleEncoders(0x13, subSatTape, 'SatTape',
            [0x01, 0x02, 0x03, 0x07, null, null, null, null]);
        bindModuleToggles(0x13, subSatTape, 'SatTape',
            [0x05, 0x06, null, null, null, null, null, null]);
        
        // Tube Saturation: NO toggles, Output is at 0x06 (different from
        // Magneto/Tape which have Output at 0x07).
        //   0x01 Drive, 0x02 Lo Filter, 0x03 Hi Filter, 0x06 Output (cont)
        // paramIds 0x04, 0x05, 0x07 are unnamed/empty.
        bindModuleEncoders(0x13, subSatTube, 'SatTube',
            [0x01, 0x02, 0x03, 0x06, null, null, null, null]);
        bindModuleToggles(0x13, subSatTube, 'SatTube',
            [null, null, null, null, null, null, null, null]);
        
        // ── Limiter variants (modId 0x14) ──
        
        // Brickwall Limiter:
        //   0x01 Thresh, 0x04 Release (cont)
        //   0x05 Au-Release (toggle)
        bindModuleEncoders(0x14, subLimBrick, 'LimitBrickwall',
            [0x01, 0x04, null, null, null, null, null, null]);
        bindModuleToggles(0x14, subLimBrick, 'LimitBrickwall',
            [0x05, null, null, null, null, null, null, null]);
        
        // Maximizer: 3 cont params, no toggle.
        //   0x01 Optimize, 0x03 Mix, 0x06 Output
        bindModuleEncoders(0x14, subLimMax, 'LimitMaximizer',
            [0x01, 0x03, 0x06, null, null, null, null, null]);
        bindModuleToggles(0x14, subLimMax, 'LimitMaximizer',
            [null, null, null, null, null, null, null, null]);
        
        // Standard Limiter:
        //   0x01 Input, 0x04 Release, 0x07 Output (cont)
        //   0x05 Au-Release (toggle)
        bindModuleEncoders(0x14, subLimStd, 'LimitStandard',
            [0x01, 0x04, 0x07, null, null, null, null, null]);
        bindModuleToggles(0x14, subLimStd, 'LimitStandard',
            [0x05, null, null, null, null, null, null, null]);
        
    } catch(e) {
        console.log("[Strip 1d] outer error: " + e);
    }
})();

