import tkinter as tk
from tkinter import messagebox
from datetime import datetime
import numpy as np
import re
import json
import sys
import os
from settings import get_settings
from generic_input import prompt_filepath, prompt_bound_tuple
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt

"""
Later, if possible: test on low DPI displays and multiple monitors
	Fix tiny Windows checkboxes and weird Notebook on Mac - really should port to PyQt or PySide
Also multithread the GC/CA file reads so the program never freezes
Dependencies on Ubuntu: tkinter, matplotlib, and PyQt5
"""

# Packaging: use PyInstaller to freeze executables for Mac, Windows, Linux, and distribute via Conda
# Auto generate a PDF or other high fidelity plot of single run at end; but also output excel file
# and have separate program in Python to aggregate plots with error bars

# For fitting: use blog post about deconvolution. Also for baseline fitting: convert function to monotonically decreasing
# (locally) then fit to high degree polynomial, and THEN do integration. Maybe also have absolute value threshold of second deriv

#TODO: NMR module and generate calibration value module

def main():
    root = gui_init()

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