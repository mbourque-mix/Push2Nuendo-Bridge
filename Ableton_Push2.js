// =============================================================================
// Ableton_Push2.js — Script MIDI Remote pour Nuendo 14
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
    } else if (scanCooldown <= 0) {
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
        }
    }

    if (scanCooldown > 0) scanCooldown--;

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
    var insertBypassVar = surface.makeCustomValueVariable("insertBypass");

    page.makeActionBinding(insertResetVar, insertsViewer.mAction.mReset);
    page.makeActionBinding(insertNextVar, insertsViewer.mAction.mNext);
    page.makeValueBinding(insertEditVar, insertsViewer.mEdit);
    page.makeValueBinding(insertBypassVar, insertsViewer.mBypass);

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

    // BYPASS : 8 viewers dédiés
    // CC 30-37 : toggle bypass slot 0-7
    // Note 60-67 channel 1 : Reset viewer 0-7
    // Note 70-77 channel 1 : Next viewer 0-7
    var insertBypassViewers = [];
    
    for (var bv = 0; bv < 8; bv++) {
        try {
            var bViewer = page.mHostAccess.mTrackSelection.mMixerChannel.mInsertAndStripEffects.makeInsertEffectViewer("bypassViewer" + bv);
            
            // Bypass toggle via CC 20+bv channel 4
            var bBtn = surface.makeButton(20 + bv, 24 + bv * 2, 2, 2);
            bBtn.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToControlChange(3, 20 + bv);
            page.makeValueBinding(bBtn.mSurfaceValue, bViewer.mBypass).setTypeToggle();
            
            // Reset via Note 60+bv
            var bReset = surface.makeButton(60 + bv, 40 + bv * 2, 2, 2);
            bReset.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToNote(0, 60 + bv);
            page.makeActionBinding(bReset.mSurfaceValue, bViewer.mAction.mReset);
            
            // Next via Note 70+bv
            var bNext = surface.makeButton(70 + bv, 56 + bv * 2, 2, 2);
            bNext.mSurfaceValue.mMidiBinding.setInputPort(midiInput_Loop).bindToNote(0, 70 + bv);
            page.makeActionBinding(bNext.mSurfaceValue, bViewer.mAction.mNext);
            
            insertBypassViewers.push(bViewer);
            
            // Feedback bypass : envoyer l'état au bridge
            bViewer.mBypass.mOnProcessValueChange = (function(slotIdx) {
                return function(activeDevice, activeMapping, value) {
                    midiOutput_Loop.sendMidi(activeDevice, [0xF0, 0x00, 0x13, slotIdx & 0x7F, value > 0.5 ? 1 : 0, 0xF7]);
                };
            })(bv);
            
            console.log('Bypass viewer ' + bv + ' OK (CC' + (30+bv) + '/N' + (60+bv) + '/N' + (70+bv) + ')');
        } catch(e) {
            console.log('Bypass viewer ' + bv + ' error: ' + e);
        }
    }

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

