# Installing from source

You only need this to work *on* the package. To regrid ISMIP7 output, install
from conda-forge instead (see {doc}`../user/installation`).

Create the conda environment and install the package into it:

```bash
conda env create -f ismip7_interp_env.yml
conda activate ismip7-interp
python -m pip install --no-deps --no-build-isolation -e .
```

`ismip7_interp_env.yml` installs the dependencies — CDO among them — but not
the package itself, so the environment it creates is not the one conda-forge
gives you: an `ismip7-interp` environment made this way holds no
`ismip7-interpolation` package until the `pip install` runs.

```{warning}
**Use those pip flags.** All dependencies come from conda-forge, and a plain
`pip install .` can silently replace them with PyPI wheels — `netCDF4` in
particular bundles its own copy of the netCDF C library — which is exactly how
two people end up with different results from the same files. `--no-deps`
keeps pip from resolving anything, and `--no-build-isolation` builds with the
environment's `setuptools` instead of downloading one from PyPI. Add
`--no-index` if you want any accidental network fetch to fail loudly rather
than succeed quietly.
```

`-e` gives an editable install, which is worth having while developing: the
tests import the installed package, so after a non-editable install, edits to
the source tree do not affect a test run until you reinstall.

(`pytest` and the documentation packages come from the conda environment, so
neither the `[test]` nor the `[docs]` extra is needed; see
{doc}`building-docs`.)

If a rebuild ever behaves as though it were still running older code, delete
the `build/` directory: `setuptools` reuses its contents, so files that have
since been renamed or removed can otherwise end up back in the installed
package.

## Dependencies

Installing from conda-forge pulls these in for you, and you can skip this
section. It matters when you install from source, where the environment is
yours to create.

Versions are constrained in `ismip7_interp_env.yml`; the same constraints
appear in `pyproject.toml`. The suite is tested at both ends of every range,
so results should agree across machines and operating systems within these
bounds.

| Package | Constraint | Why bounded |
|---|---|---|
| `python` | `>=3.11,<3.15` | `X \| None` annotations and `tomllib`; 3.10 is EOL in Oct 2026 |
| `cdo` | `>=2.2` | performs every remapping; `remap`, `gen*` and `setmisstoc` are all long-standing, so the floor is conservative rather than forced |
| `netcdf4` | `>=1.7,<2` | reads NetCDF headers for the inventory |
| `isschecker` | `>=0.2,<1` | ships the ISMIP7 grids and data request — see {doc}`../user/data-sources` |

```{note}
CDO is not in `pyproject.toml`'s `dependencies`, and cannot be: it is not
installable from PyPI. It is a dependency of the conda-forge package and of
`ismip7_interp_env.yml`, and the code reports its absence in as many words
rather than assuming it.
```

If you report a problem, please include the output of `conda list` for your
environment, and `cdo --version`.
