import tkinter as tk
import tkinter.font
from tkinter import ttk
import re

padding = 5

def get_background(widget):
    return '#%x%x%x' % widget.winfo_rgb(widget.cget('background'))

def is_positive_int(str):
        # Use regex instead of isnumeric() because isnumeric() accepts exponents and fractions.
        # Must explicitly convert match to boolean because any non-bool return value disables validation. Sigh.
        return re.match(r'^[0-9]+$', str) != None

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

        (self.gas_var, self.min_var, self.max_var, self.calib_var) = input_vars
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

        (gas_pos, min_pos, max_pos, calib_pos) = column_order
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
        if not is_positive_int(final_text):
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

class GasListContainer(ttk.LabelFrame):
    def __init__(self, master):
        super().__init__(master, text='Gas List Parameters')
        gas_list = GasList(master=self)
        gas_list.grid(padx=padding, pady=padding)
    
class GasList(ttk.Frame):
    TTK_ERROR_LABEL_STYLE = 'Red.TLabel'
    NUM_FIELDS = 4
    ADDITIONAL_COLS = 2
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

        (gas_pos, min_pos, max_pos, calib_pos) = range(1, 5)
        gas_title.grid(column=gas_pos, row=0, padx=0, sticky=tk.W)
        retention_min_title.grid(column=min_pos, row=0, padx=(padding, 0), sticky=tk.W)
        retention_max_title.grid(column=max_pos, row=0, padx=(padding, 0), sticky=tk.W)
        calib_title.grid(column=calib_pos, row=0, padx=(padding, 0), sticky=tk.W)

        self.add_row_button = ttk.Button(self, text='Add Gas', command=self.add_row)
        self.manual_integration_checkbutton = ttk.Checkbutton(self, text='Enable automatic integration')
        self.save_params_checkbutton = ttk.Checkbutton(self, text='Save these parameters')
        self.footer_widgets = [self.add_row_button, self.manual_integration_checkbutton, self.save_params_checkbutton]

        self.gas_params = []
        for _ in range(GasList.DEFAULT_GAS_COUNT):
            self.add_row()

    def attach_footer_widgets(self):
        self.add_row_button.grid(
            columnspan=GasList.NUM_FIELDS + GasList.ADDITIONAL_COLS, pady=(padding * 2, 0))
        self.manual_integration_checkbutton.grid(
            columnspan=GasList.NUM_FIELDS + GasList.ADDITIONAL_COLS, pady=(padding, 0), sticky=tk.W)
        self.save_params_checkbutton.grid(
            columnspan=GasList.NUM_FIELDS + GasList.ADDITIONAL_COLS, pady=(padding, 0), sticky=tk.W)
        
    def detach_footer_widgets(self):
        for widget in self.footer_widgets:
            widget.grid_forget()

    def add_row(self):
        self.detach_footer_widgets()
        
        index = len(self.gas_params)
        vars = (tk.StringVar() for _ in range(GasList.NUM_FIELDS))
        GasRow(master=self, index=index, row_number=index + 1, input_vars=vars)
        self.gas_params.append(vars)

        self.attach_footer_widgets()
        if index + 1 >= GasList.MAX_GAS_COUNT:
            self.add_row_button.grid_remove()

class Application(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.grid()
        gas_list = GasListContainer(self)
        gas_list.grid(padx=100, pady=100)
        # self.grid(column=0, row=0, sticky=tk.N+tk.S+tk.E+tk.W)

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
    (screen_width, screen_height, *_) = get_geometry(root)
    root.attributes('-fullscreen', False)

    root.deiconify()
    root.update_idletasks()
    (window_width, window_height, *_) = get_geometry(root)

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
