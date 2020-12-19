""" Basic utility functions. """

def is_nonnegative_int(str):
    # Use regex instead of built-in isnumeric() because isnumeric() accepts exponents and fractions.
    return re.match(r'^[0-9]+$', str) != None

def is_nonnegative_float(str):
    return re.match(r'^\d+(\.\d*)?$', str) != None

def safe_int(str):
    try:
        return int(str)
    except ValueError:
        return None

def find_contiguous_sequence(nums):
    """ Given an unordered list of non-negative, unique integers, finds the contiguous sequence
    of ints of any length with the smallest lower bound. Returns the lower and upper bounds
    of this sequence as a tuple (inclusive). Also find the next highest int in the list
    that is not included in the run, if it exists. Assumes valid input list of ints with
    length greater than zero. LeetCode easy. """
    nums.sort()
    upper_bound = 0
    while upper_bound < len(nums) - 1 and nums[upper_bound + 1] == nums[upper_bound] + 1:
        upper_bound += 1
    next_highest = nums[upper_bound + 1] if upper_bound < len(nums) - 1 else None
    return {
        'bounds': (nums[0], nums[upper_bound]),
        'next_highest': next_highest
    }

class filetype:
    GC = 'asc'
    CA = 'mpt'