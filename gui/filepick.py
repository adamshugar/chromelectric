from tkinter import ttk, filedialog, messagebox
import tkinter as tk
import textwrap
import os
from functools import reduce
from utils import filetype, find_sequences, duration_to_str
import algos.fileparse as fileparse
import gui.constants as GUI
import gui.prompts as prompts

class FilePicker(ttk.Frame):
    MAX_DISPLAY_LEN = 70

    def __init__(self, master, file_label, file_type, label_text, button_text='Browse', msg_detail=''):
        super().__init__(master)
        self.filepath = None
        self.label_variable = tk.StringVar(value=label_text)

        self.file_label = file_label
        self.file_type = file_type
        self.msg_detail = msg_detail

        picker_button = ttk.Button(self, text=button_text, command=self.on_click_picker)
        picker_label = ttk.Label(self, textvariable=self.label_variable)
        picker_button.grid(row=0, column=0, sticky=tk.W, padx=(0, GUI.PADDING), pady=GUI.PADDING)
        picker_label.grid(row=0, column=1, sticky=tk.W, pady=GUI.PADDING)
        

    def on_click_picker(self):
        filepath = self.prompt_filepath()
        if filepath:
            self.set_filepath_label(filepath)
            self.filepath = filepath

    def set_filepath_label(self, filepath):
        self.file_variable = filepath
        _, filename = os.path.split(filepath)
        if len(filename) > FilePicker.MAX_DISPLAY_LEN:
            slice_len = FilePicker.MAX_DISPLAY_LEN//2
            filename = f'{filename[:slice_len].strip()} ... {filename[-slice_len:].strip()}'
        self.label_variable.set(filename)
        
    def prompt_filepath(self):
        file_picked = False
        while not file_picked:
            try:
                detail_str = f' {self.msg_detail}' if len(self.msg_detail) > 0 else ''
                path = filedialog.askopenfilename(
                    title=f'Select a {self.file_label} file.\n\n{detail_str}',
                    filetypes=[(self.file_label, self.file_type)])
                if not path:
                    return None
                handle = open(path, 'r') # Check that file is openable
                file_picked = True
            except IOError as err:
                should_retry = messagebox.askretrycancel(
                    title='Unable to open file',
                    message=f'Error while opening {self.file_label} file. {err.strerror}.')
                if not should_retry:
                    return None
        handle.close()
        return path

    def get_parsed_input(self):
        return self.filepath

class CAFilePicker(FilePicker):
    def __init__(self, master, file_label, file_type, label_text, button_text, msg_detail=''):
        super().__init__(master, file_label, file_type, label_text, button_text, msg_detail)
        self.parsed_data = None

        self.parsed_frame = ttk.Frame(self)
        self.parsed_message = tk.StringVar()
        parsed_label = ttk.Label(self.parsed_frame, textvariable=self.parsed_message)
        button_frame = ttk.Frame(self.parsed_frame, relief=tk.GROOVE)
        current_button = ttk.Button(button_frame, text='View I vs. t')
        resistance_button = ttk.Button(button_frame, text='View Ω vs. t')

        parsed_label.grid(row=0, column=0, sticky=tk.W, padx=(0, GUI.PADDING))
        button_frame.grid(row=0, column=1, sticky=tk.E)
        current_button.grid(row=0, column=0, sticky=tk.E)
        resistance_button.grid(row=0, column=1, sticky=tk.E)
        self.parsed_frame.columnconfigure(1, weight=1)
        button_frame.columnconfigure(0, weight=1)
        # TODO: Also graph change in resistance over time (from current and potential)
        # View CA file raw
        # View system resistance over time (measure of stability/hysteresis)

    def on_click_picker(self):
        filepath, parsed_data = self.prompt_filepath()
        if parsed_data is not None:
            self.set_filepath_label(filepath)
            self.filepath = filepath
            self.parsed_data = parsed_data

            time_diff = parsed_data['current_vs_time'][-1][0] - parsed_data['current_vs_time'][0][0]
            potentials = parsed_data['potentials_by_trial']
            self.parsed_message.set(textwrap.dedent(f"""\
                Found cyclic amperometry data with total
                duration {duration_to_str(time_diff)}
                spanning {len(potentials)} potentials, from {max(potentials)}V to {min(potentials)}V."""))
            self.parsed_frame.grid(column=1, columnspan=2, sticky=tk.W+tk.E, pady=(0, GUI.PADDING))

    def prompt_filepath(self):
        filepath = super().prompt_filepath()
        valid_file_picked = False
        while not valid_file_picked:
            try:
                parsed_data = fileparse.CA.parse_file(filepath)
                valid_file_picked = True
            except Exception: # Fails safely for CA files with improper meta or data format
                should_retry = prompts.retrycancel(
                    title='Error while reading file', message='CA file is not properly formatted.',
                    style=prompts.ERROR)
                if not should_retry:
                    return (None, None)

        return (filepath, parsed_data)

    def get_parsed_input(self):
        return self.parsed_data

# TODO: 'Found n total injections with indices <s1>-<e1>, <s2>-<e2> and mean duration x hours, y minutes, and z seconds.'
class GCFilePicker(FilePicker):
    def __init__(self, master, file_label, file_type, label_text, button_text, msg_detail=''):
        super().__init__(master, file_label, file_type, label_text, button_text, msg_detail)
        self.parsed_list = None

    def on_click_picker(self):
        filepath, parsed_list = self.prompt_filepath()
        if filepath:
            self.set_filepath_label(filepath)
            self.filepath = filepath
            self.parsed_list = parsed_list
    
    def prompt_filepath(self):
        valid_file_picked = False
        while not valid_file_picked:
            filepath = super().prompt_filepath()
            if not filepath:
                return (None, None)
        
            result = GCFilePicker.get_parsed_list(filepath)
            parsed_list, error_message = (result.get('parsed_list'), result.get('error_message'))
            if not parsed_list: # If no list, then we failed, so need to re-pick
                should_retry = prompts.retrycancel(
                    title='Error while reading file list', message=error_message, style=prompts.ERROR)
                if not should_retry:
                    return (None, None)
            elif error_message: # If list exists but there is an error message, it's just a warning (re-pick optional)
                response = prompts.abortretryignore(
                    title='Missing injection files', message=error_message, style=prompts.WARNING)
                if response is None: # User elected to abort
                    return (None, None)
                elif response: # User elected to retry
                    continue
                else:
                    valid_file_picked = True
            else:
                valid_file_picked = True
        
        return (filepath, parsed_list)

    def get_parsed_input(self):
        return self.parsed_list

    @staticmethod
    def get_parsed_list(injection_file):
        raw_list = fileparse.GC.find_list(injection_file)
        if not raw_list:
            error_message = 'Invalid file chosen. Ensure that the filename ends with "<injection_number>.asc".'
            return {'error_message': error_message}
        
        # Alert the user of any potentially missing injections
        sequences = find_sequences([*raw_list])
        first_injection = sequences[1][0]
        next_highest = sequences[1][0] if len(sequences) > 1 else None
        missing_list = []
        if next_highest:
            missing_list.append((f'Found injection {next_highest} after contiguous run '
                                f'of injections {first_injection} through {sequences[0][1]}.'))
        if first_injection > 1:
            missing_list.append(f'Injection {first_injection} was first found (expected injection 1).')
        error_message = 'Missing files detected.\n' + reduce(lambda accum, next: accum + '\n' + next, missing_list) if missing_list else None
        
        parsed_list = fileparse.GC.parse_list(raw_list, sequence_bounds)
        if not isinstance(parsed_list, dict):
            io_fail_index = parsed_list
            error_message = f'File read failed for injection {io_fail_index}.'
            return {'error_message': error_message}
        
        return {
            'parsed_list': parsed_list,
            'error_message': error_message
        }

class FileList(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)

        self.file_pickers = {}
        file_labels = ['FID', 'TCD', 'CA']
        label_text = 'No file selected.'

        for file_label in file_labels:
            if file_label == 'FID' or file_label == 'TCD':
                msg_detail = textwrap.dedent("""\
                    Any injection file from the experiment is acceptable, provided that
                    all injection files are in the same directory and follow the naming scheme:
                    "<identical_filename><injection_number>.asc".
                    (The "auto-increment" option in PeakSimple would ensure this.)""")
                extension = filetype.GC
                instance = GCFilePicker
            else:
                msg_detail = 'This will be aligned to the GC files to generate the final output.'
                extension = filetype.CA
                instance = CAFilePicker

            self.file_pickers[file_label] = instance(
                self, button_text=f'Choose {file_label} File', file_label=file_label, file_type=f'.{extension}',
                msg_detail=msg_detail, label_text=label_text)
            self.file_pickers[file_label].grid(sticky=tk.W)
    
    def get_parsed_input(self):
        return { key: val.get_parsed_input() for key, val in self.file_pickers.items() }