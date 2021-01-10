"""
A graphical view of the GC injection list (all channels at once) for use in quickly integrating peaks.
These peak integrations are the main data used to generate the final output file.
"""
from PySide2.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QComboBox, QSizePolicy, QFrame, QSpacerItem,
    QPushButton, QLabel, QGridLayout, QLayout, QScrollArea, QMessageBox)
from PySide2.QtCore import Qt
import numpy as np
import matplotlib
from matplotlib.backends.backend_qt5agg import FigureCanvas, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from datetime import timedelta
from math import nan, isnan
from functools import reduce
import gui
from gui.graphshared import Pagination, GraphPushButton
import physcalc
import integrate

matplotlib.use('Qt5Agg')

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
    """Wrapper for Qt label that automatically resizes when text changes."""
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
            "{:.2f}%".format(integral['faradaic_efficiency']) if not isnan(integral['faradaic_efficiency']) else 'N/A')

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
        if isnan(self.mol_e) or isnan(self.avg_current):
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
        
        if not isnan(self.mol_e):
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
                combined_graph['uncorrected_voltage'] = combined_graph['corrected_voltage'] = nan
            
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
