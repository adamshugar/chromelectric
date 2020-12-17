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

# For fitting: use blog post about deconvolution. Also for baseline fitting: convert function to monotonically decreasing
# (locally) then fit to high degree polynomial, and THEN do integration. Maybe also have absolute value threshold of second deriv

#TODO: NMR module and generate calibration value module

GC_RAW_EXTENSION = 'asc'

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

main()