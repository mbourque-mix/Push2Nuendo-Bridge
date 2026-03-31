"""
control_room.py — Control Room mode for the Push 2

Manages 4 pages: MAIN, PHONES, CUE, MONITORS
Each page uses 8 encoders, 8 upper buttons, 8 lower buttons.
"""

# ── CC Map: each CR parameter has a fixed CC in the JS ──

# MAIN page encoders
CR_CC_MAIN_LEVEL       = 91
CR_CC_MAIN_CLICK_LVL   = 92
CR_CC_MAIN_LISTEN_LVL  = 93
CR_CC_REF_LEVEL        = 94
CR_CC_LISTEN_DIM_LVL   = 95

# MAIN page buttons
CR_CC_DIM_ONOFF        = 11
CR_CC_REF_ENABLED      = 15
CR_CC_MON_A            = 17
CR_CC_MON_B            = 18
CR_CC_TALKBACK         = 28
CR_CC_MAIN_CLICK_ON    = 29
CR_CC_MAIN_LISTEN_ON   = 30
CR_CC_MAIN_CUE1        = 31
CR_CC_MAIN_CUE2        = 49
CR_CC_MAIN_CUE3        = 71
CR_CC_MAIN_CUE4        = 72
CR_CC_MAIN_MUTE        = 73
CR_CC_MAIN_RESET       = 78

# PHONES page encoders
CR_CC_PHONES_LEVEL     = 96
CR_CC_PHONES_CLICK_LVL = 97
CR_CC_PHONES_LISTEN_LVL = 98

# PHONES page buttons
CR_CC_PHONES_CLICK_ON  = 36
CR_CC_PHONES_LISTEN_ON = 37
CR_CC_PHONES_CUE1      = 38
CR_CC_PHONES_CUE2      = 39
CR_CC_PHONES_CUE3      = 32
CR_CC_PHONES_CUE4      = 33
CR_CC_PHONES_MUTE      = 34

# CUE page encoders
CR_CC_CUE1_LEVEL       = 41
CR_CC_CUE2_LEVEL       = 42
CR_CC_CUE3_LEVEL       = 43
CR_CC_CUE4_LEVEL       = 44

# CUE page buttons
CR_CC_CUE1_MUTE        = 35
CR_CC_CUE2_MUTE        = 66
CR_CC_CUE3_MUTE        = 67
CR_CC_CUE4_MUTE        = 68

# MONITORS page encoders
CR_CC_MON0_LEVEL       = 45
CR_CC_MON1_LEVEL       = 62
CR_CC_TB_DIM_LEVEL     = 63


# ── Param IDs for SysEx feedback ──
# Continuous values (SysEx 0x0E)
PARAM_MAIN_LEVEL       = 0
PARAM_MAIN_CLICK_LVL   = 1
PARAM_MAIN_LISTEN_LVL  = 2
PARAM_REF_LEVEL        = 3
PARAM_LISTEN_DIM_LVL   = 4
PARAM_PHONES_LEVEL     = 30
PARAM_PHONES_CLICK_LVL = 31
PARAM_PHONES_LISTEN_LVL = 32
PARAM_CUE1_LEVEL       = 50
PARAM_CUE2_LEVEL       = 51
PARAM_CUE3_LEVEL       = 52
PARAM_CUE4_LEVEL       = 53
PARAM_MON0_LEVEL       = 60
PARAM_MON1_LEVEL       = 61
PARAM_TB_DIM_LEVEL     = 62

# Toggles (SysEx 0x0F)
PARAM_DIM_ONOFF        = 10
PARAM_REF_ENABLED      = 11
PARAM_MON_A            = 12
PARAM_MON_B            = 13
PARAM_TALKBACK         = 14
PARAM_MAIN_CLICK_ON    = 15
PARAM_MAIN_LISTEN_ON   = 16
PARAM_MAIN_MUTE        = 22
PARAM_MAIN_CUE1        = 17
PARAM_MAIN_CUE2        = 18
PARAM_MAIN_CUE3        = 19
PARAM_MAIN_CUE4        = 20
PARAM_PHONES_CLICK_ON  = 40
PARAM_PHONES_LISTEN_ON = 41
PARAM_PHONES_CUE1      = 42
PARAM_PHONES_CUE2      = 43
PARAM_PHONES_CUE3      = 44
PARAM_PHONES_CUE4      = 45
PARAM_PHONES_MUTE      = 46
PARAM_CUE1_MUTE        = 54
PARAM_CUE2_MUTE        = 55
PARAM_CUE3_MUTE        = 56
PARAM_CUE4_MUTE        = 57


CR_PAGE_MAIN    = 0
CR_PAGE_PHONES  = 1
CR_PAGE_CUE     = 2
CR_PAGE_SOURCES = 3

CR_PAGE_NAMES = ['MAIN', 'PHONES', 'CUE', 'SOURCES']

# ── Layout per page ──
# Each page defines:
#   encoders: [(label, cc, param_id), ...] for the 8 knobs
#   upper_btns: [(label, cc, param_id, is_toggle), ...] for the 8 upper buttons
#   lower_btn_page_indices: [page_index, ...] for the lower buttons (navigation)

CR_PAGES = {
    CR_PAGE_MAIN: {
        'encoders': [
            ('Main Level', CR_CC_MAIN_LEVEL, PARAM_MAIN_LEVEL, 12),
            ('Click Lvl',  CR_CC_MAIN_CLICK_LVL, PARAM_MAIN_CLICK_LVL, 12),
            ('Listen Lvl', CR_CC_MAIN_LISTEN_LVL, PARAM_MAIN_LISTEN_LVL, 18),
            ('Ref Level',  CR_CC_REF_LEVEL, PARAM_REF_LEVEL, 12),
            ('Listen Dim', CR_CC_LISTEN_DIM_LVL, PARAM_LISTEN_DIM_LVL, 12),
            None, None, None,
        ],
        'upper_btns': [
            ('Dim',      CR_CC_DIM_ONOFF,     PARAM_DIM_ONOFF, True),
            ('Ref',      CR_CC_REF_ENABLED,   PARAM_REF_ENABLED, True),
            ('Mon A',    CR_CC_MON_A,         PARAM_MON_A, True),
            ('Mon B',    CR_CC_MON_B,         PARAM_MON_B, True),
            ('Talkback', CR_CC_TALKBACK,      PARAM_TALKBACK, True),
            ('Click',    CR_CC_MAIN_CLICK_ON, PARAM_MAIN_CLICK_ON, True),
            ('Listen',   CR_CC_MAIN_LISTEN_ON, PARAM_MAIN_LISTEN_ON, True),
            ('Mute',     CR_CC_MAIN_MUTE,     PARAM_MAIN_MUTE, True),
        ],
        'lower_btns': [
            ('Cue 1', CR_CC_MAIN_CUE1, PARAM_MAIN_CUE1),
            ('Cue 2', CR_CC_MAIN_CUE2, PARAM_MAIN_CUE2),
            ('Cue 3', CR_CC_MAIN_CUE3, PARAM_MAIN_CUE3),
            ('Cue 4', CR_CC_MAIN_CUE4, PARAM_MAIN_CUE4),
            None, None, None, None,
        ],
    },
    CR_PAGE_PHONES: {
        'encoders': [
            ('Phones',   CR_CC_PHONES_LEVEL, PARAM_PHONES_LEVEL, 12),
            ('Click Lvl', CR_CC_PHONES_CLICK_LVL, PARAM_PHONES_CLICK_LVL, 12),
            ('Listen Lvl', CR_CC_PHONES_LISTEN_LVL, PARAM_PHONES_LISTEN_LVL, 18),
            None, None, None, None, None,
        ],
        'upper_btns': [
            None,
            None,
            None,
            None,
            ('Talkback', CR_CC_TALKBACK,       PARAM_TALKBACK, True),
            ('Click',    CR_CC_PHONES_CLICK_ON, PARAM_PHONES_CLICK_ON, True),
            ('Listen',   CR_CC_PHONES_LISTEN_ON, PARAM_PHONES_LISTEN_ON, True),
            ('Mute',     CR_CC_PHONES_MUTE,     PARAM_PHONES_MUTE, True),
        ],
        'lower_btns': [
            ('Cue 1', CR_CC_PHONES_CUE1, PARAM_PHONES_CUE1),
            ('Cue 2', CR_CC_PHONES_CUE2, PARAM_PHONES_CUE2),
            ('Cue 3', CR_CC_PHONES_CUE3, PARAM_PHONES_CUE3),
            ('Cue 4', CR_CC_PHONES_CUE4, PARAM_PHONES_CUE4),
            None, None, None, None,
        ],
    },
    CR_PAGE_CUE: {
        'encoders': [
            ('Cue 1', CR_CC_CUE1_LEVEL, PARAM_CUE1_LEVEL, 12),
            ('Cue 2', CR_CC_CUE2_LEVEL, PARAM_CUE2_LEVEL, 12),
            ('Cue 3', CR_CC_CUE3_LEVEL, PARAM_CUE3_LEVEL, 12),
            ('Cue 4', CR_CC_CUE4_LEVEL, PARAM_CUE4_LEVEL, 12),
            None, None, None, None,
        ],
        'upper_btns': [
            ('Cue1 Mute', CR_CC_CUE1_MUTE, PARAM_CUE1_MUTE, True),
            ('Cue2 Mute', CR_CC_CUE2_MUTE, PARAM_CUE2_MUTE, True),
            ('Cue3 Mute', CR_CC_CUE3_MUTE, PARAM_CUE3_MUTE, True),
            ('Cue4 Mute', CR_CC_CUE4_MUTE, PARAM_CUE4_MUTE, True),
            None, None, None, None,
        ],
        'lower_btns': [
            None, None, None, None,
            None, None, None, None,
        ],
    },
    CR_PAGE_SOURCES: {
        'encoders': [
            ('Mon A Lvl', CR_CC_MON0_LEVEL, PARAM_MON0_LEVEL, 12),
            ('Mon B Lvl', CR_CC_MON1_LEVEL, PARAM_MON1_LEVEL, 12),
            ('TB Dim',    CR_CC_TB_DIM_LEVEL, PARAM_TB_DIM_LEVEL, 12),
            None, None, None, None, None,
        ],
        'upper_btns': [
            ('Mon A', CR_CC_MON_A, PARAM_MON_A, True),
            ('Mon B', CR_CC_MON_B, PARAM_MON_B, True),
            None, None, None, None, None, None,
        ],
        'lower_btns': [
            None, None, None, None,
            None, None, None, None,
        ],
    },
}


class ControlRoomState:
    """Stores Control Room values received via feedback."""
    
    def __init__(self):
        self.values = {}    # param_id → float 0.0-1.0
        self.toggles = {}   # param_id → bool
        self.displays = {}  # param_id → string (dB value formatted by Nuendo)
        self.page = CR_PAGE_MAIN
    
    def set_value(self, param_id, value_127):
        self.values[param_id] = value_127 / 127.0
    
    def set_toggle(self, param_id, on):
        self.toggles[param_id] = on
    
    def set_display(self, param_id, text):
        self.displays[param_id] = text
    
    def get_value(self, param_id):
        return self.values.get(param_id, 0.0)
    
    def get_toggle(self, param_id):
        return self.toggles.get(param_id, False)
    
    def get_display(self, param_id):
        return self.displays.get(param_id, "")
