import re
import os
import sys
import csv

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

def make_dir(filepaths):
    """
    Make directory to contain all output files. Use the shared naming convention of the
    injection files as the start of the directory name.
    """
    first_active_channel = [ch for ch in channels if filepaths[ch]][0]
    sibling_path = os.path.split(filepaths[first_active_channel])
    match = re.search(GC.suffix_regex, sibling_path[1], re.IGNORECASE)
    shared_name = sibling_path[1][:-len(match.group(0))] if match else sibling_path[1]
    # If file ends with 'fid01.asc' for example, also cut off the 'fid' as it is not part of the shared name
    if match and shared_name.lower().endswith(first_active_channel.lower()):
        shared_name = shared_name[:-len(first_active_channel)]
    shared_name = shared_name.strip()
    dirname = 'Chromelectric - ' + shared_name + f' - {datetime.now().strftime("%Y-%m-%d %I:%M:%S%p")}'
    dirpath = os.path.join(sibling_path[0], dirname)

    try:
        os.mkdir(dirpath)
    except FileExistsError as err:
        m = platform_messagebox(
            text='Attempted to create an output directory but the directory already exists.',
            buttons=QMessageBox.Ok, icon=QMessageBox.Critical, default_button=QMessageBox.Ok,
            detailed=f'Path `{dirpath}` already exists.')
        result = m.exec()
        return (None, None)
    
    return (dirpath, shared_name)

def output_analysis(filepaths, experiment_params, graphs_by_page, integrals_by_page):
    dirpath, shared_name = make_dir(filepaths)
    if not dirpath:
        return

    settings_path = os.path.join(dirpath, 'Settings Used - ' + shared_name + '.txt')
    with open(settings_path, 'w') as settings_handle:
        settings_handle.write(settings_header)
        json.dump(experiment_params, settings_handle, indent=4)

    integration_path = os.path.join(dirpath, 'Integration Params - ' + shared_name + '.txt')
    with open(integration_path, 'w') as integration_handle:
        integration_handle.write(integration_header)
        json.dump(get_integration_output(integrals_by_page), integration_handle, indent=4)

    fieldnames, rows = graphs_to_csv(experiment_params, graphs_by_page, integrals_by_page)
    csv_path = os.path.join(dirpath, 'Output - ' + shared_name + '.csv')
    with open(csv_path, 'w') as csv_handle:
        writer = csv.DictWriter(csv_handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    # if experiment_params['plot_j']:
    #     pass

    # if experiment_params['plot_fe']:
    #     pass
    #     if experiment_params['fe_total']:
    #         pass
    # then generate 2 plots maybe from csv

def graphs_to_csv(experiment_params, graphs_by_page, integrals_by_page):
    j_str = lambda gas: f'{gas} Partial Current (mA)'
    fe_str = lambda gas: f'{gas} Faradaic Efficiency (%)'

    gases = experiment_params['attributes_by_gas_name'].keys()
    gas_fields = [field for gas in gases for field in [j_str(gas), fe_str(gas)]]
    fieldnames = [
        'Injection Number', 'Uncorrected Voltage (V)', 'Corrected Voltage (V)',
        *gas_fields, 'Total Current (mA)', 'Total Faradaic Efficiency (%)',
    ]
    rows = []
    for page in graphs_by_page:
        total_fe = 0
        total_current = 0
        gas_stats = {field: 0 for gas in gases for field in [j_str(gas), fe_str(gas)]}
        for integral in integrals_by_page[page]:
            curr_gas = integral['gas']
            gas_stats[j_str(curr_gas)] += integral['partial_current']
            gas_stats[fe_str(curr_gas)] += integral['faradaic_efficiency']
            total_current += integral['partial_current']
            total_fe += integral['faradaic_efficiency']
        uv, cv = graphs_by_page[page]['uncorrected_voltage'], graphs_by_page[page]['corrected_voltage']
        rows.append({
            'Injection Number': page,
            'Uncorrected Voltage (V)': uv if not math.isnan(uv) else 'No Alignment',
            'Corrected Voltage (V)': cv if not math.isnan(cv) else 'No Alignment',
            'Total Current (mA)': total_current,
            'Total Faradaic Efficiency (%)': total_fe,
            **gas_stats
        })

    return (fieldnames, rows)

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
                'window': baseline_pure.window,
                'domain': baseline_pure.domain
            }
            curr_list.append(curr_integral)
        if curr_list:
            result[page] = curr_list
    return result
