from PySide2.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QComboBox, QSizePolicy, QFrame, QSpacerItem,
    QHBoxLayout, QPushButton, QLineEdit, QLabel, QGridLayout, QLayout, QScrollArea, QMessageBox)
from PySide2.QtCore import Signal, Slot, Qt
from PySide2.QtGui import QFont, QIntValidator
import matplotlib
from matplotlib.backends.backend_qt5agg import FigureCanvas, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import gui
from gui.graphshared import Pagination, GraphPushButton
import numpy as np
import os, re, sys
import json
from util import is_windows
from datetime import datetime, timedelta
from enum import Enum
import math
from numpy.polynomial.polynomial import Polynomial
from functools import reduce
import physcalc
import csv
matplotlib.use('Qt5Agg')
import integrate
class filetype:
    GC = 'asc'
class GC:
    suffix_regex = rf'(\d+)(?:\.)+(?:{filetype.GC})$'

    @staticmethod
    # Parse raw data from a single GC injection into a numpy array with metadata fields
    def parse_file(handle):
        # Parse relevant information from metadata lines at start of file
        # Metadata lines begin with <FIELD_NAME> (might contain spaces)
        meta_count = 0
        line = handle.readline()
        while match := re.search(r'<([A-Za-z ]*)>', line):
            meta_count += 1
            field_name = match.group(1).lower()
            val_str = line.partition('=')[2].strip()

            if field_name == 'date':
                # E.g. '12-02-2020' is represented as '12- 2-2020' for some reason
                date_string = val_str.replace(' ', '0')
            elif field_name == 'time':
                time_string = val_str.replace(' ', '0')
            elif field_name == 'rate':
                # Find GC sample rate in readings per second (Hz); can be decimal
                sample_rate = float(re.search(r'\d+(.\d+)?', line).group())
            elif field_name == 'size':
                # Total number of readings collected during the current injection
                num_readings = int(re.search(r'\d+', line).group())

            line = handle.readline()

        handle.seek(os.SEEK_SET)
        # Data lines have the form n,n for an integer n (second copy on each line is redundant)
        potentials = np.genfromtxt(fname=handle, comments=',', skip_header=meta_count)

        # Build return object with metadata
        run_duration = num_readings / sample_rate # In seconds
        time_increments = np.linspace(0, run_duration, potentials.size)
        warning = potentials.size != num_readings # Indicates file might be truncated prematurely
        start_time = datetime.strptime(f'{date_string} {time_string}', r'%m-%d-%Y %H:%M:%S')
        return {
            'warning': warning,
            'start_time': start_time,
            'x': time_increments,
            'y': potentials / 1000 # Convert from microvolts to millivolts to match calibration curves
        }
    
    @staticmethod
    def parse_list(raw_list):
        parsed_list = {}
        for index, path in raw_list.items():
            try:
                handle = open(path, 'r')
            except IOError:
                return index
            
            try:
                parsed_list[index] = GC.parse_file(handle)
            except Exception: # Fails safely for GA files with improper meta or data format
                handle.close()
                return index
            else:
                handle.close()

        return parsed_list

    @staticmethod
    # Using the file inputted by the user, find all other GC files in the run
    # assuming an auto-increment scheme of <filepath>/<shared filename><#>.<GC extension>
    def find_list(filepath):
        head, tail = os.path.split(filepath)
        user_input_match = re.search(GC.suffix_regex, tail, re.IGNORECASE)
        if user_input_match is None:
            return None # User supplied an invalid file (didn't have <#> suffix)
        shared_filename = tail[:-len(user_input_match.group(0))]

        paths_by_index = {}
        for entry in os.listdir(head):
            if not os.path.isfile(os.path.join(head, entry)):
                continue
            match = re.search(shared_filename + GC.suffix_regex, entry, re.IGNORECASE)
            if match:
                file_num = int(match.group(1))
                paths_by_index[file_num] = os.path.join(head, entry)
        return paths_by_index
class CA:
    @staticmethod
    def parse_file(filepath):
        handle = open(filepath, 'r', encoding='latin-1')
        handle.readline()
        meta_total_str = handle.readline().partition(':')[2].strip() # Total meta count on line 2
        meta_total = int(meta_total_str)

        meta_curr = 3
        while meta_curr < meta_total:
            meta_curr += 1
            line = handle.readline().lower()
            if line.startswith('acquisition started on'):
                date_str = line.partition(':')[2].strip()
                acquisition_start = datetime.strptime(date_str, r'%m/%d/%Y %H:%M:%S')
            elif line.startswith('ei (v)'):
                potentials_by_trial = [float(potential) for potential in line.split()[2:]]
            elif line.startswith('ti (h:m:s)'):
                duration_by_trial = []
                for duration in line.split()[2:]:
                    components = [float(component) for component in duration.split(':')]
                    duration_by_trial.append(timedelta(
                        hours=components[0], minutes=components[1], seconds=components[2]))

                total_duration = timedelta()
                total_dur_by_trial = [total_duration]
                for duration in duration_by_trial:
                    total_duration += duration
                    total_dur_by_trial.append(total_duration)

        # NOTE: 'time/s' field represents offset from acquisition start, NOT technique start.
        data_fields = ['Ns', 'time/s', '<I>/mA']
        # Header row for data will always be last line of metadata;
        # this line was just read in final iteration of above loop
        header_row = handle.readline().split('\t')
        data_cols = [header_row.index(name) for name in data_fields]
        current_vs_time = np.genfromtxt(fname=handle, usecols=data_cols)
        handle.close()

        # For quick lookup so we don't have to convert 'Ns' from float to int on every iteration
        potentials_dict = { float(index): potential for index, potential in enumerate(potentials_by_trial) }
        current_to_resistance = lambda row: [row[1], potentials_dict[row[0]] / row[2]]
        resistance_vs_time = np.array([current_to_resistance(row) for row in current_vs_time])
        # We don't need the trial # field (Ns) anymore, so delete it to free a couple kB
        current_vs_time = np.delete(current_vs_time, obj=0, axis=1)

        technique_start = acquisition_start + timedelta(seconds=current_vs_time[0, 0])
        end_time_by_trial = [total_dur + technique_start for total_dur in total_dur_by_trial]

        return {
            'acquisition_start': acquisition_start,
            'current_vs_time': current_vs_time,
            'resistance_vs_time': resistance_vs_time,
            'end_time_by_trial': end_time_by_trial,
            'potentials_by_trial': potentials_by_trial
        }
channels = ['FID', 'TCD']
class Pagination(QVBoxLayout):
    page_changed = Signal(int, int)

    def __init__(self, pages, start_index=0, handle_page_change=lambda old, new: None):
        super().__init__()

        self.pages = pages
        self._curr_index = start_index

        # Signal when page is changed so client can update accordingly
        self.page_changed.connect(handle_page_change)

        # Container for all items responsible for actual navigation: arrows, text entry box, "Go" button
        self.controls_container = QHBoxLayout()
        self.prev_button = GraphPushButton(text='←', font_size=32, fixed_width=80)
        self.next_button = GraphPushButton(text='→', font_size=32, fixed_width=80)
        self.prev_button.clicked.connect(self.handle_prev_click)
        self.next_button.clicked.connect(self.handle_next_click)
        self.update_button_states()

        # Container for text entry box and "Go button" only
        self.jump_container = QVBoxLayout()
        IntAction(
            layout=self.jump_container, text='Go', min_value=min(pages), max_value=max(pages),
            on_click=self.handle_jump_click)

        # Initialize overall layout
        self.controls_container.addWidget(self.prev_button, alignment=Qt.AlignTop|Qt.AlignRight)
        self.controls_container.addLayout(self.jump_container, alignment=Qt.AlignTop|Qt.AlignHCenter)
        self.controls_container.addWidget(self.next_button, alignment=Qt.AlignTop|Qt.AlignLeft)
        self.controls_container.setStretchFactor(self.prev_button, 1)
        self.controls_container.setStretchFactor(self.next_button, 1)

        self.indicator = PageIndicator(pages, start_index)
        self.addLayout(self.indicator, alignment=Qt.AlignHCenter)
        self.addLayout(self.controls_container, alignment=Qt.AlignHCenter)

    @property
    def curr_index(self):
        return self._curr_index

    @curr_index.setter
    def curr_index(self, new_value):
        old_value = self._curr_index
        self._curr_index = new_value
        self.page_changed.emit(self.pages[old_value], self.pages[new_value])
        self.update_button_states()
        self.indicator.set_index(new_value)

    def update_button_states(self):
        self.prev_button.setEnabled(True)
        self.next_button.setEnabled(True)
        if self.curr_index == 0:
            self.prev_button.setDisabled(True)
        if self.curr_index == len(self.pages) - 1:
            self.next_button.setDisabled(True)

    @Slot()
    def handle_prev_click(self):
        if self.curr_index > 0:
            self.curr_index -= 1
            
    @Slot()
    def handle_next_click(self):
        if self.curr_index < len(self.pages) - 1:
            self.curr_index += 1
            
    @Slot()
    def handle_jump_click(self, text):
        try:
            new_page = int(text)
            new_index = self.pages.index(new_page)
        except ValueError:
            return False
        
        if new_index != self.curr_index:
            self.curr_index = new_index
        return True
class PageIndicator(QHBoxLayout):
    def __init__(self, pages, start_index):
        super().__init__()

        self.pages = pages
        self.labels = []
        self.addStretch(1)
        for _ in range(5):
            label = QLabel('')
            label.setFixedWidth(25)
            label.setAlignment(Qt.AlignCenter)
            self.labels.append(label)
            self.addWidget(label, alignment=Qt.AlignCenter)
        self.addStretch(1)
        self.set_index(start_index)

        font = self.labels[0].font()

        font.setPointSize(12)
        font.setWeight(QFont.ExtraLight)
        self.labels[0].setFont(font)
        self.labels[4].setFont(font)

        font.setPointSize(14)
        font.setWeight(QFont.Normal)
        self.labels[1].setFont(font)
        self.labels[3].setFont(font)

        font.setPointSize(18)
        font.setWeight(QFont.DemiBold)
        self.labels[2].setFont(font)
    
    def set_index(self, index, should_resize=False):
        text_vals = [str(self.pages[index]) if 0 <= index < len(self.pages) else '' for index in range(index - 2, index + 3)]
        for index, val in enumerate(text_vals):
            self.labels[index].setText(val)
class GraphPushButton(QPushButton):
    def __init__(self, text, font_size=None, fixed_width=None, fixed_height=None):
        super().__init__(text=text)
        if fixed_width:
            self.setFixedWidth(fixed_width)
        if fixed_height:
            self.setFixedHeight(fixed_height)
        if font_size:
            font = self.font()
            font.setPointSize(font_size)
            self.setFont(font)
class IntAction:
    # Assumes `layout` is QHBoxLayout
    def __init__(self, layout, text, min_value, max_value, on_click, insertion_index=None):
        self.on_click = on_click
        trigger_button = GraphPushButton(text=text)
        trigger_button.clicked.connect(lambda: self.handle_click())

        self.input_field = QLineEdit()
        self.input_field.setAlignment(Qt.AlignHCenter)
        self.input_field.setFixedWidth(80)
        self.input_field.setMaxLength(5)
        input_field_font = self.input_field.font()
        input_field_font.setPointSize(16)
        self.input_field.setFont(input_field_font)
        self.input_field.setValidator(QIntValidator(min_value, max_value))
        
        if insertion_index is not None:
            layout.insertWidget(insertion_index, self.input_field, alignment=Qt.AlignHCenter)
            layout.insertWidget(insertion_index + 1, trigger_button, alignment=Qt.AlignHCenter)
        else:
            layout.addWidget(self.input_field, alignment=Qt.AlignHCenter)
            layout.addWidget(trigger_button, alignment=Qt.AlignHCenter)

    @Slot()
    def handle_click(self):
        did_succeed = self.on_click(self.input_field.text())
        if did_succeed:
            self.input_field.setText('')
def get_settings():
    return json.load(open(os.path.join(sys.path[0], 'chromelectric_settings.txt'), 'r'))
def get_integration_params():
        experiment_params = get_settings()
        gases_by_channel = {}
        for gas_name, attributes in experiment_params['attributes_by_gas_name'].items():
            channel = attributes['channel']
            if gases_by_channel.get(channel) is None:
                gases_by_channel[channel] = []
            gases_by_channel[channel].append(gas_name)
        return (experiment_params, gases_by_channel)
def bootstrap():
    routes = {
        'FID': '/Users/adamshugar/Desktop/Temp Data/20201125 - Ag - 10 sccm CO2 - 0p0005 mg cm2 - 1-TBPS Trial 2/20201125 - Ag - 10 sccm CO2 - 0p0005 mg cm2 - 1TBPS Trial 2 fid01.asc',
        'TCD': '/Users/adamshugar/Desktop/Temp Data/20201125 - Ag - 10 sccm CO2 - 0p0005 mg cm2 - 1-TBPS Trial 2/20201125 - Ag - 10 sccm CO2 - 0p0005 mg cm2 - 1TBPS Trial 2 tcd01.asc'
    }
    
    file_lists = {ch: GC.find_list(route) for ch, route in routes.items()}
    parsed_file_input = {ch: {'data': GC.parse_list(file_list), 'path': routes[ch]} for ch, file_list in file_lists.items()}
    CA_route = '/Users/adamshugar/Desktop/Temp Data/20201125 - Ag - 10 sccm CO2 - 0p0005 mg cm2 - 1-TBPS Trial 2/20201125 - Ag - 10 sccm CO2 - 0p0005 mg cm2 - 1TBPS Trial 2 - CA_03_CA_C12.mpt'
    parsed_file_input['CA'] = {
        'data': CA.parse_file(CA_route),
        'path': CA_route,
    }
    experiment_params, gases_by_channel = get_integration_params()

    all_inputs = {
        'experiment_params': experiment_params,
        'gases_by_channel': gases_by_channel,
        'parsed_file_input': parsed_file_input
    }
    launch_window(all_inputs, 'Integration and Analysis', '{} Injection #{}', 'Time (sec)', 'Potential (mV)')
def platform_messagebox(text, buttons, icon, default_button=None, informative='', detailed='', parent=None):
    """Platform-independent dialog box for quick messages and button-based user input"""
    messagebox = QMessageBox(icon, '', '', buttons, parent)
    messagebox.setIcon(icon)
    messagebox.setDefaultButton(default_button)
    if is_windows():
        messagebox.setWindowTitle(QCoreApplication.applicationName())
        messagebox.setText(text + informative)
    else:
        messagebox.setText(text)
        if informative:
            messagebox.setInformativeText(informative)
    if detailed:
        messagebox.setDetailedText(detailed)
    return messagebox
# BEGIN INTEGRATE MODULE

class QHLine(QFrame):
    def __init__(self):
        super().__init__()
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)

def launch_window(all_inputs, window_title, ch_index_title, xlabel, ylabel):
    qapp = QApplication([''])
    app = IntegrateWindow(all_inputs, window_title, ch_index_title, xlabel, ylabel)
    app.show()
    qapp.exec_()

class ComboBox(QComboBox):
    """Wrapper for Qt "combo box" with convenience method to remove all choices."""
    def removeAll(self):
        for _ in range(self.count()):
            self.removeItem(0)

class Label(QLabel):
    def __init__(self, text, font_size=None):
        super().__init__(text)
        if font_size:
            font = self.font()
            font.setPointSize(font_size)
            self.setFont(font)

    def setText(self, text):
        super().setText(text)
        self.adjustSize()

    def resizeEvent(self, event):
        new_height = self.heightForWidth(self.width())
        if new_height > 0:
            self.setMinimumHeight(new_height)
        
class IntegralInfoContainer(QGridLayout):
    def __init__(self):
        super().__init__()
        self.setHorizontalSpacing(gui.PADDING // 2)
        self.setVerticalSpacing(gui.PADDING // 2)
        self.setColumnStretch(2, 1)

class IntegralInfo:
    def __init__(self, container, row_index, integral=None, on_apply_all=None, on_delete=None, display_index=None):
        super().__init__()
        self.layout = container
        self.row_index = row_index

        controls_container = QVBoxLayout()
        self.peak_label = Label('')
        controls_container.addWidget(self.peak_label, alignment=Qt.AlignHCenter)
        self.apply_all_button = QPushButton('Spread')
        self.apply_all_button.clicked.connect(self.handle_apply_all)
        controls_container.addWidget(self.apply_all_button, alignment=Qt.AlignHCenter)
        self.delete_button = QPushButton('Delete')
        self.delete_button.clicked.connect(self.handle_delete)
        controls_container.addWidget(self.delete_button, alignment=Qt.AlignHCenter)
        controls_container.addStretch(1)
        
        fields = ['Gas', 'Area', 'Moles', 'Farad. eff.']
        rows_per_item = len(fields) + 3 # Include divider bar and two spacer items
        base_row = 0 if row_index == 0 else row_index * rows_per_item - 1 # No divider bar before first element (subtract 1)
        
        if row_index > 0:
            self.line = QHLine()
            self.layout.addWidget(self.line, base_row, 0, 1, 3)
            offset = 2
        else:
            self.line = None
            offset = 1
        self.spacer_size = (1, gui.PADDING // 2)
        self.spacers = [QSpacerItem(*self.spacer_size) for _ in range(2)]
        self.layout.addItem(self.spacers[0], base_row + 1, 0)

        self.layout.addLayout(controls_container, base_row + offset, 0, len(fields), 1)
        self.key_labels = {}
        self.value_labels = {}
        for field_index, field in enumerate(fields):
            self.key_labels[field] = Label(f'{field}: ')
            self.layout.addWidget(self.key_labels[field], base_row + field_index + offset, 1, alignment=Qt.AlignRight)
            self.value_labels[field] = Label('')
            self.layout.addWidget(self.value_labels[field], base_row + field_index + offset, 2, alignment=Qt.AlignRight)

        self.layout.addItem(self.spacers[1], base_row + len(fields) + offset, 0)
        
        if integral:
            self.set_integral(integral)
        if on_apply_all:
            self.set_apply_all(on_apply_all)
        if on_delete:
            self.set_delete(on_delete)
        if display_index:
            self.set_index(display_index)

    def handle_delete(self):
        if self.on_delete:
            self.on_delete(self.row_index)

    def handle_apply_all(self):
        if self.on_apply_all:
            self.on_apply_all(self.row_index)

    def show(self):
        if self.line:
            self.line.show()
        for spacer in self.spacers:
            spacer.changeSize(*self.spacer_size)
        self.peak_label.show()
        self.apply_all_button.show()
        self.delete_button.show()
        for _, label in self.key_labels.items():
            label.show()
        for _, label in self.value_labels.items():
            label.show()

    def hide(self):
        if self.line:
            self.line.hide()
        for spacer in self.spacers:
            spacer.changeSize(0, 0)
        self.peak_label.hide()
        self.apply_all_button.hide()
        self.delete_button.hide()
        for _, label in self.key_labels.items():
            label.hide()
        for _, label in self.value_labels.items():
            label.hide()

    def set_integral(self, integral):
        self.value_labels['Gas'].setText(integral['gas'])
        self.value_labels['Area'].setText("{:.3E}".format(integral['area']))
        self.value_labels['Moles'].setText("{:.3E}".format(integral['moles']))
        self.value_labels['Farad. eff.'].setText(
            "{:.2f}%".format(integral['faradaic_efficiency']) if not math.isnan(integral['faradaic_efficiency']) else 'N/A')

    def set_apply_all(self, on_apply_all):
        self.on_apply_all = on_apply_all

    def set_delete(self, on_delete):
        self.on_delete = on_delete

    def set_display_index(self, display_index):
        self.peak_label.setText(f'Peak #{display_index}')

class DynamicScrollArea(QScrollArea):
    def adjustWidth(self):
        self.widget().adjustSize()
        self.setFixedWidth(self.widget().width())

# Function handles to numerically integrate
# TODO: Add Gaussian and Lorentzian
INTEGRATION_BY_MODE = {
    'Trapezoidal': integrate.trapz,
}

class IntegrateControls(QGridLayout):
    # Ordered list of instructions shown to user before picking each next point
    INSTRUCTIONS_BY_MODE = {
        'Trapezoidal': [
            'Select the start of the peak (leftmost point).',
            'Select the end of the peak (rightmost point).'
        ],
        'Gaussian': [
            'Select the start of the peak (leftmost point).',
            'Select the extremum of the peak (highest or lowest point).',
            'Select the end of the peak (rightmost point).'
        ],
        'Lorentzian': [
            'Select the start of the peak (leftmost point).',
            'Select the extremum of the peak (highest or lowest point).',
            'Select the end of the peak (rightmost point).'
        ],
    }

    # Function handles to draw a graphical representation of the successful numerical integration
    # TODO: Add Gaussian and Lorentzian
    RENDER_BY_MODE = {
        'Trapezoidal': integrate.trapz_draw,
    }

    def __init__(self, canvas, experiment_params, gases_by_channel, on_apply_all):
        super().__init__()
        self.experiment_params = experiment_params
        self.gases_by_channel = gases_by_channel
        self.on_apply_all = on_apply_all
        self.setSizeConstraint(QLayout.SetMaximumSize)
        self.canvas = canvas
        self.disconnect_id = self.canvas.mpl_connect('pick_event', self.handle_pick)

        # Channel and gas selection
        self.channel_selector = ComboBox()
        self.channel_selector.currentTextChanged.connect(self.update_gases)
        self.gas_selector = ComboBox()
        self.addWidget(Label('Channel'), 0, 0, alignment=Qt.AlignHCenter)
        self.addWidget(self.channel_selector, 1, 0, alignment=Qt.AlignHCenter)
        self.addWidget(Label('Gas'), 0, 1, alignment=Qt.AlignHCenter)
        self.addWidget(self.gas_selector, 1, 1, alignment=Qt.AlignHCenter)
        self.prev_gas = self.prev_channel = None

        # Peak parameter selection
        self.peak_type = QComboBox()
        self.peak_type.addItems(INTEGRATION_BY_MODE.keys())
        self.addWidget(Label('Peak Type'), 0, 2, alignment=Qt.AlignHCenter)
        self.addWidget(self.peak_type, 1, 2, alignment=Qt.AlignHCenter)

        # Integration start/stop and information
        self.integrate_button = GraphPushButton(text='Start Integration')
        self.integrate_button.clicked.connect(self.handle_click_integrate)
        self.integrate_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.integrate_label = Label('')
        self.integrate_instruction = Label('')
        self.integrate_label.hide()
        self.integrate_instruction.hide()
        self.integrate_label.setWordWrap(True)
        self.integrate_instruction.setWordWrap(True)
        self.integrate_label.setAlignment(Qt.AlignHCenter)
        self.integrate_instruction.setAlignment(Qt.AlignHCenter)
        self.addWidget(self.integrate_button, 2, 0, 1, 3, alignment=Qt.AlignHCenter)
        self.addWidget(self.integrate_label, 3, 0, 1, 3, alignment=Qt.AlignHCenter)
        self.addWidget(self.integrate_instruction, 4, 0, 1, 3, alignment=Qt.AlignHCenter)

        self.addItem(QSpacerItem(1, gui.PADDING), 5, 0, 1, 3)
        # List of peak information cards for current injection (plus overall Faradaic efficiency)
        self.fe_label = Label('Total Faradaic efficiency: 0%')
        self.fe_label.setAlignment(Qt.AlignHCenter)
        self.fe_label.setWordWrap(True)
        self.fe_label.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        self.addWidget(self.fe_label, 6, 0, 1, 3, alignment=Qt.AlignHCenter)
        peak_list_scroll = DynamicScrollArea()
        peak_list_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        peak_list_scroll.setWidgetResizable(True)
        peak_list_frame = QFrame(peak_list_scroll)
        peak_list_container = QVBoxLayout()
        peak_list_container.setContentsMargins(gui.PADDING // 3, gui.PADDING, gui.PADDING, gui.PADDING)
        self.peak_list_grid = IntegralInfoContainer()
        peak_list_container.addLayout(self.peak_list_grid)
        peak_list_container.addStretch(1)
        peak_list_frame.setLayout(peak_list_container)
        peak_list_frame.layout().setSizeConstraint(QLayout.SetFixedSize)
        peak_list_scroll.setWidget(peak_list_frame)
        self.peak_list_frame = peak_list_frame
        peak_list_scroll.setAlignment(Qt.AlignHCenter)
        peak_list_scroll.hide()
        self.addWidget(peak_list_scroll, 7, 0, 1, 3, alignment=Qt.AlignHCenter)
        self.peak_list_scroll = peak_list_scroll
        self.peak_list_items = []
        self.setRowStretch(7, 1)

        # Integration state variables container
        self.curr_integral = { 'is_active': False }
        # Holds reference to artist for each Line2D object per channel
        self.lines_by_channel = {}
        # List of all integral-related artists
        self.integral_artists = []
        # Lists of successfully completed peak integrations
        self.integrals = []
        
    def update_gases(self, new_channel):
        """Update the available gas list when the user changes the current channel."""
        if not new_channel:
            return
        self.gas_selector.removeAll()
        gas_list = self.gases_by_channel[new_channel]
        self.gas_selector.addItems(gas_list)
        # Try to preserve what the user has already selected if possible
        if self.prev_gas in gas_list:
            self.gas_selector.setCurrentText(self.prev_gas)

    def set_injection_params(self, mol_e, avg_current):
        """
        Called when the page/injection is changed: updates the relevant parameters
        that are unique to each injection, namely the number of moles of electrons
        added to the sample via electroreduction in the cell (`mol_e`) and the average
        current during the period preceding the injection.

        If either of these values is `nan`, then a CA file to align to the injection
        could not be found; update the UI to reflect this to the user.
        """
        self.mol_e = mol_e
        self.avg_current = avg_current
        if math.isnan(self.mol_e) or math.isnan(self.avg_current):
            self.fe_label.setText('Warning: This injection could not be\naligned to the supplied CA file.')

    def set_active_channels(self, active_channels, lines_by_channel):
        """
        Update the list of currently displayed channels and the artist for each Line2D object.
        Called by client of this class when switching injection numbers.
        
        For example, if the FID channel was available but is missing when switching to
        injection #5, it might be removed from the list of active channels.
        """
        self.lines_by_channel = lines_by_channel

        # Keep track of most recent user selections
        self.prev_gas = self.gas_selector.currentText()
        self.prev_channel = self.channel_selector.currentText()

        self.channel_selector.removeAll()
        self.channel_selector.addItems(active_channels)
        # Try to preserve what the user has already selected if possible
        if self.prev_channel in active_channels:
            self.channel_selector.setCurrentText(self.prev_channel)

    def do_integral(self, line_xy, axes):
        """
        Numerically compute an integral of the current type on the supplied line, store the
        resulting information and draw a graphical representation of the successul integral.

        Called when user has requested to perform an integration and has picked all required points.
        """
        mode, gas = self.curr_integral['mode'], self.curr_integral['gas']
        x_data, y_data = line_xy[:, 0], line_xy[:, 1]
        integral_result = INTEGRATION_BY_MODE[mode](
            x_data=x_data, y_data=y_data, points=self.curr_integral['points'])

        render_func = IntegrateControls.RENDER_BY_MODE[mode]
        curr_artists = []
        curr_artists.extend(self.curr_integral['point_artists'])
        curr_artists.extend(integrate.draw_integral(
            x_data, y_data, integral_result, axes, len(self.integrals) + 1, render_func))
        
        self.integral_artists.append(curr_artists)

        gas_attrs = self.experiment_params['attributes_by_gas_name'][gas]
        calib_val, reduction_count = [gas_attrs.get(attr) for attr in ['calibration_value', 'reduction_count']]
        final_integral = integrate.interpret_integral(
            integral=integral_result, total_gas_mol=self.experiment_params['mol_gas'],
            mol_e=self.mol_e, calib_val=calib_val, reduction_count=reduction_count,
            avg_current=self.avg_current)
        self.integrals.append({
            **final_integral,
            'mode': mode,
            'gas': gas
        })
        self.update_integral_list()

    def handle_pick(self, event):
        """Handler for any attempted user selection of a point on any currently rendered Line2D object."""
        # First, validate the pick
        target_artist = self.lines_by_channel.get(self.curr_integral.get('channel'))
        if not self.curr_integral['is_active'] or event.artist is not target_artist:
            return
        
        # If pick is valid, get coordinates, add to pick list, and draw selected point to screen
        coords = integrate.line2d_point(event)
        if coords not in self.curr_integral['points']:
            self.curr_integral['points'].append(coords)
            pt = integrate.draw_point(coords, target_artist.axes)
            self.curr_integral['point_artists'].append(pt)
            self.canvas.draw()

        # If user has picked all the points needed, then process them and integrate.
        # Otherwise, show instructions to pick next point.
        picked_count = len(self.curr_integral['points'])
        # 1 user-facing instruction per point needed
        points_needed = len(IntegrateControls.INSTRUCTIONS_BY_MODE[self.curr_integral['mode']])
        if picked_count >= points_needed:
            self.do_integral(line_xy=event.artist.get_xydata(), axes=event.artist.axes)
            self.stop_integration(did_succeed=True)
        else:
            self.integrate_instruction.setText(self.curr_integral['instructions'][picked_count])
    
    def handle_click_integrate(self):
        if self.curr_integral['is_active']:
            self.stop_integration(did_succeed=False)
        else:
            self.start_integration()

    def start_integration(self):
        self.curr_integral['is_active'] = True
        self.curr_integral['mode'] = self.peak_type.currentText()
        self.curr_integral['gas'] = self.gas_selector.currentText()
        self.curr_integral['channel'] = self.channel_selector.currentText()
        self.curr_integral['points'] = []
        self.curr_integral['point_artists'] = []
        self.curr_integral['instructions'] = IntegrateControls.INSTRUCTIONS_BY_MODE[self.curr_integral['mode']]

        self.integrate_button.setText('Cancel Integration')
        self.integrate_label.setText(
            f"{self.curr_integral['mode']} integration of {self.curr_integral['gas']} peak in progress.")
        self.integrate_instruction.setText(self.curr_integral['instructions'][0])
        self.integrate_label.show()
        self.integrate_instruction.show()

    def stop_integration(self, did_succeed):
        self.integrate_button.setText('Start Integration')
        self.integrate_label.hide()
        self.integrate_instruction.hide()
        self.curr_integral['is_active'] = False

        if not did_succeed:
            for point in self.curr_integral['point_artists']:
                point.remove()
        self.canvas.draw()

    def get_integrals_and_clear(self):
        """
        Called when user changes pages. All artists are removed and a list of all integrals from the current
        page is returned, which can be stored by the client and loaded when the user revisits this page later.
        """
        for artist_list in self.integral_artists:
            for artist in artist_list:
                artist.remove()
        self.integral_artists = []

        result = self.integrals
        self.integrals = []
        self.update_integral_list()
        return result

    def set_integrals(self, integrals):
        """
        Called when user navigates to a page that has existing integrals. Loads the integrals passed as an argument
        and draws those integrals to the screen.
        """
        gas_list = self.experiment_params['attributes_by_gas_name']
        self.integrals = integrals
        for index, integral in enumerate(self.integrals):
            channel = gas_list[integral['gas']]['channel']
            line = self.lines_by_channel[channel]
            xy_data = line.get_xydata()
            x_data, y_data = xy_data[:, 0], xy_data[:, 1]
            render_func = IntegrateControls.RENDER_BY_MODE[integral['mode']]
            artists = integrate.draw_integral(x_data, y_data, integral, line.axes, index + 1, render_func, draw_points=True)
            self.integral_artists.append(artists)
        self.update_integral_list()

    def update_integral_list(self):
        n_labels, n_integrals = len(self.peak_list_items), len(self.integrals)
        size_diff = n_integrals - n_labels
        if size_diff > 0:
            for additional_index in range(size_diff):
                self.peak_list_items.append(IntegralInfo(
                    self.peak_list_grid, row_index=n_labels + additional_index,
                    on_apply_all=self.apply_to_all, on_delete=self.delete_integral))
        elif size_diff < 0:
            for hide_index in range(n_integrals, n_labels):
                self.peak_list_items[hide_index].hide()
        
        if not math.isnan(self.mol_e):
            total_fe = sum([peak['faradaic_efficiency'] for peak in self.integrals])
            self.fe_label.setText('Total Faradaic efficiency: {:.2f}%'.format(total_fe))

        for index, integral in enumerate(self.integrals):
            display_index = index + 1

            peak_entry = self.peak_list_items[index]
            peak_entry.set_integral(integral)
            peak_entry.set_display_index(display_index)
            peak_entry.show()
            # Update index readings of peak annotations for each integral, as indices may have changed
            # Annotation artist is always last in list
            self.integral_artists[index][-1].set_text(display_index)
        self.canvas.draw()

        self.peak_list_scroll.adjustWidth()
        if n_integrals == 0:
            self.peak_list_scroll.hide()
        else:
            self.peak_list_scroll.show()

    def delete_integral(self, index):
        for artist in self.integral_artists[index]:
            artist.remove()
        self.integral_artists.pop(index)
        self.canvas.draw()
        self.integrals.pop(index)
        self.update_integral_list()

    def apply_to_all(self, index):
        self.on_apply_all(self.integrals[index], display_index=index + 1)
        
class IntegrateWindow(QMainWindow):
    # In seconds; TODO: replace with calculation involving gas mixing in pre-GC vessel
    CURRENT_AVG_DURATION = 120
    # In seconds; allow injections that occur this many seconds later than a CA
    # constant-voltage trial to still be aligned to that trial
    MISALIGNMENT_TOLERANCE = 10

    def __init__(self, all_inputs, window_title, ch_index_title, xlabel, ylabel):
        super().__init__()
        self.all_inputs = all_inputs
        """
        Convert from injection list separated by channel to combined list keyed primarily by index;
        done for easy pagination and conversion to final CSV output
        E.g.:
            { 'FID': { '1': graph_1_f, '2': graph_2_f, '3': graph_3_f },
            { 'TCD': { '2': graph_2_t, '4': graph_4_t } }
                                    becomes
            { '1': { 'FID': graph_1_f }, '2': { 'TCD': graph_2_t, 'FID': graph_2_f },
              '3': { 'FID': graph_3_f }, '4': { 'TCD': graph_4_t } }
        """
        parsed_files = all_inputs['parsed_file_input']
        all_indices = reduce(lambda accum, next: accum | next.keys(), [parsed_files[channel]['data'] for channel in channels], set())
        self.combined_graphs = {index: {channel: parsed_files[channel]['data'].get(index) for channel in channels} for index in all_indices}

        CA_data = parsed_files['CA']['data']
        experiment_params = all_inputs['experiment_params']
        # Number of seconds of flow that are collected by the GC during an injection
        # NOTE: `sample_vol` in mL, `flow_rate` in standard cubic centimeters per minute (sccm)
        experiment_params['flow_seconds'] = experiment_params['sample_vol'] / experiment_params['flow_rate'] * 60
        # Compute number of total gas moles per injection, which is constant between injections and depends only on
        # sample loop volume
        experiment_params['mol_gas'] = physcalc.ideal_gas_moles(V=experiment_params['sample_vol'] / 1000)
        # Compute values that vary for each injection, namely: voltage, average current (i.e.
        # averaged over the relevant timescale immediately preceding the injection) and moles
        # of electrons (this average current times the "flow-seconds" of gas collected)
        for page, combined_graph in self.combined_graphs.items():
            # Assume that all channels for the current injection have the same timestamp
            any_channel = [ch for ch in combined_graph.values() if ch is not None][0]
            # In milliamperes
            combined_graph['avg_current'] = physcalc.average_current(
                cyclic_amp=CA_data, end_time=any_channel['start_time'], duration=IntegrateWindow.CURRENT_AVG_DURATION)
            combined_graph['mol_e'] = physcalc.electrons_from_amps(
                A=combined_graph['avg_current'] / 1000, t=experiment_params['flow_seconds'])

            # Find uncorrected voltage of CA trial which the current injection was measuring
            tolerance = timedelta(seconds=IntegrateWindow.MISALIGNMENT_TOLERANCE)
            # Start and end CA trial timestamps such that, if an injection has a timestamp
            # in this range, it will be aligned to that trial.
            end_times = CA_data['end_time_by_trial']
            trial_end_ranges = [
                ((end_times[index - 1] + tolerance).timestamp(), (end_times[index] + tolerance).timestamp()) \
                for index in range(1, len(end_times))
            ]
            injection_timestamp = any_channel['start_time'].timestamp()
            matching_trials = [
                index for index, trial_range in enumerate(trial_end_ranges) \
                if trial_range[0] <= injection_timestamp <= trial_range[1]
            ]
            if matching_trials:
                combined_graph['uncorrected_voltage'] = CA_data['potentials_by_trial'][matching_trials[0]]
                combined_graph['corrected_voltage'] = physcalc.correct_voltage(
                    V=combined_graph['uncorrected_voltage'], I=combined_graph['avg_current'] / 1000,
                    Ru=experiment_params['solution_resistance'], pH=experiment_params['pH'],
                    deviation=experiment_params['ref_potential'])
            else:
                combined_graph['uncorrected_voltage'] = combined_graph['corrected_voltage'] = math.nan
            
        self.main = QWidget()
        self.setCentralWidget(self.main)
        self.layout = QGridLayout(self.main)
        self.setWindowTitle(window_title)
        self.ch_index_title = ch_index_title
        self.xlabel = xlabel
        self.ylabel = ylabel

        self.canvas = FigureCanvas(Figure())
        self.layout.addWidget(self.canvas, 0, 0)
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.addToolBar(self.toolbar)

        self.controls = IntegrateControls(
            self.canvas, all_inputs['experiment_params'], all_inputs['gases_by_channel'],
            on_apply_all=self.apply_to_all)
        self.layout.addLayout(self.controls, 0, 1)

        self.pages = sorted([int(page) for page in self.combined_graphs])
        # Dict of lists: keyed by page/injection #, value = list of integrals for current page
        self.integrals_by_page = {page: [] for page in self.pages}
        pagination = Pagination(self.pages, handle_page_change=self.handle_page_change)
        self.layout.addLayout(pagination, 1, 0)

        done_button = QPushButton('Write Output')
        done_button.clicked.connect(self.handle_done)
        self.layout.addWidget(done_button, 1, 1, alignment=Qt.AlignCenter)

        self.axes = []
        self.graph_page(page=self.pages[0])

        # Canvas should take up all extra space, but should also have suitable min dimensions
        overall_active_channel_count = len(['' for channel in channels if parsed_files[channel]])
        min_graph_height_per_channel_px = 240
        min_graph_width_px = 480
        self.layout.setRowMinimumHeight(0, overall_active_channel_count * min_graph_height_per_channel_px)
        self.layout.setColumnMinimumWidth(0, min_graph_width_px)
        self.layout.setRowStretch(0, 1)
        self.layout.setColumnStretch(0, 1)

    def handle_page_change(self, old_page, new_page):
        self.ungraph_page(old_page)
        self.graph_page(new_page)

    def ungraph_page(self, page):
        """
        After finishing with current page and before graphing next page, do necessary cleanup
        and saving of integration-related information.
        """
        self.integrals_by_page[page] = self.controls.get_integrals_and_clear()
        
        for ax in self.axes:
            ax.remove()

    def graph_page(self, page):
        self.curr_page = page
        curr_graph = self.combined_graphs[page]
        active_channels = [ch for ch in channels if curr_graph[ch]]
        self.axes = [self.canvas.figure.add_subplot(len(active_channels), 1, i) for i in range(1, len(active_channels) + 1)]

        lines_by_channel = {}
        for index, ax in enumerate(self.axes):
            curr_channel = active_channels[index]
            ax.set_title(self.ch_index_title.format(curr_channel, page))
            ax.set_xlabel(self.xlabel)
            ax.set_ylabel(self.ylabel)
            lines = ax.plot(
                curr_graph[curr_channel]['x'], curr_graph[curr_channel]['y'],
                color='#000000', marker='.', markersize=4, pickradius=4, picker=True)
            lines_by_channel[curr_channel] = lines[0]
        
        self.controls.set_injection_params(curr_graph['mol_e'], curr_graph['avg_current'])
        self.controls.set_active_channels(active_channels, lines_by_channel)
        self.controls.set_integrals(self.integrals_by_page[page])
        
        self.toolbar.update()
        self.canvas.figure.tight_layout()

        # Disable autoscaling after initial draw so we can draw integration related objects
        # without worrying about disorienting rescaling
        for ax in self.axes:
            ax.autoscale(True)
        self.canvas.draw()
        for ax in self.axes:
            ax.autoscale(False)

    def apply_to_all(self, integral, display_index):
        experiment_params = self.all_inputs['experiment_params']
        gas_attrs = experiment_params['attributes_by_gas_name'][integral['gas']]
        channel = gas_attrs['channel']
        # Get all pages containing the current channel
        target_pages = [page for page in self.pages if self.combined_graphs[page][channel]]
        target_pages.remove(self.curr_page)
        m = platform_messagebox(
            text=f'This operation will integrate all {len(target_pages)} other {channel} graphs using Peak #{display_index}\'s parameters.',
            buttons=QMessageBox.Ok | QMessageBox.Cancel, icon=QMessageBox.Question, default_button=QMessageBox.Ok,
            informative='Are you sure you want to continue?', parent=self)
        result = m.exec()
        if result != QMessageBox.Ok:
            return
        
        
        for page in target_pages:
            curr_graph = self.combined_graphs[page]

            x, y = [curr_graph[channel][axis] for axis in ['x', 'y']]
            # Recalculate point positions
            new_points = []
            for point in integral['points']:
                if point[0] < x[0] or point[0] > x[-1]:
                    return # Ignore graphs that don't extend as far as this peak
                new_index = np.searchsorted(x, point[0])
                new_x, new_y = x[new_index], y[new_index]
                new_points.append((new_x, new_y))

            curr_integral = INTEGRATION_BY_MODE[integral['mode']](x, y, new_points)
            
            final_integral = integrate.interpret_integral(
                integral=curr_integral, total_gas_mol=experiment_params['mol_gas'],
                mol_e=curr_graph['mol_e'], calib_val=gas_attrs['calibration_value'],
                reduction_count=gas_attrs['reduction_count'], avg_current=curr_graph['avg_current'])

            self.integrals_by_page[page].append({
                **final_integral,
                'mode': integral['mode'],
                'gas': integral['gas'],
            })

    def handle_done(self):
        # Confirm that all gases have at least one peak for every injection;
        # if not, notify the user with overridable dialog
        gas_list = self.all_inputs['experiment_params']['attributes_by_gas_name'].keys()
        missing_gases_by_page = {}
        for page in self.pages:
            curr_page_gases = set()
            for integral in self.integrals_by_page[page]:
                curr_page_gases.add(integral['gas'])
            missing_gases_by_page[page] = list(gas_list - curr_page_gases)
        
        missing_gases = set().union(*missing_gases_by_page.values())
        if missing_gases:
            missing_str_list = [f"{page}: {', '.join(gas_list)}" for page, gas_list in missing_gases_by_page.items() if gas_list]
            missing_str = '\n'.join(missing_str_list)
            m = platform_messagebox(
                text='Some injections do not have peaks for all gases.',
                buttons=QMessageBox.Ok | QMessageBox.Cancel, icon=QMessageBox.Warning, default_button=QMessageBox.Ok,
                informative='Are you sure you want to continue?', parent=self,
                detailed=f'The following gases on the following pages do not have peaks:\n{missing_str}')
            result = m.exec()
            if result != QMessageBox.Ok:
                return

        file_input = self.all_inputs['parsed_file_input']
        filepaths = {filetype: file_input[filetype]['path'] for filetype in file_input}
        output_analysis(filepaths, self.all_inputs['experiment_params'], self.combined_graphs, self.integrals_by_page)

settings_header = """
These are the settings used by Chromelectric while analyzing your experiment.

You may use this file as a settings file for future runs of Chromelectric
by copying and pasting it into the same directory as the Chromelectric program,
naming the file `chromelectric_settings.txt`, and deleting this comment
(i.e., the dashed line and all text above it).

Note the following units used for each entry:

calibration_value       mV*sec/ppm      peak area per ppm
flow_rate               cm^3/min        sccm
sample_vol              mL
mix_vol                 mL
solution_resistance     ohms
ref_potential           V
-------------------------------------------------------------------------------

"""

integration_header = """
This file contains raw data about each integrated peak. It is mostly
intended for reference or sanity checking since Chromelectric automatically
processes this data into more relevant final output (e.g. Faradaic efficiency).
Most experimenters will rarely if ever need this file.

See below for discussion on polynomial domain and window:
https://stackoverflow.com/questions/52339907/numpy-polynomial-generation
https://numpy.org/doc/stable/reference/generated/numpy.polynomial.polynomial.Polynomial.html
Note that directly mapping the polynomial to the true domain before
recovering a numerical approximation will likely result in numerical instability.

Units:
- area = mV * sec
- peak_start / peak_end = (sec, mV)
--------------------------------------------------------------------------------------------

"""

def make_dir(filepaths):
    """
    Make directory to contain all output files. Use the shared naming convention of the
    injection files as the start of the directory name.
    """
    first_active_channel = [ch for ch in channels if filepaths[ch]][0]
    sibling_path = os.path.split(filepaths[first_active_channel])
    match = re.search(GC.suffix_regex, sibling_path[1], re.IGNORECASE)
    shared_name = sibling_path[1][:-len(match.group(0))] if match else sibling_path[1]
    # If file ends with 'fid01.asc' for example, also cut off the 'fid' as it is not part of the shared name
    if match and shared_name.lower().endswith(first_active_channel.lower()):
        shared_name = shared_name[:-len(first_active_channel)]
    shared_name = shared_name.strip()
    dirname = 'Chromelectric - ' + shared_name + f' - {datetime.now().strftime("%Y-%m-%d %I:%M:%S%p")}'
    dirpath = os.path.join(sibling_path[0], dirname)

    try:
        os.mkdir(dirpath)
    except FileExistsError as err:
        m = platform_messagebox(
            text='Attempted to create an output directory but the directory already exists.',
            buttons=QMessageBox.Ok, icon=QMessageBox.Critical, default_button=QMessageBox.Ok,
            detailed=f'Path `{dirpath}` already exists.')
        result = m.exec()
        return (None, None)
    
    return (dirpath, shared_name)

def output_analysis(filepaths, experiment_params, graphs_by_page, integrals_by_page):
    dirpath, shared_name = make_dir(filepaths)
    if not dirpath:
        return

    settings_path = os.path.join(dirpath, 'Settings Used - ' + shared_name + '.txt')
    with open(settings_path, 'w') as settings_handle:
        settings_handle.write(settings_header)
        json.dump(experiment_params, settings_handle, indent=4)

    integration_path = os.path.join(dirpath, 'Integration Params - ' + shared_name + '.txt')
    with open(integration_path, 'w') as integration_handle:
        integration_handle.write(integration_header)
        json.dump(get_integration_output(integrals_by_page), integration_handle, indent=4)

    fieldnames, rows = graphs_to_csv(experiment_params, graphs_by_page, integrals_by_page)
    csv_path = os.path.join(dirpath, 'Output - ' + shared_name + '.csv')
    with open(csv_path, 'w') as csv_handle:
        writer = csv.DictWriter(csv_handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    # if experiment_params['plot_j']:
    #     pass

    # if experiment_params['plot_fe']:
    #     pass
    #     if experiment_params['fe_total']:
    #         pass
    # then generate 2 plots maybe from csv

def graphs_to_csv(experiment_params, graphs_by_page, integrals_by_page):
    j_str = lambda gas: f'{gas} Partial Current (mA)'
    fe_str = lambda gas: f'{gas} Faradaic Efficiency (%)'

    gases = experiment_params['attributes_by_gas_name'].keys()
    gas_fields = [field for gas in gases for field in [j_str(gas), fe_str(gas)]]
    fieldnames = [
        'Injection Number', 'Uncorrected Voltage (V)', 'Corrected Voltage (V)',
        *gas_fields, 'Total Current (mA)', 'Total Faradaic Efficiency (%)',
    ]
    rows = []
    for page in graphs_by_page:
        total_fe = 0
        total_current = 0
        gas_stats = {field: 0 for gas in gases for field in [j_str(gas), fe_str(gas)]}
        for integral in integrals_by_page[page]:
            curr_gas = integral['gas']
            gas_stats[j_str(curr_gas)] += integral['partial_current']
            gas_stats[fe_str(curr_gas)] += integral['faradaic_efficiency']
            total_current += integral['partial_current']
            total_fe += integral['faradaic_efficiency']
        uv, cv = graphs_by_page[page]['uncorrected_voltage'], graphs_by_page[page]['corrected_voltage']
        rows.append({
            'Injection Number': page,
            'Uncorrected Voltage (V)': uv if not math.isnan(uv) else 'No Alignment',
            'Corrected Voltage (V)': cv if not math.isnan(cv) else 'No Alignment',
            'Total Current (mA)': total_current,
            'Total Faradaic Efficiency (%)': total_fe,
            **gas_stats
        })

    return (fieldnames, rows)

def get_integration_output(integrals_by_page):
    result = {}
    for page, integrals in integrals_by_page.items():
        curr_list = []
        for integral in integrals:
            curr_integral = {
                'gas': integral['gas'],
                'area': integral['area'],
                'moles': integral['moles'],
                'integration_mode': integral['mode'],
                'peak_start': integral['points'][0],
                'peak_end': integral['points'][1]
            }
            baseline_pure = integral['baseline'][1]
            # Convert numpy polynomial fit object to human-readable string of the form 'ax^0 + bx^1 + ...'
            polystr = ' + '.join([f'{coef}x^{index}' for index, coef in enumerate(baseline_pure.coef)])
            curr_integral['baseline'] = {
                'polynomial': polystr,
                'window': baseline_pure.window,
                'domain': baseline_pure.domain
            }
            curr_list.append(curr_integral)
        if curr_list:
            result[page] = curr_list
    return result

# END INTEGRATE MODULE

"""
TODO:
7. Also have user able to specify output location of files
    - Output Location: No folder selected. (Leave unselected to indicate same folder as FID/TCD file.)

<shared> - Partial Current Density.pdf
<shared> - Faradaic Efficiency.pdf
"""

# BOOTSTRAP
bootstrap()