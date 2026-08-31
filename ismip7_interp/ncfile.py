"""Reading what regridding needs to know out of a NetCDF file.

Two ways of finding a file's spatial dimensions live here, and the difference
between them matters.

:func:`grid_dims` asks CDO.  It is what the regridding path uses, because CDO
is what performs the regrid: a file CDO cannot open has to fail here rather
than fail later, halfway through a run.

:func:`header_grid_dims` reads the header with ``netCDF4``.  It is what the
read-only inventory uses.  It touches only the declared dimensions, never the
data, so its cost does not scale with file size -- on a real 1.2 GB experiment
file that is the difference between milliseconds and seconds, across thousands
of files.  It also has no opinion about dimension order, so it reads files CDO
refuses (the archive holds a whole submission whose files trip CDO's "time
must be the first dimension" check).  The inventory is explicitly a report on
what is *there*, so reading more files than CDO can is the right trade; it
means the inventory cannot promise that a file it read will regrid.
"""

from __future__ import annotations

import re
from pathlib import Path

import netCDF4

from ismip7_interp import cdo
from ismip7_interp.cdo import CdoError

_GRIDID = re.compile(r'^#\s*gridID')
_GRIDDES_SIZE = re.compile(r'^\s*(?P<key>[xy]size)\s*=\s*(?P<value>\d+)')


class NetCDFError(RuntimeError):
    """A NetCDF file could not be read."""


def parse_griddes_dims(text: str) -> tuple[int, int] | None:
    """Return ``(xsize, ysize)`` from the output of ``cdo griddes``.

    ``None`` when the file has no two-dimensional grid at all, which is the
    normal case for a scalar time series.

    ``cdo griddes`` prints one block per grid in the file, and a file commonly
    carries a bounds pseudo-grid (``xsize`` but no ``ysize``, for
    ``time_bnds``) alongside the real one.  The first block with *both* sizes
    is the spatial grid; matching the first ``xsize`` alone finds the bounds
    grid instead.
    """
    sizes: dict[str, int] = {}
    for line in text.splitlines():
        if _GRIDID.match(line):
            if 'xsize' in sizes and 'ysize' in sizes:
                return sizes['xsize'], sizes['ysize']
            sizes = {}
            continue
        match = _GRIDDES_SIZE.match(line)
        if match:
            sizes.setdefault(match.group('key'), int(match.group('value')))
    if 'xsize' in sizes and 'ysize' in sizes:
        return sizes['xsize'], sizes['ysize']
    return None


def grid_dims(path: Path) -> tuple[int, int] | None:
    """Return ``(xsize, ysize)`` for a file, via ``cdo griddes``.

    ``None`` if the file opens but holds no spatial grid.  Raises
    :class:`NetCDFError` if CDO cannot read the file at all: the archive holds
    stray non-ISMIP7 files, and one of those must not be mistaken for a
    perfectly good scalar variable.
    """
    try:
        described = cdo.run_cdo(['-s', 'griddes', str(path)], capture=True)
    except CdoError as exc:
        raise NetCDFError(
            f'cdo could not read a grid from {path} (corrupt or non-standard '
            f'file?): {exc}') from exc
    return parse_griddes_dims(described)


def header_grid_dims(path: Path) -> tuple[int, int] | None:
    """Return ``(xsize, ysize)`` for a file, from its header alone.

    The sizes of the dimensions named ``x`` and ``y``, per the ISMIP7
    convention; ``None`` if either is absent, which is the normal case for a
    scalar time series.  Raises :class:`NetCDFError` if the file cannot be
    opened.
    """
    try:
        with netCDF4.Dataset(path) as dataset:
            dims = dataset.dimensions
            if 'x' not in dims or 'y' not in dims:
                return None
            return len(dims['x']), len(dims['y'])
    except OSError as exc:
        raise NetCDFError(
            f'could not read {path} (corrupt or non-standard file?): '
            f'{exc}') from exc


def parse_info_missing_count(text: str) -> int:
    """Return the total missing-value count in the output of ``cdo info``.

    Each data row is ``N : Date Time Level Gridsize Miss : Min Mean Max :
    Name``, so ``Miss`` is the seventh whitespace-separated field.  The header
    row has no leading record number and is skipped by requiring one.
    """
    total = 0
    for line in text.splitlines():
        fields = line.split()
        if len(fields) < 7 or fields[1] != ':':
            continue
        try:
            total += int(fields[6])
        except ValueError:
            continue
    return total


def has_missing_values(path: Path) -> bool:
    """Return whether a file has a missing value anywhere in it.

    This reads the data, so it is not cheap; it is asked only for the few
    variables whose mask must be preserved, to find out whether there is in
    fact a mask to preserve.  A file CDO cannot read raises rather than
    answering "no": answering "no" would send it down the cached-weights path,
    which is the wrong one for a file with a mask.
    """
    try:
        described = cdo.run_cdo(['-s', 'info', str(path)], capture=True)
    except CdoError as exc:
        raise NetCDFError(
            f'cdo could not report on {path}, so whether its missing-value '
            f'mask must be preserved is unknown: {exc}') from exc
    return parse_info_missing_count(described) > 0


def file_size(path: Path) -> int:
    """Return a file's size in bytes."""
    return Path(path).stat().st_size
