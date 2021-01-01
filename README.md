# Chromelectric

Quickly and accurately compute **partial current density** and **Faradaic efficiency** from your experiments in gas chromatography & cyclic amperometry. (For use in electrocatalysis research.)

# Use on Windows and Mac

Simply download and run the frozen executables for Windows or Mac; no installation necessary. (What is a frozen executable?) Packaging: use PyInstaller or Py2Exe

# Use on Linux

TODO: Distribute as a package for Linux users to install. (Dependencies on Ubuntu: matplotlib, and PyQt5) Potentially distribute via Conda

# Future directions

- Implement peak deconvolution functionality as described [here](http://www.emilygraceripka.com/blog/16). Locally fit to a high degree polynomial to find the baseline. Maybe also examine the second derivative value; if it gets too high, it is peak and not baseline.
- Show suspected min/max retention times on integration graphs so that those input fields are actually useful
- Multithread the GC/CA file reads so the UI is never blocked (currently only a problem for reading **many** files or **very large** files)
- Support other file formats in addition to `*.asc` (such as Agilent `*.ch`)
- Write module to auto-generate GC calibration values from standard
