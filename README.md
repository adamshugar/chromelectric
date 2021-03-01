# Chromelectric

Quickly and accurately compute **partial current density** and **Faradaic efficiency** from your multi-injection experiments in gas chromatography & cyclic amperometry. (For use in electrocatalysis research and related fields.)

# Installation

### Use on Windows and Mac

Simply download and run the executable files for Windows or Mac; no installation necessary. ([What is a frozen executable](https://docs.python-guide.org/shipping/freezing/)?) The executables for Windows 10 and OS X are available through GitHub Releases.

### Use on Linux

For now, on Linux, you'll have to pull the source and directly run `python3 main.py`. Dependencies include `matplotlib` and `PyQt5`.

# Usage Guide

### 1. Input your experimental parameters

Each section in the **General Parameters** tab is described in more detail here.

![The General Parameters tab.](readme_assets/general_params.png?raw=true "The General Parameters tab.")

#### Gas List

- **Reduction count**. The number of electrons required to reduce the feedstock gas to the gas in the current row. For example, it takes 2e<sup>-</sup> to reduce CO2 into CO.
- **Calibration value**. You will need to supply calibration values for each gas of interest on your machine to convert raw peak areas into ppm concentrations.
- **Analysis channel**. FID and TCD are available by default.

#### Faradaic efficiency parameters

- **Total flow rate** and **GC injection volume**. These are used in conjunction to calculate the number of seconds of electrical current flow "represented" by the gas volume being injected into the GC. For example, if it is determined that 2 seconds of current flow is represented by the a given injection, the previous 2 seconds of current are integrated to give the total number of electrons transferred into the injection sample during the sample's time in the cell. This number is used to calculate Faradaic efficiency.
- **Pre-GC mixing volume**. Currently unused.

#### Voltage correction parameters

- **PEIS resistance**. Used as an estimate of the uncompensated resistance (R<sub>u</sub>) of the electrolyte solution.
- All 3 of the parameters in this section are combined to convert the constant voltage applied by the potentiostat into the true, effective voltage in the electrochemical system. Letting _i_ equal the electrical current, the conversion is performed using the following formula:
  > V<sub>eff</sub> = V<sub>ideal</sub> + V<sub>ref vs. SHE</sub> + 0.059·pH - i·R<sub>u</sub>

#### Saving your settings

If the box **Save all above parameters for future runs** is checked (as it is by default), when you press the **Integrate** button in the **File Analysis** tab, these settings are automatically written to a file titled `chromelectric_settings.txt` in the same directory as the executable program. Note that this overwrites whatever file may have previously existed with that name.

Every time the program starts up, it checks for such a file in its same directory, and if one is found, all values specified in **General Parameters** are auto-populated from the settings file.

### 2. Load your injection and CA files

The next step is to choose the list of injection files and the associated cyclic amperometry (CA) file to analyze.

Chromelectric is smart and only needs you to pick one of your injection files to recognize all other files, provided they are in the same directory. It assumes identical naming scheme with a unique injection number at the end of the filename; for example: `Au fid5.asc`, `Au fid6.asc`, and `Au fid7.asc` would all be automatically recognized, while `My 5th injection.asc` would not. It will also let you know if any injection files seem to be missing. Support for FID and TCD, whether simultaneously or one at a time, is available.

![Choose any file from the injection list.](readme_assets/file_list.png?raw=true "Choose any file from the injection list.")
![An example with CA, FID, and TCD files loaded.](readme_assets/file_select.png?raw=true "An example with CA, FID, and TCD files loaded.")

Once loaded, you can view the sequence of all injection files from a given channel in a separate window. You can also overlay multiple injections as pictured below.

![Overlay multiple GC injections.](readme_assets/overlay.png?raw=true "Overlay multiple GC injections.")

When you press the **Integrate** button, all settings from **General Parameters** and all files from **File Analysis** are captured and displayed a new integration window.

### 3. Integrate peaks and adjust as necessary

The key value of Chromelectric is in the interactive integration console. Choose from a linear or high-degree polynomial fit baseline with automatic fitting and baseline subtraction. For now, only trapezoidal integration is available, but Gaussian and Lorentzian peak fitting may be released.

Each peak is labeled with a unique number and its statistics are visible in the sidebar. You can instantly see the Faradaic efficiency for each peak, as well as the overall Faradaic efficiency for a given injection.

Using the **Spread** button, you can apply the same integral -- identical start and end points, channel, and baseline type -- to all other injections in the experiment. This saves time compared to manually integrating each injection, but you can always tweak a peak for a given injection if it doesn't look quite right.

When all integration is finished, the **Write Output** button creates a folder in the same directory as the injection data containing a variety of output files. Most importantly, it creates a spreadsheet containing the partial current density and Faradaic efficiency for each gas by injection number (along with corrected voltage). The folder also includes plots if you chose to generate them, the experimental parameters you used to generate this data, and a detailed accounting of every integrated peak in human-readable format.

![Output folder generated by Chromelectric.](readme_assets/outputs.png?raw=true "Output folder generated by Chromelectric.")

# Future Directions

### Much Needed

- Implement peak deconvolution functionality as described [here](http://www.emilygraceripka.com/blog/16)
- Implement Gaussian and Lorentzian peak fitting in addition to trapezoidal integration (related to peak deconvolution)
- Support other GC file formats in addition to `*.asc` (such as Agilent `*.ch`)

### Nice-to-Haves

- Show suspected min/max retention times on integration graphs so that those input fields are actually useful
- Allow user to choose output folder location and name
- Multithread the GC/CA file reads so the UI thread is never blocked (currently only a problem for reading **many** files or **very large** files)
