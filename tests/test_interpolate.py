"""Regridding one file: what is decided, and what CDO is then asked to do."""

from __future__ import annotations

from pathlib import Path

import pytest

from ismip7_interp.grids import GridError, gdf_dims, gdf_path
from ismip7_interp.interpolate import (
    ALREADY_AT_TARGET,
    NO_SPATIAL_GRID,
    interpolate_file,
    main,
    place_unchanged,
)
from ismip7_interp.ncfile import NetCDFError, grid_dims

from conftest import NAME_TAIL, SOURCE_RES, TARGET_RES

SOURCE_DIMS = gdf_dims(gdf_path('GrIS', SOURCE_RES))


@pytest.fixture
def fake_source(tmp_path, monkeypatch):
    """A stand-in input file whose grid CDO is not asked to read.

    Returns a helper that writes a file for one variable and declares what
    ``grid_dims`` should report for it, so the decision logic can be exercised
    over every variable and grid without CDO.
    """
    def make(variable: str, dims=SOURCE_DIMS, missing: bool = False) -> Path:
        path = tmp_path / f'{variable}_{NAME_TAIL}'
        path.write_bytes(b'not really netcdf')
        monkeypatch.setattr('ismip7_interp.interpolate.grid_dims',
                            lambda _path: dims)
        monkeypatch.setattr('ismip7_interp.interpolate.has_missing_values',
                            lambda _path: missing)
        return path

    return make


# --- place_unchanged -------------------------------------------------------

def test_place_unchanged_symlink_is_absolute_and_resolves(tmp_path):
    source = tmp_path / 'in' / 'lithk.nc'
    source.parent.mkdir()
    source.write_bytes(b'data')
    target = tmp_path / 'out' / 'lithk.nc'

    assert place_unchanged(source, target, 'symlink') == 'symlink'
    assert target.is_symlink()
    assert Path(target.readlink()).is_absolute()
    assert target.read_bytes() == b'data'


def test_place_unchanged_symlink_replaces_what_is_already_there(tmp_path):
    """Reruns must be idempotent, not fail or nest a link in a directory."""
    source = tmp_path / 'lithk.nc'
    source.write_bytes(b'data')
    target = tmp_path / 'out' / 'lithk.nc'
    target.parent.mkdir()
    target.write_bytes(b'stale')

    place_unchanged(source, target, 'symlink')
    assert target.is_symlink()
    assert target.read_bytes() == b'data'


@pytest.mark.parametrize('mode', ['symlink', 'copy'])
def test_place_unchanged_refuses_a_directory_in_the_way(tmp_path, mode):
    """`ln -sf` would put the link *inside* such a directory instead.

    Refused rather than cleared away: a directory at an output file's path is
    an anomaly, and removing one could throw away a great deal.
    """
    source = tmp_path / 'lithk.nc'
    source.write_bytes(b'data')
    target = tmp_path / 'out' / 'lithk.nc'
    target.mkdir(parents=True)

    with pytest.raises(IsADirectoryError):
        place_unchanged(source, target, mode)
    assert target.is_dir()


def test_place_unchanged_copy_makes_a_real_file(tmp_path):
    source = tmp_path / 'lithk.nc'
    source.write_bytes(b'data')
    target = tmp_path / 'out' / 'lithk.nc'

    assert place_unchanged(source, target, 'copy') == 'copy'
    assert not target.is_symlink()
    assert target.read_bytes() == b'data'


def test_place_unchanged_skip_writes_nothing(tmp_path):
    source = tmp_path / 'lithk.nc'
    source.write_bytes(b'data')
    target = tmp_path / 'out' / 'lithk.nc'

    assert place_unchanged(source, target, 'skip') == 'skip'
    assert not target.exists()
    # Not even the directory: skip means nothing was written.
    assert not target.parent.exists()


def test_place_unchanged_creates_the_output_directory(tmp_path):
    source = tmp_path / 'lithk.nc'
    source.write_bytes(b'data')
    target = tmp_path / 'deep' / 'nested' / 'lithk.nc'
    place_unchanged(source, target, 'copy')
    assert target.is_file()


def test_place_unchanged_rejects_an_unknown_mode(tmp_path):
    source = tmp_path / 'lithk.nc'
    source.write_bytes(b'data')
    with pytest.raises(ValueError, match='on-unchanged'):
        place_unchanged(source, tmp_path / 'out.nc', 'hardlink')


# --- what interpolate_file decides -----------------------------------------

def test_a_scalar_variable_is_placed_unchanged(tmp_path, fake_cdo):
    source = tmp_path / f'lim_{NAME_TAIL}'
    source.write_bytes(b'data')
    result = interpolate_file(source, tmp_path / 'out.nc', 'GrIS', TARGET_RES,
                              weights_dir=tmp_path / 'weights')
    assert result.action == 'symlink'
    assert result.reason == NO_SPATIAL_GRID
    assert not result.regridded
    assert fake_cdo == []


def test_an_explicit_method_cannot_make_a_scalar_regriddable(tmp_path,
                                                             fake_cdo):
    """--method must not push a domain-integrated series into CDO's remap."""
    source = tmp_path / f'lim_{NAME_TAIL}'
    source.write_bytes(b'data')
    result = interpolate_file(source, tmp_path / 'out.nc', 'GrIS', TARGET_RES,
                              method='bil', weights_dir=tmp_path / 'weights')
    assert result.reason == NO_SPATIAL_GRID
    assert fake_cdo == []


def test_a_file_already_at_the_target_is_placed_unchanged(tmp_path, fake_cdo,
                                                          fake_source):
    source = fake_source('lithk')
    result = interpolate_file(source, tmp_path / 'out.nc', 'GrIS', SOURCE_RES,
                              weights_dir=tmp_path / 'weights')
    assert result.reason == ALREADY_AT_TARGET
    assert result.source_res == SOURCE_RES
    assert fake_cdo == []


@pytest.mark.parametrize('on_unchanged, expected', [
    ('symlink', 'symlink'),
    ('copy', 'copy'),
    ('skip', 'skip'),
])
def test_on_unchanged_is_honored(tmp_path, fake_cdo, fake_source,
                                  on_unchanged, expected):
    source = fake_source('lithk')
    result = interpolate_file(source, tmp_path / 'out.nc', 'GrIS', SOURCE_RES,
                              on_unchanged=on_unchanged,
                              weights_dir=tmp_path / 'weights')
    assert result.action == expected


def test_an_ordinary_variable_is_filled_and_uses_cached_weights(
        tmp_path, fake_cdo, fake_source):
    source = fake_source('lithk')
    result = interpolate_file(source, tmp_path / 'out.nc', 'GrIS', TARGET_RES,
                              weights_dir=tmp_path / 'weights')
    assert result.regridded
    assert result.method == 'ycon'
    remap = fake_cdo[-1]
    assert any(argument.startswith('remap,') for argument in remap)
    assert '-setmisstoc,0' in remap


@pytest.mark.parametrize('variable, expected', [
    ('lithk', 'ycon'),
    ('acabf', 'ycon'),
    ('xvelsurf', 'bil'),
])
def test_the_method_comes_from_the_variable(tmp_path, fake_cdo, fake_source,
                                            variable, expected):
    source = fake_source(variable)
    result = interpolate_file(source, tmp_path / 'out.nc', 'GrIS', TARGET_RES,
                              weights_dir=tmp_path / 'weights')
    assert result.method == expected
    generated = [call for call in fake_cdo if call[0].startswith('gen')]
    assert generated and generated[0][0].startswith(f'gen{expected}')


def test_an_explicit_method_overrides_the_variables_own(tmp_path, fake_cdo,
                                                        fake_source):
    source = fake_source('lithk')
    result = interpolate_file(source, tmp_path / 'out.nc', 'GrIS', TARGET_RES,
                              method='nn', weights_dir=tmp_path / 'weights')
    assert result.method == 'nn'


def test_a_mask_variable_with_a_mask_skips_the_cache(tmp_path, fake_cdo,
                                                     fake_source):
    """Its real missing-value pattern must survive, so no shared weights."""
    source = fake_source('xvelsurf', missing=True)
    interpolate_file(source, tmp_path / 'out.nc', 'GrIS', TARGET_RES,
                     weights_dir=tmp_path / 'weights')
    assert not any(call[0].startswith('gen') for call in fake_cdo)
    remap = fake_cdo[-1]
    assert any(argument.startswith('remapbil,') for argument in remap)
    assert '-setmisstoc,0' not in remap


def test_a_mask_variable_without_a_mask_still_uses_the_cache(tmp_path,
                                                             fake_cdo,
                                                             fake_source):
    """With nothing to preserve, the full-grid weights are the right ones."""
    source = fake_source('xvelsurf', missing=False)
    interpolate_file(source, tmp_path / 'out.nc', 'GrIS', TARGET_RES,
                     weights_dir=tmp_path / 'weights')
    assert any(call[0].startswith('genbil') for call in fake_cdo)
    remap = fake_cdo[-1]
    assert any(argument.startswith('remap,') for argument in remap)
    # Cached weights, but still no fill: its own values are used as they are.
    assert '-setmisstoc,0' not in remap


def test_the_source_grid_is_declared_before_remapping(tmp_path, fake_cdo,
                                                      fake_source):
    """ISMIP7 files carry no CF grid mapping CDO can use, hence setgrid."""
    source = fake_source('lithk')
    interpolate_file(source, tmp_path / 'out.nc', 'GrIS', TARGET_RES,
                     weights_dir=tmp_path / 'weights')
    remap = fake_cdo[-1]
    setgrid = [argument for argument in remap
               if argument.startswith('-setgrid,')]
    assert len(setgrid) == 1
    assert f'{SOURCE_RES:05d}m' in setgrid[0]


# --- what interpolate_file refuses -----------------------------------------

def test_a_missing_input_is_reported(tmp_path):
    with pytest.raises(FileNotFoundError):
        interpolate_file(tmp_path / 'absent.nc', tmp_path / 'out.nc', 'GrIS',
                         TARGET_RES, weights_dir=tmp_path / 'weights')


def test_an_unknown_method_is_reported(tmp_path):
    source = tmp_path / f'lithk_{NAME_TAIL}'
    source.write_bytes(b'data')
    with pytest.raises(ValueError, match='unknown method'):
        interpolate_file(source, tmp_path / 'out.nc', 'GrIS', TARGET_RES,
                         method='quadratic', weights_dir=tmp_path / 'weights')


def test_an_unknown_target_resolution_is_reported_before_reading_the_file(
        tmp_path, fake_cdo, fake_source):
    source = fake_source('lithk')
    with pytest.raises(GridError):
        interpolate_file(source, tmp_path / 'out.nc', 'GrIS', 3000,
                         weights_dir=tmp_path / 'weights')
    assert fake_cdo == []


def test_a_non_scalar_file_with_no_grid_is_reported(tmp_path, fake_cdo,
                                                    fake_source):
    source = fake_source('lithk', dims=None)
    with pytest.raises(NetCDFError, match='no x,y grid'):
        interpolate_file(source, tmp_path / 'out.nc', 'GrIS', TARGET_RES,
                         weights_dir=tmp_path / 'weights')


def test_an_unrecognized_source_grid_is_reported(tmp_path, fake_cdo,
                                                 fake_source):
    """A source grid is never guessed at."""
    source = fake_source('lithk', dims=(37, 41))
    with pytest.raises(NetCDFError, match='no GrIS ISMIP7 grid matches'):
        interpolate_file(source, tmp_path / 'out.nc', 'GrIS', TARGET_RES,
                         weights_dir=tmp_path / 'weights')


# --- the command line ------------------------------------------------------

def test_main_reports_a_failure_as_a_status_not_a_traceback(tmp_path, capsys):
    status = main(['--domain', 'GrIS', '--target-res', str(TARGET_RES),
                   str(tmp_path / 'absent.nc'), str(tmp_path / 'out.nc')])
    assert status == 1


def test_main_rejects_an_unknown_domain(tmp_path):
    with pytest.raises(SystemExit):
        main(['--domain', 'Mars', '--target-res', '4000', 'in.nc', 'out.nc'])


def test_main_rejects_a_non_numeric_resolution(tmp_path):
    with pytest.raises(SystemExit):
        main(['--domain', 'GrIS', '--target-res', 'fine', 'in.nc', 'out.nc'])


def test_main_places_a_scalar_file(tmp_path, fake_cdo):
    source = tmp_path / f'lim_{NAME_TAIL}'
    source.write_bytes(b'data')
    out = tmp_path / 'out' / 'lim.nc'
    status = main(['--domain', 'GrIS', '--target-res', str(TARGET_RES),
                   '--weights-dir', str(tmp_path / 'weights'),
                   str(source), str(out)])
    assert status == 0
    assert out.is_symlink()


# --- against real CDO ------------------------------------------------------

@pytest.mark.cdo
def test_regridding_lands_on_the_target_grid(fixture_files, tmp_path,
                                             weights_dir):
    out = tmp_path / 'lithk_out.nc'
    result = interpolate_file(fixture_files['lithk'], out, 'GrIS', TARGET_RES,
                              weights_dir=weights_dir)
    assert result.regridded
    assert result.method == 'ycon'
    assert grid_dims(out) == gdf_dims(gdf_path('GrIS', TARGET_RES))


@pytest.mark.cdo
@pytest.mark.parametrize('variable', ['lithk', 'acabf', 'xvelsurf',
                                      'yvelsurf'])
def test_every_spatial_fixture_regrids(fixture_files, tmp_path, weights_dir,
                                       variable):
    out = tmp_path / f'{variable}_out.nc'
    interpolate_file(fixture_files[variable], out, 'GrIS', TARGET_RES,
                     weights_dir=weights_dir)
    assert grid_dims(out) == gdf_dims(gdf_path('GrIS', TARGET_RES))


@pytest.mark.cdo
def test_weights_are_generated_once_and_shared(fixture_files, tmp_path,
                                               weights_dir):
    """Two variables on the same grid pair and method share one weight file."""
    for variable in ('lithk', 'acabf'):
        interpolate_file(fixture_files[variable], tmp_path / f'{variable}.nc',
                         'GrIS', TARGET_RES, weights_dir=weights_dir)
    assert len(list(weights_dir.glob('*.nc'))) == 1


@pytest.mark.cdo
def test_a_mask_preserving_variable_leaves_the_cache_alone(fixture_files,
                                                           tmp_path,
                                                           weights_dir):
    interpolate_file(fixture_files['yvelsurf'], tmp_path / 'yvelsurf.nc',
                     'GrIS', TARGET_RES, weights_dir=weights_dir)
    assert not weights_dir.exists() or list(weights_dir.glob('*.nc')) == []


@pytest.mark.cdo
def test_a_scalar_file_is_never_handed_to_cdo(fixture_files, tmp_path,
                                              weights_dir):
    out = tmp_path / 'lim_out.nc'
    result = interpolate_file(fixture_files['lim'], out, 'GrIS', TARGET_RES,
                              weights_dir=weights_dir)
    assert result.reason == NO_SPATIAL_GRID
    assert out.is_symlink()


@pytest.mark.cdo
def test_missing_values_are_really_filled_for_a_fill_allowed_variable(
        fixture_files, tmp_path, weights_dir):
    """The setmisstoc,0 is observable in the output, so check it there.

    `lithk` may be filled: "no ice" is legitimately zero thickness. Its
    missing values must therefore be gone from the regridded file, not
    spread into its neighbors as missing.
    """
    import netCDF4
    import numpy as np

    source = fixture_files['lithk_with_missing']
    with netCDF4.Dataset(source) as dataset:
        masked = np.ma.count_masked(dataset['lithk'][:])
    assert masked > 0, 'the fixture is supposed to have missing values'

    out = tmp_path / 'lithk_out.nc'
    interpolate_file(source, out, 'GrIS', TARGET_RES, weights_dir=weights_dir)
    with netCDF4.Dataset(out) as dataset:
        values = dataset['lithk'][:]
    assert np.ma.count_masked(values) == 0
    assert values.min() == 0.0


@pytest.mark.cdo
def test_the_mask_is_really_preserved_for_a_mask_variable(fixture_files,
                                                          tmp_path,
                                                          weights_dir):
    """`yvelsurf` must keep its missing values: zero is not a velocity.

    The counterpart of the test above, and the distinction that matters most
    in the whole package -- so it is checked in the output rather than in the
    command that produced it.
    """
    import netCDF4
    import numpy as np

    out = tmp_path / 'yvelsurf_out.nc'
    interpolate_file(fixture_files['yvelsurf'], out, 'GrIS', TARGET_RES,
                     weights_dir=weights_dir)
    with netCDF4.Dataset(out) as dataset:
        values = dataset['yvelsurf'][:]
    assert np.ma.count_masked(values) > 0
