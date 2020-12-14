import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import re
import os

padding = 5
GC_RAW_EXTENSION = 'asc'

class GasRow:
    # Widths in number of characters (these are minimums; if header text is longer, entry box expands)
    STRING_WIDTH = 14
    INT_WIDTH = 5
    FLOAT_WIDTH = 8

    def __init__(self, master, index, row_number, input_vars, column_order=range(1, 5)):
        self.master = master

        NUM_ERROR_MESSAGES = 3
        self.base_row = row_number * NUM_ERROR_MESSAGES
        self.active_errors = 0

        validate_min_max_command = master.register(self.validate_min_max)
        validate_calib_command = master.register(self.validate_calib)

        self.gas_var, self.min_var, self.max_var, self.calib_var = input_vars
        gas_name = ttk.Entry(master, width=GasRow.STRING_WIDTH, textvariable=self.gas_var)
        retention_min = ttk.Entry(
            master, width=GasRow.INT_WIDTH, validate='all',
            validatecommand=(validate_min_max_command, '%V', '%P'), textvariable=self.min_var)
        retention_max = ttk.Entry(
            master, width=GasRow.INT_WIDTH, validate='all',
            validatecommand=(validate_min_max_command, '%V', '%P'), textvariable=self.max_var)
        calib_val = ttk.Entry(
            master, width=GasRow.FLOAT_WIDTH, validate='all',
            validatecommand=(validate_calib_command, '%V', '%P'), textvariable=self.calib_var)

        pady = (padding, 0)

        ttk.Label(master, text=f'{index + 1}.').grid(column=0, row=self.base_row, padx=(0, padding), pady=pady)

        gas_pos, min_pos, max_pos, calib_pos = column_order
        span_horiz = tk.W+tk.E
        gas_name.grid(column=gas_pos, row=self.base_row, padx=(0, padding), pady=pady, sticky=span_horiz)
        retention_min.grid(column=min_pos, row=self.base_row, padx=padding, pady=pady, sticky=span_horiz)
        retention_max.grid(column=max_pos, row=self.base_row, padx=padding, pady=pady, sticky=span_horiz)
        calib_val.grid(column=calib_pos, row=self.base_row, padx=(padding, 0), pady=pady, sticky=span_horiz)

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
        # Use regex instead of isnumeric() because isnumeric() accepts exponents and fractions.
        is_numeric = re.match(r'^[0-9]+$', str) != None
        if not is_numeric:
            return False
        if reason == 'focusout':
            try:
                min_val = int(self.min_var.get())
                max_val = int(self.max_var.get())
            except ValueError:
                return True
            self.toggle_error_label(min_val >= max_val, 'bounds_error_label', 'Maximum must be greater than minimum.')
        return True

    def validate_calib(self, reason, final_text):
        if not final_text:
            return True
        is_positive_float = re.match(r'^\d+(\.\d*)?$', final_text) != None
        if not is_positive_float:
            return False
        if reason == 'focusout':
            self.toggle_error_label(float(final_text) == 0, 'calib_error_label', 'Calibration value must be non-zero.')
        return True
class GasList(ttk.Frame):
    TTK_ERROR_LABEL_STYLE = 'Red.TLabel'
    NUM_FIELDS = 4
    ADDITIONAL_COLS = 1
    DEFAULT_GAS_COUNT = 2
    MAX_GAS_COUNT = 6

    def __init__(self, master):
        super().__init__(master)

        # Initialize error label style
        style = ttk.Style()
        style.configure(GasList.TTK_ERROR_LABEL_STYLE, foreground='red')

        gas_title = ttk.Label(self, text='Gas Identity')
        retention_min_title = ttk.Label(self, text='Min. Retention (sec)')
        retention_max_title = ttk.Label(self, text='Max. Retention (sec)')
        calib_title = ttk.Label(self, text='Calibration Value')

        gas_pos, min_pos, max_pos, calib_pos = range(1, 5)
        gas_title.grid(column=gas_pos, row=0, padx=0, sticky=tk.W)
        retention_min_title.grid(column=min_pos, row=0, padx=(padding, 0), sticky=tk.W)
        retention_max_title.grid(column=max_pos, row=0, padx=(padding, 0), sticky=tk.W)
        calib_title.grid(column=calib_pos, row=0, padx=(padding, 0), sticky=tk.W)

        self.auto_integration, self.should_save = (tk.IntVar(value=1), tk.IntVar(value=1))
        self.add_row_button = ttk.Button(self, text='Add Gas', command=self.add_row)
        self.auto_integration_checkbutton = ttk.Checkbutton(self, text='Enable automatic integration', variable=self.auto_integration)
        self.should_save_checkbutton = ttk.Checkbutton(self, text='Save these parameters for future analysis', variable=self.should_save)
        self.footer_widgets = [self.add_row_button, self.auto_integration_checkbutton, self.should_save_checkbutton]

        self.gas_list = []
        self.params = {
            'gas_list': self.gas_list,
            'auto_integration': self.auto_integration,
            'should_save': self.should_save
        }
        for _ in range(GasList.DEFAULT_GAS_COUNT):
            self.add_row()

    def attach_footer_widgets(self):
        self.add_row_button.grid(
            columnspan=GasList.NUM_FIELDS + GasList.ADDITIONAL_COLS, pady=(padding * 2, 0))
        self.auto_integration_checkbutton.grid(
            columnspan=GasList.NUM_FIELDS + GasList.ADDITIONAL_COLS, pady=(padding, 0), sticky=tk.W)
        self.should_save_checkbutton.grid(
            columnspan=GasList.NUM_FIELDS + GasList.ADDITIONAL_COLS, pady=(padding, 0), sticky=tk.W)
        
    def detach_footer_widgets(self):
        for widget in self.footer_widgets:
            widget.grid_forget()

    def add_row(self):
        self.detach_footer_widgets()
        
        index = len(self.gas_list)
        vars = (tk.StringVar() for _ in range(GasList.NUM_FIELDS))
        GasRow(master=self, index=index, row_number=index + 1, input_vars=vars)
        self.gas_list.append(vars)

        self.attach_footer_widgets()
        if index + 1 >= GasList.MAX_GAS_COUNT:
            self.add_row_button.grid_remove()

class FilePicker(ttk.Frame):
    def __init__(self, master, file_label, file_type, variable, label_text, msg_detail='', button_text='Browse'):
        super().__init__(master)
        self.file_variable = variable
        self.label_variable = tk.StringVar(value=label_text)

        self.file_label = file_label
        self.file_type = file_type
        self.msg_detail = msg_detail

        picker_button = ttk.Button(self, text=button_text, command=self.get_filepath)
        picker_label = ttk.Label(self, textvariable=self.label_variable)
        picker_button.grid(row=0, column=0, sticky=tk.W, padx=(0, padding), pady=padding)
        picker_label.grid(row=0, column=1, sticky=tk.W, pady=padding)

    def get_filepath(self):
        filepath = self.prompt_filepath()
        self.file_variable.set(filepath)
        if filepath:
            _, tail = os.path.split(filepath)
            self.label_variable.set(tail)
        
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
        var = tk.StringVar()
        filepaths = {}
        gc_files = ['FID', 'TCD']
        for gc_file in gc_files:
            msg_detail = f"""This will be the only {gc_file} file from which 
            to choose integration bounds if automatic integration is enabled."""
            label_text = 'No file selected.'
            filepaths[gc_file] = tk.StringVar()
            file_picker = FilePicker(
                self, button_text=f'Choose {gc_file} File', file_label=gc_file, file_type=f'.{GC_RAW_EXTENSION}',
                variable=filepaths[gc_file], msg_detail=msg_detail, label_text=label_text)
            file_picker.grid(sticky=tk.W)

class Application(ttk.Frame):
    PADX, PADY = (25, 20)

    def __init__(self, master):
        super().__init__(master)
        self.grid()

        container = ttk.Frame(self)
        container.grid(padx=Application.PADX, pady=Application.PADY)

        gas_list = GasList(container)
        gas_list.grid()

        separator = ttk.Separator(container, orient=tk.HORIZONTAL)
        separator.grid(pady=Application.PADY, sticky=tk.E+tk.W)

        file_list = FileList(container)
        file_list.grid(sticky=tk.W)

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

root = tk.Tk()
root.title('Chromelectric')
root.resizable(False, False)
app = Application(master=root)
center_window(root, y_percent=50)
app.mainloop()
