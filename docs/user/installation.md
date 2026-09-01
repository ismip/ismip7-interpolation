# Installation

```bash
conda create -n ismip7-interp -c conda-forge ismip7-interpolation
conda activate ismip7-interp
```

This is the supported way to install the tools, and the only one that gets you
a working CDO.

## Why conda and not pip

[CDO](https://mpimet.mpg.de/cdo) performs every remapping this package does.
It is a compiled program, not a Python library, and it is not on PyPI — so
`pip install ismip7-interpolation` gives you the Python code with nothing to
run it. The commands then report that CDO is missing rather than failing
obscurely, but they cannot regrid anything.

The same argument applies to `netCDF4`, whose PyPI wheels bundle their own copy
of the netCDF C library: mixing those with a conda-forge CDO is how two people
end up with different results from the same files.

## What comes with it

| Package | Why |
|---|---|
| `cdo` | performs every remapping; nothing works without it |
| `netcdf4` | reads NetCDF headers for the inventory, without reading data |
| `isschecker` | ships the ISMIP7 grid definitions and data request — see {doc}`data-sources` |

## Check the install

```bash
ismip7-interpolate --version
cdo --version
```

If `cdo` is not found, the environment is not active, or CDO was installed
somewhere that is not on `PATH`. Every command reports this in as many words
rather than failing part-way through a run.

## Installing from source

Only needed to work *on* the package — see {doc}`../dev/source-install`.
