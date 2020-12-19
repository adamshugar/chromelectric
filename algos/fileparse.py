import numpy as np
from datetime import datetime
import re
import os
from utils import filetype

# Using classes in this module purely as additional namespaces; all methods are static
# and classes are not meant to be instantiated.

class GC:
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
    
    @staticmethod
    def parse_list(raw_list, bounds):
        parsed_list = {}
        for index in range(bounds[0], bounds[1] + 1): # Include final file number
            path = raw_list.get(index)
            try:
                handle = open(path, 'r')
            except IOError:
                return index
            else:
                parsed_list[index] = GC.parse_file(handle)
                handle.close()

        return parsed_list

    @staticmethod
    # Using the file inputted by the user, find all other GC files in the run
    # assuming an auto-increment scheme of <filepath>/<shared filename><#>.asc
    def find_list(filepath):
        head, tail = os.path.split(filepath)
        suffix_regex = rf'(\d+)\.(?:{filetype.GC})$'
        user_input_match = re.search(suffix_regex, tail, re.IGNORECASE)
        if user_input_match == None:
            return None # User supplied an invalid file (didn't have <#> suffix)
        shared_filename = tail[:-len(user_input_match.group(0))]

        paths_by_index = {}
        for file in os.listdir(head):
            match = re.search(shared_filename + suffix_regex, file, re.IGNORECASE)
            if match:
                file_num = int(match.group(1))
                paths_by_index[file_num] = os.path.join(head, file)
        return paths_by_index

class CA:
    @staticmethod
    def parse_file(handle):
        handle.readline()
        meta_total_str = handle.readline().rpartition(':')[2].strip() # Total meta count on line 2
        try:
            meta_total = int(meta_total_str)
        except ValueError:
            return None