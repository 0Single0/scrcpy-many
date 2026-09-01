#include "automation_recorder.h"

#include <stdio.h>
#include <string.h>

#define SC_AUTOMATION_RECORDER_MIN_WAIT_MS 200

struct sc_automation_recorder {
    FILE *file;
    char path[1024];
    char temp_path[1024];
    bool first_step;
    bool has_recorded_action;
    uint32_t pending_wait_ms;
    bool touch_down;
    uint32_t touch_elapsed_ms;
    int32_t touch_start_x;
    int32_t touch_start_y;
    int32_t touch_last_x;
    int32_t touch_last_y;
};

static struct sc_automation_recorder recorder;

static void
json_string(FILE *file, const char *value) {
    fputc('"', file);
    for (const unsigned char *p = (const unsigned char *) value; *p; ++p) {
        switch (*p) {
            case '\\': fputs("\\\\", file); break;
            case '"': fputs("\\\"", file); break;
            case '\n': fputs("\\n", file); break;
            case '\r': fputs("\\r", file); break;
            case '\t': fputs("\\t", file); break;
            default: fputc(*p, file); break;
        }
    }
    fputc('"', file);
}

static bool
step_prefix(void) {
    if (!recorder.file) {
        return false;
    }
    if (!recorder.first_step) {
        fputs(",\n    ", recorder.file);
    } else {
        fputs("\n    ", recorder.file);
        recorder.first_step = false;
    }
    return true;
}

static bool
record_pending_wait(void) {
    uint32_t elapsed_ms = recorder.pending_wait_ms;
    recorder.pending_wait_ms = 0;

    if (!recorder.has_recorded_action
            || elapsed_ms < SC_AUTOMATION_RECORDER_MIN_WAIT_MS) {
        return true;
    }
    if (!step_prefix()) {
        return false;
    }
    fprintf(recorder.file, "{\"action\":\"wait\",\"ms\":%u}", elapsed_ms);
    return true;
}

static void
add_pending_wait(uint32_t elapsed_ms) {
    if (UINT32_MAX - recorder.pending_wait_ms < elapsed_ms) {
        recorder.pending_wait_ms = UINT32_MAX;
    } else {
        recorder.pending_wait_ms += elapsed_ms;
    }
}

bool
sc_automation_recorder_start(const char *path, const char *serial,
                              uint16_t width, uint16_t height) {
    if (recorder.file || !path || !serial || !*path || !*serial
            || strlen(path) >= sizeof recorder.path) {
        return false;
    }
    int written = snprintf(recorder.temp_path, sizeof recorder.temp_path, "%s.tmp", path);
    if (written < 0 || (size_t) written >= sizeof recorder.temp_path) {
        return false;
    }
    FILE *file = fopen(recorder.temp_path, "wb");
    if (!file) {
        return false;
    }
    recorder.file = file;
    strcpy(recorder.path, path);
    recorder.first_step = true;
    recorder.has_recorded_action = false;
    recorder.pending_wait_ms = 0;
    recorder.touch_down = false;
    recorder.touch_elapsed_ms = 0;
    fputs("{\n  \"name\": \"recorded-actions\",\n  \"serial\": ", file);
    json_string(file, serial);
    fprintf(file, ",\n  \"metadata\": {\"width\": %u, \"height\": %u},\n  \"steps\": [", width, height);
    if (ferror(file)) {
        sc_automation_recorder_stop();
        return false;
    }
    return true;
}

bool
sc_automation_recorder_record_touch(uint8_t action, int32_t x, int32_t y,
                                    uint16_t width, uint16_t height,
                                    uint32_t elapsed_ms) {
    (void) width;
    (void) height;
    if (!recorder.file || x < 0 || y < 0) {
        return false;
    }
    switch (action) {
        case SC_AUTOMATION_TOUCH_DOWN:
            add_pending_wait(elapsed_ms);
            recorder.touch_down = true;
            recorder.touch_elapsed_ms = 0;
            recorder.touch_start_x = recorder.touch_last_x = x;
            recorder.touch_start_y = recorder.touch_last_y = y;
            return true;
        case SC_AUTOMATION_TOUCH_MOTION:
            if (!recorder.touch_down) {
                return false;
            }
            recorder.touch_elapsed_ms += elapsed_ms;
            recorder.touch_last_x = x;
            recorder.touch_last_y = y;
            return true;
        case SC_AUTOMATION_TOUCH_UP:
            if (!recorder.touch_down) {
                return false;
            }
            recorder.touch_elapsed_ms += elapsed_ms;
            recorder.touch_last_x = x;
            recorder.touch_last_y = y;
            if (!record_pending_wait()) {
                return false;
            }
            if (!step_prefix()) {
                return false;
            }
            if (recorder.touch_start_x == recorder.touch_last_x
                    && recorder.touch_start_y == recorder.touch_last_y) {
                fprintf(recorder.file, "{\"action\":\"tap\",\"x\":%d,\"y\":%d}",
                        x, y);
            } else {
                fprintf(recorder.file,
                        "{\"action\":\"swipe\",\"x1\":%d,\"y1\":%d,\"x2\":%d,\"y2\":%d,\"duration_ms\":%u}",
                        recorder.touch_start_x, recorder.touch_start_y,
                        x, y, recorder.touch_elapsed_ms);
            }
            recorder.touch_down = false;
            recorder.has_recorded_action = true;
            return !ferror(recorder.file);
        default:
            return false;
    }
}

bool
sc_automation_recorder_record_key(uint32_t keycode, uint32_t elapsed_ms) {
    if (!recorder.file) {
        return false;
    }
    add_pending_wait(elapsed_ms);
    if (!record_pending_wait()) {
        return false;
    }
    if (!step_prefix()) {
        return false;
    }
    fprintf(recorder.file, "{\"action\":\"keyevent\",\"code\":%u}", keycode);
    recorder.has_recorded_action = true;
    return !ferror(recorder.file);
}

void
sc_automation_recorder_stop(void) {
    if (!recorder.file) {
        return;
    }
    fputs("\n  ]\n}\n", recorder.file);
    bool ok = !ferror(recorder.file);
    fclose(recorder.file);
    recorder.file = NULL;
    if (ok) {
        if (rename(recorder.temp_path, recorder.path) != 0) {
            remove(recorder.temp_path);
        }
    } else {
        remove(recorder.temp_path);
    }
    if (ok) {
        recorder.path[0] = '\0';
    }
}
