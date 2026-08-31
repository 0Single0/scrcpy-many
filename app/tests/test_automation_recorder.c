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
        SC_AUTOMATION_TOUCH_UP, 10, 20, 1080, 1920, 100));
    assert(sc_automation_recorder_record_key(4, 1, 50));
    sc_automation_recorder_stop();

    FILE *file = fopen(path, "rb");
    assert(file);
    char buffer[4096] = {0};
    size_t size = fread(buffer, 1, sizeof buffer - 1, file);
    fclose(file);
    remove(path);
    assert(size > 0);
    assert(strstr(buffer, "\"action\":\"tap\"") != NULL);
    assert(strstr(buffer, "\"action\":\"keyevent\"") != NULL);
    assert(strstr(buffer, "\"ms\":50") != NULL);
    return 0;
}
