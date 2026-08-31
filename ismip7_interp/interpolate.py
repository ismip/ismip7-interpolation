"""Regridding one ISMIP7 NetCDF file onto a target ISMIP7 grid."""

from __future__ import annotations

import argparse
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from ismip7_interp import cdo, cli
from ismip7_interp.grids import gdf_path
from ismip7_interp.ncfile import NetCDFError, grid_dims, has_missing_values
from ismip7_interp.variables import (
    COPY,
    METHODS,
    interp_method,
    use_setmisstoc,
    var_from_filename,
)
from ismip7_interp.weights import ensure_weights

LOGGER = logging.getLogger(__name__)

#: ``--method`` values: a specific algorithm, or let the variable decide.
METHOD_CHOICES = (*sorted(METHODS), 'auto')

#: Why a file was not regridded, for :attr:`Result.reason`.
NO_SPATIAL_GRID = 'no spatial grid to remap'
ALREADY_AT_TARGET = 'already at the target resolution'


@dataclass(frozen=True)
class Result:
    """What happened to one file."""

    #: ``'regridded'``, ``'symlink'``, ``'copy'`` or ``'skip'``.
    action: str
    variable: str
    #: The resolution the file was read at, or ``None`` if it has no grid.
    source_res: int | None
    #: The remapping used, or ``None`` if the file was not regridded.
    method: str | None
    #: Why the file was not regridded, or ``None`` if it was.
    reason: str | None = None

    @property
    def regridded(self) -> bool:
        """Return whether the file was actually put through CDO."""
        return self.action == 'regridded'


def place_unchanged(in_file: Path, out_file: Path, on_unchanged: str) -> str:
    """Put a file that is not being regridded into place, and say how.

    ``symlink`` points an absolute symlink at the source, so that the link
    resolves wherever the output tree is read from and no large file is copied
    for nothing; ``copy`` makes a real copy; ``skip`` writes nothing at all.
    """
    if on_unchanged not in cli.ON_UNCHANGED_CHOICES:
        raise ValueError(
            f'unknown --on-unchanged value {on_unchanged!r} (expected one of '
            f'{", ".join(cli.ON_UNCHANGED_CHOICES)})')
    if on_unchanged == 'skip':
        return 'skip'

    out_file = Path(out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    if on_unchanged == 'copy':
        if out_file.is_dir() and not out_file.is_symlink():
            raise IsADirectoryError(
                f'{out_file} is a directory, so no output file can be '
                f'written there')
        shutil.copy2(in_file, out_file)
        return 'copy'

    # Remove first rather than relying on `ln -sf` semantics, which would
    # quietly create the link *inside* a directory that happened to be at the
    # output path instead of replacing it.  A directory there is an anomaly
    # rather than a stale result, and deleting one could throw away a great
    # deal, so it is refused rather than cleared away.
    if out_file.is_dir() and not out_file.is_symlink():
        raise IsADirectoryError(
            f'{out_file} is a directory, so no output file can be written '
            f'there')
    if out_file.is_symlink() or out_file.exists():
        out_file.unlink()
    out_file.symlink_to(Path(in_file).resolve())
    return 'symlink'


def interpolate_file(in_file: Path, out_file: Path, domain: str,
                     target_res: int, method: str = 'auto',
                     on_unchanged: str = 'symlink',
                     weights_dir: Path | None = None,
                     verbose: bool = False) -> Result:
    """Regrid one file onto the ISMIP7 ``domain`` grid at ``target_res``.

    A file is left unchanged, and placed per ``on_unchanged``, in two cases:
    the variable has no spatial grid at all, or the file is already at the
    target resolution.  Note that the first is decided from the data request,
    not from ``method``: asking for a specific algorithm cannot make a
    domain-integrated time series regriddable, and trying would only hand CDO
    a file it must reject.
    """
    in_file = Path(in_file)
    out_file = Path(out_file)
    if not in_file.is_file():
        raise FileNotFoundError(f'input file not found: {in_file}')
    if method not in METHOD_CHOICES:
        raise ValueError(
            f'unknown method {method!r} (expected one of '
            f'{", ".join(METHOD_CHOICES)})')
    if weights_dir is None:
        from ismip7_interp.weights import default_weights_dir
        weights_dir = default_weights_dir()

    variable = var_from_filename(in_file)
    auto_method = interp_method(variable)

    if auto_method == COPY:
        action = place_unchanged(in_file, out_file, on_unchanged)
        LOGGER.info('%s %s: %s', action.upper(), variable, NO_SPATIAL_GRID)
        return Result(action, variable, None, None, NO_SPATIAL_GRID)

    # Resolve the target grid before reading the input: a resolution with no
    # ISMIP7 grid is a mistake in the command line, and should be reported
    # without first spending CDO time on the file.
    target_gdf = gdf_path(domain, target_res)

    dims = grid_dims(in_file)
    if dims is None:
        raise NetCDFError(
            f'{in_file} has no x,y grid, but {variable} is not one of the '
            f'ISMIP7 variables without one -- non-standard file?')
    from ismip7_interp.grids import detect_res_from_dims
    source_res = detect_res_from_dims(domain, dims)
    if source_res is None:
        raise NetCDFError(
            f'no {domain} ISMIP7 grid matches the dimensions {dims[0]}x'
            f'{dims[1]} of {in_file} -- non-standard source grid?')

    if source_res == target_res:
        action = place_unchanged(in_file, out_file, on_unchanged)
        LOGGER.info('%s %s: %s (%dm)', action.upper(), variable,
                    ALREADY_AT_TARGET, target_res)
        return Result(action, variable, source_res, None, ALREADY_AT_TARGET)

    resolved = auto_method if method == 'auto' else method
    remap_op = METHODS[resolved][0]
    source_gdf = gdf_path(domain, source_res)

    fill_missing = use_setmisstoc(variable)
    # A variable whose mask must be preserved can still use the shared weights
    # when the file has no missing values: there is then no mask to preserve,
    # and the full-grid weights are the right ones.
    cacheable = fill_missing or not has_missing_values(in_file)

    out_file.parent.mkdir(parents=True, exist_ok=True)
    if cacheable:
        weights = ensure_weights(weights_dir, domain, source_res, target_res,
                                 resolved, verbose=verbose)
        LOGGER.info('REGRID %s: %dm -> %dm via %s (cached weights)', variable,
                    source_res, target_res, remap_op)
        command = [f'remap,{target_gdf},{weights}']
        if fill_missing:
            command.append('-setmisstoc,0')
    else:
        LOGGER.info('REGRID %s: %dm -> %dm via %s (missing-value mask '
                    'preserved, weights not cached)', variable, source_res,
                    target_res, remap_op)
        command = [f'{remap_op},{target_gdf}']
    command += [f'-setgrid,{source_gdf}', str(in_file), str(out_file)]
    cdo.run_cdo(command, verbose=verbose)
    return Result('regridded', variable, source_res, resolved)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog='ismip7-interpolate',
        description=__doc__,
        epilog='A file with no spatial grid, or one already at the target '
               'resolution, is not regridded; --on-unchanged says what to put '
               'at OUT.nc instead.')
    cli.add_common_arguments(parser)
    cli.add_grid_arguments(parser)
    parser.add_argument(
        '--method', choices=METHOD_CHOICES, default='auto',
        help='the remapping to use; the default picks conservative remapping '
             'unless the variable is configured for bilinear or '
             'nearest-neighbor')
    cli.add_on_unchanged_argument(parser)
    cli.add_weights_argument(parser)
    parser.add_argument('in_file', type=Path, metavar='IN.nc',
                        help='the ISMIP7 NetCDF file to regrid')
    parser.add_argument('out_file', type=Path, metavar='OUT.nc',
                        help='where to write the result')
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point for ``ismip7-interpolate``."""
    args = _parse_args(argv)
    cli.configure_logging(args.verbose)

    def work() -> int:
        interpolate_file(args.in_file, args.out_file, args.domain,
                         args.target_res, method=args.method,
                         on_unchanged=args.on_unchanged,
                         weights_dir=args.weights_dir,
                         verbose=args.verbose > 0)
        return 0

    return cli.run_main(work)


if __name__ == '__main__':  # pragma: no cover
    raise SystemExit(main())
