"""The ISMIP7 grid description files and the lookups over them."""

from __future__ import annotations

import pytest

from ismip7_interp.grids import (
    DOMAINS,
    GridError,
    available_resolutions,
    detect_res_from_dims,
    gdf_dims,
    gdf_path,
    res_dir_name,
)


@pytest.mark.parametrize('domain, res_m, expected', [
    ('GrIS', 4000, 'GrIS_04000m'),
    ('GrIS', 1000, 'GrIS_01000m'),
    ('AIS', 8000, 'AIS_08000m'),
    # Five digits already: the padding must not push it to six.
    ('AIS', 32000, 'AIS_32000m'),
])
def test_res_dir_name(domain, res_m, expected):
    assert res_dir_name(domain, res_m) == expected


def test_both_domains_have_grids():
    for domain in DOMAINS:
        assert available_resolutions(domain)


def test_available_resolutions_are_domain_specific():
    """GrIS and AIS have different grids and must not pick up each other's."""
    gris = available_resolutions('GrIS')
    ais = available_resolutions('AIS')
    assert 1000 in gris and 1000 not in ais
    assert 32000 in ais and 32000 not in gris
    for path in gris.values():
        assert 'GrIS' in path.name
    for path in ais.values():
        assert 'AIS' in path.name


def test_gdf_path_resolves_a_known_resolution():
    assert gdf_path('GrIS', 4000).name == 'gdf_ISMIP7_GrIS_04000m.txt'


def test_gdf_path_reports_an_unknown_resolution_with_the_known_ones():
    with pytest.raises(GridError) as caught:
        gdf_path('GrIS', 3000)
    message = str(caught.value)
    assert '3000' in message
    # The message should be enough to fix the command line without looking
    # anything up.
    assert '4000' in message


def test_gdf_dims_parses_a_shipped_grid():
    assert gdf_dims(gdf_path('GrIS', 4000)) == (421, 721)
    assert gdf_dims(gdf_path('GrIS', 16000)) == (106, 181)


def test_every_shipped_grid_has_dimensions():
    for domain in DOMAINS:
        for res_m, path in available_resolutions(domain).items():
            xsize, ysize = gdf_dims(path)
            assert xsize > 0 and ysize > 0


def test_every_shipped_grid_has_distinct_dimensions():
    """Two grids with the same shape would make source detection ambiguous."""
    for domain in DOMAINS:
        shapes = [gdf_dims(path)
                  for path in available_resolutions(domain).values()]
        assert len(set(shapes)) == len(shapes)


def test_gdf_dims_reports_a_file_it_cannot_parse(tmp_path):
    path = tmp_path / 'gdf.txt'
    path.write_text('gridtype = projection\nxsize = 421\n')
    with pytest.raises(GridError, match='xsize/ysize'):
        gdf_dims(path)


def test_detect_res_from_dims_matches_a_known_grid():
    assert detect_res_from_dims('GrIS', (421, 721)) == 4000
    assert detect_res_from_dims('GrIS', (106, 181)) == 16000


def test_detect_res_from_dims_returns_none_for_an_unknown_grid():
    assert detect_res_from_dims('GrIS', (100, 100)) is None


def test_detect_res_from_dims_does_not_cross_domains():
    """An AIS grid's shape must not be reported as a GrIS resolution."""
    ais_dims = gdf_dims(gdf_path('AIS', 8000))
    assert detect_res_from_dims('GrIS', ais_dims) is None


def test_detect_res_from_dims_is_not_fooled_by_a_transposed_grid():
    """421x721 is a GrIS grid; 721x421 is not, and must not read as one."""
    assert detect_res_from_dims('GrIS', (721, 421)) is None


def test_every_shipped_grid_round_trips_through_detection():
    for domain in DOMAINS:
        for res_m, path in available_resolutions(domain).items():
            assert detect_res_from_dims(domain, gdf_dims(path)) == res_m
