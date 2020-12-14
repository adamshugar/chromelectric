from tkinter import messagebox, simpledialog
from generic_input import prompt_bound_tuple 
import json
import sys
import os
import re

# Load the experimental parameters from the settings file. For any not found,
# prompt the user for them and optionally save them into the settings file.
# Experimental parameters:
#   - Gases used (e.g. CO, CH4, C2H4, H2)
#   - Min and max bounds on retention time for each gas
#   - Calibration values for each gas, converting integration area to ppm
#   - Whether integration bounds should be selected manually (every file) or automatically (one file)
def get_settings():
    SETTINGS_FILE_NAME = 'chromelectric_settings.txt'
    settings_path = os.path.join(sys.path[0], SETTINGS_FILE_NAME)
    settings = {}
    try:
        file = open(settings_path, 'r')
        settings = json.load(file)
    except IOError:
        pass # File won't exist on first program run
    return prompt_missing_settings(settings, settings_path)

# Prompts the user for any missing settings. Accepts as parameters settings already
# read from the settings file (if they exist). Optionally saves updated parameters
# to settings file if user desires.
def prompt_missing_settings(settings, settings_path):
    prompts_by_field = {
        'gas_names': prompt_gas_names,
        'retention_bounds': prompt_retention_bounds,
        'manual_integration': prompt_manual_integration
    }

    was_field_updated = False
    for field, prompt_func in prompts_by_field.items():
        if settings.get(field) == None:
            settings[field] = prompt_func(settings)
            was_field_updated = True
        if settings.get(field) == None:
            return None
    
    if was_field_updated:
        should_save = messagebox.askyesno(
            'Save experimental parameters?',
            ('Do you want to save these parameters to '
            'automatically load for future runs of the program?'))
        if should_save:
            try:
                settings_handle = open(settings_path, 'w')
                json.dump(settings, settings_handle, indent=4)
            except IOError as err:
                messagebox.showwarning(
                    'Unable to save file',
                    f'Error while saving settings file. {err.strerror}.')

    return settings

# Get a list of gas names from the user (e.g. ['CO2', 'H2', 'methane'])
def prompt_gas_names(settings):
    valid_gas_list = False
    while not valid_gas_list:
        user_gas_list = simpledialog.askstring(
            'Specify relevant gases',
            ('Enter names of all gases to be analyzed, '
            'separated by commas or whitespace or both.'))
        if user_gas_list == None:
            return None
        gas_names = list(filter(lambda token: token, re.split(r'(?:,| )+', user_gas_list)))
        if len(gas_names) > 0:
            valid_gas_list = True
        else:
            messagebox.showinfo('Invalid gas list', 'Please enter at least one gas name.')
    return list(set(gas_names)) # Remove duplicates

# Get min and max retention times (in seconds) for each gas name previously prompted
# E.g. ['CO2', 'H2'] -> { 'CO2': (91, 235), 'H2': (50, 110) }
def prompt_retention_bounds(settings):
    gas_names = settings.get('gas_names')
    if not gas_names:
        return None

    retention_times = {}
    for gas in gas_names:
        bound_tuple = prompt_bound_tuple(
            gas,
            f'Enter the minimum retention time for {gas}, in seconds.',
            f'Enter the maximum retention time for {gas}, in seconds.')
        if not bound_tuple:
            return None
        retention_times[gas] = bound_tuple
    return retention_times

def prompt_manual_integration(settings):
    return messagebox.askyesnocancel(
        'Select integration type',
        ('For a given gas, do you want to select integration bounds '
        'for each injection manually? Selecting \'No\' means you will choose '
        'integration bounds from one representative injection, then apply those '
        'bounds automatically to all other injections.'))