from PySide2.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QLineEdit, QLabel, QGridLayout)
from PySide2.QtCore import Signal, Slot, Qt
from PySide2.QtGui import QFont, QIntValidator
import matplotlib
from matplotlib.backends.backend_qt5agg import FigureCanvas, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from gui.graphshared import Pagination, GraphPushButton
from util import channels
matplotlib.use('Qt5Agg')

def launch_window(graph_info, window_title, index_title, xlabel, ylabel):
    qapp = QApplication([''])
    app = IntegrateWindow(graph_info, window_title, index_title, xlabel, ylabel)
    app.show()
    qapp.exec_()

# put output files in new folder in same directory as CA file (check if already exists and then append first available number to it)
# Also have user able to specify output location of files
class IntegrateWindow(QMainWindow):
    def __init__(self, graph_info, window_title, index_title, xlabel, ylabel):
        super().__init__()

        parsed_files = graph_info['parsed_file_input']
        fid_graphs, tcd_graphs = [parsed_files[channel] if parsed_files[channel] else {} for channel in ['FID', 'TCD']]
        all_indices = fid_graphs.keys() | tcd_graphs.keys()
        # 1: {FID: np.arr, TCD: np.arr}
        combined_graphs = {index: {channel: parsed_files[channel][index]} for index in all_indices}
        print(combined_graphs)

        self.main = QWidget()
        self.setCentralWidget(self.main)
        self.layout = QGridLayout(self.main)
        self.setWindowTitle(window_title)
        self.index_title = index_title
        self.graph_list = fid_graphs # extract from graph info
        self.xlabel = xlabel
        self.ylabel = ylabel

        self.canvas = FigureCanvas(Figure())
        self.layout.addWidget(self.canvas, 0, 0)
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.addToolBar(self.toolbar)

        pages = [int(page) for page in self.graph_list]
        pages.sort()
        pagination = Pagination(pages, handle_page_change=self.graph_page)
        self.layout.addLayout(pagination, 1, 0)

        init_page = pages[0]
        self.axes = self.canvas.figure.add_subplot(211)
        self.curr_plot = None
        self.graph_page(page=init_page)

    def graph_page(self, _=None, page=0):
        self.axes.clear()
        self.axes.plot(self.graph_list[page]['x'], self.graph_list[page]['y'])
        self.axes.set_title(self.index_title.format(page))
        self.axes.set_xlabel(self.xlabel)
        self.axes.set_ylabel(self.ylabel)

        self.toolbar.update()
        self.canvas.draw()

"""
line, = ax.plot(time_incr, gc_parsed['data'], marker='.', markersize=5, pickradius=5, picker=True)
fig.canvas.mpl_connect('pick_event', bind_handle_click(result_dict, is_overlap))

def get_pick_coords(event):
    points_clicked = event.ind # numpy array containing all points clicked, by index
    if points_clicked.size <= 5:
        # Find closest point to actual mouse click
        actual_click = (event.mouseevent.xdata, event.mouseevent.ydata)
        pick_index = min(points_clicked, key=lambda pt: abs(np.linalg.norm(pt - actual_click)))
    else:
        # Pick middle point; user is too zoomed out to pick at a granular level
        pick_index = points_clicked.size // 2
    line = event.artist
    return (line.get_xdata()[pick_index], line.get_ydata()[pick_index])

def bind_handle_click(result_dict, is_overlap):
    def handle_click_standard(event):
        pick_coords = get_pick_coords(event)
        print('picked', pick_coords)

        baseline = result_dict['baseline']
        if pick_coords in baseline:
            baseline.remove(pick_coords)
        elif len(baseline) < 2:
            baseline.append(pick_coords)
        print('baseline is ', baseline)
        # before moving on, show integration area / cauchy curve
    def handle_click_overlap(event):
        baseline = result_dict['baseline']
        n_points = len(baseline)
        if n_points == 0:
            pass # select peak first
        elif n_points:
            pass
        print(result_dict)
    return handle_click_overlap if is_overlap else handle_click_standard
"""
