import matplotlib.pyplot as plt
import numpy as np
from tkinter import filedialog
import re
import os
from datetime import datetime

def main():
    # path = filedialog.askopenfilename(title='Select', filetypes=[('GC', '.asc')])
    # print(path)

    n = 1
    # paths = ['/Users/adamshugar/Desktop/2020-12_Super_Mario/20201209_CH1_1000ppm_TCD_high_04..ASC',
    # '/Users/adamshugar/Desktop/20201214 - Ag - 0p0005mgcm2 - 1MPPD - 2/20201214 - Ag - 0p0005mgcm2 - 1MPPD - 2 fid03.asc']
    # NOTE: issue with intermediate value FIDs on Ag bare, super mario (also w/12 and 13 on FID for 1MPPD run 1)
    # NOTE: issue with all TCDs on 1MPPD run 1
    # Run 2 of MPPD is great

    # Bare silver super mario: not cooling

    integrals = []
    for i in range(2, 14):
        plt.close()
        path = '/Users/adamshugar/Desktop/20201214 - Ag - 0p0005mgcm2 - 1MPPD - 2/20201214 - Ag - 0p0005mgcm2 - 1MPPD - 2 tcd{:02}.asc'.format(i)
        # path = '/Users/adamshugar/Desktop/20201214 - Au counter - Ag bare - 10 sccm CO2 - 1MKHCO3 - true trial 2/20201214 - Ag bare - 1M KHCO3  -tcd{:02}.asc'.format(i)
        # path = '/Users/adamshugar/Desktop/20201214 - Ag - 0p0005mgcm2 - 1MPPD - 1/20201214 - Ag 0p0005 mgm2 1MPPD - 1M KHCO3 - fid{:02}.asc'.format(i)
        # path = '/Users/adamshugar/Desktop/20201214 - Au counter - Ag bare - 10 sccm CO2 - 1MKHCO3 - trial 1/20201214 - Au counter - Ag bare - 10 sccm CO2 - 1MKHCO3 - trial 1 tcd{:02}.asc'.format(i)
        handle = open(path, 'r')
        parsed = read_gc_raw(handle)
        handle.close()

        times = np.linspace(0, parsed['run_duration'], parsed['data'].size)
        plt.plot(times, parsed['data'])
        plt.title(f'Graph {i}')
        plt.show()

# Parse raw data from a single GC injection into a numpy array with metadata fields
def read_gc_raw(handle):
    # Parse relevant information from metadata lines at start of file
    # Metadata lines begin with <FIELD_NAME> (might contain spaces)
    meta_count = 0
    line = handle.readline()
    while match := re.search(r'<([A-Za-z ]*)>', line):
        meta_count += 1
        field_name = match.group(1).lower()
        val_str = line.rpartition('=')[2].strip()

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
    data = np.genfromtxt(fname=handle, comments=',', skip_header=meta_count)
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

def read_ca_raw(handle):
    handle.readline()
    meta_total_str = handle.readline().rpartition(':')[2].strip() # Total meta count on line 2
    try:
        meta_total = int(meta_total_str)
    except ValueError:
        return None

main()