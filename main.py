import multiprocessing as mp
import json
import sys
import os
from PySide2.QtWidgets import (
    QApplication, QMainWindow, QWidget, QSizePolicy,
    QVBoxLayout, QLayout, QCheckBox, QPushButton,
    QTabWidget, QSpacerItem, QMessageBox)
from PySide2.QtCore import Slot, Qt, QCoreApplication
import gui
from gui.paraminput import GasList, ShortEntryList, CheckboxList
from gui.filepick import FileList
from util import platform_messagebox

class GeneralParams(QVBoxLayout):
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
            file = open(GeneralParams.SETTINGS_PATH, 'r')
            settings = json.load(file)
            return settings
        except IOError:
            return None # File won't exist on first program run

    def save_settings(self):
        if not self.save_checkbox.isChecked():
            return

        settings = {
            **self.gas_list.get_parsed_input(),
            **self.short_entry_list.get_parsed_input(),
            **self.checkbox_list.get_parsed_input()
        }
        try:
            settings_handle = open(GeneralParams.SETTINGS_PATH, 'w')
            json.dump(settings, settings_handle, indent=4)
        except IOError as err:
            warning = platform_messagebox(
                text='Unable to save settings', buttons=QMessageBox.Ok, icon=QMessageBox.Warning,
                informative=f'Error while saving to settings file: {err.strerror}.')
            warning.exec()
    
class FileAnalysis(QVBoxLayout):
    def __init__(self, on_click_analysis, resize_handler):
        super().__init__()

        self.addLayout(FileList())

        self.on_click_analysis = on_click_analysis
        analysis_button = QPushButton(text='Integrate')
        analysis_button.clicked.connect(self.handle_click_analysis)
        analysis_button.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
        self.addWidget(analysis_button, alignment=Qt.AlignRight)

    def handle_click_analysis(self):
        if self.on_click_analysis:
            self.on_click_analysis()

class ApplicationWindow(QMainWindow):
    PADX, PADY = (50, 40)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(QCoreApplication.applicationName())

        self.main = QWidget()
        self.setCentralWidget(self.main)
        self.layout = QVBoxLayout(self.main)
        self.layout.setSizeConstraint(QLayout.SetFixedSize)
        self.layout.setContentsMargins(
            ApplicationWindow.PADX, ApplicationWindow.PADY, ApplicationWindow.PADX, ApplicationWindow.PADY)
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        self.params_container = QWidget()
        self.general_params = GeneralParams(resize_handler=self.resize)
        self.params_container.setLayout(self.general_params)
        self.tabs.addTab(self.params_container, 'General Parameters')

        self.file_analysis = QWidget()
        self.file_analysis.setLayout(
            FileAnalysis(on_click_analysis=self.handle_click_analysis, resize_handler=self.resize))
        self.tabs.addTab(self.file_analysis, 'File Analysis')
        
        self.resize()

    @Slot()
    def resize(self):
        QApplication.instance().processEvents()
        self.tabs.setFixedSize(self.tabs.sizeHint())
        self.layout.activate()
        self.setFixedSize(self.sizeHint())

    def handle_click_analysis(self):
        print('Saving settings (TEMP)')
        self.general_params.save_settings()

def main():
    qapp = QApplication([''])
    QCoreApplication.setApplicationName('Chromelectric')
    app = ApplicationWindow()
    app.show()
    qapp.exec_()

if __name__ == '__main__':
    mp.set_start_method('spawn')
    main()
