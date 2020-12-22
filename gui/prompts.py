""" Extra functionality for simple tkinter dialogs/prompts available
here: https://docs.python.org/3/library/tkinter.messagebox.html.
In particular, extends ask<options> methods to show any type of icon
(question icon is immutable default in standard implementation).
Copied '_show' implementation from:
https://github.com/python/cpython/blob/3.9/Lib/tkinter/messagebox.py
so that our use of internal '_show' method isn't broken by future
tkinter updates. """
from tkinter.commondialog import Dialog

# Icons / dialog styles
ERROR = "error"
INFO = "info"
QUESTION = "question"
WARNING = "warning"
YES = "yes"
NO = "no"

# Responses
_ABORT = "abort"
_RETRY = "retry"

# Option types
_ABORTRETRYIGNORE = "abortretryignore"
_RETRYCANCEL = "retrycancel"

class Message(Dialog):
    command  = "tk_messageBox"

# Rename _icon and _type options to allow overriding them in options
def _show(title=None, message=None, _icon=None, _type=None, **options):
    if _icon and "icon" not in options:    options["icon"] = _icon
    if _type and "type" not in options:    options["type"] = _type
    if title:   options["title"] = title
    if message: options["message"] = message
    res = Message(**options).show()
    # In some Tcl installations, yes/no is converted into a boolean.
    if isinstance(res, bool):
        if res:
            return YES
        return NO
    # In others we get a Tcl_Obj.
    return str(res)

def retrycancel(title=None, message=None, style=QUESTION, **options):
    "Show an error message with retry and cancel options for the user."
    result = _show(title, message, style, _RETRYCANCEL, **options)
    return result == _RETRY

def abortretryignore(title=None, message=None, style=QUESTION, **options):
    "Show a warning message with abort, retry, and ignore options for the user."
    result = _show(title, message, style, _ABORTRETRYIGNORE, **options)
    # result might be a Tcl index object, so convert it to a string
    result = str(result)
    if result == _ABORT:
        return None
    return result == _RETRY