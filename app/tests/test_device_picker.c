#include "common.h"

#include <assert.h>
#include <string.h>

#include "device_picker.h"

static void test_device_type_labels(void) {
    assert(!strcmp(sc_device_picker_type_name("0123456789"), "USB"));
    assert(!strcmp(sc_device_picker_type_name("192.168.1.8:5555"),
                   "TCP/IP"));
    assert(!strcmp(sc_device_picker_type_name("adb-tls-connect-foo"),
                   "TCP/IP"));
    assert(!strcmp(sc_device_picker_type_name("emulator-5554"),
                   "Emulator"));
}

static void test_device_readiness(void) {
    struct sc_adb_device ready = {
        .serial = "usb-serial",
        .state = "device",
    };
    struct sc_adb_device unauthorized = {
        .serial = "usb-serial",
        .state = "unauthorized",
    };

    assert(sc_device_picker_device_is_ready(&ready));
    assert(!sc_device_picker_device_is_ready(&unauthorized));
}

int main(int argc, char *argv[]) {
    (void) argc;
    (void) argv;
    test_device_type_labels();
    test_device_readiness();
    return 0;
}
