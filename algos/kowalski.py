"""Given a list of gases with minimum and maximum bounds on retention time, find all overlaps
between these bounds. Runs in O(n^2); faster than asymptotically optimal (but more complex)
solutions, since we only ever deal with a few gases.
E.g. { 'CO2': (1, 10), 'H2': (9, 12), 'C2H4': (100, 130) } -> { 'CO2': ['H2'], 'H2': ['CO2'], 'C2H4': [] }"""
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
