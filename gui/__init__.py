"""GUI-specific constants and util functions"""
from PySide2.QtWidgets import QLabel, QApplication, QMessageBox, QFrame, QComboBox
from util import is_windows

# Standard padding for any widget, in pixels
PADDING = 15
# Widths in number of characters for a "LineEdit" text entry box.
# They set the fixed width of the entry box but don't limit how many chars the user can enter.
STRING_WIDTH = 10
INT_WIDTH = 5
FLOAT_WIDTH = 8

class HLine(QFrame):
    """A horizontal line."""
    def __init__(self):
        super().__init__()
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)

class Label(QLabel):
    """Wrapper for Qt label that automatically resizes when text changes."""
    def __init__(self, text='', font_size=None):
        super().__init__(text)
        if font_size:
            font = self.font()
            font.setPointSize(font_size)
            self.setFont(font)

    def setText(self, text):
        super().setText(text)
        self.adjustSize()

    def resizeEvent(self, event):
        new_height = self.heightForWidth(self.width())
        if new_height > 0:
            self.setMinimumHeight(new_height)

class ComboBox(QComboBox):
    """Wrapper for Qt "combo box" with convenience method to remove all choices."""
    def removeAll(self):
        for _ in range(self.count()):
            self.removeItem(0)

def platform_messagebox(text, buttons, icon, default_button=None, informative='', detailed='', parent=None):
    """Platform-independent dialog box for quick messages and button-based user input"""
    messagebox = QMessageBox(icon, '', '', buttons, parent)
    messagebox.setIcon(icon)
    messagebox.setDefaultButton(default_button)
    if is_windows():
        messagebox.setWindowTitle(QCoreApplication.applicationName())
        messagebox.setText(text + ' ' + informative)
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

    @staticmethod
    def default_pt():
        return QApplication.font().pointSize()
