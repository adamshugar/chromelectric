from util import is_nonnegative_int, is_nonnegative_float, safe_int, safe_float
import tkinter as tk
from tkinter import ttk
import gui
import gui.hdpi as hdpi

# Intentionally does not subclass ttk.Frame so that all GasRow objects can share the same grid layout
class GasRow:
    ERRORS_BY_LABEL = {
        'bounds_error_label': 'Maximum must be greater than minimum.',
        'calib_error_label': 'Calibration value must be non-zero.'
    }
    ERROR_NAMES = [name for name in ERRORS_BY_LABEL]
    INTERNAL_ROWS_PER_OBJ = len(ERRORS_BY_LABEL) + 1

    def __init__(self, master, index, header_rows, row_number, input_vars, column_order=range(1, 6)):
        self.master = master

        self.base_row = header_rows + row_number * GasRow.INTERNAL_ROWS_PER_OBJ

        validate_min_max_command = master.register(self.validate_min_max)
        validate_calib_command = master.register(self.validate_calib)

        self.gas_var, self.min_var, self.max_var, self.calib_var, self.channel_var = input_vars
        gas_name = ttk.Entry(master, width=gui.STRING_WIDTH, textvariable=self.gas_var)
        retention_min = ttk.Entry(
            master, width=gui.INT_WIDTH, justify=tk.RIGHT, validate='all',
            validatecommand=(validate_min_max_command, '%V', '%P'), textvariable=self.min_var)
        retention_max = ttk.Entry(
            master, width=gui.INT_WIDTH, justify=tk.RIGHT, validate='all',
            validatecommand=(validate_min_max_command, '%V', '%P'), textvariable=self.max_var)
        calib_val = ttk.Entry(
            master, width=gui.FLOAT_WIDTH, justify=tk.RIGHT, validate='all',
            validatecommand=(validate_calib_command, '%V', '%P'), textvariable=self.calib_var)
        channel_options = ('FID', 'TCD')
        channel_val = ttk.OptionMenu(master, self.channel_var, self.channel_var.get(), *channel_options)

        pady = (gui.PADDING, 0)

        ttk.Label(master, text=f'{index + 1}.').grid(column=0, row=self.base_row, padx=(0, gui.PADDING), pady=pady)

        gas_pos, min_pos, max_pos, calib_pos, channel_pos = column_order
        span_horiz = tk.W+tk.E
        gas_name.grid(column=gas_pos, row=self.base_row, padx=(0, gui.PADDING), pady=pady, sticky=span_horiz)
        retention_min.grid(column=min_pos, row=self.base_row, padx=gui.PADDING, pady=pady, sticky=span_horiz)
        retention_max.grid(column=max_pos, row=self.base_row, padx=gui.PADDING, pady=pady, sticky=span_horiz)
        calib_val.grid(column=calib_pos, row=self.base_row, padx=gui.PADDING, pady=pady, sticky=span_horiz)
        channel_val.grid(column=channel_pos, row=self.base_row, padx=(gui.PADDING, 0), pady=pady)

    def toggle_error_label(self, condition, name, message):
        if condition:
            if not hasattr(self, name):
                label = ttk.Label(self.master, text=message, style=GasList.TTK_ERROR_LABEL_STYLE)
                label.grid(columnspan=4, column=1, row=self.base_row + GasRow.ERROR_NAMES.index(name) + 1, sticky=tk.W)
                setattr(self, name, label)
        else:
            try:
                getattr(self, name).grid_forget()
                getattr(self, name).destroy()
                delattr(self, name)
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
            name = 'bounds_error_label'
            self.toggle_error_label(min_val >= max_val, name, GasRow.ERRORS_BY_LABEL[name])
        return True

    def validate_calib(self, reason, final_text):
        if not final_text:
            return True
        if not is_nonnegative_float(final_text):
            return False
        if reason == 'focusout':
            name = 'calib_error_label'
            self.toggle_error_label(float(final_text) == 0, name, GasRow.ERRORS_BY_LABEL[name])
        return True

class GasList(ttk.Frame):
    TTK_ERROR_LABEL_STYLE = 'Red.TLabel'
    NUM_FIELDS = 5
    DEFAULT_GAS_COUNT = 2
    MAX_GAS_COUNT = 5
    SETTINGS_ID = 'attributes_by_gas_name'

    def __init__(self, master, saved_settings=None):
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
        retention_min_title.grid(column=min_pos, row=0, padx=(gui.PADDING, 0), sticky=tk.W)
        retention_max_title.grid(column=max_pos, row=0, padx=(gui.PADDING, 0), sticky=tk.W)
        calib_title.grid(column=calib_pos, row=0, padx=(gui.PADDING, 0), sticky=tk.W)
        channel_title.grid(column=channel_pos, row=0, padx=(gui.PADDING, 0), sticky=tk.W)

        self.add_row_button = hdpi.Button(self, text='Add Gas', command=self.add_row)
        self.add_row_button.grid(row=GasRow.INTERNAL_ROWS_PER_OBJ * GasList.MAX_GAS_COUNT, columnspan=GasList.NUM_FIELDS + 1, pady=(gui.PADDING * 2, 0))

        self.gas_list = []
        if saved_settings and saved_settings[GasList.SETTINGS_ID]:
            attributes_by_gas_name = saved_settings[GasList.SETTINGS_ID]
            attribute_order = ['retention_min', 'retention_max', 'calibration_value', 'channel']
            for gas_name, attrs in attributes_by_gas_name.items():
                self.add_row([gas_name, *[attrs[key] for key in attribute_order]])
        else:
            for _ in range(GasList.DEFAULT_GAS_COUNT):
                self.add_row()

    def add_row(self, initial_vals=['' for _ in range(NUM_FIELDS)]):        
        index = len(self.gas_list)
        vars = [tk.StringVar(value=initial_vals[i]) for i in range(GasList.NUM_FIELDS)]
        GasRow(master=self, index=index, header_rows=1, row_number=index, input_vars=vars)
        self.gas_list.append(vars)

        if index + 1 >= GasList.MAX_GAS_COUNT:
            self.add_row_button.grid_remove()

    def get_parsed_input(self):
        result = { GasList.SETTINGS_ID: {}, 'duplicates': [] }
        for gas in self.gas_list:
            name, retention_min_str, retention_max_str, calib_val_str, channel = [val.get() for val in gas]

            calib_val = safe_float(calib_val_str)
            # Assume if min is blank 0 is intended and if max is blank end of GC run is intended
            retention_min = safe_int(retention_min_str)
            retention_max = safe_int(retention_max_str)

            if not name or not calib_val: # Calibration value must be greater than zero
                continue
            
            if name in result[GasList.SETTINGS_ID]:
                result['duplicates'].append(name)
            result[GasList.SETTINGS_ID][name] = {
                'calibration_value': calib_val,
                'channel': channel
            }
            is_retention_valid = retention_min is None or retention_max is None or retention_min < retention_max
            if is_retention_valid:
                result[GasList.SETTINGS_ID][name]['retention_min'] = retention_min
                result[GasList.SETTINGS_ID][name]['retention_max'] = retention_max

        return result

# Intentionally does not subclass ttk.Frame so that all ShortEntry objects can share the same grid layout
class ShortEntry:
    def __init__(self, master, row, before_text, after_text, textvariable, validation_callback=lambda final_text: True, indent=0):
        validate_command = master.register(validation_callback)

        before_text = ttk.Label(master, text=before_text)
        entry = ttk.Entry(
            master, width=gui.FLOAT_WIDTH, justify=tk.RIGHT, validate='key',
            validatecommand=(validate_command, '%P'), textvariable=textvariable)
        after_text = ttk.Label(master, text=' ' + after_text)
        
        before_text.grid(row=row, column=0, padx=(indent, gui.PADDING * 2), pady=(gui.PADDING, 0), sticky=tk.W)
        entry.grid(row=row, column=1)
        after_text.grid(row=row, column=2, sticky=tk.W)

class NamedDivider(ttk.Frame):
    def __init__(self, master, name):
        super().__init__(master)
        ttk.Label(self, text=name).grid(row=0, column=0, padx=(0, gui.PADDING * 2), sticky=tk.W)
        ttk.Separator(self, orient=tk.HORIZONTAL).grid(row=0, column=1, sticky=tk.W+tk.E)
        self.columnconfigure(1, weight=1)

class CheckbuttonList(ttk.Frame):
    def __init__(self, master, saved_settings={}):
        super().__init__(master)

        self.checkbutton_fields = {
            'plot_j': {
                'label': 'Generate plot of partial current densities (log(mA/cm²) vs. V)',
                'default': True
            },
            'plot_fe': {
                'label': 'Generate plot of Faradaic efficiencies (% vs. V)',
                'default': True
            },
            'fe_total': {
                'label': 'Include total Faradaic efficiency in plot',
                'default': False,
                'indent': gui.PADDING * 5
            },
        }

        if not isinstance(saved_settings, dict):
            saved_settings = {}

        self.columnconfigure(0, weight=1)
        div = NamedDivider(self, name='Additional output parameters')
        div.grid(pady=(0, gui.PADDING * 3), sticky=tk.E+tk.W)
        
        base_indent = gui.PADDING * 5
        for name, attrs in self.checkbutton_fields.items():
            attrs['var'] = tk.IntVar(value=int(attrs['default']) if saved_settings[name] is None else int(saved_settings[name]))
            attrs['ref'] = ttk.Checkbutton(self, text=attrs['label'], variable=attrs['var'])
            indent = attrs.get('indent') if attrs.get('indent') else 0
            attrs['ref'].grid(sticky=tk.W, padx=(base_indent + indent, 0), pady=(0, gui.PADDING))

        self.checkbutton_fields['plot_fe']['ref'].config(command=self.toggle_disable_fe_total)

    def toggle_disable_fe_total(self):
        fe_total = self.checkbutton_fields['fe_total']['ref']
        is_enabled = 'disabled' not in fe_total.state()
        fe_total.state([f"{'' if is_enabled else '!'}disabled"])

    def get_parsed_input(self):
        return { field: bool(self.checkbutton_fields[field]['var'].get()) for field in self.checkbutton_fields }

class ShortEntryList(ttk.Frame):
    def __init__(self, master, saved_settings={}):
        super().__init__(master)

        self.fe_params = {
            'flow_total': {
                'before_text': 'Total gaseous flow rate',
                'after_text': 'sccm'
            },
            'flow_active': {
                'before_text': 'Flow rate of electrochemically active gases',
                'after_text': 'sccm'
            },
            'mix_vol': {
                'before_text': 'Pre-GC mixing volume',
                'after_text': 'mL'
            }
        }

        self.v_correction_params = {
            'high_freq_resistance': {
                'before_text': 'High frequency resistance (PEIS)',
                'after_text': 'Ω',
            },
            'pH': {
                'before_text': 'Electrolyte pH',
                'after_text': '',
                'allow_negative': True
            },
            'ref_potential': {
                'before_text': 'Reference electrode potential',
                'after_text': 'V vs. SHE',
                'allow_negative': True
            },
        }

        if not isinstance(saved_settings, dict):
            saved_settings = {}
        self.row = 0
        indent = gui.PADDING * 5
        self.columnconfigure(2, weight=1)

        div1 = NamedDivider(self, name='Faradaic efficiency parameters')
        div1.grid(row=self.row, columnspan=3, pady=(0, gui.PADDING), sticky=tk.E+tk.W)
        self.row += 1
        self.render_short_entries(self.fe_params, indent=indent, saved_settings=saved_settings)
        
        div2 = NamedDivider(self, name='Voltage correction parameters')
        div2.grid(row=self.row, columnspan=3, pady=(gui.PADDING * 4, gui.PADDING), sticky=tk.E+tk.W)
        self.row += 1
        self.render_short_entries(self.v_correction_params, indent=indent, saved_settings=saved_settings)

    def render_short_entries(self, entry_dict, indent, saved_settings):
        nonnegative_float_validation = lambda final_text: not final_text or is_nonnegative_float(final_text)
        any_float_validation = lambda final_text: not final_text or final_text == '-' or safe_float(final_text) is not None
        for field_name, field_attrs in entry_dict.items():
            field_attrs['var'] = tk.StringVar(value=saved_settings[field_name] if saved_settings[field_name] else '')
            validation = any_float_validation if field_attrs.get('allow_negative') else nonnegative_float_validation
            ShortEntry(
                self, row=self.row, before_text=field_attrs['before_text'], after_text=field_attrs['after_text'],
                textvariable=field_attrs['var'], validation_callback=validation, indent=indent)
            self.row += 1

    def get_parsed_input(self):
        result = {}
        entry_list = {**self.fe_params, **self.v_correction_params}
        for entry, attributes in entry_list.items():
            result[entry] = safe_float(attributes['var'].get())
        return result