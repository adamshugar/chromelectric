# For entire module
from tkinter import ttk
from util import is_windows

# For Windows-specific functionality
import ctypes
import tkinter as tk
import gui
if is_windows():
    from ctypes import WINFUNCTYPE, windll
    from ctypes.wintypes import UINT, HWND

"""
We need to do a bit of extra work on Windows to accommodate high DPI displays, as detailed here:
https://stackoverflow.com/questions/41315873/attempting-to-resolve-blurred-tkinter-text-scaling-on-windows-10-high-dpi-disp.
Note that 72 DPI is the "true" DPI even though Windows claims that standard DPI is 96. See here:
https://docs.microsoft.com/en-us/archive/blogs/fontblog/where-does-96-dpi-come-from-in-windows
"""

# Placeholder until `tk_process_init()` is called
SCALE_FACTOR = 1

# See enum here: 
# https://docs.microsoft.com/en-us/windows/win32/api/shellscalingapi/ne-shellscalingapi-process_dpi_awareness
_PROCESS_SYSTEM_DPI_AWARE = 1

# True only if a process HDPI init function from this package is called *and* platform is windows
_IS_WIN_HDPI = False
_WIN_DPI_DEFAULT = 72

_IS_HDPI_SUPPORT_ENABLED = True

# Returns a properly scaled root Tk GUI window
def tk_process_init():    
    if not is_windows() or not _IS_HDPI_SUPPORT_ENABLED:
        return tk.Tk()
    _IS_WIN_HDPI = True

    ctypes.windll.shcore.SetProcessDpiAwareness(_PROCESS_SYSTEM_DPI_AWARE)

    root = tk.Tk()
    hwnd = root.winfo_id()
    dpi_prototype = WINFUNCTYPE(UINT, HWND)
    get_dpi = dpi_prototype(('GetDpiForWindow', windll.user32))
    true_dpi = get_dpi(hwnd)

    global SCALE_FACTOR
    SCALE_FACTOR = true_dpi / _WIN_DPI_DEFAULT
    gui.PADDING *= SCALE_FACTOR
    root.tk.call('tk', 'scaling', SCALE_FACTOR)

    return root

class Button(ttk.Button):
    def __init__(self, master=None, **kw):
        text = kw.get('text')
        # On high DPI Windows displays, button padding is reduced, so hack around it.
        global SCALE_FACTOR
        if text and is_windows() and SCALE_FACTOR >= 2:
            kw['text'] = f' {text} '
        super().__init__(master=master, **kw)