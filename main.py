import multiprocessing as mp
from itertools import chain
import json
import sys
import os
from PySide2.QtWidgets import (
    QApplication, QMainWindow, QWidget, QSizePolicy,
    QVBoxLayout, QLayout, QCheckBox, QPushButton,
    QTabWidget, QSpacerItem, QMessageBox)
from PySide2.QtCore import Slot, Qt, QCoreApplication, QSize
import gui
import gui.peakpick as peakpick
from gui.paraminput import GasList, ShortEntryList, CheckboxList
from gui.filepick import FileList
from gui import platform_messagebox
from util import channels, atomic_subprocess

class GeneralParams(QVBoxLayout):
    """Wrapper class for GUI to enter all relevant experimental parameters."""
    SETTINGS_FILE_NAME = 'chromelectric_settings.txt'
    SETTINGS_PATH = os.path.join(sys.path[0], SETTINGS_FILE_NAME)

    def __init__(self, resize_handler):
        super().__init__()

        self.setSizeConstraint(QLayout.SetFixedSize)
        saved_settings = GeneralParams.load_settings()

        self.gas_list = GasList(resize_handler, saved_settings=saved_settings)
        self.addLayout(self.gas_list)

        self.short_entry_list = ShortEntryList(saved_settings=saved_settings)
        self.addLayout(self.short_entry_list)

        self.checkbox_list = CheckboxList(saved_settings=saved_settings)
        self.addLayout(self.checkbox_list)

        self.addItem(QSpacerItem(1, gui.PADDING))

        self.save_checkbox = QCheckBox('Save all above parameters for future runs')
        self.save_checkbox.setChecked(True)
        self.addWidget(self.save_checkbox, 0, Qt.AlignCenter)

    @staticmethod
    def load_settings():
        try:
            return json.load(open(GeneralParams.SETTINGS_PATH, 'r'))
        except IOError:
            return None # File won't exist on first program run
        except json.decoder.JSONDecodeError:
            warning = platform_messagebox(
                text='Unable to load settings', buttons=QMessageBox.Ok, icon=QMessageBox.Warning,
                informative=(
                    'Your saved settings file is improperly formatted. '
                    'Running the program again and saving settings will automatically fix the problem.'))
            warning.exec()

    def save_settings(self):
        if not self.save_checkbox.isChecked():
            return

        try:
            settings_handle = open(GeneralParams.SETTINGS_PATH, 'w')
            json.dump(self.get_parsed_input(), settings_handle, indent=4)
        except IOError as err:
            warning = platform_messagebox(
                text='Unable to save settings', buttons=QMessageBox.Ok, icon=QMessageBox.Warning,
                informative=f'Error while saving to settings file: {err.strerror}.', parent=self.parentWidget())
            warning.exec()

    def get_parsed_input(self):
        return {
            **self.gas_list.get_parsed_input(),
            **self.short_entry_list.get_parsed_input(),
            **self.checkbox_list.get_parsed_input()
        }
    
    def get_fields(self):
        return self.short_entry_list.get_fields()
    
class FileAnalysis(QVBoxLayout):
    """Wrapper class for GUI to pick and view GC/CA files."""
    def __init__(self, on_click_analysis, resize_handler):
        super().__init__()

        self.file_list = FileList(resize_handler=resize_handler)
        self.addLayout(self.file_list)

        self.on_click_analysis = on_click_analysis
        analysis_button = QPushButton(text='Integrate')
        analysis_button.clicked.connect(self.handle_click_analysis)
        analysis_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.addWidget(analysis_button, alignment=Qt.AlignRight)

    def handle_click_analysis(self):
        if self.on_click_analysis:
            self.on_click_analysis(self.file_list.get_parsed_input())

class ResizableTabWidget(QTabWidget):
    """
    Wrapper for Qt tabs widget that automatically vertically resizes to accommodate the
    minimum possible height of the tab contents. Useful primarily for a tab widget as a
    top-level container within a window, as is the case in this program.
    """
    # Determined "experimentally" by investigation on various OSes; these seem to work well enough.
    WIDTH_PADDING = 6
    HEIGHT_PADDING = 31

    def __init__(self):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def sizeHint(self):
        standard_size = super().sizeHint()
        tab_size = self.currentWidget().sizeHint()
        return QSize(
            standard_size.width(),
            tab_size.height() + ResizableTabWidget.HEIGHT_PADDING)
    
    def minimumSizeHint(self):
        standard_size = super().sizeHint()
        tab_size = self.currentWidget().minimumSizeHint()
        return QSize(
            standard_size.width(),
            tab_size.height() + ResizableTabWidget.HEIGHT_PADDING)

class ApplicationWindow(QMainWindow):
    PADX, PADY = (50, 40)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(QCoreApplication.applicationName())
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)

        self.main = QWidget()
        self.setCentralWidget(self.main)
        self.layout = QVBoxLayout(self.main)
        self.layout.setSizeConstraint(QLayout.SetMinimumSize)
        self.layout.setContentsMargins(
            ApplicationWindow.PADX, ApplicationWindow.PADY, ApplicationWindow.PADX, ApplicationWindow.PADY)
        self.tabs = ResizableTabWidget()
        self.layout.addWidget(self.tabs)

        self.params_container = QWidget()
        self.general_params = GeneralParams(resize_handler=self.resize)
        self.params_container.setLayout(self.general_params)
        self.tabs.addTab(self.params_container, 'General Parameters')

        self.files_container = QWidget()
        self.files_container.setLayout(
            FileAnalysis(on_click_analysis=self.handle_click_analysis, resize_handler=self.resize))
        self.tabs.addTab(self.files_container, 'File Analysis')

        self.tabs.currentChanged.connect(self.resize)
        self.resize()

    @Slot()
    def resize(self):
        QApplication.instance().processEvents()
        self.tabs.adjustSize()
        self.layout.activate()
        self.setFixedSize(self.minimumSizeHint())

    def get_integration_params(self):
        experiment_params = self.general_params.get_parsed_input()
        gases_by_channel = {}
        for gas_name, attributes in experiment_params['attributes_by_gas_name'].items():
            channel = attributes['channel']
            if gases_by_channel.get(channel) is None:
                gases_by_channel[channel] = []
            gases_by_channel[channel].append(gas_name)
        return (experiment_params, gases_by_channel)
    
    def validate_all_inputs(self, all_inputs, entry_fields):
        """
        Validates all relevant parameters and files for subsequent integration and analysis, and alerts
        the user via dialog boxes of any validation failure. Returns true if valid, false otherwise.
        """
        experiment_params, gases_by_channel, parsed_file_input = [all_inputs[key] for key in ['experiment_params', 'gases_by_channel', 'parsed_file_input']]

        active_channels = [channel for channel in channels if parsed_file_input[channel]['data']]
        if not active_channels:
            m = platform_messagebox(
                parent=self, text='Please select at least one injection file.',
                buttons=QMessageBox.Ok, icon=QMessageBox.Critical)
            m.exec()
            return False
        if not parsed_file_input['CA']['data']:
            m = platform_messagebox(
                parent=self, text='Please select a CA file.',
                buttons=QMessageBox.Ok, icon=QMessageBox.Critical)
            m.exec()
            return False
        
        missing_channels = [channel for channel in channels if channel in active_channels and channel not in gases_by_channel]
        if missing_channels:
            m = platform_messagebox(
                parent=self, text=f"Please assign at least one gas to the following channel(s): {', '.join(missing_channels)}.",
                buttons=QMessageBox.Ok, icon=QMessageBox.Critical)
            m.exec()
            return False

        if experiment_params['duplicate_gases']:
            m = platform_messagebox(
                parent=self, text=f"Duplicate gas(es) found: {', '.join(experiment_params['duplicate_gases'])}.",
                informative='The highest numbered gas in each case will be used. Continue?',
                buttons=QMessageBox.Ok | QMessageBox.Cancel, default_button=QMessageBox.Cancel,
                icon=QMessageBox.Warning)
            result = m.exec()
            if result == QMessageBox.Cancel:
                return False

        missing_fields = [field for field in entry_fields if experiment_params[field] is None]
        if missing_fields:
            m = platform_messagebox(
                parent=self, text=f"Unspecified fields found.",
                informative='Please populate the missing fields under "General Parameters" before analysis.',
                detailed=f"Missing fields: {', '.join(missing_fields)}",
                buttons=QMessageBox.Ok, icon=QMessageBox.Critical)
            m.exec()
            return False
        
        return True

    def handle_click_analysis(self, parsed_file_input):
        self.general_params.save_settings()
        experiment_params, gases_by_channel = self.get_integration_params()
        
        all_inputs = {
            'experiment_params': experiment_params,
            'gases_by_channel': gases_by_channel,
            'parsed_file_input': parsed_file_input
        }
        is_valid = self.validate_all_inputs(all_inputs, self.general_params.get_fields())
        if is_valid:        
            atomic_subprocess(
                obj=self, subprocess_attrname='integrate_subprocess', target=peakpick.launch_window,
                args=(all_inputs, 'Integration and Analysis', 'Integration for {} Injection {}', 'Time (sec)', 'Potential (mV)'))

def main():
    qapp = QApplication([''])
    QCoreApplication.setApplicationName('Chromelectric')
    app = ApplicationWindow()
    app.show()
    qapp.exec_()

if __name__ == '__main__':
    mp.set_start_method('spawn')
    main()
