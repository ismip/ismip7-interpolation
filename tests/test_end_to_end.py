"""The whole pipeline against real CDO and a small synthetic archive.

Everything else in the suite tests one piece with the rest stood in for.  This
tests the pieces together, doing real work: a two-experiment archive is
inventoried, regridded, and the result checked against the ISMIP7 target grid.
"""

from __future__ import annotations

import csv

import pytest

from ismip7_interp.grids import gdf_dims, gdf_path
from ismip7_interp.inventory import NEEDS_REGRID, inventory_archive
from ismip7_interp.ncfile import grid_dims
from ismip7_interp.run_all import run_all_experiments

from conftest import NAME_TAIL, TARGET_RES

pytestmark = pytest.mark.cdo

TARGET_DIMS = gdf_dims(gdf_path('GrIS', TARGET_RES))


@pytest.fixture
def archive(tmp_path, fixture_files):
    """Two experiments across two groups, from the session's real files."""
    root = tmp_path / 'archive'
    for relative, variables in {
        'GroupA/ModelA/CORE/C001': ('lithk', 'acabf', 'lim'),
        'GroupB/ModelB/CORE/C002': ('lithk', 'xvelsurf', 'yvelsurf'),
    }.items():
        experiment = root / relative
        experiment.mkdir(parents=True)
        for variable in variables:
            (experiment / f'{variable}_{NAME_TAIL}').write_bytes(
                fixture_files[variable].read_bytes())
    return root


def test_the_whole_archive_regrids(tmp_path, archive, weights_dir):
    output = tmp_path / 'out'
    report = run_all_experiments(archive, output, 'GrIS', TARGET_RES,
                                 weights_dir=weights_dir)

    assert report.n_total == 2
    assert report.pass_pct == 100

    regridded = output / 'GrIS_08000m'
    for relative, variables in {
        'GroupA/ModelA/CORE/C001': ('lithk', 'acabf'),
        'GroupB/ModelB/CORE/C002': ('lithk', 'xvelsurf', 'yvelsurf'),
    }.items():
        for variable in variables:
            path = regridded / relative / f'{variable}_{NAME_TAIL}'
            assert grid_dims(path) == TARGET_DIMS, path


def test_the_scalar_file_is_symlinked_not_regridded(tmp_path, archive,
                                                    weights_dir):
    output = tmp_path / 'out'
    run_all_experiments(archive, output, 'GrIS', TARGET_RES,
                        weights_dir=weights_dir)
    path = (output / 'GrIS_08000m/GroupA/ModelA/CORE/C001'
            / f'lim_{NAME_TAIL}')
    assert path.is_symlink()


def test_the_directory_tree_is_mirrored_exactly(tmp_path, archive,
                                                weights_dir):
    output = tmp_path / 'out'
    run_all_experiments(archive, output, 'GrIS', TARGET_RES,
                        weights_dir=weights_dir)
    regridded = output / 'GrIS_08000m'
    source = {path.relative_to(archive)
              for path in archive.rglob('*.nc')}
    written = {path.relative_to(regridded)
               for path in regridded.rglob('*.nc')}
    assert written == source


def test_weights_are_shared_across_experiments(tmp_path, archive,
                                               weights_dir):
    """One conservative and one bilinear file, however many experiments."""
    run_all_experiments(archive, tmp_path / 'out', 'GrIS', TARGET_RES,
                        weights_dir=weights_dir)
    generated = sorted(path.name for path in weights_dir.glob('*.nc'))
    assert generated == ['GrIS_16000m_to_08000m_bil.nc',
                         'GrIS_16000m_to_08000m_ycon.nc']


def test_a_second_run_reuses_the_weights(tmp_path, archive, weights_dir):
    run_all_experiments(archive, tmp_path / 'out', 'GrIS', TARGET_RES,
                        weights_dir=weights_dir)
    stamps = {path.name: path.stat().st_mtime_ns
              for path in weights_dir.glob('*.nc')}
    run_all_experiments(archive, tmp_path / 'out2', 'GrIS', TARGET_RES,
                        weights_dir=weights_dir)
    assert {path.name: path.stat().st_mtime_ns
            for path in weights_dir.glob('*.nc')} == stamps


def test_the_inventory_agrees_with_what_regridding_did(tmp_path, archive):
    """The inventory says these need regridding; regridding then does."""
    inventory = inventory_archive(archive, tmp_path / 'inventory', 'GrIS',
                                  TARGET_RES)
    assert len(inventory.experiments) == 2
    for summary in inventory.experiments:
        assert summary.regrid_status == NEEDS_REGRID

    with open(tmp_path / 'inventory/files.csv', newline='') as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 6
    for row in rows:
        assert row['kind'] in ('spatial', 'scalar')


def test_regridding_twice_gives_the_same_values(tmp_path, archive,
                                                weights_dir):
    """Reruns must be idempotent.

    Compared as data, not as bytes: a NetCDF4 file is HDF5, whose header
    carries per-run bookkeeping, so two runs that computed exactly the same
    numbers still differ byte for byte.
    """
    import netCDF4
    import numpy as np

    first = tmp_path / 'first'
    second = tmp_path / 'second'
    for output in (first, second):
        run_all_experiments(archive, output, 'GrIS', TARGET_RES,
                            weights_dir=weights_dir)
    path = f'GrIS_08000m/GroupA/ModelA/CORE/C001/lithk_{NAME_TAIL}'
    with netCDF4.Dataset(first / path) as one, \
            netCDF4.Dataset(second / path) as two:
        assert np.array_equal(one['lithk'][:], two['lithk'][:])


def test_rerunning_over_an_existing_output_tree_succeeds(tmp_path, archive,
                                                         weights_dir):
    output = tmp_path / 'out'
    for _ in range(2):
        report = run_all_experiments(archive, output, 'GrIS', TARGET_RES,
                                     weights_dir=weights_dir)
        assert report.pass_pct == 100


def test_a_run_at_the_target_resolution_changes_nothing(tmp_path, archive,
                                                        weights_dir):
    """Every file is already there, so every one is placed unchanged."""
    output = tmp_path / 'out'
    from conftest import SOURCE_RES

    report = run_all_experiments(archive, output, 'GrIS', SOURCE_RES,
                                 weights_dir=weights_dir)
    assert report.pass_pct == 100
    assert not weights_dir.exists() or list(weights_dir.glob('*.nc')) == []
    for path in (output / 'GrIS_16000m').rglob('*.nc'):
        assert path.is_symlink()
