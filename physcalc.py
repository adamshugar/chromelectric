"""Physical calculation module. Largely responsible for converting peak areas into useful data."""
import numpy as np
from math import nan

def average_current(cyclic_amp, end_time, duration):
    """
    Return the average current (from CA file in `cyclic_amp`) over the specified `duration` (seconds),
    where the final timestamp is no greater than `end_time` (must be a datetime object).
    """
    # NOTE: Time field represents seconds offset from acquisition start.
    target_end = (end_time - cyclic_amp['acquisition_start']).total_seconds()
    target_start = target_end - duration
    time_column = cyclic_amp['current_vs_time'][:, 0]
    if target_start > time_column[-1] or target_end < time_column[0]:
        return nan

    start_index, end_index = [np.searchsorted(time_column, target) for target in (target_start, target_end)]
    return np.mean(cyclic_amp['current_vs_time'][start_index:end_index + 1, 1])

def electrons_from_amps(A, t):
    """
    Given a current in amperes and a duration of time, return the number of moles of electrons.
    """
    # Shoutout to my main man Mikey F
    F = 96485.34 # Faraday's constant: Coulombs / mol electron
    return -A * t / F

def ideal_gas_moles(V=1, P=1, T=298):
    """
    Calculated using PV = nRT at standard conditions (298 K, 1 atm).
    """
    R = 0.082057 # L * atm / (mol * K)
    return P * V / (R * T)

def correct_voltage(V, I, Ru, pH, deviation):
    """
    Correct the supplied uncorrected voltage using solution pH, uncompensated solution resistance (R_u)
    determined from PEIS, and reference electrode difference from true reference (SHE)
    """
    # RHE is a generalization of SHE (defined at pH = 0) and this value is calculated from the
    # Nernst equation.
    V_per_pH = -0.059
    return V + deviation - V_per_pH * pH - I * Ru
    