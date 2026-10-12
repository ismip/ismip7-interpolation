# Installation

## From conda-forge

The tools are packaged on
[conda-forge](https://anaconda.org/conda-forge/ismip7-interpolation), for
Linux and macOS. Nothing is built and there is no need to clone the
repository:

```bash
conda create -n ismip7-interp -c conda-forge ismip7-interpolation
conda activate ismip7-interp
ismip7-interpolate --version
cdo --version
```

`mamba` and `micromamba` work the same way. If your conda is set up with the
`defaults` channel, add `--override-channels`; packages from the two channels
do not mix.

The package installs the four commands, and brings CDO with it, which does
every remapping. CDO is not on PyPI, so `pip install` cannot give you a
working install.

## Updating

```bash
conda update -n ismip7-interp -c conda-forge ismip7-interpolation
```

The conda-forge package is built from tagged releases, so it can be a release
behind the repository. Quote the output of `ismip7-interpolate --version` when
you report a problem.

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

## From source

You only need a source install to work *on* the package: to test a change
that has not been released yet, or to develop one. {doc}`../dev/source-install`
covers it.
