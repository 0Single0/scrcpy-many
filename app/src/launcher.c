#include <windows.h>

#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>

static bool
append_text(wchar_t **buffer, size_t *length, size_t *capacity,
            const wchar_t *text) {
    size_t text_length = wcslen(text);
    // Windows command lines and paths are well below this limit.
    const size_t max_length = 1u << 20;
    if (text_length > max_length
            || *length > max_length - text_length - 1) {
        return false;
    }
    size_t required = *length + text_length + 1;
    if (required > *capacity) {
        size_t next = *capacity ? *capacity : 256;
        while (next < required) {
            if (next > SIZE_MAX / 2) {
                next = required;
                break;
            }
            next *= 2;
        }
        wchar_t *resized = realloc(*buffer, next * sizeof(**buffer));
        if (!resized) {
            return false;
        }
        *buffer = resized;
        *capacity = next;
    }
    wmemcpy(*buffer + *length, text, text_length);
    *length += text_length;
    (*buffer)[*length] = L'\0';
    return true;
}

static bool
get_root_path(wchar_t *root, size_t capacity) {
    DWORD length = GetModuleFileNameW(NULL, root, (DWORD) capacity);
    if (!length || length >= capacity) {
        return false;
    }
    wchar_t *separator = wcsrchr(root, L'\\');
    if (!separator) {
        return false;
    }
    *separator = L'\0';
    return true;
}

static bool
build_path(wchar_t **path, const wchar_t *root, const wchar_t *relative) {
    size_t length = 0;
    size_t capacity = 0;
    *path = NULL;
    return append_text(path, &length, &capacity, root)
        && append_text(path, &length, &capacity, L"\\")
        && append_text(path, &length, &capacity, relative);
}

static const wchar_t *
skip_program_argument(const wchar_t *command_line) {
    const wchar_t *p = command_line;
    while (*p == L' ' || *p == L'\t') {
        ++p;
    }
    if (*p == L'\"') {
        ++p;
        while (*p && *p != L'\"') {
            ++p;
        }
        if (*p == L'\"') {
            ++p;
        }
    } else {
        while (*p && *p != L' ' && *p != L'\t') {
            ++p;
        }
    }
    while (*p == L' ' || *p == L'\t') {
        ++p;
    }
    return p;
}

static wchar_t *
build_core_command(const wchar_t *core_path) {
    const wchar_t *arguments = skip_program_argument(GetCommandLineW());
    size_t length = 0;
    size_t capacity = 0;
    wchar_t *command = NULL;
    if (!append_text(&command, &length, &capacity, L"\"")
            || !append_text(&command, &length, &capacity, core_path)
            || !append_text(&command, &length, &capacity, L"\"")) {
        free(command);
        return NULL;
    }
    if (*arguments) {
        if (!append_text(&command, &length, &capacity, L" ")
                || !append_text(&command, &length, &capacity, arguments)) {
            free(command);
            return NULL;
        }
    }
    return command;
}

static wchar_t *
build_environment_path(const wchar_t *root) {
    wchar_t *lib_path = NULL;
    wchar_t *tools_path = NULL;
    if (!build_path(&lib_path, root, L"lib")
            || !build_path(&tools_path, root, L"platform-tools")) {
        free(lib_path);
        free(tools_path);
        return NULL;
    }

    DWORD old_length = GetEnvironmentVariableW(L"PATH", NULL, 0);
    wchar_t *old_path = NULL;
    if (old_length) {
        old_path = malloc((size_t) old_length * sizeof(*old_path));
        if (!old_path || GetEnvironmentVariableW(L"PATH", old_path,
                                                 old_length) >= old_length) {
            free(lib_path);
            free(tools_path);
            free(old_path);
            return NULL;
        }
    }

    size_t length = 0;
    size_t capacity = 0;
    wchar_t *path = NULL;
    bool ok = append_text(&path, &length, &capacity, lib_path)
           && append_text(&path, &length, &capacity, L";")
           && append_text(&path, &length, &capacity, tools_path);
    if (ok && old_path && *old_path) {
        ok = append_text(&path, &length, &capacity, L";")
          && append_text(&path, &length, &capacity, old_path);
    }
    free(lib_path);
    free(tools_path);
    free(old_path);
    if (!ok) {
        free(path);
        return NULL;
    }
    return path;
}

int WINAPI
WinMain(HINSTANCE instance, HINSTANCE previous, LPSTR command_line, int show) {
    (void) instance;
    (void) previous;
    (void) command_line;
    (void) show;

    wchar_t root[MAX_PATH * 4];
    if (!get_root_path(root, sizeof(root) / sizeof(*root))) {
        return 1;
    }

    wchar_t *core_path = NULL;
    wchar_t *environment_path = NULL;
    wchar_t *command = NULL;
    if (!build_path(&core_path, root, L"bin\\scrcpy-core.exe")
            || !(environment_path = build_environment_path(root))
            || !(command = build_core_command(core_path))) {
        free(core_path);
        free(environment_path);
        free(command);
        return 1;
    }

    if (!SetEnvironmentVariableW(L"PATH", environment_path)) {
        free(core_path);
        free(environment_path);
        free(command);
        return 1;
    }

    STARTUPINFOW startup = {
        .cb = sizeof(startup),
    };
    PROCESS_INFORMATION process;
    bool created = CreateProcessW(core_path, command, NULL, NULL, FALSE, 0,
                                  NULL, root, &startup, &process);
    free(core_path);
    free(environment_path);
    free(command);
    if (!created) {
        return 1;
    }

    CloseHandle(process.hThread);
    WaitForSingleObject(process.hProcess, INFINITE);
    DWORD exit_code = 1;
    GetExitCodeProcess(process.hProcess, &exit_code);
    CloseHandle(process.hProcess);
    return (int) exit_code;
}
