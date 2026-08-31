"""The standard ISMIP7 target grids, as CDO grid description files."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from ismip7_interp.paths import gdf_dir

#: The two ISMIP7 ice sheet domains.
DOMAINS = ('GrIS', 'AIS')

_GDF_NAME = re.compile(
    r'^gdf_ISMIP7_(?P<domain>[A-Za-z]+)_(?P<res>\d+)m\.txt$')
_SIZE = re.compile(r'^\s*(?P<key>[xy]size)\s*=\s*(?P<value>\d+)\s*$')


class GridError(ValueError):
    """No ISMIP7 grid matches what was asked for."""


def res_dir_name(domain: str, res_m: int) -> str:
    """Return the output directory name for a domain and resolution.

    ``GrIS``, 4000 -> ``GrIS_04000m``.  Output is written under
    ``OUTPUT_ROOT/<res_dir_name>/``, so the resolution lives in one top-level
    directory rather than in every filename.
    """
    return f'{domain}_{res_m:05d}m'


@lru_cache(maxsize=None)
def available_resolutions(domain: str) -> dict[int, Path]:
    """Return every resolution with a grid description file, by resolution."""
    found = {}
    for path in sorted(gdf_dir().glob(f'gdf_ISMIP7_{domain}_*.txt')):
        match = _GDF_NAME.match(path.name)
        if match and match.group('domain') == domain:
            found[int(match.group('res'))] = path
    return found


def gdf_path(domain: str, res_m: int) -> Path:
    """Return the grid description file for a domain and resolution."""
    grids = available_resolutions(domain)
    if res_m not in grids:
        known = ', '.join(str(res) for res in sorted(grids)) or 'none'
        raise GridError(
            f'no ISMIP7 grid for domain={domain} resolution={res_m}m '
            f'(known {domain} resolutions: {known})')
    return grids[res_m]


@lru_cache(maxsize=None)
def gdf_dims(path: Path) -> tuple[int, int]:
    """Return the ``(xsize, ysize)`` declared by a grid description file."""
    sizes: dict[str, int] = {}
    for line in Path(path).read_text().splitlines():
        match = _SIZE.match(line)
        if match:
            sizes.setdefault(match.group('key'), int(match.group('value')))
    if 'xsize' not in sizes or 'ysize' not in sizes:
        raise GridError(f'could not parse xsize/ysize from {path}')
    return sizes['xsize'], sizes['ysize']


def detect_res_from_dims(domain: str, dims: tuple[int, int]) -> int | None:
    """Return the ISMIP7 resolution whose grid has these dimensions.

    ``None`` if no grid for ``domain`` matches -- a source grid is never
    guessed.
    """
    for res_m, path in sorted(available_resolutions(domain).items()):
        if gdf_dims(path) == tuple(dims):
            return res_m
    return None
