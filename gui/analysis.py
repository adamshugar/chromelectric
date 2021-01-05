"""
A graphical view of the GC injection list (all channels at once) for use in quickly integrating peaks.
These peak integrations are the main data used to generate the final output file.
"""
from PySide2.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QLineEdit, QGridLayout)
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

        print(graph_info)
        print('\n\n\n\n\n')

        parsed_files = graph_info['parsed_file_input']
        fid_graphs, tcd_graphs = [parsed_files[channel] if parsed_files[channel] else {} for channel in ['FID', 'TCD']]
        all_indices = fid_graphs.keys() | tcd_graphs.keys()
        # 1: {FID: np.arr, TCD: np.arr}
        combined_graphs = {index: {channel: parsed_files[channel][index] for channel in channels} for index in all_indices}
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