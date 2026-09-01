#ifndef SC_KEYBOARD_SDK_H
#define SC_KEYBOARD_SDK_H

#include "common.h"

#include <stdbool.h>

#include "android/keycodes.h"
#include "controller.h"
#include "input_events.h"
#include "options.h"
#include "trait/key_processor.h"

struct sc_keyboard_sdk {
    struct sc_key_processor key_processor; // key processor trait

    struct sc_controller *controller;

    // SDL reports repeated events as a boolean, but Android expects the actual
    // number of repetitions. This variable keeps track of the count.
    unsigned repeat;

    enum sc_key_inject_mode key_inject_mode;
    bool forward_key_repeat;
};

void
sc_keyboard_sdk_init(struct sc_keyboard_sdk *kb,
                     struct sc_controller *controller,
                     enum sc_key_inject_mode key_inject_mode,
                     bool forward_key_repeat);

/**
 * Return the Android key code the SDK keyboard processor will inject for an
 * event. Non-SDK keyboard processors and text-only events are not recordable
 * as an Android key event.
 */
bool
sc_keyboard_sdk_get_android_keycode(const struct sc_key_processor *kp,
                                    const struct sc_key_event *event,
                                    enum android_keycode *keycode);

#endif
