// =============================================================================
// Ableton_Push2.js — MIDI Remote Script for Nuendo / Cubase
// Version 1.0.3
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

var JS_VERSION = '1.0.3';

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

    // Main Level Reset (absolu)
    var crMainResetKnob = surface.makeKnob(78, 40, 2, 2);
    crMainResetKnob.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(0, 78).setTypeAbsolute();
    page.makeValueBinding(crMainResetKnob.mSurfaceValue, crMain.mLevelValue);

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

    page.mOnActivate = function(activeDevice, activeMapping) {
        daMapping = activeMapping;
        daAvailable = false;
        daInsActive = false;
        daInsExplored = false;
        daInsSlotCache = [];
        midiOutput_Loop.sendMidi(activeDevice, [0xB0, 68, 1]);
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
    // Sends each param to Python via SysEx 0x29, then completion via 0x2A.
    function daEnumPluginParams(activeDevice, activeMapping, slotIdx) {
        if (!daInsExplored || slotIdx >= daInsSlotCache.length) {
            console.log('DA Enum: cache not ready or slot ' + slotIdx + ' out of range');
            return;
        }
        var entry = daInsSlotCache[slotIdx];
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
            console.log('DA Enum slot ' + slotIdx + ' (' + entry.title + '): ' + paramCount + ' params (sending ' + maxParams + ')');

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
        // High bits
        var hiBtn = surface.makeButton(9 + ei, 100, 2, 2);
        hiBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(8, 9 + ei);
        hiBtn.mSurfaceValue.mOnProcessValueChange = (function(idx) {
            return function(activeDevice, value, diff) {
                var hi = Math.round(value * 127);
                daEncParamIdx[idx] = (daEncParamIdx[idx] & 0x7F) | (hi << 7);
                // Once high bits received, resolve the DA tag and send display value
                if (daEncSlot >= 0 && daEncSlot < daInsSlotCache.length) {
                    var entry = daInsSlotCache[daEncSlot];
                    if (entry.pluginObjectID >= 0 && daMapping) {
                        try {
                            var m = daMapping;
                            var paramIdx = daEncParamIdx[idx];
                            var tag = daInserts.getParameterTagByIndex(m, entry.pluginObjectID, paramIdx);
                            daEncParamTag[idx] = tag;
                            // Read and send current display value
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
                }
            };
        })(ei);
    }

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

                if (daEncSlot < 0 || !daMapping || !daInsExplored) return;
                if (daEncSlot >= daInsSlotCache.length) return;
                var entry = daInsSlotCache[daEncSlot];
                if (entry.pluginObjectID < 0) return;
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
        // Only care about bypass changes on cached slots
        if (parameterTag !== SLOT_BYPASS_TAG) return;
        for (var i = 0; i < daInsSlotCache.length; i++) {
            if (daInsSlotCache[i].objectID === objectID) {
                var newVal = daInserts.getParameterProcessValue(activeMapping, objectID, parameterTag);
                var wasBypassed = daInsSlotCache[i].bypassed;
                daInsSlotCache[i].bypassed = (newVal > 0.5);
                if (wasBypassed !== daInsSlotCache[i].bypassed) {
                    midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x13, i & 0x7F, daInsSlotCache[i].bypassed ? 1 : 0, 0xF7]);
                    console.log('DA: bypass changed slot ' + i + ' (' + daInsSlotCache[i].title + '): ' + (daInsSlotCache[i].bypassed ? 'BYPASS' : 'ACTIVE'));
                }
                return;
            }
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

