from PySide2.QtWidgets import (
    QPushButton, QLineEdit, QLabel, QVBoxLayout, QHBoxLayout, QFrame,
    QGridLayout, QComboBox, QLayout, QSizePolicy, QCheckBox, QSpacerItem)
from PySide2.QtCore import Signal, Slot, Qt
from PySide2.QtGui import QValidator
from util import is_nonnegative_int, is_nonnegative_float, safe_int, safe_float, QtPt, channels
import gui

class MinMaxValidator(QValidator):
    def __init__(self, parent, _):
        super().__init__(parent)

    def validate(self, final_text, _):
        if not final_text or is_nonnegative_int(final_text):
            return QValidator.Acceptable
        return QValidator.Invalid

    @staticmethod
    def on_focus_out(row_object, _):
        try:
            min_val = int(row_object.min_input.text())
            max_val = int(row_object.max_input.text())
            name = 'bounds_error_label'
            row_object.toggle_error_label(min_val >= max_val, name)
        except ValueError:
            pass # Only toggle error label if both values are populated

class CalibValidator(QValidator):
    def __init__(self, parent, row_object):
        super().__init__(parent)
        self.row = row_object

    def validate(self, final_text, _):
        if final_text and not is_nonnegative_float(final_text):
            return QValidator.Invalid
        return QValidator.Acceptable

    @staticmethod
    def on_focus_out(row_object, text):
        name = 'calib_error_label'
        row_object.toggle_error_label(safe_float(text) == 0, name)

class LineEdit(QLineEdit):
    def __init__(
        self, width=None, max_width=None, alignment=None, initial_text=None,
        validator_instance=None, validator_class=None, row_object=None):
        super().__init__()
        self.row_object = row_object
        if width:
            self.setMinimumWidth(width * QtPt.font_size_px(self.font()))
            self.setMaxLength(width * 2)
        if max_width:
            self.setMaximumWidth(max_width * QtPt.font_size_px(self.font()))
        if alignment:
            self.setAlignment(alignment)
        if initial_text:
            self.setText(str(initial_text))
        if validator_instance:
            self.setValidator(validator_instance)
        elif validator_class and row_object:
            self.setValidator(validator_class(self, row_object))
            self.validator_class = validator_class

    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        if hasattr(self, 'validator_class'):
            self.validator_class.on_focus_out(self.row_object, self.text())

# Intentionally does not subclass QLayout so that all GasRow objects can share the same QGridLayout
class GasRow:
    ERRORS_BY_LABEL = {
        'bounds_error_label': 'Maximum must be greater than minimum.',
        'calib_error_label': 'Calibration value must be non-zero.'
    }
    ERROR_NAMES = [name for name in ERRORS_BY_LABEL]
    INTERNAL_ROWS_PER_OBJ = len(ERRORS_BY_LABEL) + 1

    def __init__(self, parent, header_row_count, row_number, initial_vals, resize_signal):
        self.parent = parent
        self.base_row = header_row_count + row_number * GasRow.INTERNAL_ROWS_PER_OBJ
        self.resize_signal = resize_signal

        self.columns = []
        number_label = QLabel(text=f'{row_number + 1}.')
        self.columns.append(number_label)
        self.parent.addWidget(number_label, self.base_row, 0, Qt.AlignLeft)

        # Widths are in characters
        field_types = {
            'string': {
                'width': gui.STRING_WIDTH,
                'alignment': Qt.AlignLeft
            },
            'int': {
                'width': gui.INT_WIDTH,
                'alignment': Qt.AlignRight
            },
            'float': {
                'width': gui.FLOAT_WIDTH,
                'alignment': Qt.AlignRight
            }
        }
        line_edit_order = [('string', None), ('int', MinMaxValidator), ('int', MinMaxValidator), ('float', CalibValidator)]
        line_edits = [
            LineEdit(
                **field_types[edit_params[0]], initial_text=str(initial_vals[edit_index]),
                validator_class=edit_params[1], row_object=self)
            for edit_index, edit_params in enumerate(line_edit_order)
        ]
        for index, line_edit in enumerate(line_edits):
            self.columns.append(line_edit)
            self.parent.addWidget(line_edit, self.base_row, index + 1)
        self.min_input, self.max_input = line_edits[1:3]

        channel_index = len(line_edits)
        channel_selector = QComboBox()
        channel_selector.addItems(channels)
        channel_selector.setCurrentText(initial_vals[channel_index] if initial_vals[channel_index] else channels[0])
        self.columns.append(channel_selector)
        self.parent.addWidget(channel_selector, self.base_row, channel_index + 1, Qt.AlignCenter)

        for index, err_name in enumerate(GasRow.ERROR_NAMES):
            curr_label = QLabel(text=GasRow.ERRORS_BY_LABEL[err_name])
            curr_label.setStyleSheet('color: red;')
            setattr(self, err_name, curr_label)
            self.parent.addWidget(curr_label, self.base_row + index + 1, 1, 1, GasList.NUM_FIELDS + 1)
            curr_label.hide()

        self.line_edits = line_edits
        self.channel_selector = channel_selector

    def toggle_error_label(self, condition, name):
        if condition:
            getattr(self, name).show()
        else:
            getattr(self, name).hide()
        self.resize_signal.emit()

    def hide(self):
        for col in self.columns:
            col.hide()

    def show(self):
        for col in self.columns:
            col.show()
        self.resize_signal.emit()

class GasList(QGridLayout):
    NUM_FIELDS = 5
    DEFAULT_GAS_COUNT = 2
    MAX_GAS_COUNT = 5
    SETTINGS_ID = 'attributes_by_gas_name'

    resize_requested = Signal()

    def __init__(self, resize_handler, saved_settings=None):
        super().__init__()
        self.setHorizontalSpacing(gui.PADDING)
        self.setVerticalSpacing(gui.PADDING // 3)
        self.setSizeConstraint(QLayout.SetFixedSize)
        self.resize_requested.connect(resize_handler)

        col_titles = ['Gas Name', 'Min Retention (sec)', 'Max Retention (sec)', 'Calib. (ppm/(mV•s))', 'Analysis Channel']
        for index, label in enumerate([QLabel(col_title) for col_title in col_titles]):
            self.addWidget(label, 0, index + 1, Qt.AlignLeft)

        self.gas_list = []
        if saved_settings and GasList.SETTINGS_ID in saved_settings:
            attributes_by_gas_name = saved_settings[GasList.SETTINGS_ID]
            attribute_order = ['retention_min', 'retention_max', 'calibration_value', 'channel']
            for gas_name, attrs in attributes_by_gas_name.items():
                self.add_row(initial_vals=[gas_name, *[attrs.get(key) if attrs.get(key) else '' for key in attribute_order]])

        saved_row_count = len(self.gas_list)
        additional_row_count = max(GasList.MAX_GAS_COUNT - saved_row_count, 0)
        for _ in range(additional_row_count):
            self.add_row()

        self.visible_rows = max(saved_row_count, GasList.DEFAULT_GAS_COUNT)
        for hidden_row in range(self.visible_rows, GasList.MAX_GAS_COUNT):
            self.gas_list[hidden_row].hide()

        add_button_base = GasRow.INTERNAL_ROWS_PER_OBJ * GasList.MAX_GAS_COUNT
        self.add_row_button = QPushButton(text='Add Gas')
        self.add_row_button.clicked.connect(self.show_next_row)
        self.addItem(QSpacerItem(1, gui.PADDING // 3), add_button_base, 0)
        self.addWidget(self.add_row_button, add_button_base + 1, 0, 1, GasList.NUM_FIELDS + 1, Qt.AlignCenter)
        self.add_row_button.setSizePolicy(QSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred))

    def add_row(self, initial_vals=['' for _ in range(NUM_FIELDS)]):
        self.gas_list.append(GasRow(
            parent=self, header_row_count=1, row_number=len(self.gas_list),
            initial_vals=initial_vals, resize_signal=self.resize_requested))

    @Slot()
    def show_next_row(self, _):
        if self.visible_rows < GasList.MAX_GAS_COUNT:
            self.gas_list[self.visible_rows].show()
            self.visible_rows += 1
        if self.visible_rows == GasList.MAX_GAS_COUNT:
            self.add_row_button.hide()
            self.resize_requested.emit()

    def get_parsed_input(self):
        result = { GasList.SETTINGS_ID: {}, 'duplicate_gases': [] }
        for gas in self.gas_list:
            name, retention_min_str, retention_max_str, calib_val_str = [line_edit.text() for line_edit in gas.line_edits]
            channel = gas.channel_selector.currentText()

            calib_val = safe_float(calib_val_str)
            # Assume if min is blank 0 is intended and if max is blank end of GC run is intended
            retention_min = safe_int(retention_min_str)
            retention_max = safe_int(retention_max_str)

            if not name or not calib_val: # Calibration value must be greater than zero
                continue

            if name in result[GasList.SETTINGS_ID]:
                result['duplicate_gases'].append(name)
            result[GasList.SETTINGS_ID][name] = {
                'calibration_value': calib_val,
                'channel': channel
            }
            is_retention_valid = retention_min is None or retention_max is None or retention_min < retention_max
            if is_retention_valid:
                result[GasList.SETTINGS_ID][name]['retention_min'] = retention_min
                result[GasList.SETTINGS_ID][name]['retention_max'] = retention_max

        return result

# Intentionally does not subclass QLayout so that all ShortEntry objects can share same grid layout
class ShortEntry:
    def __init__(
        self, parent, row, before_text, after_text, initial_text,
        validator_instance, col_offset=0):
        before_text = QLabel(before_text)
        self.entry = LineEdit(
            width=gui.FLOAT_WIDTH, max_width=gui.FLOAT_WIDTH,
            alignment=Qt.AlignRight, initial_text=initial_text, validator_instance=validator_instance)
        after_text = QLabel(' ' + after_text)

        parent.addWidget(before_text, row, col_offset + 0)
        parent.addWidget(self.entry, row, col_offset + 1)
        parent.addWidget(after_text, row, col_offset + 2)
    
    def get_input_ref(self):
        return self.entry

class QHLine(QFrame):
    def __init__(self):
        super().__init__()
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)

class NamedDivider(QHBoxLayout):
    def __init__(self, name):
        super().__init__()
        self.setSpacing(gui.PADDING)
        self.addWidget(QLabel(name), Qt.AlignLeft)
        self.addWidget(QHLine(), Qt.AlignCenter)

class CheckboxList(QVBoxLayout):
    def __init__(self, saved_settings):
        super().__init__()

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
                'indent': gui.PADDING
            },
        }

        if not isinstance(saved_settings, dict):
            saved_settings = {}

        self.addLayout(NamedDivider(name='Additional output parameters'))
        base_indent = gui.PADDING * 2
        for name, attrs in self.checkbutton_fields.items():
            curr_row = QHBoxLayout()

            total_indent = base_indent + (attrs.get('indent') if attrs.get('indent') else 0)
            curr_row.addItem(QSpacerItem(total_indent, 1))

            checkbox = QCheckBox(attrs['label'])
            curr_row.addWidget(checkbox)
            bool_checked = saved_settings[name] if name in saved_settings else self.checkbutton_fields[name]['default']
            checkbox.setCheckState(Qt.Checked if bool_checked else Qt.Unchecked)
            attrs['ref'] = checkbox

            self.addLayout(curr_row)

        self.checkbutton_fields['plot_fe']['ref'].clicked.connect(self.toggle_disable_fe_total)

    @Slot()
    def toggle_disable_fe_total(self):
        self.checkbutton_fields['fe_total']['ref'].setEnabled(self.checkbutton_fields['plot_fe']['ref'].isChecked())

    def get_parsed_input(self):
        return { field: bool(self.checkbutton_fields[field]['ref'].isChecked()) for field in self.checkbutton_fields }

class GenericValidator(QValidator):
    def __init__(self, validator):
        super().__init__()
        self.validator = validator

    def validate(self, final_text, _):
        return QValidator.Acceptable if self.validator(final_text) else QValidator.Invalid

class ShortEntryList(QGridLayout):
    def __init__(self, saved_settings):
        super().__init__()

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

        indent = gui.PADDING * 2

        self.curr_row = 0
        self.addLayout(NamedDivider(name='Faradaic efficiency parameters'), self.curr_row, 0, 1, 5)
        self.curr_row += 1
        self.render_short_entries(self.fe_params, indent=indent, saved_settings=saved_settings)
        self.addItem(QSpacerItem(1, gui.PADDING), self.curr_row, 0)
        self.curr_row += 1

        self.addLayout(NamedDivider(name='Voltage correction parameters'), self.curr_row, 0, 1, 5)
        self.curr_row += 1
        self.render_short_entries(self.v_correction_params, indent=indent, saved_settings=saved_settings)
        self.addItem(QSpacerItem(1, gui.PADDING), self.curr_row, 0)

    def render_short_entries(self, entry_dict, indent, saved_settings):
        nonnegative_float_validation = GenericValidator(lambda final_text: not final_text or is_nonnegative_float(final_text))
        any_float_validation = GenericValidator(lambda final_text: not final_text or final_text == '-' or safe_float(final_text) is not None)
        for index, (field_name, field_attrs) in enumerate(entry_dict.items()):
            initial_text = saved_settings[field_name] if field_name in saved_settings else ''
            validation = any_float_validation if field_attrs.get('allow_negative') else nonnegative_float_validation
            self.addItem(QSpacerItem(indent, 1), self.curr_row, 0)
            short_entry = ShortEntry(
                self, row=self.curr_row + index, before_text=field_attrs['before_text'], after_text=field_attrs['after_text'],
                initial_text=initial_text, validator_instance=validation, col_offset=1)
            field_attrs['ref'] = short_entry.get_input_ref()
            self.addItem(QSpacerItem(1, 1, QSizePolicy.Expanding, QSizePolicy.Minimum), self.curr_row, 4)
            self.curr_row += len(entry_dict)

    def get_parsed_input(self):
        result = {}
        entry_list = {**self.fe_params, **self.v_correction_params}
        for entry, attributes in entry_list.items():
            result[entry] = safe_float(attributes['ref'].text())
        return result
