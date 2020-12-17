import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import re
import os

class GUI:
    PADDING = 5
    # Widths in number of characters (these are minimums; if header text is longer, entry box expands)
    STRING_WIDTH = 14
    INT_WIDTH = 5
    FLOAT_WIDTH = 8

class FileType:
    GC = 'asc'
    CA = 'mpt'

# TODO: If min or max is not filled, default to start and end of GC run respectively
# TODO: If min is greater than end of GC run, print warning and show whole GC run

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

# Intentionally does not subclass ttk.Frame so that all GasRow objects can share the same grid layout
class GasRow:
    NUM_ERROR_MESSAGES = 2
    INTERNAL_ROWS_PER_OBJ = NUM_ERROR_MESSAGES + 1

    def __init__(self, master, index, header_rows, row_number, input_vars, column_order=range(1, 6)):
        self.master = master

        self.base_row = header_rows + row_number * GasRow.INTERNAL_ROWS_PER_OBJ
        self.active_errors = 0

        validate_min_max_command = master.register(self.validate_min_max)
        validate_calib_command = master.register(self.validate_calib)

        self.gas_var, self.min_var, self.max_var, self.calib_var, self.channel_var = input_vars
        gas_name = ttk.Entry(master, width=GUI.STRING_WIDTH, textvariable=self.gas_var)
        retention_min = ttk.Entry(
            master, width=GUI.INT_WIDTH, validate='all',
            validatecommand=(validate_min_max_command, '%V', '%P'), textvariable=self.min_var)
        retention_max = ttk.Entry(
            master, width=GUI.INT_WIDTH, validate='all',
            validatecommand=(validate_min_max_command, '%V', '%P'), textvariable=self.max_var)
        calib_val = ttk.Entry(
            master, width=GUI.FLOAT_WIDTH, validate='all',
            validatecommand=(validate_calib_command, '%V', '%P'), textvariable=self.calib_var)
        channel_options = ('FID', 'TCD')
        channel_val = ttk.OptionMenu(master, self.channel_var, channel_options[0], *channel_options)

        pady = (GUI.PADDING, 0)

        ttk.Label(master, text=f'{index + 1}.').grid(column=0, row=self.base_row, padx=(0, GUI.PADDING), pady=pady)

        gas_pos, min_pos, max_pos, calib_pos, channel_pos = column_order
        span_horiz = tk.W+tk.E
        gas_name.grid(column=gas_pos, row=self.base_row, padx=(0, GUI.PADDING), pady=pady, sticky=span_horiz)
        retention_min.grid(column=min_pos, row=self.base_row, padx=GUI.PADDING, pady=pady, sticky=span_horiz)
        retention_max.grid(column=max_pos, row=self.base_row, padx=GUI.PADDING, pady=pady, sticky=span_horiz)
        calib_val.grid(column=calib_pos, row=self.base_row, padx=GUI.PADDING, pady=pady, sticky=span_horiz)
        channel_val.grid(column=channel_pos, row=self.base_row, padx=(GUI.PADDING, 0), pady=pady)

    def toggle_error_label(self, condition, name, message):
        if condition:
            if not hasattr(self, name):
                self.active_errors += 1
                label = ttk.Label(self.master, text=message, style=GasList.TTK_ERROR_LABEL_STYLE)
                label.grid(columnspan=4, column=1, row=self.base_row + self.active_errors, sticky=tk.W)
                setattr(self, name, label)
        else:
            try:
                getattr(self, name).destroy()
                delattr(self, name)
                self.active_errors -= 1
            except AttributeError:
                pass

    def validate_min_max(self, reason, final_text):
        if not final_text:
            return True
        if not is_nonnegative_int(final_text):
            return False
        if reason == 'focusout':
            try:
                min_val = int(self.min_var.get())
                max_val = int(self.max_var.get())
            except ValueError:
                return True # Only toggle error label if both values are populated
            self.toggle_error_label(min_val >= max_val, 'bounds_error_label', 'Maximum must be greater than minimum.')
        return True

    def validate_calib(self, reason, final_text):
        if not final_text:
            return True
        if not is_nonnegative_float(final_text):
            return False
        if reason == 'focusout':
            self.toggle_error_label(float(final_text) == 0, 'calib_error_label', 'Calibration value must be non-zero.')
        return True

class GasList(ttk.Frame):
    TTK_ERROR_LABEL_STYLE = 'Red.TLabel'
    NUM_FIELDS = 5
    DEFAULT_GAS_COUNT = 2
    MAX_GAS_COUNT = 6

    def __init__(self, master):
        super().__init__(master)

        # Initialize error label style
        style = ttk.Style()
        style.configure(GasList.TTK_ERROR_LABEL_STYLE, foreground='red')

        gas_title = ttk.Label(self, text='Gas Name')
        retention_min_title = ttk.Label(self, text='Min. Retention (sec)')
        retention_max_title = ttk.Label(self, text='Max. Retention (sec)')
        calib_title = ttk.Label(self, text='Calib. (ppm/(mV•s))')
        channel_title = ttk.Label(self, text='Analysis Channel')

        gas_pos, min_pos, max_pos, calib_pos, channel_pos = range(1, 6)
        gas_title.grid(column=gas_pos, row=0, padx=0, sticky=tk.W)
        retention_min_title.grid(column=min_pos, row=0, padx=(GUI.PADDING, 0), sticky=tk.W)
        retention_max_title.grid(column=max_pos, row=0, padx=(GUI.PADDING, 0), sticky=tk.W)
        calib_title.grid(column=calib_pos, row=0, padx=(GUI.PADDING, 0), sticky=tk.W)
        channel_title.grid(column=channel_pos, row=0, padx=(GUI.PADDING, 0), sticky=tk.W)

        self.add_row_button = ttk.Button(self, text='Add Gas', command=self.add_row)
        self.add_row_button.grid(row=GasRow.INTERNAL_ROWS_PER_OBJ * GasList.MAX_GAS_COUNT, columnspan=GasList.NUM_FIELDS + 1, pady=(GUI.PADDING * 2, 0))

        self.gas_list = []
        for _ in range(GasList.DEFAULT_GAS_COUNT):
            self.add_row()

    def add_row(self):        
        index = len(self.gas_list)
        vars = [tk.StringVar() for _ in range(GasList.NUM_FIELDS)]
        GasRow(master=self, index=index, header_rows=1, row_number=index, input_vars=vars)
        self.gas_list.append(vars)

        if index + 1 >= GasList.MAX_GAS_COUNT:
            self.add_row_button.grid_remove()

    def get_parsed_input(self):
        result = { 'attributes_by_gas_name': {}, 'duplicates': [] }
        for gas in self.gas_list:
            name, retention_min_str, retention_max_str, calib_val_str, channel = [val.get() for val in gas]

            # Assume if min is blank 0 is intended and if max is blank end of GC run is intended
            retention_min = safe_int(retention_min_str)
            retention_max = safe_int(retention_max_str)
            
            try:
                calib_val = float(calib_val_str)
            except ValueError:
                continue # Only complete gas with valid calibration value to parsed result

            is_retention_valid = not retention_min or not retention_max or retention_min < retention_max
            are_inputs_valid = name and is_retention_valid and calib_val > 0
            if are_inputs_valid:
                if name in result['attributes_by_gas_name']:
                    result['duplicates'].append(name)
                result['attributes_by_gas_name'][name] = {
                    'retention_min': retention_min,
                    'retention_max': retention_max,
                    'calibration_value': calib_val,
                    'channel': channel
                }

        return result

# Non-negative floats only
class FloatEntry(ttk.Frame):
    def __init__(self, master, before_text, after_text, textvariable):
        super().__init__(master)
        validate_command = self.register(FloatEntry.validate)

        before_text = ttk.Label(self, text=before_text)
        entry = ttk.Entry(
            self, width=GUI.INT_WIDTH, validate='key',
            validatecommand=(validate_command, '%P'), textvariable=textvariable)
        after_text = ttk.Label(self, text=after_text)
        
        before_text.grid(row=0, column=0)
        entry.grid(row=0, column=1)
        after_text.grid(row=0, column=2)

    @staticmethod
    def validate(final_text):
        return not final_text or is_nonnegative_float(final_text)

# Includes flow rate (sccm) and checkboxes for automatic integration and saving all parameters.
class AdditionalFields(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.flow_rate, self.auto_integration, self.should_save = (tk.StringVar(), tk.IntVar(value=1), tk.IntVar(value=1))
        self.flow_rate_entry = FloatEntry(
            self, before_text='Total flow rate of electrochemically active gas: ', after_text='sccm', textvariable=self.flow_rate)
        self.auto_integration_checkbutton = ttk.Checkbutton(
            self, text='Enable automatic integration (i.e. for a given channel, choose bounds on single injection to apply to all)',
            variable=self.auto_integration)
        self.should_save_checkbutton = ttk.Checkbutton(
            self, text='Save these parameters to auto-populate for subsequent experiments', variable=self.should_save)

        self.flow_rate_entry.grid(pady=(GUI.PADDING * 4, 0), sticky=tk.W)
        self.auto_integration_checkbutton.grid(pady=(GUI.PADDING * 4, 0), sticky=tk.W)
        self.should_save_checkbutton.grid(pady=(GUI.PADDING, 0), sticky=tk.W)

        self.params = {
            'flow_rate': self.flow_rate,
            'auto_integration': self.auto_integration,
            'should_save': self.should_save
        }

    def get_parsed_input(self):
        result = {}

        try:
            flow_rate = float(self.params['flow_rate'].get())
        except ValueError:
            flow_rate = None
        result['flow_rate'] = flow_rate

        result['auto_integration_enabled'] = bool(self.params['auto_integration'].get())
        result['should_save'] = bool(self.params['should_save'].get())

        return result

class FilePicker(ttk.Frame):
    MAX_DISPLAY_LEN = 50

    def __init__(self, master, file_label, file_type, variable, label_text, msg_detail='', button_text='Browse'):
        super().__init__(master)
        self.file_variable = variable
        self.label_variable = tk.StringVar(value=label_text)

        self.file_label = file_label
        self.file_type = file_type
        self.msg_detail = msg_detail

        picker_button = ttk.Button(self, text=button_text, command=self.get_filepath)
        picker_label = ttk.Label(self, textvariable=self.label_variable)
        picker_button.grid(row=0, column=0, sticky=tk.W, padx=(0, GUI.PADDING), pady=GUI.PADDING)
        picker_label.grid(row=0, column=1, sticky=tk.W, pady=GUI.PADDING)

    def get_filepath(self):
        filepath = self.prompt_filepath()
        self.file_variable.set(filepath)
        if filepath:
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
                    title=f'Select a {self.file_label} file.{detail_str}',
                    filetypes=[(self.file_label, self.file_type)])
                handle = open(path, 'r') # Check that file is openable
                file_picked = True
            except IOError as err:
                should_retry = messagebox.askretrycancel(
                    'Unable to open file',
                    f'Error while opening {self.file_label} file. {err.strerror}.')
                if not should_retry:
                    return None
        handle.close()
        return path

class FileList(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)

        self.filepaths = {}
        file_labels = ['FID', 'TCD', 'CA']
        label_text = 'No file selected.'

        for file_label in file_labels:
            if file_label == 'FID' or file_label == 'TCD':
                msg_detail = f"""This will be the only {file_label} file from which 
                to choose integration bounds if automatic integration is enabled."""
                extension = FileType.GC
            else:
                msg_detail = 'This will be aligned to the GC files to generate the final output.'
                extension = FileType.CA

            self.filepaths[file_label] = tk.StringVar()
            file_picker = FilePicker(
                self, button_text=f'Choose {file_label} File', file_label=file_label, file_type=f'.{extension}',
                variable=self.filepaths[file_label], msg_detail=msg_detail, label_text=label_text)
            file_picker.grid(sticky=tk.W)
    
    def get_parsed_input(self):
        return {key: val.get() for key, val in self.filepaths.items()}

class Application(ttk.Frame):
    PADX, PADY = (25, 20)

    def __init__(self, master):
        super().__init__(master)
        self.grid()

        container = ttk.Frame(self)
        container.grid(padx=Application.PADX, pady=Application.PADY)

        self.gas_list = GasList(container)
        self.gas_list.grid()

        self.additional_fields = AdditionalFields(container)
        self.additional_fields.grid()

        separator = ttk.Separator(container, orient=tk.HORIZONTAL)
        separator.grid(pady=Application.PADY, sticky=tk.E+tk.W)

        self.file_list = FileList(container)
        self.file_list.grid(sticky=tk.W)

        run_button = ttk.Button(container, text='Run Analysis', command=self.print_test)
        run_button.grid(sticky=tk.E, pady=(Application.PADY, 0))

    def print_test(self):
        # Invalid params ignore notification
        # At least one valid needed
        print(self.gas_list.get_parsed_input())
        print(self.additional_fields.get_parsed_input())
        print(self.file_list.get_parsed_input())

def get_geometry(frame):
    geometry = frame.winfo_geometry()
    match = re.match(r'^(\d+)x(\d+)\+(\d+)\+(\d+)$', geometry)
    return [int(val) for val in match.group(*range(1, 5))]

def center_window(root, y_percent=100):
    """Center the root window of the Tk application in
    the currently active screen/monitor. Works properly
    with multiscreen setups. Must be called after application
    is fully initialized so that the root window is the true
    final size.
    
    Set y_percent to a value between 0 and 100 inclusive to
    translate the window vertically, where 100 is fully centered and
    0 is top of window touching top of screen."""
    root.attributes('-alpha', 0)

    root.withdraw()
    root.attributes('-fullscreen', True)
    root.update_idletasks()
    screen_width, screen_height, *_ = get_geometry(root)
    root.attributes('-fullscreen', False)

    root.deiconify()
    root.update_idletasks()
    window_width, window_height, *_ = get_geometry(root)

    pos_x = round(screen_width / 2 - window_width / 2)
    pos_y = round((screen_height / 2 - window_height / 2) * y_percent / 100)
    root.geometry(f'+{pos_x}+{pos_y}')
    root.update_idletasks()
    
    root.attributes('-alpha', 1)

def main():
    root = tk.Tk()
    root.title('Chromelectric')
    root.resizable(False, False)
    app = Application(master=root)
    center_window(root, y_percent=50)
    app.mainloop()

if __name__ == '__main__':
    main()