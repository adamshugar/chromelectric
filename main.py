import tkinter as tk
from tkinter import ttk
import re
import matplotlib.pyplot as plt
import multiprocessing as mp
import gui
import gui.hdpi as hdpi
import util
from gui.paraminput import GasList, ShortEntryList, CheckbuttonList
from gui.filepick import FileList

class GeneralParams(ttk.Frame):
    def __init__(self, master, padx=0, pady=0):
        super().__init__(master)

        container = ttk.Frame(self)
        container.grid(padx=padx, pady=pady)

        self.gas_list = GasList(container)
        self.gas_list.grid(sticky=tk.W+tk.E, pady=(0, pady))

        self.short_entry_list = ShortEntryList(container)
        self.short_entry_list.grid(sticky=tk.E+tk.W, pady=(0, pady))

        self.checkbutton_list = CheckbuttonList(container)
        self.checkbutton_list.grid(sticky=tk.E+tk.W)

class FileAnalysis(ttk.Frame):
    def __init__(self, master, padx=0, pady=0):
        super().__init__(master)

        container = ttk.Frame(self)
        container.grid(padx=padx, pady=pady)

        self.file_list = FileList(container)
        self.file_list.grid(sticky=tk.W+tk.E)

        run_button = hdpi.Button(container, text='Integrate', command=self.print_test)
        run_button.grid(sticky=tk.E, pady=(pady, 0))

    def print_test(self):
        print(self.short_entry_list.get_parsed_input())

# Extends the ttk Notebook functionality to dynamically resize on every tab change.
class DynamicNotebook(ttk.Notebook):
    def __init__(self, master):
        super().__init__(master)

    def setup(self, tabs_by_name, first_tab):
        self.tabs_by_name = tabs_by_name
        self.dummies_by_name = {name: ttk.Frame() for name in tabs_by_name}
        for name in tabs_by_name:
            if name == first_tab:
                self.add(tabs_by_name[name], text=name)
            else:
                self.add(self.dummies_by_name[name], text=name)

        self.name_map = {**DynamicNotebook.get_name_map(tabs_by_name), **DynamicNotebook.get_name_map(self.dummies_by_name)}

        self.current_tab_name = first_tab
        # After a manual swap, notebook thinks we have changed tabs so fires the handler again;
        # we want to ignore it the second time
        self.guard_duplicate = False
        self.bind("<<NotebookTabChanged>>", self.handle_tab_change)

    @staticmethod
    # Returns map with keys as tk window names and values as the titles from the original dictionary
    def get_name_map(widgets_by_title):
        return { str(widget): name for name, widget in widgets_by_title.items() }

    # Returns ordered list of tab titles
    def tab_titles(self):
        return [self.name_map[tab_window_name] for tab_window_name in self.tabs()]

    def handle_tab_change(self, event):
        if self.guard_duplicate:
            self.guard_duplicate = False
            return
        new_name = event.widget.tab(event.widget.select(), 'text')
        if new_name == self.current_tab_name:
            return
        self.swap_tab(self.current_tab_name, self.dummies_by_name[self.current_tab_name])
        self.current_tab_name = None
        self.swap_tab(new_name, self.tabs_by_name[new_name])
        self.current_tab_name = new_name
        self.select(self.get_widget_from_name(new_name))
        self.guard_duplicate = True

    def get_widget_from_name(self, name):
        if name == self.current_tab_name:
            return self.tabs_by_name[name]
        else:
            return self.dummies_by_name[name]

    def swap_tab(self, name, new_widget):
        tab_order = self.tab_titles()
        old_widget = self.get_widget_from_name(name)

        name_index = tab_order.index(name)
        subsequent_name = tab_order[name_index + 1] if name_index < len(tab_order) - 1 else None
        subsequent_widget = self.get_widget_from_name(subsequent_name) if subsequent_name is not None else "end"

        self.forget(old_widget)
        self.insert(subsequent_widget, new_widget, text=name)

def get_geometry(frame):
    geometry = frame.winfo_geometry()
    match = re.match(r'^(\d+)x(\d+)\+(\d+)\+(\d+)$', geometry)
    return [int(val) for val in match.group(*range(1, 5))]

def center_window(root, y_percent=50):
    """ Center the root window of the Tk application in
    the currently active screen/monitor. Works properly
    with multiscreen setups. Must be called after application
    is fully initialized so that the root window is the true
    final size.
    
    Set y_percent to a value between 0 and 100 inclusive to
    translate the window vertically, where 100 is fully centered and
    0 is top of window touching top of screen. """
    root.eval('tk::PlaceWindow . center')
    _, _, xpos, ypos = get_geometry(root)
    ypos = round(ypos * y_percent / 100)
    root.geometry(f'+{xpos}+{ypos}')
    root.update_idletasks()

class Application(ttk.Frame):
    PADX, PADY = (25, 20)

    def __init__(self):
        root = hdpi.tk_process_init()
        root.title('Chromelectric')
        root.resizable(False, False)

        super().__init__(root)
        self.root = root
        self.root.bind( "<Configure>", self.handle_resize_scheduler)
        self.grid()

        # We have made the root unable to be resized by the user, so we know that
        # the only resizing is being done by our DynamicNotebook module. We handle this
        # resizing to keep the window from jumping around as it is resized.
        self.scheduled_resize_handler = None
        # Only handle resize if no more resize events have been triggered for 10 millis
        self.resize_wait_millis = 10
        
        padx = Application.PADX * hdpi.SCALE_FACTOR
        pady = Application.PADY * hdpi.SCALE_FACTOR
        # Necessary to have global frame container for non-empty background
        container = ttk.Frame(self)
        container.grid(padx=padx, pady=pady)

        self.notebook = DynamicNotebook(container)
        self.general_params = GeneralParams(self.notebook, padx=padx, pady=pady)
        self.file_analysis = FileAnalysis(self.notebook, padx=padx, pady=pady)
        general_params_name = 'General Parameters' if not is_windows() else ' General Parameters '
        file_analysis_name = 'File Analysis' if not is_windows() else ' File Analysis '
        self.tabs_by_name = {
            general_params_name: self.general_params,
            file_analysis_name: self.file_analysis,
        }
        self.notebook.setup(self.tabs_by_name, first_tab=general_params_name)
        self.notebook.grid()

        center_window(root, y_percent=50)

        # 'should_save': {
        #     'label': 'Save all above parameters for future runs',
        #     'default': True
        # },
    
    def handle_resize_scheduler(self, event):
        print('scheduling')
        if self.scheduled_resize_handler is not None:
            self.root.after_cancel(self.scheduled_resize_handler)
        self.scheduled_resize_handler = self.root.after(self.resize_wait_millis, lambda: self.handle_resize(event))

    def handle_resize(self, event):
        print('handled')
        self.scheduled_resize_handler = None

def main():
    app = Application()
    app.mainloop()

if __name__ == '__main__':
    mp.set_start_method('spawn')
    main()