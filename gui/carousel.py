import PySide2
from PySide2.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QStyle, QStyleFactory,
    QLineEdit, QLabel, QSizePolicy)
import PySide2.QtCore as QtCore
from PySide2.QtCore import Signal, Slot
from PySide2.QtGui import QIcon, QFont, QIntValidator
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvas, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

class ApplicationWindow(QMainWindow):
    def __init__(self, graph_list, window_title, index_title, xlabel, ylabel):
        super().__init__()
        self.main = QWidget()
        self.setCentralWidget(self.main)
        self.layout = QVBoxLayout(self.main)
        self.setWindowTitle(window_title)
        self.index_title = index_title
        self.graph_list = graph_list
        self.xlabel = xlabel
        self.ylabel = ylabel

        self.canvas = FigureCanvas(Figure())
        self.layout.addWidget(self.canvas)
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.addToolBar(self.toolbar)

        pages = [page for page in self.graph_list]
        pages.sort()
        pagination = Pagination(pages, handle_page_change=lambda _, new_page: self.graph_index(new_page))
        self.layout.addLayout(pagination)

        self.axes = self.canvas.figure.add_subplot()
        self.curr_plot = None
        self.graph_index(1)

    def graph_index(self, index):
        self.axes.clear()
        self.axes.plot(self.graph_list[index]['x'], self.graph_list[index]['y'])
        self.axes.set_title(self.index_title.format(index))
        self.axes.set_xlabel(self.xlabel)
        self.axes.set_ylabel(self.ylabel)
        self.toolbar.update()
        self.canvas.draw()

    def add_index(self, index):
        pass

class PushButton(QPushButton):
    def __init__(self, text, font_size=None, fixed_width=None):
        super().__init__(text=text)
        if fixed_width:
            self.setFixedWidth(fixed_width)
        if font_size:
            font = self.font()
            font.setPointSize(font_size)
            self.setFont(font)

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
        self.prev_button = PushButton(text='←', font_size=32, fixed_width=80)
        self.next_button = PushButton(text='→', font_size=32, fixed_width=80)
        self.prev_button.clicked.connect(self.handle_prev_click)
        self.next_button.clicked.connect(self.handle_next_click)
        self.update_button_states()

        # Container for text entry box and "Go button" only
        self.jump_container = QVBoxLayout()
        jump_button = PushButton(text='Go')
        self.jump_entry = QLineEdit()
        self.jump_entry.setAlignment(QtCore.Qt.AlignHCenter)
        self.jump_entry.setFixedWidth(80)
        self.jump_entry.setMaxLength(5)
        entry_font = self.jump_entry.font()
        entry_font.setPointSize(16)
        self.jump_entry.setFont(entry_font)
        self.jump_entry.setValidator(QIntValidator(min(pages), max(pages)))
        jump_button.clicked.connect(self.handle_jump_click)
        self.jump_container.addWidget(self.jump_entry, alignment=QtCore.Qt.AlignHCenter)
        self.jump_container.addWidget(jump_button, alignment=QtCore.Qt.AlignHCenter)

        # Initialize overall layout
        self.controls_container.addWidget(self.prev_button, alignment=QtCore.Qt.AlignTop|QtCore.Qt.AlignRight)
        self.controls_container.addLayout(self.jump_container, alignment=QtCore.Qt.AlignTop|QtCore.Qt.AlignHCenter)
        self.controls_container.addWidget(self.next_button, alignment=QtCore.Qt.AlignTop|QtCore.Qt.AlignLeft)
        self.controls_container.setStretchFactor(self.prev_button, 1)
        self.controls_container.setStretchFactor(self.next_button, 1)

        self.indicator = PageIndicator(pages, start_index)
        self.addLayout(self.indicator, alignment=QtCore.Qt.AlignHCenter)
        self.addLayout(self.controls_container, alignment=QtCore.Qt.AlignHCenter)

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
    def handle_jump_click(self):
        try:
            new_page = int(self.jump_entry.text())
            new_index = self.pages.index(new_page)
        except ValueError:
            return
        
        if new_index != self.curr_index:
            self.curr_index = new_index

class PageIndicator(QHBoxLayout):
    def __init__(self, pages, start_index):
        super().__init__()

        self.pages = pages
        self.labels = []
        self.addStretch(1)
        for _ in range(5):
            label = QLabel('')
            label.setFixedWidth(20)
            label.setAlignment(QtCore.Qt.AlignCenter)
            self.labels.append(label)
            self.addWidget(label, alignment=QtCore.Qt.AlignCenter)
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

def launch_window(graph_list, window_title, index_title, xlabel, ylabel):
    qapp = QApplication([''])
    app = ApplicationWindow(graph_list, window_title, index_title, xlabel, ylabel)
    app.show()
    qapp.exec_()