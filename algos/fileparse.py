"""
Parsing of gas chromatography files and cyclic amperometry files into Python objects.

Currently supports only SRI/PeakSimple GC files (*.asc). Support for Agilent GC files (*.ch)
is a priority and may be added soon.

Supports EC-Lab BioLogic text-style CA files (*.mpt). It is unlikely that support will be added for
binary EC-Lab CA files (*.mpr) as EC-Lab offers built-in "export to text" functionality.
"""
from datetime import datetime, timedelta
import re
import os
import numpy as np
from util import filetype

# Using classes in this module purely as additional namespaces; all methods are static
# and classes are not meant to be instantiated.

class GC:
    suffix_regex = rf'(\d+)(?:\.)+(?:{filetype.GC})$'

    @staticmethod
    # Parse raw data from a single GC injection into a numpy array with metadata fields
    def parse_file(handle):
        # Parse relevant information from metadata lines at start of file
        # Metadata lines begin with <FIELD_NAME> (might contain spaces)
        meta_count = 0
        line = handle.readline()
        while match := re.search(r'<([A-Za-z ]*)>', line):
            meta_count += 1
            field_name = match.group(1).lower()
            val_str = line.partition('=')[2].strip()

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
                num_readings = int(re.search(r'\d+', line).group())

            line = handle.readline()

        handle.seek(os.SEEK_SET)
        # Data lines have the form n,n for an integer n (second copy on each line is redundant)
        potentials = np.genfromtxt(fname=handle, comments=',', skip_header=meta_count)

        # Build return object with metadata
        run_duration = num_readings / sample_rate # In seconds
        time_increments = np.linspace(0, run_duration, potentials.size)
        warning = potentials.size != num_readings # Indicates file might be truncated prematurely
        start_time = datetime.strptime(f'{date_string} {time_string}', r'%m-%d-%Y %H:%M:%S')
        return {
            'warning': warning,
            'start_time': start_time,
            'x': time_increments,
            'y': potentials / 1000 # Convert from microvolts to millivolts to match calibration curves
        }
    
    @staticmethod
    def parse_list(raw_list):
        parsed_list = {}
        for index, path in raw_list.items():
            try:
                handle = open(path, 'r')
            except IOError:
                return index
            
            try:
                parsed_list[index] = GC.parse_file(handle)
            except Exception: # Fails safely for GA files with improper meta or data format
                handle.close()
                return index
            else:
                handle.close()

        return parsed_list

    @staticmethod
    # Using the file inputted by the user, find all other GC files in the run
    # assuming an auto-increment scheme of <filepath>/<shared filename><#>.<GC extension>
    def find_list(filepath):
        head, tail = os.path.split(filepath)
        user_input_match = re.search(GC.suffix_regex, tail, re.IGNORECASE)
        if user_input_match is None:
            return None # User supplied an invalid file (didn't have <#> suffix)
        shared_filename = tail[:-len(user_input_match.group(0))]

        paths_by_index = {}
        for entry in os.listdir(head):
            if not os.path.isfile(os.path.join(head, entry)):
                continue
            match = re.search(shared_filename + GC.suffix_regex, entry, re.IGNORECASE)
            if match:
                file_num = int(match.group(1))
                paths_by_index[file_num] = os.path.join(head, entry)
        return paths_by_index

class CA:
    @staticmethod
    def parse_file(filepath):
        handle = open(filepath, 'r', encoding='latin-1')
        handle.readline()
        meta_total_str = handle.readline().partition(':')[2].strip() # Total meta count on line 2
        meta_total = int(meta_total_str)

        meta_curr = 3
        while meta_curr < meta_total:
            meta_curr += 1
            line = handle.readline().lower()
            if line.startswith('acquisition started on'):
                date_str = line.partition(':')[2].strip()
                acquisition_start = datetime.strptime(date_str, r'%m/%d/%Y %H:%M:%S')
            elif line.startswith('ei (v)'):
                potentials_by_trial = [float(potential) for potential in line.split()[2:]]
            elif line.startswith('ti (h:m:s)'):
                duration_by_trial = []
                for duration in line.split()[2:]:
                    components = [float(component) for component in duration.split(':')]
                    duration_by_trial.append(timedelta(
                        hours=components[0], minutes=components[1], seconds=components[2]))

                total_duration = timedelta()
                total_dur_by_trial = [total_duration]
                for duration in duration_by_trial:
                    total_duration += duration
                    total_dur_by_trial.append(total_duration)

        # NOTE: 'time/s' field represents offset from acquisition start, NOT technique start.
        data_fields = ['Ns', 'time/s', '<I>/mA']
        # Header row for data will always be last line of metadata;
        # this line was just read in final iteration of above loop
        header_row = handle.readline().split('\t')
        data_cols = [header_row.index(name) for name in data_fields]
        current_vs_time = np.genfromtxt(fname=handle, usecols=data_cols)
        handle.close()

        # For quick lookup so we don't have to convert 'Ns' from float to int on every iteration
        potentials_dict = { float(index): potential for index, potential in enumerate(potentials_by_trial) }
        current_to_resistance = lambda row: [row[1], potentials_dict[row[0]] / row[2]]
        resistance_vs_time = np.array([current_to_resistance(row) for row in current_vs_time])
        # We don't need the trial # field (Ns) anymore, so delete it to free a couple kB
        current_vs_time = np.delete(current_vs_time, obj=0, axis=1)

        technique_start = acquisition_start + timedelta(seconds=current_vs_time[0, 0])
        end_time_by_trial = [total_dur + technique_start for total_dur in total_dur_by_trial]

        return {
            'acquisition_start': acquisition_start,
            'current_vs_time': current_vs_time,
            'resistance_vs_time': resistance_vs_time,
            'end_time_by_trial': end_time_by_trial,
            'potentials_by_trial': potentials_by_trial
        }
