"""Locating the data files this package reads.

Two directories, from two packages, and the split is deliberate.

The ISMIP7 grid definitions and the ISMIP7 data request are the project's, not
this tool's.  They are maintained in `ISM_SimulationChecker
<https://github.com/ismip/ISM_SimulationChecker>`_ and read out of the
installed ``isschecker`` package rather than copied into this one.  A copy is a
thing that can drift, and an earlier copy of both silently did; worse, drift in
the grids would be invisible -- the checker would validate submissions against
a revised grid while this tool went on regridding onto the old one.

What *is* this package's own is the regridding policy in ``data/config/``:
which variables need bilinear or nearest-neighbour remapping rather than
conservative, whose missing-value mask must be preserved, and which experiment
sets are open.  None of that is part of the data request, and none of it
belongs to the checker.

``importlib.resources`` hands back a ``Traversable``, which need not be a real
file on disk.  CDO is a subprocess and can only be given a filesystem path, so
each directory is materialised once, on first use, and kept for the life of the
process.
"""

from __future__ import annotations

import atexit
from contextlib import ExitStack
from functools import lru_cache
from importlib import resources
from pathlib import Path

#: This package's own data: the regridding policy.
DATA_PACKAGE = f'{__package__}.data'

#: The ISMIP7 project's data, maintained in ISM_SimulationChecker.
ISSCHECKER_DATA_PACKAGE = 'isschecker.data'


class MissingDataError(RuntimeError):
    """A data directory this package reads is not where it should be."""


@lru_cache(maxsize=None)
def _materialise(package: str) -> Path:
    """Return the on-disk path of a data package's directory."""
    try:
        traversable = resources.files(package)
    except ModuleNotFoundError as exc:
        raise MissingDataError(
            f'{package} is not installed.  The ISMIP7 grid definitions and '
            f'data request are read from the isschecker package rather than '
            f'copied into this one; install ismip7-interpolation from '
            f'conda-forge, which brings it, or add isschecker to your '
            f'environment.') from exc
    stack = ExitStack()
    atexit.register(stack.close)
    return Path(stack.enter_context(resources.as_file(traversable)))


def config_dir() -> Path:
    """Return the directory holding this package's regridding policy."""
    return _materialise(DATA_PACKAGE) / 'config'


def gdf_dir() -> Path:
    """Return the directory holding the ISMIP7 grid description files."""
    directory = _materialise(ISSCHECKER_DATA_PACKAGE) / 'gdfs'
    if not directory.is_dir():  # pragma: no cover - install error
        raise MissingDataError(
            f'isschecker is installed but ships no grid definitions at '
            f'{directory}')
    return directory


def variable_request_path() -> Path:
    """Return the path of the ISMIP7 variable request."""
    path = (_materialise(ISSCHECKER_DATA_PACKAGE)
            / 'ISMIP7_variable_request.csv')
    if not path.is_file():  # pragma: no cover - install error
        raise MissingDataError(
            f'isschecker is installed but ships no data request at {path}')
    return path
