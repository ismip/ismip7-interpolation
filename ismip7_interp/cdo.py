"""Running CDO.

CDO does the regridding, exactly as the shell scripts this package replaced
did; only the orchestration moved into Python.  The commands are built and run
here so that every caller reports a failure the same way and so that the tests
have one place to intercept.
"""

from __future__ import annotations

import logging
import shutil
import subprocess

LOGGER = logging.getLogger(__name__)

#: The executable.  Not configurable: CDO is a hard dependency of the package,
#: and picking up a different binary would silently change the numerics.
CDO = 'cdo'


class CdoError(RuntimeError):
    """A CDO command failed."""


class CdoNotFoundError(CdoError):
    """CDO is not installed, or not on ``PATH``."""


def require_cdo() -> str:
    """Return the path to the ``cdo`` executable, or say that it is absent."""
    path = shutil.which(CDO)
    if path is None:
        raise CdoNotFoundError(
            "'cdo' is not on PATH.  It does the regridding, so nothing here "
            'works without it.  Install this package from conda-forge, which '
            "brings CDO with it, or add it yourself with 'conda install -c "
            "conda-forge cdo'.")
    return path


def run_cdo(args: list[str], capture: bool = False,
            verbose: bool = False) -> str:
    """Run ``cdo`` with ``args`` and return its standard output.

    ``verbose`` adds CDO's own ``-v``, which reports every weight, bound and
    timing it computes.  That is a great deal of output per file -- on a whole
    archive, more than anyone reads -- so it follows this package's
    ``--verbose`` rather than being always on.

    With ``capture`` false -- the regridding calls, whose output is progress
    reporting for a human -- CDO's own messages go straight to this process's
    standard error, and the empty string is returned.  CDO writes diagnostics
    to standard output as well as standard error, so nothing it prints is ever
    left on standard output for a caller to mistake for data.
    """
    require_cdo()
    command = [CDO, *(['-v'] if verbose else []), *args]
    LOGGER.debug('running: %s', ' '.join(command))
    if capture:
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise CdoError(
                f'cdo {" ".join(args)} failed with exit status '
                f'{result.returncode}: {result.stderr.strip()}')
        return result.stdout
    # stdout is redirected to stderr rather than captured: CDO's progress
    # messages stay visible to the user while they run, and cannot end up
    # mixed into anything this process writes to stdout.
    result = subprocess.run(command, stdout=2)
    if result.returncode != 0:
        raise CdoError(
            f'cdo {" ".join(args)} failed with exit status '
            f'{result.returncode}')
    return ''
