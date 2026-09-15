# Installation

From a checkout of the repository:

```bash
git clone https://github.com/ismip/ismip7-interpolation.git
cd ismip7-interpolation
conda env create -f ismip7_interp_env.yml
conda activate ismip7-interp
python -m pip install --no-deps --no-build-isolation .
ismip7-interpolate --version
cdo --version
```

The conda environment is the supported way to install, and the only one that
gets you a working CDO. CDO does every remapping; it is a compiled program,
not on PyPI, so a plain `pip install` of the package gives you Python code
with nothing to run it.

```{warning}
**Use those pip flags.** All dependencies come from the conda environment,
and a plain `pip install .` can silently replace them with PyPI wheels —
`netCDF4` in particular bundles its own copy of the netCDF C library — which
is exactly how two people end up with different results from the same files.
`--no-deps` keeps pip from resolving anything, and `--no-build-isolation`
builds with the environment's `setuptools` instead of downloading one from
PyPI.
```

To update, `git pull` and run the `pip install` again.

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

## Working on the package

{doc}`../dev/source-install` covers the editable install and the dependency
ranges.
