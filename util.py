""" Basic utility functions. """
import re
import sys
from PySide2.QtWidgets import QApplication, QMessageBox

def is_nonnegative_int(str):
    # Use regex instead of built-in isnumeric() because isnumeric() accepts exponents and fractions.
    return re.match(r'^[0-9]+$', str) != None

def is_nonnegative_float(str):
    return re.match(r'^\d+(\.\d*)?$', str) != None

def safe_int(str):
    try:
        return int(str)
    except ValueError:
        return None

def safe_float(str):
    try:
        return float(str)
    except ValueError:
        return None

def find_sequences(nums):
    """ Given an unordered list of non-negative, unique integers, find all contiguous sequences.
    Returns the list of sequences as a list of tuples. Assumes valid input list of ints with 
    length greater than zero. LeetCode easy. """
    nums.sort()
    prev = nums[0]
    sequences = [[prev, None]]
    for n in nums[1:]:
        if n > prev + 1:
            sequences[-1][1] = prev
            sequences.append([n, None])
        prev = n
    sequences[-1][1] = nums[-1]
    return sequences

def sequences_to_str(sequences):
    return ', '.join([f'{s[0]}-{s[1]}' if s[0] != s[1] else str(s[0]) for s in sequences])

def duration_to_str(duration_seconds):
    mins_total = duration_seconds // 60
    hours_total = mins_total // 60
    mins_display = mins_total % 60
    seconds_display = duration_seconds % 60

    def num_to_str(num):
        return str(int(num)) if isinstance(num, int) or num.is_integer() else '{:.1f}'.format(num)

    def field_str(val, name):
        return (num_to_str(val) + f" {name}{'' if val == 1 else 's'}") if val != 0 else None

    fields_by_name = {'hour': hours_total, 'minute': mins_display, 'second': seconds_display}
    field_list = [field_str(val, name) for name, val in fields_by_name.items()]
    result = ', '.join([field for field in field_list if field])
    return result if result else '0 seconds'

def is_windows():
    return sys.platform.startswith('win32') or sys.platform.startswith('cygwin')

class QtPt:
    @staticmethod
    def pt_to_px(pt):
        BASE_DPI = 72
        # Logical DPI is more robust than physical DPI (in the caes of retina displays & user customization)
        logical_dpi = QApplication.instance().primaryScreen().logicalDotsPerInch()
        return pt * (logical_dpi / BASE_DPI)

    @staticmethod
    def font_size_px(font):
        if font.pixelSize() != -1:
            return font.pixelSize()
        return QtPt.pt_to_px(font.pointSize())

def platform_messagebox(text, buttons, icon, default_button=None, informative='', detailed=''):
    messagebox = QMessageBox()
    messagebox.setIcon(icon)
    messagebox.setStandardButtons(buttons)
    messagebox.setDefaultButton(default_button)
    if is_windows():
        messagebox.setWindowTitle(QCoreApplication.applicationName())
        messagebox.setText(text + informative)
        if detailed:
            messagebox.setDetailedText(detailed)
    else:
        messagebox.setText(text)
        if informative:
            messagebox.setInformativeText(informative)
        if detailed:
            messagebox.setDetailedText(detailed)
    return messagebox

def retry_cancel(text, informative='', detailed='', icon=QMessageBox.Critical):
    messagebox = platform_messagebox(
        text=text, buttons=QMessageBox.Cancel | QMessageBox.Retry, default_button=QMessageBox.Retry,
        icon=icon, informative=informative, detailed=detailed)
    return messagebox.exec() == QMessageBox.Retry

class filetype:
    GC = 'asc'
    CA = 'mpt'
