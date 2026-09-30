// Copyright 2026 Rotep
// SPDX-License-Identifier: GPL-2.0-or-later
// ScissorBall 36 – keyboard level config
#pragma once

/* ---- split ---- */
#define SPLIT_POINTING_ENABLE          // trackball lives on the right half
#define POINTING_DEVICE_RIGHT

/* ---- PMW3360 on SPI0 (right half only) ---- */
#define SPI_DRIVER SPID0
#define SPI_SCK_PIN GP2
#define SPI_MOSI_PIN GP3
#define SPI_MISO_PIN GP4
#define PMW33XX_CS_PIN GP13
#define PMW33XX_CPI 800
#define PMW33XX_LIFTOFF_DISTANCE 0x02

/* Sensor looks UP at the ball bottom through the breakout; adjust these two
 * lines if the pointer moves the wrong way (see docs/組立手順.md). */
#define POINTING_DEVICE_ROTATION_90
#define POINTING_DEVICE_INVERT_X

/* ---- auto mouse layer (clicks appear under the right fingers while the ball moves) ---- */
#define POINTING_DEVICE_AUTO_MOUSE_ENABLE
#define AUTO_MOUSE_DEFAULT_LAYER 4
#define AUTO_MOUSE_TIME 650
#define AUTO_MOUSE_DEBOUNCE 25

/* ---- misc ---- */
#define RP2040_BOOTLOADER_DOUBLE_TAP_RESET
#define RP2040_BOOTLOADER_DOUBLE_TAP_RESET_TIMEOUT 500U
#define TAPPING_TERM 200
#define PERMISSIVE_HOLD
