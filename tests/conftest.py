"""Shared fixtures.

The suite is in two halves.  Most tests are pure logic -- name parsing, grid
lookup, archive walking, report writing -- and run anywhere Python does.  The
rest are marked ``cdo`` and exercise the real regridding against small
synthetic files; they are skipped when CDO is not installed, so that a
contributor without it still gets a useful run.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from ismip7_interp.grids import gdf_path

#: The smallest grid that ships with the package, so fixtures stay quick.
SOURCE_RES = 16000
#: One step finer, so that every regridding test actually regrids rather than
#: taking the already-at-target shortcut.
TARGET_RES = 8000

#: An ISMIP7 filename tail: {region}_{project}_{submission}_{modelid}_{ESM}_
#: {forcingid}_{experiment}_{years}.nc
NAME_TAIL = 'GrIS_TEST_MODEL_m001_ESM_f001_ssp585_C001_2015-2015.nc'

_HAVE_CDO = shutil.which('cdo') is not None

requires_cdo = pytest.mark.skipif(
    not _HAVE_CDO, reason='cdo is not installed')


def pytest_collection_modifyitems(config, items):
    """Skip the ``cdo`` tests when CDO is not installed."""
    if _HAVE_CDO:
        return
    skip = pytest.mark.skip(reason='cdo is not installed')
    for item in items:
        if 'cdo' in item.keywords:
            item.add_marker(skip)


def _cdo(*args: str) -> None:
    subprocess.run(['cdo', '-s', *args], check=True, capture_output=True,
                   text=True)


@pytest.fixture(scope='session')
def fixture_files(tmp_path_factory) -> dict[str, Path]:
    """Build small synthetic ISMIP7 files, once for the whole session.

    Spatial files come from CDO's own ``random`` generator on the coarsest
    ISMIP7 grid; the scalar one is written with ``netCDF4``, since it needs no
    grid at all and CDO has no generator for that.
    """
    if not _HAVE_CDO:
        pytest.skip('cdo is not installed')
    directory = tmp_path_factory.mktemp('fixtures')
    source_gdf = gdf_path('GrIS', SOURCE_RES)
    files: dict[str, Path] = {}

    def spatial(variable: str, missing: bool = False) -> None:
        path = directory / f'{variable}_{NAME_TAIL}'
        random = f'-random,{source_gdf}'
        # CDO's `random` draws from [0,1), so blanking 0.4-0.6 leaves a genuine
        # partial mask -- some missing values, not all of them.
        steps = [f'chname,random,{variable}']
        if missing:
            steps.append('-setrtomiss,0.4,0.6')
        _cdo('-f', 'nc4', *steps, random, str(path))
        files[variable] = path

    # A state variable and a flux variable: both resolve to conservative
    # remapping, and both are mandatory in the data request.
    spatial('lithk')
    spatial('acabf')
    # Configured for bilinear remapping and for a preserved missing-value mask,
    # but with no missing values -- so it should still use the shared weights.
    spatial('xvelsurf')
    # The same, but with a real mask, which must not go through the cache.
    spatial('yvelsurf', missing=True)
    files['lim'] = _write_scalar(directory / f'lim_{NAME_TAIL}')
    return files


def _write_scalar(path: Path) -> Path:
    """Write a scalar time series: a `t`-only variable, with no x,y grid."""
    import netCDF4

    with netCDF4.Dataset(path, 'w') as dataset:
        dataset.createDimension('time', None)
        time = dataset.createVariable('time', 'f8', ('time',))
        time.units = 'days since 1850-01-01'
        time.calendar = 'standard'
        values = dataset.createVariable('lim', 'f4', ('time',),
                                        fill_value=-9999.0)
        time[:] = [60225.0, 60590.0]
        values[:] = [1.0e15, 1.01e15]
    return path


@pytest.fixture
def write_gridded():
    """Return a helper writing a tiny NetCDF file with given x,y dimensions.

    Written with ``netCDF4`` rather than CDO, so that the tests of everything
    that only reads a header -- the inventory above all -- run whether or not
    CDO is installed.
    """
    def write(path: Path, xsize: int, ysize: int,
              variable: str = 'lithk') -> Path:
        import netCDF4

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with netCDF4.Dataset(path, 'w') as dataset:
            dataset.createDimension('x', xsize)
            dataset.createDimension('y', ysize)
            dataset.createDimension('time', None)
            values = dataset.createVariable(variable, 'f4',
                                            ('time', 'y', 'x'))
            values[0, :, :] = 1.0
        return path

    return write


@pytest.fixture
def fake_cdo(monkeypatch):
    """Replace CDO with a recorder, so branching can be tested without it.

    Every call is recorded, and any output file the command names is created
    empty, so that code which goes on to look at its own output still works.
    Returns the list of recorded argument lists.
    """
    calls: list[list[str]] = []

    def record(args, capture=False, verbose=False):
        calls.append(list(args))
        # By CDO convention the output file is the last argument; create it so
        # that the caller sees the file its command was supposed to write.
        if not capture and args:
            last = Path(args[-1])
            if last.suffix == '.nc':
                last.parent.mkdir(parents=True, exist_ok=True)
                last.touch()
        return ''

    monkeypatch.setattr('ismip7_interp.cdo.run_cdo', record)
    return calls


@pytest.fixture
def weights_dir(tmp_path) -> Path:
    """A throwaway remap-weight cache, so tests never touch the user's."""
    return tmp_path / 'weights'


@pytest.fixture
def make_archive():
    """Return a helper building a fake archive of empty ``.nc`` placeholders.

    It takes a root and a mapping from a path relative to that root to the
    filenames to create there.  Only names and structure matter to the
    archive walker, so the files can be empty -- which keeps a test that
    describes a twenty-experiment archive down to twenty lines.
    """
    def build(root: Path, layout: dict[str, list[str]]) -> Path:
        for relative, names in layout.items():
            directory = Path(root) / relative
            directory.mkdir(parents=True, exist_ok=True)
            for name in names:
                (directory / name).touch()
        return Path(root)

    return build
