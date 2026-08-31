#include "device_picker.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "util/log.h"

void
sc_device_picker_selection_destroy(struct sc_device_picker_selection *selection) {
    for (size_t i = 0; i < selection->count; ++i) {
        free(selection->serials[i]);
    }
    free(selection->serials);
    selection->serials = NULL;
    selection->count = 0;
}

const char *
sc_device_picker_type_name(const char *serial) {
    switch (sc_adb_device_get_type(serial)) {
        case SC_ADB_DEVICE_TYPE_USB:
            return "USB";
        case SC_ADB_DEVICE_TYPE_TCPIP:
            return "TCP/IP";
        case SC_ADB_DEVICE_TYPE_EMULATOR:
            return "Emulator";
    }
    return "Unknown";
}

bool
sc_device_picker_device_is_ready(const struct sc_adb_device *device) {
    return device->state && !strcmp(device->state, "device");
}

static bool
selection_add(struct sc_device_picker_selection *selection, const char *serial) {
    char *copy = strdup(serial);
    if (!copy) {
        return false;
    }

    char **serials = realloc(selection->serials,
                             (selection->count + 1) * sizeof(*serials));
    if (!serials) {
        free(copy);
        return false;
    }

    selection->serials = serials;
    selection->serials[selection->count++] = copy;
    return true;
}

#ifdef _WIN32

#include <windows.h>
#include <commctrl.h>

#include "util/str.h"

#define SC_DEVICE_PICKER_CONTROL_LIST 1001
#define SC_DEVICE_PICKER_CONTROL_START 1002
#define SC_DEVICE_PICKER_CONTROL_CANCEL 1003
#define SC_DEVICE_PICKER_CONTROL_TITLE 1004
#define SC_DEVICE_PICKER_CONTROL_SUBTITLE 1005
#define SC_DEVICE_PICKER_CONTROL_STATUS 1006
#define SC_DEVICE_PICKER_MARGIN 24
#define SC_DEVICE_PICKER_HEADER_HEIGHT 82
#define SC_DEVICE_PICKER_FOOTER_HEIGHT 58

struct sc_device_picker_window {
    HWND window;
    HWND title;
    HWND subtitle;
    HWND list;
    HWND status;
    HWND start;
    HWND cancel;
    HFONT title_font;
    HFONT regular_font;
    const struct sc_vec_adb_devices *devices;
    struct sc_device_picker_selection *selection;
    enum sc_device_picker_result result;
    bool done;
};

static void
set_control_font(HWND control, HFONT font) {
    if (control && font) {
        SendMessageW(control, WM_SETFONT, (WPARAM) font, TRUE);
    }
}

static wchar_t *
to_wchars(const char *text) {
    return sc_str_to_wchars(text ? text : "");
}

static size_t
picker_ready_selection_count(const struct sc_device_picker_window *picker) {
    size_t ready = 0;
    int row = -1;
    while ((row = ListView_GetNextItem(picker->list, row, LVNI_SELECTED)) >= 0) {
        if ((size_t) row < picker->devices->size
                && sc_device_picker_device_is_ready(
                    &picker->devices->data[row])) {
            ++ready;
        }
    }
    return ready;
}

static void
picker_update_summary(struct sc_device_picker_window *picker) {
    size_t selected = (size_t) ListView_GetSelectedCount(picker->list);
    size_t ready = picker_ready_selection_count(picker);
    wchar_t summary[128];
    swprintf(summary, ARRAY_LEN(summary), L"%u selected, %u ready to start",
             (unsigned) selected, (unsigned) ready);
    SetWindowTextW(picker->status, summary);
    EnableWindow(picker->start, ready != 0);
}

static void
picker_finish(struct sc_device_picker_window *picker,
              enum sc_device_picker_result result) {
    picker->result = result;
    picker->done = true;
    if (picker->window) {
        DestroyWindow(picker->window);
    }
}

static void
picker_start(struct sc_device_picker_window *picker) {
    if (!picker_ready_selection_count(picker)) {
        MessageBoxW(picker->window,
                    L"Select at least one ready device to start scrcpy.",
                    L"scrcpy", MB_OK | MB_ICONINFORMATION);
        return;
    }

    int row = -1;
    while ((row = ListView_GetNextItem(picker->list, row, LVNI_SELECTED)) >= 0) {
        if ((size_t) row >= picker->devices->size) {
            continue;
        }
        const struct sc_adb_device *device = &picker->devices->data[row];
        if (sc_device_picker_device_is_ready(device)
                && !selection_add(picker->selection, device->serial)) {
            sc_device_picker_selection_destroy(picker->selection);
            MessageBoxW(picker->window, L"Could not copy the selection.",
                        L"scrcpy", MB_OK | MB_ICONERROR);
            return;
        }
    }

    picker_finish(picker, SC_DEVICE_PICKER_START);
}

static LRESULT
picker_custom_draw(struct sc_device_picker_window *picker,
                   NMLVCUSTOMDRAW *draw) {
    if (draw->nmcd.dwDrawStage == CDDS_PREPAINT) {
        return CDRF_NOTIFYITEMDRAW;
    }
    if (draw->nmcd.dwDrawStage == CDDS_ITEMPREPAINT) {
        size_t row = (size_t) draw->nmcd.dwItemSpec;
        if (row < picker->devices->size
                && !sc_device_picker_device_is_ready(
                    &picker->devices->data[row])) {
            draw->clrText = RGB(135, 135, 135);
        }
        return CDRF_NEWFONT;
    }
    return CDRF_DODEFAULT;
}

static void
picker_layout(struct sc_device_picker_window *picker, int width, int height) {
    const int margin = SC_DEVICE_PICKER_MARGIN;
    const int list_top = SC_DEVICE_PICKER_HEADER_HEIGHT;
    const int footer_top = height - SC_DEVICE_PICKER_FOOTER_HEIGHT;
    const int button_height = 32;
    const int cancel_width = 92;
    const int start_width = 132;
    const int gap = 10;

    MoveWindow(picker->title, margin, 18, width - 2 * margin, 28, TRUE);
    MoveWindow(picker->subtitle, margin, 50, width - 2 * margin, 22, TRUE);
    MoveWindow(picker->list, margin, list_top, width - 2 * margin,
               footer_top - list_top - 8, TRUE);
    MoveWindow(picker->status, margin, footer_top + 10, 300, 30, TRUE);
    MoveWindow(picker->cancel, width - margin - cancel_width,
               footer_top + 7, cancel_width, button_height, TRUE);
    MoveWindow(picker->start, width - margin - cancel_width - gap - start_width,
               footer_top + 7, start_width, button_height, TRUE);
}

static LRESULT CALLBACK
picker_window_proc(HWND window, UINT message, WPARAM wparam, LPARAM lparam) {
    struct sc_device_picker_window *picker =
        (struct sc_device_picker_window *) GetWindowLongPtrW(
            window, GWLP_USERDATA);

    if (message == WM_NCCREATE) {
        CREATESTRUCTW *create = (CREATESTRUCTW *) lparam;
        picker = (struct sc_device_picker_window *) create->lpCreateParams;
        picker->window = window;
        SetWindowLongPtrW(window, GWLP_USERDATA, (LONG_PTR) picker);
    }

    switch (message) {
        case WM_COMMAND:
            if (LOWORD(wparam) == SC_DEVICE_PICKER_CONTROL_START) {
                picker_start(picker);
                return 0;
            }
            if (LOWORD(wparam) == SC_DEVICE_PICKER_CONTROL_CANCEL) {
                picker_finish(picker, SC_DEVICE_PICKER_CANCEL);
                return 0;
            }
            break;
        case WM_NOTIFY: {
            NMHDR *header = (NMHDR *) lparam;
            if (header->idFrom != SC_DEVICE_PICKER_CONTROL_LIST) {
                break;
            }
            if (header->code == NM_CUSTOMDRAW) {
                return picker_custom_draw(
                    picker, (NMLVCUSTOMDRAW *) lparam);
            }
            if (header->code == LVN_ITEMCHANGED) {
                picker_update_summary(picker);
                return 0;
            }
            if (header->code == NM_DBLCLK) {
                picker_start(picker);
                return 0;
            }
            break;
        }
        case WM_SIZE:
            if (picker) {
                picker_layout(picker, LOWORD(lparam), HIWORD(lparam));
            }
            return 0;
        case WM_GETMINMAXINFO: {
            MINMAXINFO *info = (MINMAXINFO *) lparam;
            info->ptMinTrackSize.x = 700;
            info->ptMinTrackSize.y = 420;
            return 0;
        }
        case WM_CTLCOLORSTATIC: {
            HDC dc = (HDC) wparam;
            SetBkMode(dc, TRANSPARENT);
            if (picker && (HWND) lparam == picker->status) {
                SetTextColor(dc, RGB(90, 90, 90));
            } else {
                SetTextColor(dc, RGB(45, 45, 45));
            }
            return (LRESULT) GetSysColorBrush(COLOR_WINDOW);
        }
        case WM_CLOSE:
            picker_finish(picker, SC_DEVICE_PICKER_CANCEL);
            return 0;
        case WM_DESTROY:
            return 0;
        default:
            break;
    }

    return DefWindowProcW(window, message, wparam, lparam);
}

static bool
register_picker_class(HINSTANCE instance) {
    WNDCLASSW klass = {
        .style = CS_HREDRAW | CS_VREDRAW,
        .lpfnWndProc = picker_window_proc,
        .hInstance = instance,
        .hIcon = LoadIconW(NULL, MAKEINTRESOURCEW(32512)),
        .hCursor = LoadCursorW(NULL, MAKEINTRESOURCEW(32512)),
        .hbrBackground = (HBRUSH) (COLOR_WINDOW + 1),
        .lpszClassName = L"scrcpy-device-picker",
    };
    ATOM atom = RegisterClassW(&klass);
    return atom || GetLastError() == ERROR_CLASS_ALREADY_EXISTS;
}

static bool
picker_add_column(HWND list, int index, const wchar_t *title, int width) {
    LVCOLUMNW column = {
        .mask = LVCF_TEXT | LVCF_WIDTH | LVCF_SUBITEM,
        .cx = width,
        .iSubItem = index,
        .pszText = (LPWSTR) title,
    };
    return ListView_InsertColumn(list, index, &column) >= 0;
}

static bool
picker_add_device(HWND list, size_t index,
                  const struct sc_adb_device *device) {
    wchar_t *serial = to_wchars(device->serial);
    wchar_t *model = to_wchars(device->model);
    wchar_t *type = to_wchars(sc_device_picker_type_name(device->serial));
    wchar_t *state = to_wchars(device->state);
    if (!serial || !model || !type || !state) {
        free(serial);
        free(model);
        free(type);
        free(state);
        return false;
    }

    LVITEMW item = {
        .mask = LVIF_TEXT | LVIF_PARAM,
        .iItem = (int) index,
        .lParam = (LPARAM) index,
        .pszText = serial,
    };
    int row = (int) SendMessageW(list, LVM_INSERTITEMW, 0, (LPARAM) &item);
    bool ok = row >= 0;
    if (ok) {
        LVITEMW subitem = {
            .mask = LVIF_TEXT,
            .iItem = row,
            .pszText = model,
        };
        subitem.iSubItem = 1;
        SendMessageW(list, LVM_SETITEMTEXTW, row, (LPARAM) &subitem);
        subitem.pszText = type;
        subitem.iSubItem = 2;
        SendMessageW(list, LVM_SETITEMTEXTW, row, (LPARAM) &subitem);
        subitem.pszText = state;
        subitem.iSubItem = 3;
        SendMessageW(list, LVM_SETITEMTEXTW, row, (LPARAM) &subitem);
    }
    free(serial);
    free(model);
    free(type);
    free(state);
    return ok;
}

static bool
picker_add_controls(struct sc_device_picker_window *picker, HINSTANCE instance) {
    INITCOMMONCONTROLSEX common_controls = {
        .dwSize = sizeof(common_controls),
        .dwICC = ICC_LISTVIEW_CLASSES,
    };
    if (!InitCommonControlsEx(&common_controls)) {
        return false;
    }

    picker->regular_font = (HFONT) GetStockObject(DEFAULT_GUI_FONT);
    picker->title_font = CreateFontW(
        -22, 0, 0, 0, FW_SEMIBOLD, FALSE, FALSE, FALSE,
        DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
        CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
    if (!picker->title_font) {
        picker->title_font = picker->regular_font;
    }

    picker->title = CreateWindowExW(
        0, L"STATIC", L"Select Android devices",
        WS_CHILD | WS_VISIBLE, SC_DEVICE_PICKER_MARGIN, 18, 600, 28,
        picker->window, (HMENU) SC_DEVICE_PICKER_CONTROL_TITLE, instance, NULL);
    picker->subtitle = CreateWindowExW(
        0, L"STATIC", L"Choose one or more ready devices to mirror.",
        WS_CHILD | WS_VISIBLE, SC_DEVICE_PICKER_MARGIN, 50, 600, 22,
        picker->window, (HMENU) SC_DEVICE_PICKER_CONTROL_SUBTITLE, instance,
        NULL);
    picker->list = CreateWindowExW(
        WS_EX_CLIENTEDGE, WC_LISTVIEWW, L"",
        WS_CHILD | WS_VISIBLE | WS_TABSTOP | LVS_REPORT | LVS_SHOWSELALWAYS,
        SC_DEVICE_PICKER_MARGIN, SC_DEVICE_PICKER_HEADER_HEIGHT, 800, 330,
        picker->window, (HMENU) SC_DEVICE_PICKER_CONTROL_LIST, instance, NULL);
    picker->status = CreateWindowExW(
        0, L"STATIC", L"0 selected, 0 ready to start",
        WS_CHILD | WS_VISIBLE, SC_DEVICE_PICKER_MARGIN, 450, 300, 30,
        picker->window, (HMENU) SC_DEVICE_PICKER_CONTROL_STATUS, instance,
        NULL);
    picker->start = CreateWindowExW(
        0, L"BUTTON", L"Start selected",
        WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_DEFPUSHBUTTON,
        600, 445, 132, 32, picker->window,
        (HMENU) SC_DEVICE_PICKER_CONTROL_START, instance, NULL);
    picker->cancel = CreateWindowExW(
        0, L"BUTTON", L"Cancel",
        WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_PUSHBUTTON,
        742, 445, 92, 32, picker->window,
        (HMENU) SC_DEVICE_PICKER_CONTROL_CANCEL, instance, NULL);
    if (!picker->title || !picker->subtitle || !picker->list || !picker->status
            || !picker->start || !picker->cancel) {
        return false;
    }

    set_control_font(picker->title, picker->title_font);
    set_control_font(picker->subtitle, picker->regular_font);
    set_control_font(picker->list, picker->regular_font);
    set_control_font(picker->status, picker->regular_font);
    set_control_font(picker->start, picker->regular_font);
    set_control_font(picker->cancel, picker->regular_font);

    ListView_SetExtendedListViewStyle(
        picker->list, LVS_EX_FULLROWSELECT | LVS_EX_GRIDLINES
                    | LVS_EX_DOUBLEBUFFER);
    if (!picker_add_column(picker->list, 0, L"Device", 300)
            || !picker_add_column(picker->list, 1, L"Model", 190)
            || !picker_add_column(picker->list, 2, L"Connection", 110)
            || !picker_add_column(picker->list, 3, L"ADB status", 130)) {
        return false;
    }

    for (size_t i = 0; i < picker->devices->size; ++i) {
        if (!picker_add_device(picker->list, i, &picker->devices->data[i])) {
            return false;
        }
    }

    picker_update_summary(picker);
    return true;
}

static void
picker_destroy_resources(struct sc_device_picker_window *picker) {
    if (picker->title_font && picker->title_font != picker->regular_font) {
        DeleteObject(picker->title_font);
    }
}

enum sc_device_picker_result
sc_device_picker_run(const struct sc_vec_adb_devices *devices,
                     struct sc_device_picker_selection *selection) {
    selection->serials = NULL;
    selection->count = 0;

    HINSTANCE instance = GetModuleHandleW(NULL);
    if (!register_picker_class(instance)) {
        LOGE("Could not register the device picker window class");
        return SC_DEVICE_PICKER_ERROR;
    }

    struct sc_device_picker_window picker = {
        .devices = devices,
        .selection = selection,
        .result = SC_DEVICE_PICKER_ERROR,
    };
    HWND window = CreateWindowExW(
        WS_EX_DLGMODALFRAME, L"scrcpy-device-picker",
        L"scrcpy | Select devices",
        WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX
            | WS_THICKFRAME,
        CW_USEDEFAULT, CW_USEDEFAULT, 880, 540,
        NULL, NULL, instance, &picker);
    if (!window) {
        LOGE("Could not create the device picker window");
        return SC_DEVICE_PICKER_ERROR;
    }

    if (!picker_add_controls(&picker, instance)) {
        LOGE("Could not create the device picker controls");
        DestroyWindow(window);
        picker_destroy_resources(&picker);
        return SC_DEVICE_PICKER_ERROR;
    }

    RECT work_area;
    SystemParametersInfoW(SPI_GETWORKAREA, 0, &work_area, 0);
    RECT window_rect;
    GetWindowRect(window, &window_rect);
    int width = window_rect.right - window_rect.left;
    int height = window_rect.bottom - window_rect.top;
    int x = work_area.left +
            ((work_area.right - work_area.left) - width) / 2;
    int y = work_area.top +
            ((work_area.bottom - work_area.top) - height) / 2;
    SetWindowPos(window, NULL, x, y, 0, 0,
                 SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE);
    ShowWindow(window, SW_SHOW);
    UpdateWindow(window);
    SetFocus(picker.list);

    MSG message;
    while (!picker.done && GetMessageW(&message, NULL, 0, 0) > 0) {
        TranslateMessage(&message);
        DispatchMessageW(&message);
    }

    picker_destroy_resources(&picker);
    if (picker.result != SC_DEVICE_PICKER_START) {
        sc_device_picker_selection_destroy(selection);
    }
    return picker.result;
}

#else

enum sc_device_picker_result
sc_device_picker_run(const struct sc_vec_adb_devices *devices,
                     struct sc_device_picker_selection *selection) {
    (void) devices;
    selection->serials = NULL;
    selection->count = 0;
    return SC_DEVICE_PICKER_UNAVAILABLE;
}

#endif
