import tkinter as tk
from tkinter import ttk
import re
from gui.paraminput import GasList, AdditionalFields
from gui.filepick import FileList
import matplotlib.pyplot as plt

class Application(ttk.Frame):
    PADX, PADY = (25, 20)

    def __init__(self, master):
        super().__init__(master)
        self.grid()

        container = ttk.Frame(self)
        container.grid(padx=Application.PADX, pady=Application.PADY)

        self.gas_list = GasList(container)
        self.gas_list.grid()

        self.additional_fields = AdditionalFields(container)
        self.additional_fields.grid()

        separator = ttk.Separator(container, orient=tk.HORIZONTAL)
        separator.grid(pady=Application.PADY, sticky=tk.E+tk.W)

        self.file_list = FileList(container)
        self.file_list.grid(sticky=tk.W+tk.E)

        run_button = ttk.Button(container, text='Integrate', command=self.print_test)
        run_button.grid(sticky=tk.E, pady=(Application.PADY, 0))

    def print_test(self):
        # Invalid params ignore notification
        # At least one valid needed
        print(self.gas_list.get_parsed_input())
        print(self.additional_fields.get_parsed_input())
        print(self.file_list.get_parsed_input())

def get_geometry(frame):
    geometry = frame.winfo_geometry()
    match = re.match(r'^(\d+)x(\d+)\+(\d+)\+(\d+)$', geometry)
    return [int(val) for val in match.group(*range(1, 5))]

def center_window(root, y_percent=100):
    """ Center the root window of the Tk application in
    the currently active screen/monitor. Works properly
    with multiscreen setups. Must be called after application
    is fully initialized so that the root window is the true
    final size.
    
    Set y_percent to a value between 0 and 100 inclusive to
    translate the window vertically, where 100 is fully centered and
    0 is top of window touching top of screen. """
    root.attributes('-alpha', 0)

    root.withdraw()
    root.attributes('-fullscreen', True)
    root.update_idletasks()
    screen_width, screen_height, *_ = get_geometry(root)
    root.attributes('-fullscreen', False)

    root.deiconify()
    root.update_idletasks()
    window_width, window_height, *_ = get_geometry(root)

    pos_x = round(screen_width / 2 - window_width / 2)
    pos_y = round((screen_height / 2 - window_height / 2) * y_percent / 100)
    root.geometry(f'+{pos_x}+{pos_y}')
    root.update_idletasks()
    
    root.attributes('-alpha', 1)

def main():
    root = tk.Tk()
    root.title('Chromelectric')
    root.resizable(False, False)
    app = Application(master=root)
    center_window(root, y_percent=50)
    app.mainloop()

if __name__ == '__main__':
    main()