"""The read-only inventory: what it counts, and what it writes."""

from __future__ import annotations

import csv

import pytest

from ismip7_interp.grids import gdf_dims, gdf_path
from ismip7_interp.inventory import (
    ALREADY_AT_TARGET,
    NEEDS_REGRID,
    NO_SPATIAL_DATA,
    NOT_AVAILABLE,
    SCALAR,
    SPATIAL,
    UNKNOWN_GRID,
    UNREADABLE,
    default_output_dir,
    inventory_archive,
    main,
)
from ismip7_interp.variables import mandatory_variables

from conftest import NAME_TAIL, SOURCE_RES, TARGET_RES

SOURCE_DIMS = gdf_dims(gdf_path('GrIS', SOURCE_RES))
TARGET_DIMS = gdf_dims(gdf_path('GrIS', TARGET_RES))


@pytest.fixture
def archive(tmp_path, write_gridded):
    """One experiment holding a source-resolution file and a scalar one."""
    root = tmp_path / 'archive'
    experiment = root / 'GroupA/ModelA/CORE/C001'
    experiment.mkdir(parents=True)
    write_gridded(experiment / f'lithk_{NAME_TAIL}', *SOURCE_DIMS)
    _write_scalar(experiment / f'lim_{NAME_TAIL}')
    return root


def _write_scalar(path):
    import netCDF4

    with netCDF4.Dataset(path, 'w') as dataset:
        dataset.createDimension('time', None)
        dataset.createVariable('lim', 'f8', ('time',))
    return path


def read_csv(path):
    with open(path, newline='') as handle:
        return list(csv.DictReader(handle))


def run(archive, tmp_path, **kwargs):
    output = tmp_path / 'inventory'
    inventory = inventory_archive(archive, output, 'GrIS', TARGET_RES,
                                  **kwargs)
    return inventory, output


# --- what it writes --------------------------------------------------------

def test_all_three_reports_are_written(archive, tmp_path):
    _inventory, output = run(archive, tmp_path)
    for name in ('files.csv', 'experiments.csv', 'summary.txt'):
        assert (output / name).is_file()


def test_a_row_per_file(archive, tmp_path):
    _inventory, output = run(archive, tmp_path)
    rows = read_csv(output / 'files.csv')
    assert {row['variable'] for row in rows} == {'lithk', 'lim'}


def test_a_spatial_file_is_measured_and_its_resolution_detected(archive,
                                                                tmp_path):
    _inventory, output = run(archive, tmp_path)
    row = next(row for row in read_csv(output / 'files.csv')
               if row['variable'] == 'lithk')
    assert row['kind'] == SPATIAL
    assert row['source_res_m'] == str(SOURCE_RES)
    assert int(row['actual_bytes']) > 0
    assert row['mandatory'] == 'yes'


def test_a_scalar_file_predicts_its_own_size(archive, tmp_path):
    """It is placed unchanged, so regridding does not change its size."""
    _inventory, output = run(archive, tmp_path)
    row = next(row for row in read_csv(output / 'files.csv')
               if row['variable'] == 'lim')
    assert row['kind'] == SCALAR
    assert row['source_res_m'] == ''
    assert row['predicted_target_bytes'] == row['actual_bytes']


def test_the_predicted_size_scales_with_the_grid(archive, tmp_path):
    _inventory, output = run(archive, tmp_path)
    row = next(row for row in read_csv(output / 'files.csv')
               if row['variable'] == 'lithk')
    ratio = ((TARGET_DIMS[0] * TARGET_DIMS[1])
             / (SOURCE_DIMS[0] * SOURCE_DIMS[1]))
    expected = int(row['actual_bytes']) * ratio
    assert int(row['predicted_target_bytes']) == pytest.approx(expected,
                                                               rel=0.01)


def test_a_row_per_experiment(archive, tmp_path):
    _inventory, output = run(archive, tmp_path)
    rows = read_csv(output / 'experiments.csv')
    assert len(rows) == 1
    assert rows[0]['n_files'] == '2'
    assert rows[0]['regrid_status'] == NEEDS_REGRID


def test_the_summary_counts_the_scan(archive, tmp_path):
    _inventory, output = run(archive, tmp_path)
    text = (output / 'summary.txt').read_text()
    assert 'experiments_total:  1' in text
    assert 'needs_regrid:       1' in text
    assert 'target_res_m:       8000' in text


def test_a_path_with_a_comma_does_not_shift_the_columns(tmp_path,
                                                        write_gridded):
    """An archive path is free to contain a comma; a hand-joined row is not."""
    root = tmp_path / 'archive'
    experiment = root / 'Group,A/ModelA/CORE/C001'
    experiment.mkdir(parents=True)
    write_gridded(experiment / f'lithk_{NAME_TAIL}', *SOURCE_DIMS)

    _inventory, output = run(root, tmp_path)
    row = read_csv(output / 'files.csv')[0]
    assert row['variable'] == 'lithk'
    assert 'Group,A' in row['experiment']


# --- regrid status ---------------------------------------------------------

def test_status_already_at_target(tmp_path, write_gridded):
    root = tmp_path / 'archive'
    experiment = root / 'G/M/CORE/C001'
    experiment.mkdir(parents=True)
    write_gridded(experiment / f'lithk_{NAME_TAIL}', *TARGET_DIMS)

    inventory, _output = run(root, tmp_path)
    assert inventory.experiments[0].regrid_status == ALREADY_AT_TARGET


def test_status_unknown_grid(tmp_path, write_gridded):
    root = tmp_path / 'archive'
    experiment = root / 'G/M/CORE/C001'
    experiment.mkdir(parents=True)
    write_gridded(experiment / f'lithk_{NAME_TAIL}', 37, 41)

    inventory, output = run(root, tmp_path)
    assert inventory.experiments[0].regrid_status == UNKNOWN_GRID
    row = read_csv(output / 'files.csv')[0]
    assert row['source_res_m'] == ''
    assert row['predicted_target_bytes'] == NOT_AVAILABLE


def test_unknown_grid_wins_over_needs_regrid(tmp_path, write_gridded):
    """One unrecognized file makes the whole experiment worth looking at."""
    root = tmp_path / 'archive'
    experiment = root / 'G/M/CORE/C001'
    experiment.mkdir(parents=True)
    write_gridded(experiment / f'lithk_{NAME_TAIL}', *SOURCE_DIMS)
    write_gridded(experiment / f'orog_{NAME_TAIL}', 37, 41)

    inventory, _output = run(root, tmp_path)
    assert inventory.experiments[0].regrid_status == UNKNOWN_GRID


def test_status_no_spatial_data(archive, tmp_path):
    inventory, _output = run(archive, tmp_path, variables='lim')
    assert inventory.experiments[0].regrid_status == NO_SPATIAL_DATA


# --- one bad file --------------------------------------------------------

def test_an_unreadable_file_is_reported_not_fatal(tmp_path, write_gridded):
    """A scan that stops at the first bad file cannot be used to find them."""
    root = tmp_path / 'archive'
    experiment = root / 'G/M/CORE/C001'
    experiment.mkdir(parents=True)
    write_gridded(experiment / f'lithk_{NAME_TAIL}', *SOURCE_DIMS)
    (experiment / f'lonlat_{NAME_TAIL}').write_text('not a NetCDF file')

    inventory, output = run(root, tmp_path)
    rows = read_csv(output / 'files.csv')
    assert len(rows) == 2
    bad = next(row for row in rows if row['variable'] == 'lonlat')
    assert bad['kind'] == UNREADABLE
    assert bad['predicted_target_bytes'] == NOT_AVAILABLE
    # The good file is still measured, and still drives the status.
    assert inventory.experiments[0].regrid_status == NEEDS_REGRID


def test_an_unreadable_file_is_left_out_of_the_predicted_total(tmp_path,
                                                               write_gridded):
    root = tmp_path / 'archive'
    experiment = root / 'G/M/CORE/C001'
    experiment.mkdir(parents=True)
    (experiment / f'lonlat_{NAME_TAIL}').write_text('not a NetCDF file')

    inventory, _output = run(root, tmp_path)
    summary = inventory.experiments[0]
    assert summary.total_actual_bytes > 0
    assert summary.total_predicted_bytes == 0


# --- mandatory completeness ------------------------------------------------

def test_missing_mandatory_variables_are_listed(archive, tmp_path):
    _inventory, output = run(archive, tmp_path)
    row = read_csv(output / 'experiments.csv')[0]
    missing = set(row['missing_mandatory'].split(';'))
    assert 'acabf' in missing
    assert 'lithk' not in missing
    assert row['n_mandatory_expected'] == str(len(mandatory_variables()))
    assert row['n_mandatory_present'] == '2'


def test_a_substring_of_another_name_is_not_confused_with_it(tmp_path,
                                                             write_gridded):
    """`lim` present must not be read as `limnsw` present, or vice versa."""
    root = tmp_path / 'archive'
    experiment = root / 'G/M/CORE/C001'
    experiment.mkdir(parents=True)
    _write_scalar(experiment / f'limnsw_{NAME_TAIL}')

    _inventory, output = run(root, tmp_path)
    missing = set(read_csv(output / 'experiments.csv')[0][
        'missing_mandatory'].split(';'))
    assert 'lim' in missing
    assert 'limnsw' not in missing


def test_a_filtered_scan_only_expects_the_variables_it_looked_at(archive,
                                                                 tmp_path):
    """Otherwise every variable it never opened is reported as missing."""
    _inventory, output = run(archive, tmp_path, variables='lithk,acabf')
    row = read_csv(output / 'experiments.csv')[0]
    assert row['n_mandatory_expected'] == '2'
    assert row['missing_mandatory'] == 'acabf'


def test_a_filter_of_optional_variables_expects_none(archive, tmp_path):
    _inventory, output = run(archive, tmp_path, variables='hfgeoubed')
    row = read_csv(output / 'experiments.csv')[0]
    assert row['n_mandatory_expected'] == '0'
    assert row['n_mandatory_present'] == '0'


# --- filtering -------------------------------------------------------------

def test_the_variables_filter_skips_other_files_entirely(archive, tmp_path):
    _inventory, output = run(archive, tmp_path, variables='lithk')
    rows = read_csv(output / 'files.csv')
    assert [row['variable'] for row in rows] == ['lithk']


def test_the_variables_filter_tolerates_spaces(archive, tmp_path):
    _inventory, output = run(archive, tmp_path, variables='lithk, lim')
    assert len(read_csv(output / 'files.csv')) == 2


# --- nothing is written to the archive -------------------------------------

def test_the_archive_is_left_untouched(archive, tmp_path):
    before = {path: path.stat().st_mtime_ns
              for path in archive.rglob('*') if path.is_file()}
    run(archive, tmp_path)
    after = {path: path.stat().st_mtime_ns
             for path in archive.rglob('*') if path.is_file()}
    assert before == after


def test_no_cdo_is_needed(archive, tmp_path, monkeypatch):
    """The scan reads headers only; it must never reach for CDO."""
    def forbidden(*args, **kwargs):
        raise AssertionError('the inventory must not run cdo')

    monkeypatch.setattr('ismip7_interp.cdo.run_cdo', forbidden)
    run(archive, tmp_path)


# --- the command line ------------------------------------------------------

def test_default_output_dir_is_per_domain():
    """Scanning both domains without --output must not overwrite one scan."""
    assert default_output_dir('GrIS') != default_output_dir('AIS')


def test_main_writes_the_reports(archive, tmp_path):
    output = tmp_path / 'report'
    status = main(['--domain', 'GrIS', '--target-res', str(TARGET_RES),
                   '--experiments-root', str(archive),
                   '--output', str(output)])
    assert status == 0
    assert (output / 'files.csv').is_file()


def test_main_reports_a_missing_archive_root_as_a_status(tmp_path):
    status = main(['--domain', 'GrIS', '--target-res', str(TARGET_RES),
                   '--experiments-root', str(tmp_path / 'absent'),
                   '--output', str(tmp_path / 'report')])
    assert status == 1
