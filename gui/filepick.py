from tkinter import ttk, filedialog, messagebox
import tkinter as tk
import textwrap
import os
from utils import filetype, find_contiguous_sequence
import algos.fileparse as fileparse
import gui.constants as GUI
import gui.prompts as prompts

class FilePicker(ttk.Frame):
    MAX_DISPLAY_LEN = 70

    def __init__(self, master, file_label, file_type, variable, label_text, msg_detail='', button_text='Browse'):
        super().__init__(master)
        self.file_variable = variable
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

    def set_filepath_label(self, filepath):
        self.file_variable.set(filepath)
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

class GCFilePicker(FilePicker):
    def __init__(self, master, file_label, file_type, variable, label_text, msg_detail='', button_text='Browse'):
        super().__init__(master, file_label, file_type, variable, label_text, msg_detail, button_text)

    def on_click_picker(self):
        filepath, parsed_list = self.prompt_filepath()
        if filepath:
            self.set_filepath_label(filepath)
    
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
                if response == None: # User elected to abort
                    return (None, None)
                elif response: # User elected to retry
                    continue
            valid_file_picked = True
        
        return (filepath, parsed_list)

    @staticmethod
    def get_parsed_list(injection_file):
        raw_list = fileparse.GC.find_list(injection_file)
        if not raw_list:
            error_message = 'Invalid file chosen. Ensure that the filename ends with "<injection_number>.asc".'
            return {'error_message': error_message}
        
        sequence = find_contiguous_sequence([*raw_list])
        sequence_bounds = sequence['bounds']
        next_highest = sequence['next_highest']
        error_message = (f'Missing files detected. Found injection {next_highest} after contiguous '
                        f'run of injections {sequence_bounds[0]} through {sequence_bounds[1]}.') if next_highest else None
        
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

        self.filepaths = {}
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
                instance = FilePicker

            self.filepaths[file_label] = tk.StringVar()
            file_picker = instance(
                self, button_text=f'Choose {file_label} File', file_label=file_label, file_type=f'.{extension}',
                variable=self.filepaths[file_label], msg_detail=msg_detail, label_text=label_text)
            file_picker.grid(sticky=tk.W)
    
    def get_parsed_input(self):
        return {key: val.get() for key, val in self.filepaths.items()}