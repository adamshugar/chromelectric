from tkinter import messagebox, simpledialog, filedialog

# Prompts for (lower_bound, upper_bound) pair of ints. Must have non-negative lower bound.
def prompt_bound_tuple(tuple_name, lower_msg, upper_msg):
    valid_lower = False
    while not valid_lower:
        lower = simpledialog.askinteger(f'Lower bound for {tuple_name}', lower_msg)
        if lower == None:
            return None
        elif lower < 0:
            messagebox.showinfo(
                'Invalid lower bound',
                (f'Minimum value must be non-negative. '
                f'You entered {lower}.'))
        else:
            valid_lower = True
    
    valid_upper = False
    while not valid_upper:
        upper = simpledialog.askinteger(f'Upper bound for {tuple_name}', upper_msg)
        if upper == None:
            return None
        elif upper <= lower:
            messagebox.showinfo(
                'Invalid upper bound',
                ('Maximum value must larger than '
                f'minimum value ({lower}). '
                f'You entered {upper}.'))
        else:
            valid_upper = True
    
    return (lower, upper)

# Given a label (e.g. "GC file") and filetype (e.g. ".asc"),
# prompt the user to choose a file of the supplied filetype.
def prompt_filepath(label, type, msg_detail = ''):
    file_picked = False
    while not file_picked:
        try:
            detail_str = f' {msg_detail}' if len(msg_detail) > 0 else ''
            path = filedialog.askopenfilename(
                title=f'Select a {label} file.{detail_str}',
                filetypes=[(label, type)])
            handle = open(path, 'r') # Check that file is openable
            file_picked = True
        except IOError as err:
            should_retry = messagebox.askretrycancel(
                'Unable to open file',
                f'Error while opening {label} file. {err.strerror}.')
            if not should_retry:
                return None
    handle.close()
    return path