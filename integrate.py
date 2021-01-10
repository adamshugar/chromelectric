import numpy as np
from numpy.polynomial.polynomial import Polynomial

BASELINE_COLOR = '#AC53FF'

def index_bounds(data, start_value, end_value):
    """
    Given a 1D numpy array of floats and start and end values (assumed to be contained in the array),
    return as a tuple the indices of the start and end values.
    """
    start_index = np.where(np.isclose(data, start_value))[0][0]
    end_index = np.where(np.isclose(data, end_value))[0][0]
    return (start_index, end_index)

def get_baseline(x_data, y_data, peak_start_index, peak_end_index):
    """
    Given an arbitrary function represented as 1D x and y numpy arrays, and start and end indices
    within these arrays denoting a user-identified peak, compute a reasonable baseline for the peak.

    Considers points up to 1/2 of peak width (at maximum) on either side of the peak when creating the baseline.
    Fits a high-degree polynomial to these 2D lines on either side of the peak.

    Returns a numeric version of the polyfitted baseline (numpy array of (x, y) coords), a pure version
    (polynomial coefficients - N.B. locally centered and scaled for numerical stability), and the indices
    within the baseline numeric array where the peak starts and ends, as a 4-tuple.
    """
    POLYFIT_DEGREE = 7

    peak_size = peak_end_index - peak_start_index + 1 # Peak size, in number of data points contained within
    # Include number of points equal to half of peak size on either side for polynomial baseline fit
    prefix_range = np.arange(max(0, peak_start_index - peak_size // 2), peak_start_index)
    postfix_range = np.arange(peak_end_index + 1, min(x_data.size, peak_end_index + 2 + peak_size // 2))

    # Edge cases (literally) - we want to have at least one point on either side of the peak
    size_correction_start = size_correction_end = 0
    if peak_start_index == 0:
        prefix_range = np.array([peak_start_index])
        size_correction_start = -1
    if peak_end_index == x_data.size - 1:
        postfix_range = np.array([peak_end_index])
        size_correction_end = -1
    baseline_indices = np.concatenate([prefix_range, postfix_range])

    # Now we do a least squares polyfit to the data on either side of the peak to establish a baseline.
    # Numpy allows us to multiply the squared error contribution of each point by a weight factor -
    # we choose this factor to be the ratio of the number of points on the opposite side of the peak to the
    # number of points on this side. This ensures for example that if we have 3 points on the prefix side
    # and 500 points on the postfix side, then those 3 points are weighted very heavily.
    # Note also that if we are not near either edge of the graph (as in most cases), all weights are 1.
    prefix_weight = postfix_range.size / prefix_range.size
    postfix_weight = 1 / prefix_weight
    weights = np.concatenate([np.full(prefix_range.size, prefix_weight), np.full(postfix_range.size, postfix_weight)])
    baseline_x, baseline_y = x_data[baseline_indices], y_data[baseline_indices]

    poly_pure = Polynomial.fit(baseline_x, baseline_y, POLYFIT_DEGREE, w=weights)
    baseline_size = prefix_range.size + postfix_range.size + peak_size + \
        size_correction_start + size_correction_end # Size in number of data points
    poly_numeric = poly_pure.linspace(baseline_size) # Convert pure representation (coefficients) into graphable version

    # Get the indices within the baseline array where the peak starts and ends
    baseline_peak_start = prefix_range.size + size_correction_start
    baseline_peak_end = baseline_peak_start + peak_size # 1 after true end (as in a range)

    return (poly_numeric, poly_pure, baseline_peak_start, baseline_peak_end)

def correct_for_baseline(x_data, y_data, peak_start_x, peak_end_x):
    """
    Given an arbitrary 2D function and start and end x values for a user-identified peak within the function,
    compute a suitable baseline for the peak and correct for the baseline (subtract baseline from peak).

    Returns a corrected peak function which can be numerically integrated and both numeric and pure representations
    of the baseline.
    """
    peak_start_index, peak_end_index = index_bounds(x_data, peak_start_x, peak_end_x)
    baseline_numeric, baseline_pure, baseline_peak_start, baseline_peak_end = \
        get_baseline(x_data, y_data, peak_start_index, peak_end_index)
    _, baseline_y = baseline_numeric

    peak_range = np.arange(peak_start_index, peak_end_index + 1)
    peak_x, peak_y = x_data[peak_range], y_data[peak_range]
    baseline_peak_y = baseline_y[np.arange(baseline_peak_start, baseline_peak_end)]
    corrected_peak_y = peak_y - baseline_peak_y

    return {
        'peak': (peak_x, corrected_peak_y),
        'baseline': (baseline_numeric, baseline_pure),
    }

def draw_point(coords, axes):
    """Draw a single (x, y) point on the given axes. Meant to draw points relevant in a given integration."""
    return axes.plot(coords[0], coords[1], color=BASELINE_COLOR, marker='o', markersize=6)[0]

def draw_integral(x_data, y_data, integral, axes, display_index, render_func, draw_points=False):
    """Convenience function to draw an integral and optional draw the points associated with it."""
    artists = render_func(x_data, y_data, integral, axes)

    if draw_points:
        for point in integral['points']:
            artists.append(draw_point(point, axes))

    artists.append(draw_annotation(integral, y_data, axes, display_index))

    return artists

def draw_annotation(integral, y_data, axes, display_index):
    """Draw an annotation of the supplied peak including its index number and return the resulting artist."""
    peak_start, peak_end = integral['points']
    y_range = np.max(y_data) - np.min(y_data)
    return axes.annotate(
        str(display_index), (peak_end[0], peak_end[1] + y_range // 8), ha="center", va="center", size=9,
        bbox=dict(boxstyle="round,pad=0.3", facecolor="#ffffff80", edgecolor="#cccccc", linewidth=2))

def trapz(x_data, y_data, points):
    """
    Integrates a peak trapezoidally, given the full x vs. y graph and a list of points inputted by the user.
    Note that this list of points can be interpretted differently for different integration methods.

    Returns a dictionary containing the area of the peak, the user-selected start and end x coordinates of the peak,
    and both numeric (many (x, y) pairs) and pure (polynomial coefficients) forms for the baseline.
    """
    peak_start = points[0] if points[0][0] < points[1][0] else points[1]
    peak_end = points[1] if points[0][0] < points[1][0] else points[0]

    corrected = correct_for_baseline(x_data, y_data, peak_start[0], peak_end[0])
    peak_x, corrected_peak_y = corrected['peak']
    baseline_numeric, baseline_pure = corrected['baseline']

    area = np.trapz(corrected_peak_y, peak_x)

    return {
        'area': area,
        'baseline': (baseline_numeric, baseline_pure),
        'points': (peak_start, peak_end),
    }

def trapz_draw(x_data, y_data, integral, axes):
    """
    Given a trapezoidal integration result (from `trapz_integrate`) and an `axes` object to draw to,
    draw a representation of the trapezoidal integration. In particular, draw the baseline and fill
    all positive area with blue and all negative area with red.

    Returns a list of all artists drawn for later cleanup.
    """
    (baseline_x, baseline_y), _ = integral['baseline']
    graph_fill_start, graph_fill_end = index_bounds(x_data, baseline_x[0], baseline_x[-1])
    graph_fill_y = y_data[np.arange(graph_fill_start, graph_fill_end + 1)]
    baseline, = axes.plot(baseline_x, baseline_y, color=BASELINE_COLOR)
    pos_fill = axes.fill_between(baseline_x, baseline_y, graph_fill_y, where=(baseline_y < graph_fill_y), color='#38A9FF', interpolate=True)
    neg_fill = axes.fill_between(baseline_x, baseline_y, graph_fill_y, where=(baseline_y > graph_fill_y), color='#FF4A38', interpolate=True)
    return [baseline, pos_fill, neg_fill]

def line2d_point(pick_event):
    """
    Given a user pick event on a Line2D matplotlib object, return the most likely (x, y) coordinate
    on the line to which the user was referring.
    """
    points_clicked = pick_event.ind # numpy array containing all points clicked, by index
    if points_clicked.size <= 5:
        # Find closest point to actual mouse click
        actual_click = (pick_event.mouseevent.xdata, pick_event.mouseevent.ydata)
        pick_index = min(points_clicked, key=lambda pt: abs(np.linalg.norm(pt - actual_click)))
    else:
        # Pick middle point; user is too zoomed out to pick at a granular level
        pick_index = points_clicked[points_clicked.size // 2]
    line = pick_event.artist
    return (line.get_xdata()[pick_index], line.get_ydata()[pick_index])

def interpret_integral(integral, total_gas_mol, mol_e, calib_val, reduction_count, avg_current):
    """
    Given an integrated peak and the physical parameters relevant to the injection, physically
    interpret the peak and return an integral object with additional fields to reflect
    the results of these calculations.
    """
    current_peak_mol = total_gas_mol * (1e-6 * integral['area'] / calib_val) # 1e-6 for ppm to fraction
    max_mol = mol_e / reduction_count
    faradaic_eff = (current_peak_mol / max_mol) * 100 # Convert from fraction to percentage
    partial_current = faradaic_eff * avg_current
    return {
        **integral,
        'moles': current_peak_mol,
        'faradaic_efficiency': faradaic_eff,
        'partial_current': partial_current
    }
