#include "common.h"

#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef HAVE_V4L2
# include <libavdevice/avdevice.h>
#endif
#include <SDL3/SDL.h>

#include "cli.h"
#ifdef _WIN32
# include "adb/adb.h"
# include "adb/adb_device.h"
# include "device_picker.h"
# include "util/intr.h"
# include "util/memory.h"
# include "util/process.h"
#endif
#include "events.h"
#include "options.h"
#include "scrcpy.h"
#ifdef HAVE_USB
# include "usb/scrcpy_otg.h"
#endif
#include "util/log.h"
#include "util/net.h"
#include "util/term.h"
#include "version.h"

#ifdef _WIN32
#include <windows.h>
#include "util/str.h"
#endif

#ifdef _WIN32
static bool
has_explicit_device_selector(const struct scrcpy_options *options) {
    return options->serial || options->tcpip_dst || options->select_usb
        || options->select_tcpip;
}

static bool
list_adb_devices(struct sc_vec_adb_devices *devices) {
    struct sc_intr intr;
    if (!sc_intr_init(&intr)) {
        LOGE("Could not initialize ADB interruptor");
        return false;
    }

    bool ok = sc_adb_init();
    if (ok) {
        ok = sc_adb_list_devices(&intr, 0, devices);
    }
    sc_adb_destroy();
    sc_intr_destroy(&intr);
    return ok;
}

static size_t
count_ready_devices(const struct sc_vec_adb_devices *devices,
                    size_t *ready_index) {
    size_t count = 0;
    for (size_t i = 0; i < devices->size; ++i) {
        if (!strcmp(devices->data[i].state, "device")) {
            if (ready_index && !count) {
                *ready_index = i;
            }
            ++count;
        }
    }
    return count;
}

static bool
launch_scrcpy_children(int argc, char *argv[],
                        const struct sc_device_picker_selection *selection) {
    size_t command_size = (size_t) argc + 3;
    const char **command = sc_allocarray(command_size, sizeof(*command));
    if (!command) {
        LOG_OOM();
        return false;
    }

    memcpy(command, argv, (size_t) argc * sizeof(*command));
    command[argc] = "--serial";

    bool all_ok = true;
    for (size_t i = 0; i < selection->count; ++i) {
        command[argc + 1] = selection->serials[i];
        command[argc + 2] = NULL;

        sc_pid pid;
        enum sc_process_result result =
            sc_process_execute(command, &pid,
                               SC_PROCESS_NO_STDOUT | SC_PROCESS_NO_STDERR);
        if (result != SC_PROCESS_SUCCESS) {
            LOGE("Could not start scrcpy for device %s",
                 selection->serials[i]);
            all_ok = false;
            continue;
        }

        // The child is detached on Windows by the process flags above. The
        // parent does not own its lifetime, so close its process handle.
        sc_process_close(pid);
    }

    free(command);
    return all_ok;
}

static bool
maybe_select_devices(int argc, char *argv[], struct scrcpy_cli_args *args,
                     bool *skip_scrcpy, char **owned_serial) {
    *skip_scrcpy = false;
    *owned_serial = NULL;

    if (args->opts.no_device_picker || args->opts.list
            || has_explicit_device_selector(&args->opts)) {
        return true;
    }

#ifdef HAVE_USB
    if (args->opts.otg) {
        return true;
    }
#endif

    struct sc_vec_adb_devices devices = SC_VECTOR_INITIALIZER;
    if (!list_adb_devices(&devices)) {
        sc_adb_devices_destroy(&devices);
        return false;
    }

    size_t ready_index;
    size_t ready_count = count_ready_devices(&devices, &ready_index);
    if (ready_count == 0) {
        sc_adb_devices_destroy(&devices);
        return true;
    }
    if (ready_count == 1) {
        // Avoid the normal "multiple devices" error when the other entries
        // are unauthorized or offline.
        *owned_serial = devices.data[ready_index].serial;
        args->opts.serial = *owned_serial;
        devices.data[ready_index].serial = NULL;
        sc_adb_devices_destroy(&devices);
        return true;
    }

    struct sc_device_picker_selection selection;
    enum sc_device_picker_result result =
        sc_device_picker_run(&devices, &selection);
    sc_adb_devices_destroy(&devices);

    if (result == SC_DEVICE_PICKER_CANCEL) {
        *skip_scrcpy = true;
        return true;
    }
    if (result != SC_DEVICE_PICKER_START || !selection.count) {
        sc_device_picker_selection_destroy(&selection);
        return false;
    }

    if (selection.count == 1) {
        *owned_serial = selection.serials[0];
        args->opts.serial = *owned_serial;
        free(selection.serials);
        selection.serials = NULL;
        selection.count = 0;
        return true;
    }

    bool ok = launch_scrcpy_children(argc, argv, &selection);
    sc_device_picker_selection_destroy(&selection);
    *skip_scrcpy = true;
    return ok;
}
#endif

static int
main_scrcpy(int argc, char *argv[]) {
#ifdef _WIN32
    // disable buffering, we want logs immediately
    // even line buffering (setvbuf() with mode _IOLBF) is not sufficient
    setbuf(stdout, NULL);
    setbuf(stderr, NULL);
#endif

    printf("scrcpy " SCRCPY_VERSION
           " <https://github.com/Genymobile/scrcpy>\n");

    struct scrcpy_cli_args args = {
        .opts = scrcpy_options_default,
        .help = false,
        .version = false,
        .pause_on_exit = SC_PAUSE_ON_EXIT_UNDEFINED,
    };

#ifndef NDEBUG
    args.opts.log_level = SC_LOG_LEVEL_DEBUG;
#endif

    enum scrcpy_exit_code ret;

    bool term_title_saved = false;

    if (!scrcpy_parse_args(&args, argc, argv)) {
        ret = SCRCPY_EXIT_FAILURE;
        goto end;
    }

    sc_set_log_level(args.opts.log_level);

    if (args.opts.update_terminal_title) {
        sc_term_save_title();
        sc_term_set_title("scrcpy");
        term_title_saved = true;
    }

    if (args.help) {
        scrcpy_print_usage(argv[0]);
        ret = SCRCPY_EXIT_SUCCESS;
        goto end;
    }

    if (args.version) {
        scrcpy_print_version();
        ret = SCRCPY_EXIT_SUCCESS;
        goto end;
    }

#ifdef SCRCPY_LAVF_REQUIRES_REGISTER_ALL
    av_register_all();
#endif

#ifdef HAVE_V4L2
    if (args.opts.v4l2_device) {
        avdevice_register_all();
    }
#endif

    if (!net_init()) {
        ret = SCRCPY_EXIT_FAILURE;
        goto end;
    }

    sc_log_configure();

    if (!sc_main_thread_init()) {
        ret = SCRCPY_EXIT_FAILURE;
        goto net_cleanup;
    }

#ifdef _WIN32
    bool skip_scrcpy;
    char *owned_serial = NULL;
    if (!maybe_select_devices(argc, argv, &args, &skip_scrcpy,
                              &owned_serial)) {
        free(owned_serial);
        ret = SCRCPY_EXIT_FAILURE;
        goto main_thread_cleanup;
    }
    if (skip_scrcpy) {
        free(owned_serial);
        ret = SCRCPY_EXIT_SUCCESS;
        goto main_thread_cleanup;
    }
#endif

#ifdef HAVE_USB
    ret = args.opts.otg ? scrcpy_otg(&args.opts) : scrcpy(&args.opts);
#else
    ret = scrcpy(&args.opts);
#endif

#ifdef _WIN32
    free(owned_serial);
#endif

main_thread_cleanup:
    sc_main_thread_destroy();

net_cleanup:
    net_cleanup();

end:
    if (args.pause_on_exit == SC_PAUSE_ON_EXIT_TRUE ||
            (args.pause_on_exit == SC_PAUSE_ON_EXIT_IF_ERROR &&
                ret != SCRCPY_EXIT_SUCCESS)) {
        printf("Press Enter to continue...\n");
        getchar();
    }

    if (term_title_saved) {
        sc_term_set_title(""); // fallback if restore is ignored
        sc_term_restore_title();
    }

    return ret;
}

int
main(int argc, char *argv[]) {
#ifndef _WIN32
    return main_scrcpy(argc, argv);
#else
    (void) argc;
    (void) argv;
    int wargc;
    wchar_t **wargv = CommandLineToArgvW(GetCommandLineW(), &wargc);
    if (!wargv) {
        LOG_OOM();
        return SCRCPY_EXIT_FAILURE;
    }

    char **argv_utf8 = malloc((wargc + 1) * sizeof(*argv_utf8));
    if (!argv_utf8) {
        LOG_OOM();
        LocalFree(wargv);
        return SCRCPY_EXIT_FAILURE;
    }

    argv_utf8[wargc] = NULL;

    for (int i = 0; i < wargc; ++i) {
        argv_utf8[i] = sc_str_from_wchars(wargv[i]);
        if (!argv_utf8[i]) {
            LOG_OOM();
            for (int j = 0; j < i; ++j) {
                free(argv_utf8[j]);
            }
            LocalFree(wargv);
            free(argv_utf8);
            return SCRCPY_EXIT_FAILURE;
        }
    }

    LocalFree(wargv);

    int ret = main_scrcpy(wargc, argv_utf8);

    for (int i = 0; i < wargc; ++i) {
        free(argv_utf8[i]);
    }
    free(argv_utf8);

    return ret;
#endif
}
