"""
Native Windows frame for the GX window.

The window keeps a real resizable frame (WS_THICKFRAME | WS_CAPTION ...), so Windows provides
Aero Snap (drag to the top = maximise, to a side = half screen), the system menu, shadows,
rounded corners and the min/max animations. WM_NCCALCSIZE then hands the whole window to the
client area, so nothing of that frame is drawn - the GX title bar is the caption, reported to
Windows through WM_NCHITTEST (see MainWindow.nativeEvent).
"""

import ctypes
from ctypes import wintypes

WM_NCCALCSIZE = 0x0083
WM_NCHITTEST = 0x0084

HTCAPTION = 2
HTLEFT, HTRIGHT, HTTOP, HTTOPLEFT, HTTOPRIGHT = 10, 11, 12, 13, 14
HTBOTTOM, HTBOTTOMLEFT, HTBOTTOMRIGHT = 15, 16, 17

_GWL_STYLE = -16
_FRAME_STYLES = (0x00C00000 |  # WS_CAPTION
                 0x00040000 |  # WS_THICKFRAME
                 0x00080000 |  # WS_SYSMENU
                 0x00020000 |  # WS_MINIMIZEBOX
                 0x00010000)   # WS_MAXIMIZEBOX
_SWP = 0x0020 | 0x0002 | 0x0001 | 0x0004 | 0x0010  # FRAMECHANGED NOMOVE NOSIZE NOZORDER NOACTIVATE

_user32 = ctypes.windll.user32
_dwm = ctypes.windll.dwmapi
_user32.GetWindowLongW.restype = ctypes.c_long
_user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.SetWindowLongW.restype = ctypes.c_long
_user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
_user32.MonitorFromWindow.restype = wintypes.HMONITOR
_user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
_user32.GetFocus.restype = wintypes.HWND
_user32.SetFocus.restype = wintypes.HWND
_user32.SetFocus.argtypes = [wintypes.HWND]
_user32.IsWindowVisible.argtypes = [wintypes.HWND]


class _MARGINS(ctypes.Structure):
    _fields_ = [("left", ctypes.c_int), ("right", ctypes.c_int), ("top", ctypes.c_int), ("bottom", ctypes.c_int)]


class _MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD)]


def apply(hwnd: int):
    """Real frame styles + DWM shadow, rounded corners and dark system menu."""
    style = _user32.GetWindowLongW(hwnd, _GWL_STYLE)
    if style & _FRAME_STYLES != _FRAME_STYLES:
        _user32.SetWindowLongW(hwnd, _GWL_STYLE, style | _FRAME_STYLES)
        _user32.SetWindowPos(wintypes.HWND(hwnd), None, 0, 0, 0, 0, _SWP)
    _dwm.DwmExtendFrameIntoClientArea(wintypes.HWND(hwnd), ctypes.byref(_MARGINS(1, 1, 1, 1)))
    for attr, value in ((33, 2),   # DWMWA_WINDOW_CORNER_PREFERENCE = round (Windows 11)
                        (20, 1)):  # DWMWA_USE_IMMERSIVE_DARK_MODE
        v = ctypes.c_int(value)
        _dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), attr, ctypes.byref(v), ctypes.sizeof(v))


def has_frame(hwnd: int) -> bool:
    return _user32.GetWindowLongW(hwnd, _GWL_STYLE) & _FRAME_STYLES == _FRAME_STYLES


def focused_window() -> int:
    """Window with the keyboard focus in this thread's input queue - can be a WebView2 page
    window, which belongs to another process but shares the input queue as a child window."""
    return _user32.GetFocus() or 0


def set_focus(hwnd: int):
    _user32.SetFocus(hwnd)


def is_visible(hwnd: int) -> bool:
    return bool(_user32.IsWindowVisible(hwnd))


def message(address: int) -> wintypes.MSG:
    return wintypes.MSG.from_address(address)


def lparam_point(lparam: int):
    """Screen position (physical pixels) packed into a WM_NCHITTEST lParam."""
    return ctypes.c_short(lparam & 0xFFFF).value, ctypes.c_short((lparam >> 16) & 0xFFFF).value


def window_rect(hwnd: int) -> wintypes.RECT:
    r = wintypes.RECT()
    _user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(r))
    return r


def maximized_overhang(hwnd: int):
    """A maximised window with a thick frame reaches past the monitor's work area by the
    frame width. Returns (left, top, right, bottom) of that overhang in physical pixels."""
    r = window_rect(hwnd)
    info = _MONITORINFO()
    info.cbSize = ctypes.sizeof(_MONITORINFO)
    _user32.GetMonitorInfoW(_user32.MonitorFromWindow(hwnd, 2), ctypes.byref(info))
    w = info.rcWork
    return max(0, w.left - r.left), max(0, w.top - r.top), max(0, r.right - w.right), max(0, r.bottom - w.bottom)
