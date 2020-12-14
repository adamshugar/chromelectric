import tkinter as tk
from tkinter import messagebox
from datetime import datetime
import numpy as np
import re
import os
from settings import get_settings
from generic_input import prompt_filepath, prompt_bound_tuple
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt

# Packaging: use PyInstaller to freeze executables for Mac, Windows, Linux, and distribute via Conda
# Auto generate a PDF or other high fidelity plot of single run at end; but also output excel file
# and have separate program in Python to aggregate plots with error bars

# TODO: Make this into a real Tkinter application with dropdown menu for # gases from 1 to 8,
# then for each chosen a name of the gas and upper / lower retention time bound, and checkbox for manual integration
# and prompt / checkbox to save settings and two import file buttons for fid and tcd

# For fitting: use blog post about deconvolution. Also for baseline fitting: convert function to monotonically decreasing
# (locally) then fit to high degree polynomial, and THEN do integration.

GC_RAW_EXTENSION = 'asc'

def gui_init():
    # Instantiate root window required to render Tk GUIs
    root = tk.Tk()
    root.eval('tk::PlaceWindow . center')
    # Hide empty 'root' window that pops up while using Tk
    root.iconify()
    root.withdraw()
    return root

# Given a list of gases with minimum and maximum bounds on retention time, find all overlaps
# between these bounds. Runs in O(n^2); faster than asymptotically optimal (but more complex)
# solutions, since we only ever deal with a few gases.
# E.g. { 'CO2': (1, 10), 'H2': (9, 12), 'C2H4': (100, 130) } -> { 'CO2': ['H2'], 'H2': ['CO2'], 'C2H4': [] }
def calc_retention_overlaps(retention_times):
    overlaps_by_gas = {}
    items = retention_times.items()
    for gas, bounds in items:
        (start, end) = bounds
        overlaps_by_gas[gas] = []
        for other_gas, other_bounds in items:
            (other_start, other_end) = other_bounds
            if other_gas != gas and (start <= other_start <= end or start <= other_end <= end):
                overlaps_by_gas[gas].append(other_gas)
    return overlaps_by_gas

def main():
    root = gui_init()

    settings = get_settings()
    if not settings:
        return
    overlaps_by_gas = calc_retention_overlaps(settings['retention_bounds'])

    gc_raw_filepaths = prompt_gc_filepaths(['GC FID', 'GC TCD'])
    if not gc_raw_filepaths:
        return
    [fid_raw_filepath, tcd_raw_filepath] = gc_raw_filepaths
    
    # file_range = prompt_bound_tuple(
    #     'file range',
    #     """Enter the index of the first GC file to be analyzed.
    #     (E.g. 1 for 'fid01.asc' and 'tcd01.asc'""",
    #     """Enter the index of the last GC file to be analyzed.
    #     (E.g. 15 for 'fid15.asc' and 'tcd15.asc'""")
    # if not file_range:
    #     return

    fid_parsed_list = get_gc_parsed_list(fid_raw_filepath, 'fid', (1, 2))
    # tcd_parsed_list = get_gc_parsed_list(tcd_raw_filepath, 'tcd', file_range)
    gc_parsed = fid_parsed_list[1]
    time_incr = np.linspace(0, gc_parsed['run_duration'], gc_parsed['data'].size)
    fig, ax = plt.subplots()
    ax.set_title('Choose integration bounds for GAS on TCD/FID ###')
    line, = ax.plot(time_incr, gc_parsed['data'], marker='.', markersize=5, pickradius=5, picker=True)
    # find and truncate to outer bounds of retention times
    # draw line from first point clicked to second
    # draw 
    result_dict = {'baseline': []}
    is_overlap = False
    fig.canvas.mpl_connect('pick_event', bind_handle_click(result_dict, is_overlap))
    plt.show()

    # then choose bounds based on manual/auto

    

    # If no overlap, just trapezoidally integrate using two bounds
    # If there is overlap of 2 or more, pick start, peak, end and fit to cauchy distribution (with falling baseline) then integrate

    # for calibration: either manually create calibration from file,
    # or enter final data by hand
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

def get_gc_parsed_list(raw_filepaths, identifier, file_range):
    channel = identifier.upper()
    raw_list = get_gc_file_list(raw_filepaths, identifier)
    parsed_list = {}
    for index in range(file_range[0], file_range[1] + 1): # Include final file number
        path = raw_list.get(index)
        if not path:
            messagebox.showerror(
                f'Unable to find {channel} {index}',
                (f'The file \'{channel} {index}\' was not found in the directory '
                'specified. Please ensure that all files in the specified range end '
                'with the proper channel name and injection number '
                f'(e.g. <experiment_identifiers>-{channel}{index}.asc'))
            return None
        try:
            handle = open(path, 'r')
            parsed_list[index] = read_gc_raw(handle)
            handle.close()
        except IOError as err:
            _, tail = os.path.split(path)
            messagebox.showerror(
                f'Unable to read file for {channel} {index}',
                f'Error while reading {tail}. {err.strerror}.')
            return None
    return parsed_list

# Using the file inputted by the user, find all other GC files in the run
# assuming an auto-increment scheme of <filepath>/<filename>[identifier][#].asc
def get_gc_file_list(filepath, identifier):
    head, _ = os.path.split(filepath)
    paths_by_index = {}
    for file in os.listdir(head):
        match = re.search(rf'{identifier}(\d+)\.(?:{GC_RAW_EXTENSION})$', file, re.IGNORECASE)
        if match:
            file_num = int(match.group(1))
            paths_by_index[file_num] = os.path.join(head, file)
    return paths_by_index

# Get filepaths for one of the FID files and one of
# the TCD files generated by the current GC run being examined.
def prompt_gc_filepaths(file_ids):
    file_list = []
    for file in file_ids:
        msg_detail = """This will also be the file from which to choose
        integration bounds if automatic integration is enabled."""
        path = prompt_filepath(file, f'.{GC_RAW_EXTENSION}', msg_detail)
        if not path:
            return None
        file_list.append(path)
    return file_list

# Parse raw data from a single GC injection into a numpy array with metadata fields
def read_gc_raw(handle):
    # Parse relevant information from metadata lines at start of file
    # Metadata lines begin with <FIELD_NAME> (might contain spaces)
    meta_count = 0
    line = handle.readline()
    while match := re.search(r'<([A-Za-z ]*)>', line):
        meta_count += 1
        field_name = match.group(1).lower()
        val_start = line.find('=', match.end(1) + 1) + 1
        val_str = line[val_start:].rstrip('\n')

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
            data_len = int(re.search(r'\d+', line).group())

        line = handle.readline()

    handle.seek(os.SEEK_SET)
    # Data lines have the form n,n for an integer n (second copy on each line is redundant)
    data = np.loadtxt(fname=handle, comments=',', skiprows=meta_count)
    handle.close()

    # Build return object with metadata
    run_duration = data_len / sample_rate # in seconds
    warning = data.size != data_len
    start_time = datetime.strptime(f'{date_string} {time_string}', r'%m-%d-%Y %H:%M:%S').timestamp()
    return {
        'run_duration': run_duration,
        'warning': warning,
        'start_time': start_time,
        'data': data / 1000 # Convert from microvolts to millivolts to match calibration curves
    }

main()