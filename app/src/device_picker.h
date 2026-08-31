#ifndef SC_DEVICE_PICKER_H
#define SC_DEVICE_PICKER_H

#include "common.h"

#include <stdbool.h>
#include <stddef.h>

#include "adb/adb_device.h"

enum sc_device_picker_result {
    SC_DEVICE_PICKER_UNAVAILABLE,
    SC_DEVICE_PICKER_CANCEL,
    SC_DEVICE_PICKER_START,
    SC_DEVICE_PICKER_ERROR,
};

/**
 * Return the human-readable connection type for an ADB serial.
 */
const char *
sc_device_picker_type_name(const char *serial);

/**
 * Return whether an ADB device can be started by scrcpy.
 */
bool
sc_device_picker_device_is_ready(const struct sc_adb_device *device);

struct sc_device_picker_selection {
    char **serials;
    size_t count;
};

void
sc_device_picker_selection_destroy(struct sc_device_picker_selection *selection);

/**
 * Show a platform picker for the provided ADB devices.
 *
 * The selection owns its serial copies and must be destroyed by the caller.
 */
enum sc_device_picker_result
sc_device_picker_run(const struct sc_vec_adb_devices *devices,
                     struct sc_device_picker_selection *selection);

#endif
