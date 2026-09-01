"""Reading dimensions and missing-value counts out of NetCDF files."""

from __future__ import annotations

import pytest

from ismip7_interp.ncfile import (
    NetCDFError,
    file_size,
    grid_dims,
    has_missing_values,
    header_grid_dims,
    parse_griddes_dims,
    parse_info_missing_count,
)

# `cdo griddes` on a file that carries a bounds pseudo-grid alongside the real
# one.  The bounds grid comes first and has an xsize but no ysize, so matching
# the first xsize alone would report a 2x2 grid.
GRIDDES_WITH_BOUNDS = """#
# gridID 1
#
gridtype  = generic
gridsize  = 2
xsize     = 2
#
# gridID 2
#
gridtype  = projection
gridsize  = 303541
xsize     = 421
ysize     = 721
xunits    = "meter"
"""

GRIDDES_SPATIAL_ONLY = """#
# gridID 1
#
gridtype  = projection
gridsize  = 19186
xsize     = 106
ysize     = 181
"""

# A scalar time series: one point, and no x,y grid at all.
GRIDDES_SCALAR = """#
# gridID 1
#
gridtype  = generic
gridsize  = 1
"""

CDO_INFO = """    -1 :  Date  Time  Level Gridsize  Miss :  Minimum  \
Mean  Maximum : Parameter name
     1 : 2015-01-01 00:00:00       0    19186    1234 :     0.00000     \
0.49978     1.00000 : lithk
     2 : 2016-01-01 00:00:00       0    19186      66 :     0.00000     \
0.50012     1.00000 : lithk
"""

CDO_INFO_NO_MISSING = """    -1 :  Date  Time  Level Gridsize  Miss \
:  Minimum  Mean  Maximum : Parameter name
     1 : 2015-01-01 00:00:00       0    19186       0 :     0.00000     \
0.49978     1.00000 : lithk
"""


def test_parse_griddes_prefers_the_grid_with_both_sizes():
    assert parse_griddes_dims(GRIDDES_WITH_BOUNDS) == (421, 721)


def test_parse_griddes_with_a_single_block():
    assert parse_griddes_dims(GRIDDES_SPATIAL_ONLY) == (106, 181)


def test_parse_griddes_returns_none_for_a_scalar_file():
    assert parse_griddes_dims(GRIDDES_SCALAR) is None


def test_parse_griddes_returns_none_for_empty_output():
    assert parse_griddes_dims('') is None


def test_parse_griddes_ignores_a_trailing_bounds_grid():
    """The real grid first, the bounds grid after it."""
    text = GRIDDES_SPATIAL_ONLY + '#\n# gridID 2\n#\ngridsize = 2\nxsize = 2\n'
    assert parse_griddes_dims(text) == (106, 181)


def test_parse_info_missing_count_sums_every_timestep():
    assert parse_info_missing_count(CDO_INFO) == 1234 + 66


def test_parse_info_missing_count_skips_the_header_row():
    """The header's Miss column is the word "Miss", not a number."""
    assert parse_info_missing_count(CDO_INFO_NO_MISSING) == 0


def test_parse_info_missing_count_of_nothing():
    assert parse_info_missing_count('') == 0


def test_header_grid_dims_reads_a_gridded_file(tmp_path, write_gridded):
    path = write_gridded(tmp_path / 'lithk_GrIS.nc', 106, 181)
    assert header_grid_dims(path) == (106, 181)


def test_header_grid_dims_returns_none_without_x_and_y(tmp_path):
    import netCDF4

    path = tmp_path / 'lim_GrIS.nc'
    with netCDF4.Dataset(path, 'w') as dataset:
        dataset.createDimension('time', None)
        dataset.createVariable('lim', 'f8', ('time',))
    assert header_grid_dims(path) is None


def test_header_grid_dims_returns_none_with_only_one_of_them(tmp_path):
    import netCDF4

    path = tmp_path / 'odd_GrIS.nc'
    with netCDF4.Dataset(path, 'w') as dataset:
        dataset.createDimension('x', 10)
        dataset.createVariable('odd', 'f4', ('x',))
    assert header_grid_dims(path) is None


def test_header_grid_dims_reports_an_unreadable_file(tmp_path):
    """A stray non-NetCDF file must raise, not read as a scalar variable."""
    path = tmp_path / 'lonlat_GrIS.nc'
    path.write_text('this is not a NetCDF file')
    with pytest.raises(NetCDFError, match='could not read'):
        header_grid_dims(path)


def test_header_grid_dims_reports_a_missing_file(tmp_path):
    with pytest.raises(NetCDFError):
        header_grid_dims(tmp_path / 'absent.nc')


def test_grid_dims_reports_a_file_cdo_cannot_read(tmp_path, monkeypatch):
    from ismip7_interp.cdo import CdoError

    def fail(args, capture=False, verbose=False):
        raise CdoError('Unsupported file structure')

    monkeypatch.setattr('ismip7_interp.cdo.run_cdo', fail)
    with pytest.raises(NetCDFError, match='could not read a grid'):
        grid_dims(tmp_path / 'stray.nc')


def test_grid_dims_parses_what_cdo_reports(tmp_path, monkeypatch):
    monkeypatch.setattr(
        'ismip7_interp.cdo.run_cdo',
        lambda args, capture=False, verbose=False: GRIDDES_WITH_BOUNDS)
    assert grid_dims(tmp_path / 'lithk.nc') == (421, 721)


def test_has_missing_values_raises_rather_than_answering_no(
        tmp_path, monkeypatch):
    """A file CDO cannot read must not be treated as having no mask.

    Answering "no" would send it down the cached-weights path, which is the
    wrong one for a file whose mask has to be preserved.
    """
    from ismip7_interp.cdo import CdoError

    def fail(args, capture=False, verbose=False):
        raise CdoError('cannot open')

    monkeypatch.setattr('ismip7_interp.cdo.run_cdo', fail)
    with pytest.raises(NetCDFError):
        has_missing_values(tmp_path / 'stray.nc')


@pytest.mark.parametrize('info, expected', [
    (CDO_INFO, True),
    (CDO_INFO_NO_MISSING, False),
])
def test_has_missing_values(tmp_path, monkeypatch, info, expected):
    monkeypatch.setattr('ismip7_interp.cdo.run_cdo',
                        lambda args, capture=False, verbose=False: info)
    assert has_missing_values(tmp_path / 'lithk.nc') is expected


def test_file_size(tmp_path):
    path = tmp_path / 'file.nc'
    path.write_bytes(b'x' * 4096)
    assert file_size(path) == 4096
