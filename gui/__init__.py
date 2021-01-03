"""GUI-specific constants and util functions"""
from PySide2.QtWidgets import QLabel, QApplication, QMessageBox
from util import is_windows

# Standard padding for any widget, in pixels
PADDING = 15
# Widths in number of characters for entry box (these are meant as minimums)
STRING_WIDTH = 14
INT_WIDTH = 5
FLOAT_WIDTH = 8

class Label(QLabel):
    """Auto-resizing wrapper for QLabel"""
    def setText(self, str):
        super().setText(str)
        self.adjustSize()

def platform_messagebox(text, buttons, icon, default_button=None, informative='', detailed='', parent=None):
    """Platform-independent dialog box for quick messages and button-based user input"""
    messagebox = QMessageBox(icon, '', '', buttons, parent)
    messagebox.setIcon(icon)
    messagebox.setDefaultButton(default_button)
    if is_windows():
        messagebox.setWindowTitle(QCoreApplication.applicationName())
        messagebox.setText(text + informative)
    else:
        messagebox.setText(text)
        if informative:
            messagebox.setInformativeText(informative)
    if detailed:
        messagebox.setDetailedText(detailed)
    return messagebox

def retry_cancel(text, informative='', detailed='', icon=QMessageBox.Critical, parent=None):
    """
    Spawns blocking dialog box with retry and cancel buttons and returns user response.
    Specifically, returns true on retry and false on cancel.
    """
    messagebox = platform_messagebox(
        text=text, buttons=QMessageBox.Cancel | QMessageBox.Retry, default_button=QMessageBox.Retry,
        icon=icon, informative=informative, detailed=detailed, parent=parent)
    return messagebox.exec() == QMessageBox.Retry

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
