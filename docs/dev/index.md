# Developer guide

Guidance for contributing to the package and for maintaining its releases. If
you only want to regrid ISMIP7 output, you do not need any of this — install
from conda-forge as described in {doc}`../getting-started`.

The repository is laid out like this:

`ismip7_interp/interpolate.py`
: regridding one file, and the `ismip7-interpolate` entry point.

`ismip7_interp/experiment.py`
: one experiment directory, and `ismip7-process-experiment`.

`ismip7_interp/run_all.py`
: a whole archive, and `ismip7-run-all`.

`ismip7_interp/inventory.py`
: the read-only report, and `ismip7-inventory`.

`ismip7_interp/archive.py`
: finding experiments in an archive, and the shapes real archives come in.

`ismip7_interp/variables.py`, `grids.py`, `paths.py`
: which remapping each variable gets, the ISMIP7 grids, and where the data
  files come from.

`ismip7_interp/cdo.py`, `ncfile.py`, `weights.py`
: running CDO, reading NetCDF files, and the remap-weight cache.

`ismip7_interp/data/config/`
: the regridding policy — the only data this package ships. The grids and the
  data request come from `isschecker`; see {doc}`../user/data-sources`.

`tests/`
: the test suite.

`docs/`
: these pages.

```{toctree}
:maxdepth: 2
:caption: Contents

source-install
testing
building-docs
releasing
```
