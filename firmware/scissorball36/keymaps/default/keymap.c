// Copyright 2026 Rotep
// SPDX-License-Identifier: GPL-2.0-or-later
// ScissorBall 36 – default keymap
// OS side keyboard layout is assumed to be US.  (JIS users: see docs, symbols on _SYM shift)
#include QMK_KEYBOARD_H

enum layers { _BASE, _NUM, _SYM, _FN, _MOUSE };

enum custom_keycodes {
    DRG_SCR = SAFE_RANGE, // hold: trackball scrolls
    CPI_UP,
    CPI_DN,
};

// thumbs  (left: outer -> inner / right: inner -> outer)
#define TH_L2 LALT_T(KC_INT5)    // tap: 無変換 (IME off with MS-IME setting)
#define TH_L1 LCTL_T(KC_TAB)
#define TH_L0 LT(_NUM, KC_SPC)
#define TH_R0 LT(_SYM, KC_ENT)
#define TH_R1 RSFT_T(KC_BSPC)
#define TH_R4 LT(_FN, KC_INT4)   // tap: 変換 (IME on)

// clang-format off
const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
    [_BASE] = LAYOUT(
        KC_Q,    KC_W,    KC_E,    KC_R,    KC_T,         KC_Y,    KC_U,    KC_I,    KC_O,    KC_P,
        KC_A,    KC_S,    KC_D,    KC_F,    KC_G,         KC_H,    KC_J,    KC_K,    KC_L,    KC_SCLN,
        KC_Z,    KC_X,    KC_C,    KC_V,    KC_B,         KC_N,    KC_M,    KC_COMM, KC_DOT,  KC_SLSH,
                          TH_L2,   TH_L1,   TH_L0,        TH_R0,   TH_R1,                     TH_R4
    ),
    [_NUM] = LAYOUT(
        KC_1,    KC_2,    KC_3,    KC_4,    KC_5,         KC_6,    KC_7,    KC_8,    KC_9,    KC_0,
        KC_ESC,  KC_LGUI, KC_LALT, KC_LCTL, KC_LSFT,      KC_LEFT, KC_DOWN, KC_UP,   KC_RGHT, KC_BSPC,
        C(KC_Z), C(KC_X), C(KC_C), C(KC_V), C(KC_Y),      KC_HOME, KC_PGDN, KC_PGUP, KC_END,  KC_DEL,
                          _______, _______, _______,      KC_ENT,  _______,                   _______
    ),
    [_SYM] = LAYOUT(
        KC_EXLM, KC_AT,   KC_HASH, KC_DLR,  KC_PERC,      KC_CIRC, KC_AMPR, KC_ASTR, KC_LPRN, KC_RPRN,
        KC_GRV,  KC_MINS, KC_EQL,  KC_LBRC, KC_RBRC,      KC_BSLS, KC_QUOT, KC_DQUO, KC_COLN, KC_ESC,
        KC_TILD, KC_UNDS, KC_PLUS, KC_LCBR, KC_RCBR,      KC_PIPE, KC_LT,   KC_GT,   KC_QUES, KC_CAPS,
                          _______, _______, KC_SPC,       _______, _______,                   _______
    ),
    [_FN] = LAYOUT(
        KC_F1,   KC_F2,   KC_F3,   KC_F4,   KC_F5,        KC_F6,   KC_F7,   KC_F8,   KC_F9,   KC_F10,
        KC_F11,  KC_F12,  KC_PSCR, KC_MUTE, KC_VOLU,      CPI_DN,  CPI_UP,  XXXXXXX, XXXXXXX, XXXXXXX,
        QK_BOOT, EE_CLR,  XXXXXXX, KC_MPLY, KC_VOLD,      XXXXXXX, XXXXXXX, XXXXXXX, EE_CLR,  QK_BOOT,
                          _______, _______, _______,      _______, _______,                   _______
    ),
    [_MOUSE] = LAYOUT(
        _______, _______, _______, _______, _______,      _______, _______, _______, _______, _______,
        _______, _______, _______, _______, _______,      DRG_SCR, MS_BTN1, MS_BTN3, MS_BTN2, DRG_SCR,
        _______, _______, _______, _______, _______,      _______, MS_BTN4, MS_BTN5, _______, _______,
                          _______, _______, _______,      MS_BTN1, MS_BTN2,                   _______
    ),
};
// clang-format on

static bool     scrolling = false;
static float    acc_h = 0, acc_v = 0;
static uint16_t cpi       = 800;
#define SCROLL_DIVISOR 24.0f

void pointing_device_init_user(void) {
    set_auto_mouse_enable(true);
    pointing_device_set_cpi(cpi);
}

report_mouse_t pointing_device_task_user(report_mouse_t m) {
    if (scrolling) {
        acc_h += (float)m.x / SCROLL_DIVISOR;
        acc_v += (float)m.y / SCROLL_DIVISOR;
        m.h = (int8_t)acc_h;
        m.v = -(int8_t)acc_v;
        acc_h -= (int8_t)acc_h;
        acc_v -= (int8_t)acc_v;
        m.x = 0;
        m.y = 0;
    }
    return m;
}

bool is_mouse_record_user(uint16_t keycode, keyrecord_t *record) {
    return keycode == DRG_SCR;
}

bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    switch (keycode) {
        case DRG_SCR:
            scrolling = record->event.pressed;
            acc_h = acc_v = 0;
            return false;
        case CPI_UP:
        case CPI_DN:
            if (record->event.pressed) {
                if (keycode == CPI_UP && cpi < 3200) cpi += 200;
                if (keycode == CPI_DN && cpi > 200) cpi -= 200;
                pointing_device_set_cpi(cpi);
            }
            return false;
    }
    return true;
}
