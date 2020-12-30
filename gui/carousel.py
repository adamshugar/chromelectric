from PySide2.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QLineEdit, QLabel, QGridLayout)
from PySide2.QtCore import Signal, Slot, Qt
from PySide2.QtGui import QFont, QIntValidator
import matplotlib
from matplotlib.backends.backend_qt5agg import FigureCanvas, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
matplotlib.use('Qt5Agg')

class IntAction:
    # Assumes `layout` is QHBoxLayout
    def __init__(self, layout, text, min_value, max_value, on_click, insertion_index=None):
        self.on_click = on_click
        trigger_button = PushButton(text=text)
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
        
        remove_index_button = PushButton(f'Remove #{add_index}')
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

class ApplicationWindow(QMainWindow):
    def __init__(self, graph_list, window_title, index_title, xlabel, ylabel):
        super().__init__()

        self.main = QWidget()
        self.setCentralWidget(self.main)
        self.layout = QGridLayout(self.main)
        self.setWindowTitle(window_title)
        self.index_title = index_title
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
        self.axes.plot(self.graph_list[page]['x'], self.graph_list[page]['y'], label=self.index_title.format(page))
        self.axes.set_title(self.index_title.format(page))
        self.axes.set_xlabel(self.xlabel)
        self.axes.set_ylabel(self.ylabel)

        self.toolbar.update()
        self.canvas.draw()

    def add_page(self, page):
        self.visible_pages.append(page)
        self.axes.plot(self.graph_list[page]['x'], self.graph_list[page]['y'], label=self.index_title.format(page))

        self.axes.legend()

        self.toolbar.update()
        self.canvas.draw()

    def remove_page(self, page):
        line_index = self.visible_pages.index(page)
        self.axes.get_lines()[line_index].remove()
        self.visible_pages.pop(line_index)

        # Always refresh legend to reflect removed page; if only one page left, no need for legend
        self.axes.get_legend().remove()
        if len(self.visible_pages) > 1:
            self.axes.legend()

        self.toolbar.update()
        self.canvas.draw()

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
            label.setFixedWidth(20)
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

def launch_window(graph_list, window_title, index_title, xlabel, ylabel):
    qapp = QApplication([''])
    app = ApplicationWindow(graph_list, window_title, index_title, xlabel, ylabel)
    app.show()
    qapp.exec_()
