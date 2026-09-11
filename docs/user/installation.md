# Installation

```bash
conda create -n ismip7-interp -c conda-forge ismip7-interpolation
conda activate ismip7-interp
ismip7-interpolate --version
cdo --version
```

This is the supported way to install, and the only one that gets you a
working CDO. CDO does every remapping; it is a compiled program, not on PyPI,
so `pip install ismip7-interpolation` gives you Python code with nothing to
run it.

## What comes with it

| Package | Role |
|---|---|
| cdo | does every remapping |
| netcdf4 | reads NetCDF headers for the inventory |
| isschecker | ships the ISMIP7 grid definitions and data request; see {doc}`data-sources` |

## If cdo is not found

Either the environment is not active, or CDO was installed somewhere that is
not on your PATH. The commands say so in as many words rather than failing
obscurely.

## Installing from source

Only needed to work on the package itself; see {doc}`../dev/source-install`.
