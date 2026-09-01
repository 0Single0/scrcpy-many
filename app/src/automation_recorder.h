#ifndef SCRCPY_AUTOMATION_RECORDER_H
#define SCRCPY_AUTOMATION_RECORDER_H

#include <stdbool.h>
#include <stdint.h>

// Values intentionally match SDL finger event ordering used by scrcpy.
enum sc_automation_touch_action {
    SC_AUTOMATION_TOUCH_DOWN = 1,
    SC_AUTOMATION_TOUCH_MOTION = 2,
    SC_AUTOMATION_TOUCH_UP = 3,
};

bool
sc_automation_recorder_start(const char *path, const char *serial,
                              uint16_t width, uint16_t height);

bool
sc_automation_recorder_record_touch(uint8_t action, int32_t x, int32_t y,
                                    uint16_t width, uint16_t height,
                                    uint32_t elapsed_ms);

bool
sc_automation_recorder_record_key(uint32_t keycode, uint32_t elapsed_ms);

void
sc_automation_recorder_stop(void);

#endif
