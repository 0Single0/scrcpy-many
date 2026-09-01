#include "common.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "automation_recorder.h"

int
main(int argc, char *argv[]) {
    (void) argc;
    (void) argv;
    const char *path = "automation-recorder-test.json";
    remove(path);

    assert(sc_automation_recorder_start(path, "TEST123", 1080, 1920));
    assert(sc_automation_recorder_record_touch(
        SC_AUTOMATION_TOUCH_DOWN, 10, 20, 1080, 1920, 0));
    assert(sc_automation_recorder_record_touch(
        SC_AUTOMATION_TOUCH_MOTION, 10, 40, 1080, 1920, 1));
    assert(sc_automation_recorder_record_touch(
        SC_AUTOMATION_TOUCH_MOTION, 10, 80, 1080, 1920, 2));
    assert(sc_automation_recorder_record_touch(
        SC_AUTOMATION_TOUCH_MOTION, 10, 100, 1080, 1920, 6));
    assert(sc_automation_recorder_record_touch(
        SC_AUTOMATION_TOUCH_UP, 10, 120, 1080, 1920, 16));
    assert(sc_automation_recorder_record_touch(
        SC_AUTOMATION_TOUCH_DOWN, 30, 40, 1080, 1920, 500));
    assert(sc_automation_recorder_record_touch(
        SC_AUTOMATION_TOUCH_UP, 30, 40, 1080, 1920, 10));
    assert(sc_automation_recorder_record_key(4, 400));
    sc_automation_recorder_stop();

    FILE *file = fopen(path, "rb");
    assert(file);
    char buffer[4096] = {0};
    size_t size = fread(buffer, 1, sizeof buffer - 1, file);
    fclose(file);
    remove(path);
    assert(size > 0);
    assert(strstr(buffer, "\"action\":\"tap\"") != NULL);
    assert(strstr(buffer, "\"action\":\"keyevent\",\"code\":4") != NULL);
    assert(strstr(buffer, "\"key_action\"") == NULL);
    assert(strstr(buffer,
                  "\"action\":\"swipe\",\"x1\":10,\"y1\":20,\"x2\":10,\"y2\":120,\"duration_ms\":25") != NULL);
    assert(strstr(buffer, "\"action\":\"wait\",\"ms\":500}") != NULL);
    assert(strstr(buffer, "\"action\":\"wait\",\"ms\":400}") != NULL);
    assert(strstr(buffer, "\"action\":\"wait\",\"ms\":1}") == NULL);
    assert(strstr(buffer, "\"action\":\"wait\",\"ms\":2}") == NULL);
    assert(strstr(buffer, "\"action\":\"wait\",\"ms\":6}") == NULL);
    assert(strstr(buffer, "\"action\":\"wait\",\"ms\":16}") == NULL);
    return 0;
}
