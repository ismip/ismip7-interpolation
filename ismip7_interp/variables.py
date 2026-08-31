"""Per-variable remapping policy for the ISMIP7 data request.

Two kinds of fact live here.  Which variables exist, which are mandatory and
which have no spatial grid come from the ISMIP7 data request, which is
maintained in `ISM_SimulationChecker
<https://github.com/ismip/ISM_SimulationChecker>`_ and read here out of the
installed ``isschecker`` package rather than copied into this one -- a copy is
a thing that can drift, and an earlier one silently did.  Which remapping
algorithm each variable needs, and whose missing-value mask must be preserved,
are decisions specific to regridding and are configured in ``data/config/``.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

from ismip7_interp.paths import MissingDataError, config_dir, \
    variable_request_path

#: Column headings this module relies on in the data request CSV.  Checked on
#: every read so that an upstream rename fails here, loudly, rather than
#: quietly emptying the mandatory or scalar list.
_REQUIRED_COLUMNS = ('Variable Name', 'Dim', 'Mandatory (yes/no)')

#: Remapping algorithms, as the short names used on the command line, mapped to
#: the CDO operator that applies precomputed weights and the one that generates
#: them.
METHODS = {
    'ycon': ('remapycon', 'genycon'),
    'bil': ('remapbil', 'genbil'),
    'nn': ('remapnn', 'gennn'),
}

#: Returned by :func:`interp_method` for a variable that has no spatial grid to
#: remap at all.  Not a CDO operator -- such a file is placed unchanged.
COPY = 'copy'


class DataRequestError(MissingDataError):
    """The ISMIP7 data request could not be read, or lacks a needed column."""


def read_name_list(path: Path) -> tuple[str, ...]:
    """Read a configuration file of one variable name per line.

    Blank lines and ``#`` comments are ignored, so the files can carry the
    reasoning for their contents alongside them.
    """
    if not path.is_file():
        raise FileNotFoundError(f'variable list not found: {path}')
    names = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            names.append(line)
    return tuple(names)


@lru_cache(maxsize=None)
def variable_request() -> tuple[dict[str, str], ...]:
    """Return the ISMIP7 data request, one dict per variable."""
    path = variable_request_path()
    with open(path, newline='') as handle:
        reader = csv.DictReader(handle)
        missing = [column for column in _REQUIRED_COLUMNS
                   if column not in (reader.fieldnames or ())]
        if missing:
            raise DataRequestError(
                f'{path} has no {", ".join(missing)} column(s); the ISMIP7 '
                f'data request has changed shape and this package needs '
                f'updating')
        return tuple(dict(row) for row in reader)


@lru_cache(maxsize=None)
def mandatory_variables() -> frozenset[str]:
    """Return the variables the data request marks as mandatory."""
    return frozenset(
        row['Variable Name'].strip() for row in variable_request()
        if row['Mandatory (yes/no)'].strip().lower() == 'yes')


@lru_cache(maxsize=None)
def scalar_variables() -> frozenset[str]:
    """Return the variables that have no spatial grid and cannot be regridded.

    Derived from the data request's ``Dim`` column rather than listed by hand:
    a variable with no ``x`` among its dimensions (``lim``, ``iareagr``, the
    ``tend*`` fluxes -- domain-integrated time series) has no grid for
    ``cdo setgrid``/``remap`` to work on.  Such a file is placed in the output
    unchanged, whatever the target resolution.
    """
    scalar = set()
    for row in variable_request():
        dims = {dim.strip() for dim in row['Dim'].split(',')}
        if 'x' not in dims:
            scalar.add(row['Variable Name'].strip())
    return frozenset(scalar)


@lru_cache(maxsize=None)
def bilinear_variables() -> frozenset[str]:
    """Return the variables remapped bilinearly instead of conservatively."""
    return frozenset(read_name_list(config_dir() / 'bilinear_variables.txt'))


@lru_cache(maxsize=None)
def nearest_variables() -> frozenset[str]:
    """Return the variables remapped by nearest neighbour."""
    return frozenset(read_name_list(config_dir() / 'nearest_variables.txt'))


@lru_cache(maxsize=None)
def mask_missing_variables() -> frozenset[str]:
    """Return the variables whose missing-value mask must be preserved."""
    return frozenset(
        read_name_list(config_dir() / 'mask_missing_variables.txt'))


def interp_method(variable: str) -> str:
    """Return the remapping to use for ``variable``.

    One of the keys of :data:`METHODS`, or :data:`COPY` for a variable with no
    spatial grid.
    """
    if variable in scalar_variables():
        return COPY
    if variable in bilinear_variables():
        return 'bil'
    if variable in nearest_variables():
        return 'nn'
    return 'ycon'


def use_setmisstoc(variable: str) -> bool:
    """Return whether ``variable``'s missing cells may be filled with 0.

    Filling makes the source field's missing-value mask uniform across
    timesteps and files, which is what lets remap weights be computed once per
    (domain, source resolution, target resolution, method) and reused.  It is
    wrong for the few variables where 0 is not a physically meaningful value
    outside the ice sheet -- ice velocity, rather than ice thickness -- which
    ``data/config/mask_missing_variables.txt`` lists.
    """
    return variable not in mask_missing_variables()


def var_from_filename(path: Path | str) -> str:
    """Return the ISMIP7 variable name encoded in a file's name.

    The first ``_``-separated token, per the ISMIP7 convention
    ``{var}_{region}_{project}_{submission}_...nc``.
    """
    return Path(path).name.split('_')[0]
