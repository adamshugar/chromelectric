"""
GUI components to pick GC & CA files from disc and launch windows in which
graphs of the chosen files can be viewed.
"""
import os
import textwrap
from PySide2.QtWidgets import (
    QPushButton, QLineEdit, QVBoxLayout, QHBoxLayout, QFrame, QFileDialog,
    QGridLayout, QComboBox, QLayout, QSizePolicy, QCheckBox, QMessageBox)
from PySide2.QtCore import Signal, Slot, Qt, QCoreApplication
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from util import (
    filetype, find_sequences, duration_to_str, sequences_to_str,
    is_windows, atomic_subprocess, channels)
import algos.fileparse as fileparse
import gui
from gui import Label, platform_messagebox, retry_cancel
import gui.carousel as carousel
matplotlib.use('Qt5Agg')

# Need to define graphing functions at top level in order to be "pickle-able" for multiprocessing.
# See https://stackoverflow.com/questions/8804830/python-multiprocessing-picklingerror-cant-pickle-type-function.
def single_graph(title, x, y, xlabel, ylabel):
    fig = plt.figure(title)
    ax = fig.add_subplot()
    ax.plot(x, y)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    plt.show()

def carousel_graph(graph_list, window_title, index_title, multiple_title, legend_title, xlabel, ylabel):
    carousel.launch_window(graph_list, window_title, index_title, multiple_title, legend_title, xlabel, ylabel)

class FilePicker(QGridLayout):
    MAX_DISPLAY_LEN = 70

    def __init__(self, file_label, file_type, label_text, button_text='Browse', msg_detail=''):
        super().__init__()
        self.filepath = None

        self.file_label = file_label
        self.file_type = file_type
        self.msg_detail = msg_detail

        picker_button = QPushButton(button_text)
        picker_button.clicked.connect(self.on_click_picker)
        picker_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.picker_label = Label(label_text)
        self.addWidget(picker_button, 0, 0)
        self.addWidget(self.picker_label, 0, 1)

    def on_click_picker(self):
        filepath = self.prompt_filepath()
        if filepath:
            self.set_filepath_label(filepath)
            self.filepath = filepath

    def set_filepath_label(self, filepath):
        _, filename = os.path.split(filepath)
        if len(filename) > FilePicker.MAX_DISPLAY_LEN:
            slice_len = FilePicker.MAX_DISPLAY_LEN // 2
            filename = f'{filename[:slice_len].strip()} ... {filename[-slice_len:].strip()}'
        self.picker_label.setText(filename)
        
    def prompt_filepath(self):
        file_picked = False
        while not file_picked:
            try:
                detail_str = f' {self.msg_detail}' if len(self.msg_detail) > 0 else ''
                platform_file_label = f'{self.file_label} (.{self.file_type})' if is_windows() else self.file_label
                path, _ = QFileDialog.getOpenFileName(
                    None, f'Select a {self.file_label} file. {detail_str}',
                    '', f'{self.file_label} (*{self.file_type})')
                if not path:
                    return None
                handle = open(path, 'r') # Check that file is openable
                file_picked = True
            except IOError as err:
                should_retry = retry_cancel(
                    text=f'Error while opening {self.file_label} file.',
                    informative=f'{err.strerror}.', parent=self.parentWidget())
                if not should_retry:
                    return None
        handle.close()
        return path

    def get_parsed_input(self):
        return self.filepath

class CAFilePicker(FilePicker):
    def __init__(self, file_label, file_type, label_text, button_text, msg_detail, resize_handler):
        super().__init__(file_label, file_type, label_text, button_text, msg_detail)
        self.parsed_data = None
        self.resize_handler = resize_handler

        self.parsed_container = QHBoxLayout()
        self.parsed_label = Label()
        self.parsed_label.setWordWrap(True)

        resistance_button = QPushButton(text='View kΩ vs. t')
        resistance_button.clicked.connect(self.on_click_resistance)
        resistance_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        current_button = QPushButton(text='View mA vs. t')
        current_button.clicked.connect(self.on_click_current)
        current_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.parsed_container.addWidget(self.parsed_label)
        self.parsed_container.addWidget(resistance_button)
        self.parsed_container.addWidget(current_button)
    
    def on_click_current(self):
        data = self.parsed_data['current_vs_time']
        atomic_subprocess(
            obj=self, subprocess_attrname='current_subprocess', target=single_graph,
            args=('Current vs. Time in Cyclic Amperometry', data[:, 0], data[:, 1],
            'Time (sec)', 'Current (mA)'))

    def on_click_resistance(self):
        data = self.parsed_data['resistance_vs_time']
        atomic_subprocess(
            obj=self, subprocess_attrname='resistance_subprocess', target=single_graph,
            args=('Resistance vs. Time in Cyclic Amperometry', data[:, 0], data[:, 1],
            'Time (sec)', 'Resistance (kΩ)'))

    def on_click_picker(self):
        filepath, parsed_data = self.prompt_filepath()
        if parsed_data is not None:
            self.set_filepath_label(filepath)
            self.filepath = filepath
            self.parsed_data = parsed_data

            time_diff = parsed_data['current_vs_time'][-1][0] - parsed_data['current_vs_time'][0][0]
            potentials = parsed_data['potentials_by_trial']
            self.parsed_label.setText(textwrap.dedent((f"\
                Found cyclic amperometry data with "
                f"total duration {duration_to_str(time_diff)} "
                f"spanning {len(potentials)} potentials, from {max(potentials)}V to {min(potentials)}V.")))
            if self.parsed_container not in self.children():
                self.addLayout(self.parsed_container, 1, 1)
                self.resize_handler()

    def prompt_filepath(self):
        valid_file_picked = False
        while not valid_file_picked:
            filepath = super().prompt_filepath()
            if not filepath:
                return (None, None)
            
            try:
                parsed_data = fileparse.CA.parse_file(filepath)
                valid_file_picked = True
            except Exception: # Fails safely for CA files with improper meta or data format
                should_retry = retry_cancel(
                    text='Error while reading file',
                    informative='CA file is not properly formatted.', parent=self.parentWidget())
                if not should_retry:
                    return (None, None)
            
        return (filepath, parsed_data)

    def get_parsed_input(self):
        return self.parsed_data

class GCFilePicker(FilePicker):
    def __init__(self, file_label, file_type, label_text, button_text, msg_detail, resize_handler):
        super().__init__(file_label, file_type, label_text, button_text, msg_detail)
        self.parsed_list = None
        self.resize_handler = resize_handler
        self.file_label = file_label

        self.parsed_container = QHBoxLayout()
        self.parsed_label = Label()
        self.parsed_label.setWordWrap(True)
        view_button = QPushButton(text='View mV vs. t')
        view_button.clicked.connect(self.on_click_view)
        view_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.parsed_container.addWidget(self.parsed_label)
        self.parsed_container.addWidget(view_button)

    def on_click_view(self):
        atomic_subprocess(
            obj=self, subprocess_attrname='carousel_subprocess', target=carousel.launch_window,
            args=(
                self.parsed_list, f'{self.file_label} Injection List View',
                f'Potential vs. Time for {self.file_label} ' + 'Injection {}',
                f'Potential vs. Time for {self.file_label} Injections',
                'Injection {}', 'Time (sec)', 'Potential (mV)'))

    def on_click_picker(self):
        filepath, parsed_list, sequences = self.prompt_filepath()
        if parsed_list is not None:
            self.filepath = filepath
            self.parsed_list = parsed_list

            self.set_filepath_label(filepath)
            mean_duration = np.mean([injection['x'][-1] for _, injection in parsed_list.items()])
            self.parsed_label.setText(textwrap.dedent((f"\
                Found {len(parsed_list)} total injections with indices {sequences_to_str(sequences)} "
                f"and mean duration {duration_to_str(mean_duration)}.")))
            if self.parsed_container not in self.children():
                self.addLayout(self.parsed_container, 1, 1)
                self.resize_handler()
    
    def prompt_filepath(self):
        valid_file_picked = False
        while not valid_file_picked:
            filepath = super().prompt_filepath()
            if not filepath:
                return (None, None, None)
        
            result = GCFilePicker.get_parsed_list(filepath)
            parsed_list, sequences, recoverable = (result.get('parsed_list'), result.get('sequences'), result.get('recoverable'))
            error_text, error_informative, error_detailed = (result.get('error_text'), result.get('error_informative'), result.get('error_detailed'))
            if not parsed_list: # If no list, then we failed, so need to re-pick
                should_retry = retry_cancel(
                    text=error_text, informative=error_informative, detailed=error_detailed, parent=self.parentWidget())
                if not should_retry:
                    return (None, None, None)
            elif error_text: # If list exists but there is an error message, it's just a warning (re-pick optional)
                messagebox = platform_messagebox(
                    text=error_text, buttons=QMessageBox.Abort | QMessageBox.Retry | QMessageBox.Ignore,
                    default_button=QMessageBox.Retry, icon=QMessageBox.Warning,
                    informative=error_informative, detailed=error_detailed, parent=self.parentWidget())
                response = messagebox.exec()
                if response == QMessageBox.Abort:
                    return (None, None, None)
                elif response == QMessageBox.Retry:
                    continue
                else:
                    valid_file_picked = True
            else:
                valid_file_picked = True
        
        return (filepath, parsed_list, sequences)

    def get_parsed_input(self):
        return self.parsed_list

    @staticmethod
    def get_parsed_list(injection_file):
        raw_list = fileparse.GC.find_list(injection_file)
        if not raw_list:
            return {
                'error_text': 'The chosen file has an invalid name.',
                'error_informative': 'Ensure that the filename ends with "<injection_number>.asc".'
            }
        
        # Alert the user of any potentially missing injections
        sequences = find_sequences([*raw_list])
        first_injection = sequences[0][0]
        next_highest = sequences[1][0] if len(sequences) > 1 else None
        missing_list = []
        if next_highest:
            missing_list.append((f'Found injection {next_highest} after contiguous run '
                                f'of injections {first_injection} through {sequences[0][1]}.'))
        if first_injection > 1:
            missing_list.append(f'Injection {first_injection} was first found; expected injection 1.')
        if next_highest or first_injection > 1:
            error_text = 'Some injection files are missing.'
            error_detailed = '\n'.join(missing_list)
        else:
            error_text = error_detailed = None
        
        parsed_list = fileparse.GC.parse_list(raw_list)
        if not isinstance(parsed_list, dict):
            io_fail_index = parsed_list
            return {'error_text': f'File read failed for injection {io_fail_index}.'}
        
        return {
            'parsed_list': parsed_list,
            'error_text': error_text,
            'error_detailed': error_detailed,
            'sequences': sequences
        }

class FileList(QVBoxLayout):
    def __init__(self, resize_handler):
        super().__init__()

        self.file_pickers = {}
        file_labels = channels + ['CA']
        label_text = 'No file selected.'

        for file_label in file_labels:
            if file_label in channels:
                msg_detail = 'Any injection can be chosen, assuming same directory and naming scheme.'
                extension = filetype.GC
                instance = GCFilePicker
            else:
                msg_detail = 'This is aligned to GC files during analysis.'
                extension = filetype.CA
                instance = CAFilePicker

            self.file_pickers[file_label] = instance(
                button_text=f'Choose {file_label} File', file_label=file_label, file_type=f'.{extension}',
                msg_detail=msg_detail, label_text=label_text, resize_handler=resize_handler)
            self.addLayout(self.file_pickers[file_label])
            
    def get_parsed_input(self):
        return { key: val.get_parsed_input() for key, val in self.file_pickers.items() }
