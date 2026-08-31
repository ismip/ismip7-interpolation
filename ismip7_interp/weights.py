"""The cache of CDO remap weights.

Conservative remapping weights are expensive to compute and depend only on the
geometry of the two grids -- not on the data -- once the source field's
missing-value mask has been made uniform (see
:func:`~ismip7_interp.variables.use_setmisstoc`).  So one weight file per
(domain, source resolution, target resolution, method) is generated on first
use and reused by every file after it, instead of CDO recomputing weights for
every file in the archive.

Weights are generated from a synthetic constant field on the source grid, not
from an archive file: the geometry is all that matters, and it keeps the
read-only archive out of the loop entirely.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path

from ismip7_interp import cdo
from ismip7_interp.grids import gdf_path
from ismip7_interp.variables import METHODS

LOGGER = logging.getLogger(__name__)

#: Environment variable overriding where weights are cached.
WEIGHTS_DIR_ENV = 'ISMIP7_INTERP_WEIGHTS_DIR'


def default_weights_dir() -> Path:
    """Return the directory weights are cached in when none is given.

    A user cache directory rather than somewhere inside the installation: the
    package may well be installed read-only, and the cache is reproducible from
    the grid definitions alone, so it is never something to back up.
    """
    override = os.environ.get(WEIGHTS_DIR_ENV)
    if override:
        return Path(override)
    cache_home = os.environ.get('XDG_CACHE_HOME')
    base = Path(cache_home) if cache_home else Path.home() / '.cache'
    return base / 'ismip7-interpolation' / 'weights'


def weight_file_path(weights_dir: Path, domain: str, source_res: int,
                     target_res: int, method: str) -> Path:
    """Return the cached weight file for one grid pair and method."""
    return Path(weights_dir) / (
        f'{domain}_{source_res:05d}m_to_{target_res:05d}m_{method}.nc')


def ensure_weights(weights_dir: Path, domain: str, source_res: int,
                   target_res: int, method: str,
                   verbose: bool = False) -> Path:
    """Return a ready-to-use weight file, generating it if it is not cached.

    Generation writes to a temporary file and renames it into place, so that a
    crash part-way through can never leave a truncated file at the final path
    for a later run to trust.  Two processes generating the same weights at
    once each compute the same deterministic result and one rename wins, which
    wastes work but cannot corrupt the cache.
    """
    if method not in METHODS:
        raise ValueError(
            f'unknown remapping method {method!r} (expected one of '
            f'{", ".join(sorted(METHODS))})')
    weights = weight_file_path(weights_dir, domain, source_res, target_res,
                               method)
    if weights.is_file():
        return weights

    source_gdf = gdf_path(domain, source_res)
    target_gdf = gdf_path(domain, target_res)
    generate_op = METHODS[method][1]

    weights.parent.mkdir(parents=True, exist_ok=True)
    LOGGER.info('generating remap weights: %s %dm -> %dm (%s) -> %s',
                domain, source_res, target_res, method, weights)
    scratch = Path(tempfile.mkdtemp(prefix='.gen_', dir=weights.parent))
    try:
        template = scratch / 'template.nc'
        generated = scratch / 'weights.nc'
        cdo.run_cdo(['-f', 'nc', f'const,1,{source_gdf}', str(template)],
                    verbose=verbose)
        cdo.run_cdo([f'{generate_op},{target_gdf}', str(template),
                     str(generated)], verbose=verbose)
        # os.replace, not Path.rename: atomic, and it overwrites a file another
        # process put there first rather than failing on some platforms.
        os.replace(generated, weights)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return weights
