from PySide2.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QLayout, QCheckBox)
from PySide2.QtCore import Slot
import multiprocessing as mp
import json
import sys
import os
from gui.paraminput import GasList, ShortEntryList, CheckboxList

class GeneralParams(QVBoxLayout):
    SETTINGS_FILE_NAME = 'chromelectric_settings.txt'
    SETTINGS_PATH = os.path.join(sys.path[0], SETTINGS_FILE_NAME)

    def __init__(self, resize_handler, padx=0, pady=0):
        super().__init__()

        self.setSizeConstraint(QLayout.SetFixedSize)
        saved_settings = self.load()

        self.gas_list = GasList(resize_handler, saved_settings=saved_settings)
        self.addLayout(self.gas_list)

        self.short_entry_list = ShortEntryList(saved_settings=saved_settings)
        self.addLayout(self.short_entry_list)

        self.checkbox_list = CheckboxList(saved_settings=saved_settings)
        self.addLayout(self.checkbox_list)

        self.save_checkbox = QCheckBox('Save all above parameters for future runs')
        self.addWidget(self.save_checkbox)

    def load(self):
        try:
            file = open(GeneralParams.SETTINGS_PATH, 'r')
            settings = json.load(file)
            return settings
        except IOError:
            return None # File won't exist on first program run

    def save(self):
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
            pass
            # messagebox.showwarning(
            #     'Unable to save settings',
            #     f'Error while saving to settings file. {err.strerror}.')

# class FileAnalysis(ttk.Frame):
#     def __init__(self, master, padx=0, pady=0, min_width=None, on_click_analysis=None):
#         super().__init__(master)

#         container = ttk.Frame(self)
#         container.grid(padx=padx, pady=pady)

#         # Dummy min width enforcer widget
#         ttk.Frame(container, width=min_width).grid()

#         self.file_list = FileList(container)
#         self.file_list.grid(sticky=tk.W+tk.E)

#         self.on_click_analysis = on_click_analysis
#         analysis_button = hdpi.Button(container, text='Integrate', command=self.handle_click_analysis)
#         analysis_button.grid(sticky=tk.E, pady=(pady, 0))

#     def handle_click_analysis(self):
#         if self.on_click_analysis:
#             self.on_click_analysis()
#         # TODO: Launch integration subprocess

class ApplicationWindow(QMainWindow):
    PADX, PADY = (50, 40)

    def __init__(self, window_title='Chromelectric'):
        super().__init__()
        self.setWindowTitle(window_title)

        self.main = QWidget()
        self.setCentralWidget(self.main)
        self.layout = QVBoxLayout(self.main)
        self.layout.setSizeConstraint(QLayout.SetFixedSize)
        self.layout.setContentsMargins(
            ApplicationWindow.PADX, ApplicationWindow.PADY, ApplicationWindow.PADX, ApplicationWindow.PADY)

        self.general_params = GeneralParams(resize_handler=self.resize)
        self.layout.addLayout(self.general_params)

        # self.file_analysis = FileAnalysis(
        #     self.notebook, padx=padx, pady=pady, on_click_analysis=self.handle_click_analysis,
        #     min_width=Application.get_largest_width())
        # general_params_name = 'General Parameters' if not is_windows() else ' General Parameters '
        # file_analysis_name = 'File Analysis' if not is_windows() else ' File Analysis '
        # self.tabs_by_name = {
        #     general_params_name: self.general_params,
        #     file_analysis_name: self.file_analysis,
        # }
        # self.notebook.setup(self.tabs_by_name, first_tab=general_params_name)
        # self.notebook.grid()
        
        self.resize()

    @Slot()
    def resize(self):
        QApplication.instance().processEvents()
        self.setFixedSize(self.sizeHint())

def main():
    qapp = QApplication([''])
    dpi = QApplication.instance().primaryScreen().logicalDotsPerInch()
    app = ApplicationWindow()
    app.show()
    qapp.exec_()

if __name__ == '__main__':
    mp.set_start_method('spawn')
    main()