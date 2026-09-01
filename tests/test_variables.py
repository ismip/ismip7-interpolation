"""Which remapping each variable gets, and where those facts come from."""

from __future__ import annotations

import pytest

from ismip7_interp.paths import config_dir
from ismip7_interp.variables import (
    COPY,
    METHODS,
    DataRequestError,
    bilinear_variables,
    interp_method,
    mandatory_variables,
    mask_missing_variables,
    nearest_variables,
    read_name_list,
    scalar_variables,
    use_setmisstoc,
    var_from_filename,
    variable_request,
    variable_request_path,
)


def test_data_request_is_read_from_isschecker():
    """The data request is the checker's copy, not one of our own."""
    assert 'isschecker' in variable_request_path().parts


def test_data_request_has_the_columns_this_package_relies_on():
    rows = variable_request()
    assert rows
    for column in ('Variable Name', 'Dim', 'Mandatory (yes/no)'):
        assert column in rows[0]


def test_missing_column_is_reported_rather_than_emptying_the_lists(
        monkeypatch, tmp_path):
    """An upstream rename must fail loudly, not silently yield nothing."""
    csv_path = tmp_path / 'request.csv'
    csv_path.write_text('long_name,Dim,Mandatory (yes/no)\n'
                        'Ice thickness,"x,y,t",yes\n')
    monkeypatch.setattr('ismip7_interp.variables.variable_request_path',
                        lambda: csv_path)
    variable_request.cache_clear()
    try:
        with pytest.raises(DataRequestError, match='Variable Name'):
            variable_request()
    finally:
        variable_request.cache_clear()


def test_mandatory_variables_from_the_data_request():
    mandatory = mandatory_variables()
    assert 'lithk' in mandatory
    assert 'acabf' in mandatory
    # hfgeoubed is Mandatory=no in the data request
    assert 'hfgeoubed' not in mandatory


def test_scalar_variables_are_the_ones_with_no_x_dimension():
    """From the `Dim` column, not a list that could disagree with it."""
    scalar = scalar_variables()
    # Domain-integrated time series: t only.
    assert {'lim', 'limnsw', 'iareagr', 'iareafl', 'tendacabf',
            'tendlibmassbfgr', 'tendlibmassbffl', 'tendlicalvf',
            'tendlifmassbf', 'tendligroundf'} <= scalar
    # Gridded variables are not scalar, including the time-independent and the
    # three-dimensional ones.
    for variable in ('lithk', 'acabf', 'refgeoid', 'litemp'):
        assert variable not in scalar


def test_every_configured_variable_exists_in_the_data_request():
    """A typo in a config list would otherwise just never match anything."""
    known = {row['Variable Name'].strip() for row in variable_request()}
    configured = (bilinear_variables() | nearest_variables()
                  | mask_missing_variables())
    assert configured <= known, sorted(configured - known)


def test_no_variable_is_both_bilinear_and_nearest():
    assert not (bilinear_variables() & nearest_variables())


def test_read_name_list_ignores_comments_and_blank_lines(tmp_path):
    path = tmp_path / 'list.txt'
    path.write_text('# a comment\n\n  lithk  \n\n# another\nacabf\n')
    assert read_name_list(path) == ('lithk', 'acabf')


def test_read_name_list_reports_a_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_name_list(tmp_path / 'nope.txt')


def test_the_shipped_config_lists_all_parse():
    for name in ('bilinear_variables.txt', 'nearest_variables.txt',
                 'mask_missing_variables.txt'):
        read_name_list(config_dir() / name)


@pytest.mark.parametrize('variable, expected', [
    ('lim', COPY),
    ('tendacabf', COPY),
    ('xvelsurf', 'bil'),
    ('yvelmean', 'bil'),
    ('lithk', 'ycon'),
    ('acabf', 'ycon'),
    ('unknown_variable', 'ycon'),
])
def test_interp_method(variable, expected):
    assert interp_method(variable) == expected


def test_interp_method_returns_a_known_method_or_copy():
    for row in variable_request():
        method = interp_method(row['Variable Name'].strip())
        assert method in METHODS or method == COPY


def test_a_scalar_variable_never_resolves_to_a_remapping():
    """Scalars are checked first, so a scalar in a method list stays a copy."""
    for variable in scalar_variables():
        assert interp_method(variable) == COPY


def test_use_setmisstoc():
    assert use_setmisstoc('lithk')
    assert not use_setmisstoc('xvelsurf')


@pytest.mark.parametrize('filename, expected', [
    ('lithk_GrIS_NORCE_CISM3_m001_CESM2-WACCM_f001_ssp585_C007_2015-2300.nc',
     'lithk'),
    ('/some/where/acabf_AIS_X_Y.nc', 'acabf'),
    ('lim_GrIS_TEST.nc', 'lim'),
    # No underscore at all: the whole name, rather than an exception.
    ('lithk.nc', 'lithk.nc'),
])
def test_var_from_filename(filename, expected):
    assert var_from_filename(filename) == expected
