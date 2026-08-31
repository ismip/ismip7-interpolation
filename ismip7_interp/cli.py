"""Argument parsing and logging shared by the command-line entry points."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from ismip7_interp import __version__
from ismip7_interp.archive import DEFAULT_EXPERIMENTS_ROOT
from ismip7_interp.cdo import CdoError
from ismip7_interp.grids import DOMAINS, GridError
from ismip7_interp.ncfile import NetCDFError
from ismip7_interp.variables import DataRequestError
from ismip7_interp.weights import default_weights_dir

#: How a file that is not actually regridded is placed in the output.
ON_UNCHANGED_CHOICES = ('symlink', 'copy', 'skip')

#: Exceptions that mean "this run cannot go on, and why is already in the
#: message".  Reported as a one-line error rather than a traceback: none of
#: them is a bug in this package.
EXPECTED_ERRORS = (CdoError, GridError, NetCDFError, DataRequestError,
                   FileNotFoundError, NotADirectoryError, IsADirectoryError,
                   PermissionError, ValueError)


def configure_logging(verbosity: int = 0) -> None:
    """Send log messages to standard error, timestamped as the run proceeds."""
    logging.basicConfig(
        level=logging.DEBUG if verbosity > 0 else logging.INFO,
        format='[%(asctime)s] %(message)s',
        datefmt='%H:%M:%S',
        stream=sys.stderr,
        force=True)


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the arguments every entry point takes."""
    parser.add_argument(
        '--version', action='version', version=f'%(prog)s {__version__}')
    parser.add_argument(
        '-v', '--verbose', action='count', default=0,
        help='report each CDO command as it is run')


def add_grid_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the domain and target-resolution arguments."""
    parser.add_argument(
        '--domain', required=True, choices=DOMAINS,
        help='the ISMIP7 ice sheet domain')
    parser.add_argument(
        '--target-res', required=True, type=positive_int, metavar='METERS',
        help='the target ISMIP7 grid resolution, in meters')


def add_variables_argument(parser: argparse.ArgumentParser) -> None:
    """Add the ``--variables`` filter."""
    parser.add_argument(
        '--variables', metavar='VAR1,VAR2,...',
        help='restrict processing to these ISMIP7 variables, matched against '
             'the first "_"-separated token of each filename; the default is '
             'every variable found')


def add_weights_argument(parser: argparse.ArgumentParser) -> None:
    """Add the remap-weight cache location."""
    parser.add_argument(
        '--weights-dir', type=Path, default=default_weights_dir(),
        metavar='DIR',
        help='where to cache generated remap weights (default: %(default)s)')


def add_on_unchanged_argument(parser: argparse.ArgumentParser) -> None:
    """Add the option controlling files that are not actually regridded."""
    parser.add_argument(
        '--on-unchanged', choices=ON_UNCHANGED_CHOICES, default='symlink',
        help='how to place a file that is not regridded -- one with no '
             'spatial grid, or one already at the target resolution: as an '
             'absolute symlink to the source (default), a real copy, or not '
             'at all')


def add_experiments_root_argument(parser: argparse.ArgumentParser) -> None:
    """Add the archive root, which defaults per domain."""
    parser.add_argument(
        '--experiments-root', type=Path, metavar='ROOT',
        help='the archive to read; defaults per --domain to the known NIRD '
             'archive root')


def positive_int(text: str) -> int:
    """Parse a command-line integer that must be greater than zero."""
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f'{text!r} is not an integer')
    if value <= 0:
        raise argparse.ArgumentTypeError(f'{value} is not a positive integer')
    return value


def percentage(text: str) -> int:
    """Parse a command-line percentage, which must be between 0 and 100."""
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f'{text!r} is not an integer')
    if not 0 <= value <= 100:
        raise argparse.ArgumentTypeError(
            f'{value} is not a percentage (0-100)')
    return value


def resolve_experiments_root(root: Path | None, domain: str) -> Path:
    """Return the archive root to read, applying the per-domain default."""
    if root is None:
        root = DEFAULT_EXPERIMENTS_ROOT[domain]
    root = Path(root)
    if not root.is_dir():
        raise NotADirectoryError(
            f'experiments root not found: {root}.  Pass --experiments-root to '
            f'point at the archive you mean.')
    return root


def run_main(work) -> int:
    """Run an entry point's body, reporting an expected failure as one line."""
    try:
        return work()
    except EXPECTED_ERRORS as error:
        logging.getLogger('ismip7_interp').error('%s', error)
        return 1
    except KeyboardInterrupt:  # pragma: no cover - interactive only
        logging.getLogger('ismip7_interp').error('interrupted')
        return 130
