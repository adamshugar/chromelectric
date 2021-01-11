"""
Module to write output of final analysis. Writes at least four files:
- Integration Info: parameters related to each integrated peak
- Settings Info: the experimental params (e.g. flow rate) used by this specific run of the program
- Values: actual CSV output of analysis (Faradaic efficiency, partial current density)
- Plots: user can optionally enable auto-generation of plots based on CSV output
"""
import re
import os
import sys
import csv
import json
from datetime import datetime
from math import isnan
import numbers
import matplotlib
from algos import fileparse
from util import channels

settings_header = """
These are the settings used by Chromelectric while analyzing your experiment.

You may use this file as a settings file for future runs of Chromelectric
by copying and pasting it into the same directory as the Chromelectric program,
naming the file `chromelectric_settings.txt`, and deleting this comment
(i.e., the dashed line and all text above it).

Note the following units used for each entry:

calibration_value       mV*sec/ppm      peak area per ppm
flow_rate               cm^3/min        sccm
sample_vol              mL
mix_vol                 mL
solution_resistance     ohms
ref_potential           V
-------------------------------------------------------------------------------

"""

integration_header = """
This file contains raw data about each integrated peak. It is mostly
intended for reference or sanity checking since Chromelectric automatically
processes this data into more relevant final output (e.g. Faradaic efficiency).
Most experimenters will rarely if ever need this file.

See below for discussion on polynomial domain and window:
https://stackoverflow.com/questions/52339907/numpy-polynomial-generation
https://numpy.org/doc/stable/reference/generated/numpy.polynomial.polynomial.Polynomial.html
Note that directly mapping the polynomial to the true domain before
recovering a numerical approximation will likely result in numerical instability.

Units:
- area = mV * sec
- peak_start / peak_end = (sec, mV)
--------------------------------------------------------------------------------------------

"""

def exec(filepaths, experiment_params, graphs_by_page, integrals_by_page):
    """Write final output of analysis to multiple files. Returns True on success, False otherwise."""
    suffix = f' - {datetime.now().strftime("%Y-%m-%d %I:%M:%S%p")}'
    dirpath, shared_name, err = make_dir(filepaths, suffix)
    if not dirpath:
        return (False, err)

    settings_path = os.path.join(dirpath, 'Settings Used - ' + shared_name + suffix + '.txt')
    with open(settings_path, 'w') as settings_handle:
        settings_handle.write(settings_header)
        json.dump(experiment_params, settings_handle, indent=4)

    integration_path = os.path.join(dirpath, 'Integration Params - ' + shared_name + suffix + '.txt')
    with open(integration_path, 'w') as integration_handle:
        integration_handle.write(integration_header)
        json.dump(get_integration_output(integrals_by_page), integration_handle, indent=4)

    gases = experiment_params['attributes_by_gas_name'].keys()

    fieldnames, rows = graphs_to_csv(gases, experiment_params, graphs_by_page, integrals_by_page)
    csv_path = os.path.join(dirpath, 'Output - ' + shared_name + suffix + '.csv')
    with open(csv_path, 'w') as csv_handle:
        writer = csv.DictWriter(csv_handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    
    j_fig, fe_fig = generate_plots(gases, experiment_params, rows)
    if j_fig:
        j_path = os.path.join(dirpath, 'Partial Current - ' + shared_name + suffix + '.pdf')
        j_fig.savefig(j_path, format='pdf')
    if fe_fig:
        fe_path = os.path.join(dirpath, 'Faradaic Efficiency - ' + shared_name + suffix + '.pdf')
        fe_fig.savefig(fe_path, format='pdf')

    return (True, None)

def make_dir(filepaths, suffix):
    """
    Make directory to contain all output files. Use the shared naming convention of the
    injection files as the start of the directory name.
    """
    first_active_channel = [ch for ch in channels if filepaths[ch]][0]
    sibling_path = os.path.split(filepaths[first_active_channel])
    match = re.search(fileparse.GC.suffix_regex, sibling_path[1], re.IGNORECASE)
    shared_name = sibling_path[1][:-len(match.group(0))] if match else sibling_path[1]
    # If file ends with 'fid01.asc' for example, also cut off the 'fid' as it is not part of the shared name
    if match and shared_name.lower().endswith(first_active_channel.lower()):
        shared_name = shared_name[:-len(first_active_channel)]
    shared_name = shared_name.strip()
    dirname = 'Chromelectric - ' + shared_name + suffix
    dirpath = os.path.join(sibling_path[0], dirname)

    try:
        os.mkdir(dirpath)
    except FileExistsError as err:
        return (None, None, {
            'text': 'Attempted to create an output directory but the directory already exists.',
            'informative': '',
            'detailed': f'Path `{dirpath}` already exists.'
        })
    
    return (dirpath, shared_name, None)

def get_integration_output(integrals_by_page):
    result = {}
    for page, integrals in integrals_by_page.items():
        curr_list = []
        for integral in integrals:
            curr_integral = {
                'gas': integral['gas'],
                'area': integral['area'],
                'moles': integral['moles'],
                'integration_mode': integral['mode'],
                'peak_start': integral['points'][0],
                'peak_end': integral['points'][1]
            }
            baseline_pure = integral['baseline'][1]
            # Convert numpy polynomial fit object to human-readable string of the form 'ax^0 + bx^1 + ...'
            polystr = ' + '.join([f'{coef}x^{index}' for index, coef in enumerate(baseline_pure.coef)])
            curr_integral['baseline'] = {
                'polynomial': polystr,
                # Numpy arrays are not JSON serializable so convert to list
                'window': baseline_pure.window.tolist(),
                'domain': baseline_pure.domain.tolist()
            }
            curr_list.append(curr_integral)
        if curr_list:
            result[page] = curr_list
    return result

j_str = lambda gas: f'{gas} Partial Current (mA)'
fe_str = lambda gas: f'{gas} Faradaic Efficiency (%)'

def graphs_to_csv(gases, experiment_params, graphs_by_page, integrals_by_page):
    gas_fields = [field for gas in gases for field in [j_str(gas), fe_str(gas)]]
    fieldnames = [
        'Injection Number', 'Uncorrected Voltage (V)', 'Corrected Voltage (V)',
        *gas_fields, 'Total Faradaic Efficiency (%)',
        'Total Observed Current (mA)', 'CA Average Current (mA)', 
    ]
    rows = []
    for page in graphs_by_page:
        total_fe, total_current = 0, 0
        gas_stats = {field: 0 for field in gas_fields}
        for integral in integrals_by_page[page]:
            curr_gas = integral['gas']
            gas_stats[j_str(curr_gas)] += integral['partial_current']
            gas_stats[fe_str(curr_gas)] += integral['faradaic_efficiency']
            total_fe += integral['faradaic_efficiency']
            total_current += integral['partial_current']

        alignsafe = lambda val: val if not isnan(val) else 'No Alignment'
        rows.append({
            'Injection Number': page,
            'Uncorrected Voltage (V)': alignsafe(graphs_by_page[page]['uncorrected_voltage']),
            'Corrected Voltage (V)': alignsafe(graphs_by_page[page]['corrected_voltage']),
            'CA Average Current (mA)': alignsafe(graphs_by_page[page]['avg_current']),
            'Total Faradaic Efficiency (%)': alignsafe(total_fe),
            'Total Observed Current (mA)': alignsafe(total_current),
            **{key: alignsafe(val) for key, val in gas_stats.items()}
        })

    return (fieldnames, rows)

def generate_plots(gases, experiment_params, rows):
    matplotlib.use('pdf')
    import matplotlib.pyplot as plt
    j_fig = fe_fig = None

    lineparams = {'marker': '.', 'markersize': 6}
    def plot_fields(rows, xfield, yfield, label, axes):
        xydict = {
            row[xfield]: row[yfield] for row in rows \
            if isinstance(row[yfield], numbers.Number)
        }
        axes.plot(xydict.keys(), xydict.values(), **lineparams, label=label)
    
    if experiment_params['plot_j']:
        j_fig = plt.figure()
        j_ax = j_fig.add_subplot()
        j_ax.set_title('Partial Current Density vs. Potential')
        j_ax.set_xlabel('Potential / V')
        j_ax.set_ylabel('Partial Current Density / mA')
        for gas in gases:
            plot_fields(rows, 'Corrected Voltage (V)', j_str(gas), gas, j_ax)
        j_ax.legend()

    if experiment_params['plot_fe']:
        fe_fig = plt.figure()
        fe_ax = fe_fig.add_subplot()
        fe_ax.set_title('Faradaic Efficiency vs. Potential')
        fe_ax.set_xlabel('Potential / V')
        fe_ax.set_ylabel('Faradaic Efficiency / %')
        for gas in gases:
            plot_fields(rows, 'Corrected Voltage (V)', fe_str(gas), gas, fe_ax)

        if experiment_params['fe_total']:
            fe_total_field = 'Total Faradaic Efficiency (%)'
            plot_fields(rows, 'Corrected Voltage (V)', fe_total_field, 'Total', fe_ax)
        fe_ax.legend()

    return (j_fig, fe_fig)
