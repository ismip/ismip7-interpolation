"""Regrid ISMIP7 ice sheet model output onto the standard ISMIP7 grids."""

from importlib import metadata

try:
    __version__ = metadata.version('ismip7-interpolation')
except metadata.PackageNotFoundError:
    # Running from a source tree that was never installed.  Nothing here
    # depends on the version, so an honest placeholder beats an exception.
    __version__ = 'unknown'

__all__ = ['__version__']
