from PySide2.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QLineEdit, QLabel, QGridLayout)
from PySide2.QtCore import Signal, Slot, Qt
from PySide2.QtGui import QFont, QIntValidator
import matplotlib
from matplotlib.backends.backend_qt5agg import FigureCanvas, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from gui.graphshared import Pagination, IntAction, GraphPushButton
matplotlib.use('Qt5Agg')

def launch_window(graph_list, window_title, index_title, multiple_title, legend_title, xlabel, ylabel):
    qapp = QApplication([''])
    app = CarouselWindow(graph_list, window_title, index_title, multiple_title, legend_title, xlabel, ylabel)
    app.show()
    qapp.exec_()

class CarouselWindow(QMainWindow):
    def __init__(self, graph_list, window_title, index_title, multiple_title, legend_title, xlabel, ylabel):
        super().__init__()

        self.main = QWidget()
        self.setCentralWidget(self.main)
        self.layout = QGridLayout(self.main)
        self.setWindowTitle(window_title)
        self.index_title = index_title
        self.multiple_title = multiple_title
        self.legend_title = legend_title
        self.graph_list = graph_list
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
        self.overlay_tracker = OverlayTracker(
            pages, init_page, self.add_page, self.remove_page, 5)
        self.visible_pages = [init_page]
        self.layout.addLayout(self.overlay_tracker, 0, 1)

        self.axes = self.canvas.figure.add_subplot()
        self.curr_plot = None
        self.graph_page(page=init_page)

    def graph_page(self, _=None, page=0):
        self.overlay_tracker.clear()
        self.overlay_tracker.set_exclude(page)
        self.visible_pages = [page]

        self.axes.clear()
        self.axes.plot(self.graph_list[page]['x'], self.graph_list[page]['y'], label=self.legend_title.format(page))
        self.axes.set_title(self.index_title.format(page))
        self.axes.set_xlabel(self.xlabel)
        self.axes.set_ylabel(self.ylabel)

        self.toolbar.update()
        self.canvas.draw()

    def add_page(self, page):
        self.visible_pages.append(page)
        self.axes.plot(self.graph_list[page]['x'], self.graph_list[page]['y'], label=self.legend_title.format(page))

        self.axes.legend()
        self.axes.set_title(self.multiple_title)

        self.toolbar.update()
        self.canvas.draw()

    def remove_page(self, page):
        line_index = self.visible_pages.index(page)
        self.axes.get_lines()[line_index].remove()
        self.visible_pages.pop(line_index)

        # Always refresh legend to reflect removed page; if only one page left, no need for legend
        self.axes.get_legend().remove()
        if len(self.visible_pages) == 1:
            self.axes.set_title(self.index_title.format(self.visible_pages[0]))
        else:
            self.axes.legend()

        self.toolbar.update()
        self.canvas.draw()

class OverlayTracker(QVBoxLayout):
    def __init__(self, pages, exclude, on_add_overlay, on_remove_overlay, max_overlays=None):
        super().__init__()
        self.pages = pages
        self.set_exclude(exclude)
        self.on_add_overlay = on_add_overlay
        self.on_remove_overlay = on_remove_overlay
        self.max_overlays = max_overlays
        self.base_index = len(pages)

        # List current overlays at top of layout; clicking one removes it
        self.overlays = []
        self.insertStretch(self.base_index, 1)

        # "Add overlay" functionality at bottom of layout
        IntAction(
            layout=self, text='Overlay Injection', min_value=min(pages), max_value=max(pages),
            on_click=self.handle_add_click, insertion_index=self.base_index + 1)

    def handle_add_click(self, text):
        if self.max_overlays is not None and len(self.overlays) >= self.max_overlays:
            return False

        add_index = int(text)
        if add_index not in self.pages or add_index in self.overlays or add_index in self.exclude:
            return False
        
        remove_index_button = GraphPushButton(f'Remove #{add_index}')
        remove_index_button.clicked.connect(lambda: self.remove_overlay(add_index))
        self.insertWidget(len(self.overlays), remove_index_button, alignment=Qt.AlignHCenter)
        self.overlays.append(add_index)

        self.on_add_overlay(add_index)
        return True
    
    @Slot()
    def remove_overlay(self, page_index):
        remove_index = self.overlays.index(page_index)
        self.takeAt(remove_index).widget().deleteLater()
        self.overlays.pop(remove_index)
        self.on_remove_overlay(page_index)

    def clear(self):
        for _ in range(len(self.overlays)):
            self.takeAt(0).widget().deleteLater()
        self.overlays = []
        
    def set_exclude(self, exclude):
        # Supports convenient exclusion of single page or multiple
        self.exclude = exclude if isinstance(exclude, list) else [exclude]
