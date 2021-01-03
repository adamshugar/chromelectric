# Chromelectric

Quickly and accurately compute **partial current density** and **Faradaic efficiency** from your experiments in gas chromatography & cyclic amperometry. (For use in electrocatalysis research.)

# Use on Windows and Mac

Simply download and run the frozen executables for Windows or Mac; no installation necessary. (What is a frozen executable?) Packaging: use PyInstaller or Py2Exe

# Use on Linux

TODO: Distribute as a package for Linux users to install, perhaps via Conda. (Dependencies on Ubuntu: matplotlib, and PyQt5)

# Future directions

- Implement peak deconvolution functionality as described [here](http://www.emilygraceripka.com/blog/16)
- Support other file formats in addition to `*.asc` (such as Agilent `*.ch`)
- Show suspected min/max retention times on integration graphs so that those input fields are actually useful
- Multithread the GC/CA file reads so the UI thread is never blocked (currently only a problem for reading **many** files or **very large** files)
- Write module to auto-generate GC calibration values from standard
